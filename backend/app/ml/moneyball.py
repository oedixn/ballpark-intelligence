import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import psycopg2.extras
from app.db import get_connection

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
    return get_connection()

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
    data = [dict(r) for r in rows]
    # 규정 타석 기준: 시즌 최다 타석의 20% (최소 30타석). 표본이 적은 선수는 군집·백분위에서 제외한다.
    if data:
        threshold = max(30, int(max(float(r['pa'] or 0) for r in data) * 0.2))
        data = [r for r in data if float(r['pa'] or 0) >= threshold]
    return data

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
    kmeans  = KMeans(n_clusters=n_clusters, random_state=42, n_init=200)
    labels  = kmeans.fit_predict(scaled)

    # 군집 중심(원 단위 평균)의 실제 특성으로 유형 이름을 부여한다.
    # 우선순위: 종합 최상위(wOBA) -> 파워(ISO) -> 출루(BB%) -> 컨택(낮은 K%) -> 나머지
    centers = {int(c): features[labels == c].mean(axis=0) for c in np.unique(labels)}
    remaining = set(centers)
    type_map = {}
    rules = [
        ("균형형", lambda m: m[0]),   # wOBA
        ("파워형", lambda m: m[1]),   # ISO
        ("출루형", lambda m: m[2]),   # BB%
        ("컨택형", lambda m: -m[3]),  # 낮은 K%
    ]
    for name, score in rules:
        if not remaining:
            break
        best = max(remaining, key=lambda c: score(centers[c]))
        type_map[best] = name
        remaining.discard(best)
    for c in remaining:
        type_map[c] = "보완형"

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
        "보완형":   "타율·출루·장타 지표가 전반적으로 낮아 보완이 필요한 타입",
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
