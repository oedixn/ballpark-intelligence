import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import psycopg2
import psycopg2.extras

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "ballpark",
    "user": "ballpark",
    "password": "ballpark1234",
}

LATEST_SEASON = 2026

# 클러스터 유형 정의
CLUSTER_TYPES = {
    0: {"name": "파워형",   "desc": "장타력과 홈런이 뛰어난 클린업 타입"},
    1: {"name": "컨택형",   "desc": "높은 타율과 낮은 삼진으로 안정적인 출루를 하는 타입"},
    2: {"name": "균형형",   "desc": "타격·출루·장타 모든 면에서 고루 뛰어난 올라운더"},
    3: {"name": "출루형",   "desc": "볼넷을 많이 얻어 출루율이 높은 선구안 타입"},
    4: {"name": "스피드형", "desc": "발이 빠르고 컨택이 좋은 리드오프 타입"},
}

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def get_hitter_features(season: int = LATEST_SEASON):
    """전체 타자 피처 데이터 가져오기"""
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            p.player_id,
            p.player_name,
            t.team_name,
            pst.pa,
            pst.avg,
            pst.obp,
            pst.slg,
            pst.ops,
            ROUND(CAST(pst.slg - pst.avg AS NUMERIC), 3) AS iso,
            ROUND(CAST(pst.bb AS NUMERIC) / NULLIF(pst.pa, 0) * 100, 1) AS bb_pct,
            ROUND(CAST(pst.so AS NUMERIC) / NULLIF(pst.pa, 0) * 100, 1) AS k_pct,
            pst.hr,
            ROUND(CAST(
                (pst.bb*0.69 + pst.hbp*0.72
                + (pst.h - pst.double_hit - pst.triple_hit - pst.hr)*0.87
                + pst.double_hit*1.217 + pst.triple_hit*1.529 + pst.hr*1.74)
                / NULLIF(pst.pa, 0) AS NUMERIC), 3) AS woba
        FROM players p
        JOIN player_hitter_stats pst ON p.player_id = pst.player_id
        JOIN teams t ON pst.team_id = t.team_id
        WHERE pst.season_year = %s AND pst.pa > 0
        ORDER BY pst.pa DESC
    """, (season,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]

def train_kmeans(data: list, n_clusters: int = 5):
    """K-Means 학습"""
    features = np.array([
        [
            float(r['woba']  or 0),
            float(r['iso']   or 0),
            float(r['bb_pct'] or 0),
            float(r['k_pct'] or 0),
            float(r['ops']   or 0),
            float(r['avg']   or 0),
        ]
        for r in data
    ])

    scaler  = StandardScaler()
    scaled  = scaler.fit_transform(features)
    kmeans  = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels  = kmeans.fit_predict(scaled)

    # 클러스터별 평균 wOBA 계산해서 유형 매핑
    cluster_woba = {}
    for i, label in enumerate(labels):
        if label not in cluster_woba:
            cluster_woba[label] = []
        cluster_woba[label].append(float(data[i]['woba'] or 0))

    cluster_avg_woba = {k: np.mean(v) for k, v in cluster_woba.items()}

    # wOBA 기준으로 클러스터 유형 자동 매핑
    sorted_clusters = sorted(cluster_avg_woba.items(), key=lambda x: x[1], reverse=True)

    type_map = {}
    type_names = ["균형형", "파워형", "출루형", "컨택형", "스피드형"]
    for rank, (cluster_id, _) in enumerate(sorted_clusters):
        type_map[cluster_id] = type_names[rank] if rank < len(type_names) else "기타"

    return kmeans, scaler, labels, type_map, features

def get_player_moneyball(player_id: int, season: int = LATEST_SEASON):
    """특정 선수의 머니볼 분석"""
    # 전체 데이터로 모델 학습
    all_data = get_hitter_features(season)
    if not all_data:
        return None

    kmeans, scaler, labels, type_map, features = train_kmeans(all_data)

    # 해당 선수 찾기
    player_idx = None
    for i, row in enumerate(all_data):
        if str(row['player_id']) == str(player_id):
            player_idx = i
            break

    if player_idx is None:
        return None

    player_data    = all_data[player_idx]
    cluster_label  = int(labels[player_idx])
    cluster_name   = type_map.get(cluster_label, "기타")

    # UV Score 계산: wOBA 백분위 - PA 백분위
    wobas = [float(r['woba'] or 0) for r in all_data]
    pas   = [float(r['pa']   or 0) for r in all_data]

    player_woba = float(player_data['woba'] or 0)
    player_pa   = float(player_data['pa']   or 0)

    woba_pct = sum(1 for w in wobas if w <= player_woba) / len(wobas) * 100
    pa_pct   = sum(1 for p in pas   if p <= player_pa)  / len(pas)   * 100

    uv_score = round(woba_pct - pa_pct, 1)

    if uv_score >= 20:
        uv_label = "매우 저평가"
    elif uv_score >= 5:
        uv_label = "저평가"
    elif uv_score >= -5:
        uv_label = "적정 평가"
    elif uv_score >= -20:
        uv_label = "고평가"
    else:
        uv_label = "매우 고평가"

    # 클러스터 설명
    cluster_descs = {
        "균형형":   "타격·출루·장타 모든 면에서 고루 뛰어난 올라운더",
        "파워형":   "장타력과 홈런이 뛰어난 클린업 타입",
        "출루형":   "볼넷을 많이 얻어 출루율이 높은 선구안 타입",
        "컨택형":   "높은 타율과 낮은 삼진으로 안정적인 타입",
        "스피드형": "발이 빠르고 컨택이 좋은 리드오프 타입",
    }

    # 리그 내 같은 클러스터 선수들
    same_cluster = [
        all_data[i]['player_name']
        for i, l in enumerate(labels)
        if l == cluster_label and str(all_data[i]['player_id']) != str(player_id)
    ][:5]

    return {
        "cluster_type": cluster_name,
        "cluster_desc": cluster_descs.get(cluster_name, ""),
        "uv_score":     uv_score,
        "uv_label":     uv_label,
        "woba_pct":     round(woba_pct, 1),
        "pa_pct":       round(pa_pct, 1),
        "same_cluster_players": same_cluster,
        "features": {
            "woba":   player_data['woba'],
            "iso":    player_data['iso'],
            "bb_pct": player_data['bb_pct'],
            "k_pct":  player_data['k_pct'],
            "ops":    player_data['ops'],
            "avg":    player_data['avg'],
        }
    }