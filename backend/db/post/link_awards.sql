-- 크롤러가 연결하지 못한 수상을 이름으로 보강한다.
-- 조건: 연결 안 된 수상만, 2000년 이후만, 같은 이름이 players에 정확히 1명일 때만.
UPDATE player_awards a
SET player_id = p.player_id
FROM (
    SELECT player_name, MIN(player_id) AS player_id
    FROM players
    GROUP BY player_name
    HAVING COUNT(*) = 1
) p
WHERE a.player_id IS NULL
  AND p.player_name = a.player_name
  AND a.season_year >= 2000;
