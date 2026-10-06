-- KBO 선수 기본 프로필 정보
-- 신규 DB에서는 docker-entrypoint-initdb.d가 실행하고,
-- 기존 DB에서는 load_kbo_to_postgres.py가 같은 파일을 멱등 적용합니다.

ALTER TABLE public.players
    ADD COLUMN IF NOT EXISTS uniform_number INTEGER,
    ADD COLUMN IF NOT EXISTS birth_date DATE,
    ADD COLUMN IF NOT EXISTS profile_position VARCHAR(30),
    ADD COLUMN IF NOT EXISTS throws_hand VARCHAR(1),
    ADD COLUMN IF NOT EXISTS bats_side VARCHAR(1),
    ADD COLUMN IF NOT EXISTS bat_throw VARCHAR(20),
    ADD COLUMN IF NOT EXISTS height_cm INTEGER,
    ADD COLUMN IF NOT EXISTS weight_kg INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'players_throws_hand_check'
    ) THEN
        ALTER TABLE public.players
            ADD CONSTRAINT players_throws_hand_check
            CHECK (throws_hand IS NULL OR throws_hand IN ('R', 'L'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'players_bats_side_check'
    ) THEN
        ALTER TABLE public.players
            ADD CONSTRAINT players_bats_side_check
            CHECK (bats_side IS NULL OR bats_side IN ('R', 'L', 'S'));
    END IF;
END
$$;
