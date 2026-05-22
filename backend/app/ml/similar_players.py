import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity
import psycopg2
import psycopg2.extras

DB_CONFIG = {
    "host": "localhost", "port": 5432,
    "dbname": "ballpark", "user": "ballpark", "password": "ballpark1234",
}

def get_conn(): return psycopg2.connect(**DB_CONFIG)

def get_all_hitter_features():
    """전체 시즌 타자 피처 데이터"""
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            p.player_id, p.player_name, t.team_name, pst.season_year,
            pst.avg, pst.pa,
            ROUND(CAST(pst.slg - pst.avg AS NUMERIC), 3) AS iso,
            ROUND(CAST(pst.bb AS NUMERIC)/NULLIF(pst.pa,0)*100, 1) AS bb_pct,
            ROUND(CAST(pst.so AS NUMERIC)/NULLIF(pst.pa,0)*100, 1) AS k_pct,
            pst.obp, pst.slg, pst.ops,
            ROUND(CAST(
                (pst.bb*0.69+pst.hbp*0.72+(pst.h-pst.double_hit-pst.triple_hit-pst.hr)*0.87
                +pst.double_hit*1.217+pst.triple_hit*1.529+pst.hr*1.74)
                /NULLIF(pst.pa,0) AS NUMERIC), 3) AS woba
        FROM players p
        JOIN player_hitter_stats pst ON p.player_id=pst.player_id
        JOIN teams t ON pst.team_id=t.team_id
        WHERE pst.pa >= 100
        ORDER BY pst.season_year DESC, pst.pa DESC
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]

FEATURE_KEYS = ['avg', 'iso', 'bb_pct', 'k_pct', 'obp', 'slg', 'ops', 'woba']

def get_similar_players(player_id: int, top_n: int = 5):
    """특정 선수와 유사한 선수 추천"""
    all_data = get_all_hitter_features()
    if not all_data:
        return None

    # 피처 행렬 구성
    features = np.array([
        [float(r[k] or 0) for k in FEATURE_KEYS]
        for r in all_data
    ])

    scaler  = StandardScaler()
    scaled  = scaler.fit_transform(features)

    # 대상 선수 찾기 (가장 최근 시즌)
    target_idx = None
    for i, r in enumerate(all_data):
        if str(r['player_id']) == str(player_id):
            target_idx = i
            break

    if target_idx is None:
        return None

    # 코사인 유사도 계산
    target_vec  = scaled[target_idx].reshape(1, -1)
    similarities = cosine_similarity(target_vec, scaled)[0]

    # 자기 자신 제외, 유사도 높은 순 정렬
    target_player_id = str(all_data[target_idx]['player_id'])
    ranked = sorted(
        [(i, sim) for i, sim in enumerate(similarities)
         if str(all_data[i]['player_id']) != target_player_id],
        key=lambda x: x[1], reverse=True
    )

    # 중복 선수 제거 (같은 선수 다른 시즌 제거 - 가장 유사한 시즌만)
    seen_players = set()
    results = []
    for idx, sim in ranked:
        pid = str(all_data[idx]['player_id'])
        if pid not in seen_players:
            seen_players.add(pid)
            r = all_data[idx]
            results.append({
                "player_id":   r['player_id'],
                "player_name": r['player_name'],
                "team_name":   r['team_name'],
                "season_year": r['season_year'],
                "similarity":  round(float(sim) * 100, 1),
                "avg":   r['avg'],
                "ops":   r['ops'],
                "woba":  r['woba'],
                "iso":   r['iso'],
                "bb_pct": r['bb_pct'],
                "k_pct":  r['k_pct'],
            })
        if len(results) >= top_n:
            break

    target = all_data[target_idx]
    return {
        "target": {
            "player_id":   target['player_id'],
            "player_name": target['player_name'],
            "team_name":   target['team_name'],
            "season_year": target['season_year'],
            "avg":  target['avg'],
            "ops":  target['ops'],
            "woba": target['woba'],
        },
        "similar_players": results
    }

PITCHER_FEATURE_KEYS = ['era', 'whip', 'so_per_g', 'bb_per_g', 'hr_per_g']

def get_all_pitcher_features():
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            p.player_id, p.player_name, t.team_name, ps.season_year,
            ps.era, ps.whip, ps.g,
            ROUND(CAST(ps.so AS NUMERIC)/NULLIF(ps.g,0), 2) AS so_per_g,
            ROUND(CAST(ps.bb AS NUMERIC)/NULLIF(ps.g,0), 2) AS bb_per_g,
            ROUND(CAST(ps.hr AS NUMERIC)/NULLIF(ps.g,0), 2) AS hr_per_g,
            ps.w, ps.sv, ps.hld
        FROM players p
        JOIN player_pitcher_stats ps ON p.player_id=ps.player_id
        JOIN teams t ON ps.team_id=t.team_id
        WHERE ps.g >= 10
        ORDER BY ps.season_year DESC, ps.g DESC
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]

def get_similar_pitchers(player_id: int, top_n: int = 5):
    all_data = get_all_pitcher_features()
    if not all_data: return None

    features = np.array([
        [float(r[k] or 0) for k in PITCHER_FEATURE_KEYS]
        for r in all_data
    ])
    scaler  = StandardScaler()
    scaled  = scaler.fit_transform(features)

    target_idx = None
    for i, r in enumerate(all_data):
        if str(r['player_id']) == str(player_id):
            target_idx = i; break

    if target_idx is None: return None

    target_vec   = scaled[target_idx].reshape(1, -1)
    similarities = cosine_similarity(target_vec, scaled)[0]
    target_pid   = str(all_data[target_idx]['player_id'])

    ranked = sorted(
        [(i, sim) for i, sim in enumerate(similarities) if str(all_data[i]['player_id']) != target_pid],
        key=lambda x: x[1], reverse=True
    )

    seen, results = set(), []
    for idx, sim in ranked:
        pid = str(all_data[idx]['player_id'])
        if pid not in seen:
            seen.add(pid)
            r = all_data[idx]
            results.append({
                "player_id":   r['player_id'],
                "player_name": r['player_name'],
                "team_name":   r['team_name'],
                "season_year": r['season_year'],
                "similarity":  round(float(sim) * 100, 1),
                "era":     r['era'],
                "whip":    r['whip'],
                "so_per_g": r['so_per_g'],
                "w":   r['w'],
                "sv":  r['sv'],
                "hld": r['hld'],
            })
        if len(results) >= top_n: break

    target = all_data[target_idx]
    return {
        "target": {
            "player_id":   target['player_id'],
            "player_name": target['player_name'],
            "team_name":   target['team_name'],
            "season_year": target['season_year'],
            "era":  target['era'],
            "whip": target['whip'],
        },
        "similar_players": results
    }