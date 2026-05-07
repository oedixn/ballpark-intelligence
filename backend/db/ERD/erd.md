erDiagram
    teams {
        int team_id PK
        varchar team_name UK
        varchar team_code
    }

    players {
        varchar player_id PK
        varchar player_name
    }

    player_season_teams {
        int id PK
        int season_year
        varchar player_id FK
        int team_id FK
    }

    player_hitter_stats {
        int id PK
        int season_year
        varchar player_id FK
        int team_id FK
        numeric avg
        int g
        int pa
        int ab
        int h
        int hr
        numeric ops
    }

    player_pitcher_stats {
        int id PK
        int season_year
        varchar player_id FK
        int team_id FK
        numeric era
        int g
        int w
        int l
        int so
        numeric whip
    }

    player_defense_stats {
        int id PK
        int season_year
        varchar player_id FK
        int team_id FK
        varchar position
        int g
        int e
        numeric fpct
    }

    player_runner_stats {
        int id PK
        int season_year
        varchar player_id FK
        int team_id FK
        int sb
        int cs
        numeric sb_rate
    }

    team_hitter_stats {
        int id PK
        int season_year
        int team_id FK
        numeric avg
        int pa
        int hr
        numeric ops
    }

    team_pitcher_stats {
        int id PK
        int season_year
        int team_id FK
        numeric era
        int so
        int bb
        numeric whip
    }

    team_defense_stats {
        int id PK
        int season_year
        int team_id FK
        int e
        numeric fpct
    }

    team_runner_stats {
        int id PK
        int season_year
        int team_id FK
        int sb
        int cs
        numeric sb_rate
    }

    team_rank_stats {
        int id PK
        int season_year
        int team_id FK
        int games
        int wins
        int losses
        numeric win_rate
    }

    kbreport_player_hitter_advanced {
        int id PK
        int season_year
        varchar player_name
        int team_id FK
        numeric woba
        numeric war
        numeric babip
        numeric spd
    }

    kbreport_player_pitcher_advanced {
        int id PK
        int season_year
        varchar player_name
        int team_id FK
        numeric fip
        numeric kfip
        numeric fip_war
        numeric ra9_war
    }

    kbreport_team_hitter_advanced {
        int id PK
        int season_year
        int team_id FK
        numeric woba
        numeric war
        numeric expected_win_rate
    }

    kbreport_team_pitcher_advanced {
        int id PK
        int season_year
        int team_id FK
        numeric fip
        numeric kfip
        numeric fip_war
        numeric ra9_war
    }

    teams ||--o{ player_season_teams : belongs_to
    players ||--o{ player_season_teams : plays_for

    teams ||--o{ player_hitter_stats : has
    teams ||--o{ player_pitcher_stats : has
    teams ||--o{ player_defense_stats : has
    teams ||--o{ player_runner_stats : has

    players ||--o{ player_hitter_stats : records
    players ||--o{ player_pitcher_stats : records
    players ||--o{ player_defense_stats : records
    players ||--o{ player_runner_stats : records

    teams ||--o{ team_hitter_stats : has
    teams ||--o{ team_pitcher_stats : has
    teams ||--o{ team_defense_stats : has
    teams ||--o{ team_runner_stats : has
    teams ||--o{ team_rank_stats : has

    teams ||--o{ kbreport_player_hitter_advanced : has
    teams ||--o{ kbreport_player_pitcher_advanced : has
    teams ||--o{ kbreport_team_hitter_advanced : has
    teams ||--o{ kbreport_team_pitcher_advanced : has
