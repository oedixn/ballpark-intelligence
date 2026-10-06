-- KBO 공식 수상 내역과 보유 시즌 데이터 기반 클럽 경력

CREATE TABLE IF NOT EXISTS public.player_awards (
    award_id BIGSERIAL PRIMARY KEY,
    player_id VARCHAR(30) REFERENCES public.players(player_id) ON DELETE SET NULL,
    season_year INTEGER NOT NULL,
    award_type VARCHAR(30) NOT NULL,
    award_name VARCHAR(100) NOT NULL,
    player_name VARCHAR(50) NOT NULL,
    team_name VARCHAR(50) NOT NULL,
    normalized_team_name VARCHAR(50),
    position VARCHAR(30) NOT NULL DEFAULT '',
    source_url TEXT,
    CONSTRAINT uq_player_awards_source_record
        UNIQUE (season_year, award_type, player_name, team_name, position)
);

CREATE INDEX IF NOT EXISTS idx_player_awards_player_year
    ON public.player_awards (player_id, season_year DESC);

CREATE TABLE IF NOT EXISTS public.player_club_history (
    season_year INTEGER NOT NULL,
    player_id VARCHAR(30) NOT NULL
        REFERENCES public.players(player_id) ON DELETE CASCADE,
    team_name VARCHAR(50) NOT NULL,
    PRIMARY KEY (season_year, player_id, team_name)
);

CREATE INDEX IF NOT EXISTS idx_player_club_history_player_year
    ON public.player_club_history (player_id, season_year);
