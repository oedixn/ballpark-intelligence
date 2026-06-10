import numpy as np
import psycopg2
import psycopg2.extras
from sklearn.preprocessing import MinMaxScaler
import warnings
warnings.filterwarnings('ignore')

import os
DB_CONFIG = {"host":os.getenv("DB_HOST","localhost"),"port":int(os.getenv("DB_PORT",5432)),"dbname":os.getenv("DB_NAME","ballpark"),"user":os.getenv("DB_USER","ballpark"),"password":os.getenv("DB_PASSWORD","ballpark1234")}
def get_conn(): return psycopg2.connect(**DB_CONFIG)

HITTER_FEATURES  = ['avg','obp','slg','ops','bb_rate','k_rate','iso','woba']
HITTER_TARGETS   = ['avg','ops','woba']
PITCHER_FEATURES = ['era','whip','so_per_g','bb_per_g','hr_per_g']
PITCHER_TARGETS  = ['era','whip','so_per_g']

def get_hitter_time_series(player_id: int):
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT season_year, pst.avg, pst.obp, pst.slg, pst.ops,
            ROUND(CAST(pst.bb AS NUMERIC)/NULLIF(pst.pa,0)*100,1) AS bb_rate,
            ROUND(CAST(pst.so AS NUMERIC)/NULLIF(pst.pa,0)*100,1) AS k_rate,
            ROUND(CAST(pst.slg-pst.avg AS NUMERIC),3) AS iso,
            ROUND(CAST((pst.bb*0.69+pst.hbp*0.72+(pst.h-pst.double_hit-pst.triple_hit-pst.hr)*0.87
                +pst.double_hit*1.217+pst.triple_hit*1.529+pst.hr*1.74)/NULLIF(pst.pa,0) AS NUMERIC),3) AS woba,
            pst.pa, pst.hr, pst.rbi
        FROM player_hitter_stats pst
        WHERE pst.player_id=%s::varchar AND pst.pa>=50
        ORDER BY season_year
    """, (player_id,))
    rows = cur.fetchall(); cur.close(); conn.close()
    return [dict(r) for r in rows]

def get_pitcher_time_series(player_id: int):
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT season_year, ps.era, ps.whip, ps.g,
            ROUND(CAST(ps.so AS NUMERIC)/NULLIF(ps.g,0),2) AS so_per_g,
            ROUND(CAST(ps.bb AS NUMERIC)/NULLIF(ps.g,0),2) AS bb_per_g,
            ROUND(CAST(ps.hr AS NUMERIC)/NULLIF(ps.g,0),2) AS hr_per_g,
            ps.w, ps.sv, ps.hld, ps.so
        FROM player_pitcher_stats ps
        WHERE ps.player_id=%s::varchar AND ps.g>=5
        ORDER BY season_year
    """, (player_id,))
    rows = cur.fetchall(); cur.close(); conn.close()
    return [dict(r) for r in rows]

def get_training_player_ids(min_seasons=4, type='hitter'):
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if type == 'hitter':
        cur.execute("""SELECT player_id FROM player_hitter_stats WHERE pa>=100
            GROUP BY player_id HAVING COUNT(*)>=%s""", (min_seasons,))
    else:
        cur.execute("""SELECT player_id FROM player_pitcher_stats WHERE g>=10
            GROUP BY player_id HAVING COUNT(*)>=%s""", (min_seasons,))
    ids = [r['player_id'] for r in cur.fetchall()]
    cur.close(); conn.close()
    return ids

def _build_model_and_scalers(player_ids, get_ts_func, features, targets):
    try:
        import tensorflow as tf
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import LSTM, Dense, Dropout
        from tensorflow.keras.callbacks import EarlyStopping
    except ImportError:
        return None, None, None

    all_raw, all_y_raw = [], []
    for pid in player_ids:
        data = get_ts_func(pid)
        if len(data) >= 4:
            for r in data:
                all_raw.append([float(r[f] or 0) for f in features])
                all_y_raw.append([float(r[t] or 0) for t in targets])

    if not all_raw: return None, None, None

    scaler_X = MinMaxScaler().fit(all_raw)
    scaler_y = MinMaxScaler().fit(all_y_raw)

    all_X, all_y = [], []
    for pid in player_ids:
        data = get_ts_func(pid)
        if len(data) < 4: continue
        vals = np.array([[float(r[f] or 0) for f in features] for r in data])
        scaled = scaler_X.transform(vals)
        for i in range(len(scaled) - 3):
            all_X.append(scaled[i:i+3])
            all_y.append(scaler_y.transform([[float(data[i+3][t] or 0) for t in targets]])[0])

    if not all_X: return None, None, None

    X, y = np.array(all_X), np.array(all_y)
    print(f"학습 데이터: {X.shape[0]}개 시퀀스, {X.shape[2]}개 피처")

    model = Sequential([
        LSTM(64, return_sequences=True, input_shape=(3, len(features))),
        Dropout(0.2),
        LSTM(32),
        Dropout(0.2),
        Dense(16, activation='relu'),
        Dense(len(targets))
    ])
    model.compile(optimizer='adam', loss='mse', metrics=['mae'])
    model.fit(X, y, epochs=100, batch_size=16, validation_split=0.2,
              callbacks=[EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)], verbose=1)

    return model, scaler_X, scaler_y

def train_hitter_model():
    print("타자 LSTM 학습 시작...")
    ids = get_training_player_ids(4, 'hitter')
    return _build_model_and_scalers(ids, get_hitter_time_series, HITTER_FEATURES, HITTER_TARGETS)

def train_pitcher_model():
    print("투수 LSTM 학습 시작...")
    ids = get_training_player_ids(4, 'pitcher')
    return _build_model_and_scalers(ids, get_pitcher_time_series, PITCHER_FEATURES, PITCHER_TARGETS)

# 하위 호환
def train_lstm_model():
    return train_hitter_model()

def _weighted_avg_predict(data, features, targets):
    recent = data[-3:] if len(data) >= 3 else data
    w = np.array([0.2,0.3,0.5]) if len(recent)==3 else np.ones(len(recent))/len(recent)
    w = w[-len(recent):] / w[-len(recent):].sum()
    pred = {}
    for t in targets:
        vals = [float(r[t] or 0) for r in recent]
        pred[t] = round(float(np.dot(w, vals)), 3)
    if len(data) >= 2:
        for t in targets:
            trend = float(data[-1][t] or 0) - float(data[-2][t] or 0)
            pred[t] = round(pred[t] + trend * 0.3, 3)
    return pred

def predict_next_season(player_id: int, model=None, scaler_X=None, scaler_y=None):
    data = get_hitter_time_series(player_id)
    if len(data) < 3: return None

    if model is None:
        pred = _weighted_avg_predict(data, HITTER_FEATURES, HITTER_TARGETS)
        method = "weighted_average"
    else:
        vals = np.array([[float(r[f] or 0) for f in HITTER_FEATURES] for r in data[-3:]])
        scaled = scaler_X.transform(vals).reshape(1, 3, len(HITTER_FEATURES))
        pred_scaled = model.predict(scaled, verbose=0)
        pred_vals = scaler_y.inverse_transform(pred_scaled)[0]
        pred = {t: round(float(pred_vals[i]), 3) for i, t in enumerate(HITTER_TARGETS)}
        method = "lstm"

    return {
        "player_id": player_id,
        "current_season": int(data[-1]['season_year']),
        "next_season":    int(data[-1]['season_year']) + 1,
        "predictions": pred,
        "confidence": "high" if len(data)>=7 else "medium" if len(data)>=4 else "low",
        "seasons_used": len(data),
        "method": method,
        "type": "hitter",
        "recent_stats": {
            "avg":  float(data[-1]['avg'] or 0),
            "ops":  float(data[-1]['ops'] or 0),
            "woba": float(data[-1]['woba'] or 0),
        }
    }

def predict_pitcher_next_season(player_id: int, model=None, scaler_X=None, scaler_y=None):
    data = get_pitcher_time_series(player_id)
    if len(data) < 3: return None

    if model is None:
        pred = _weighted_avg_predict(data, PITCHER_FEATURES, PITCHER_TARGETS)
        method = "weighted_average"
    else:
        vals = np.array([[float(r[f] or 0) for f in PITCHER_FEATURES] for r in data[-3:]])
        scaled = scaler_X.transform(vals).reshape(1, 3, len(PITCHER_FEATURES))
        pred_scaled = model.predict(scaled, verbose=0)
        pred_vals = scaler_y.inverse_transform(pred_scaled)[0]
        pred = {t: round(float(pred_vals[i]), 3) for i, t in enumerate(PITCHER_TARGETS)}
        method = "lstm"

    return {
        "player_id": player_id,
        "current_season": int(data[-1]['season_year']),
        "next_season":    int(data[-1]['season_year']) + 1,
        "predictions": pred,
        "confidence": "high" if len(data)>=7 else "medium" if len(data)>=4 else "low",
        "seasons_used": len(data),
        "method": method,
        "type": "pitcher",
        "recent_stats": {
            "era":      float(data[-1]['era'] or 0),
            "whip":     float(data[-1]['whip'] or 0),
            "so_per_g": float(data[-1]['so_per_g'] or 0),
        }
    }