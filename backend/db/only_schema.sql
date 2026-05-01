--
-- PostgreSQL database dump
--

\restrict QP91GmIQRwqOvLfScIQAw3CvNmz31caSsq82EnwM5GYE9xiyBuRs8BB9n6pVzlx

-- Dumped from database version 18.3
-- Dumped by pg_dump version 18.3

-- Started on 2026-05-01 17:37:26

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 243 (class 1259 OID 16609)
-- Name: kbreport_player_hitter_advanced; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.kbreport_player_hitter_advanced (
    id integer NOT NULL,
    season_year integer NOT NULL,
    player_name character varying(50),
    team_id integer,
    babip numeric(6,3),
    bb_rate numeric(6,2),
    k_rate numeric(6,2),
    iso numeric(6,3),
    rc numeric(8,2),
    rc27 numeric(8,2),
    wrc numeric(8,2),
    spd numeric(6,2),
    wsb numeric(6,2),
    woba numeric(6,3),
    wraa numeric(8,2),
    war numeric(8,2)
);


ALTER TABLE public.kbreport_player_hitter_advanced OWNER TO postgres;

--
-- TOC entry 242 (class 1259 OID 16608)
-- Name: kbreport_player_hitter_advanced_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.kbreport_player_hitter_advanced_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.kbreport_player_hitter_advanced_id_seq OWNER TO postgres;

--
-- TOC entry 5075 (class 0 OID 0)
-- Dependencies: 242
-- Name: kbreport_player_hitter_advanced_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.kbreport_player_hitter_advanced_id_seq OWNED BY public.kbreport_player_hitter_advanced.id;


--
-- TOC entry 245 (class 1259 OID 16620)
-- Name: kbreport_player_pitcher_advanced; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.kbreport_player_pitcher_advanced (
    id integer NOT NULL,
    season_year integer NOT NULL,
    player_name character varying(50),
    team_id integer,
    hr9 numeric(6,2),
    lob numeric(6,2),
    fip numeric(6,2),
    kfip numeric(6,2),
    fip_war numeric(8,2),
    ra9_war numeric(8,2),
    k_rate numeric(6,2),
    bb_rate numeric(6,2),
    avg numeric(6,3),
    obp numeric(6,3),
    slg numeric(6,3),
    ops numeric(6,3)
);


ALTER TABLE public.kbreport_player_pitcher_advanced OWNER TO postgres;

--
-- TOC entry 244 (class 1259 OID 16619)
-- Name: kbreport_player_pitcher_advanced_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.kbreport_player_pitcher_advanced_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.kbreport_player_pitcher_advanced_id_seq OWNER TO postgres;

--
-- TOC entry 5076 (class 0 OID 0)
-- Dependencies: 244
-- Name: kbreport_player_pitcher_advanced_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.kbreport_player_pitcher_advanced_id_seq OWNED BY public.kbreport_player_pitcher_advanced.id;


--
-- TOC entry 247 (class 1259 OID 16632)
-- Name: kbreport_team_hitter_advanced; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.kbreport_team_hitter_advanced (
    id integer NOT NULL,
    season_year integer NOT NULL,
    team_id integer,
    expected_win_rate numeric(6,3),
    r_per_game numeric(6,2),
    babip numeric(6,3),
    bb_rate numeric(6,2),
    k_rate numeric(6,2),
    bb_k numeric(6,2),
    iso numeric(6,3),
    ab_per_hr numeric(8,2),
    rc numeric(8,2),
    rc27 numeric(8,2),
    wrc numeric(8,2),
    spd numeric(6,2),
    wsb numeric(8,2),
    woba numeric(6,3),
    wraa numeric(8,2),
    war numeric(8,2)
);


ALTER TABLE public.kbreport_team_hitter_advanced OWNER TO postgres;

--
-- TOC entry 246 (class 1259 OID 16631)
-- Name: kbreport_team_hitter_advanced_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.kbreport_team_hitter_advanced_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.kbreport_team_hitter_advanced_id_seq OWNER TO postgres;

--
-- TOC entry 5077 (class 0 OID 0)
-- Dependencies: 246
-- Name: kbreport_team_hitter_advanced_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.kbreport_team_hitter_advanced_id_seq OWNED BY public.kbreport_team_hitter_advanced.id;


--
-- TOC entry 249 (class 1259 OID 16648)
-- Name: kbreport_team_pitcher_advanced; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.kbreport_team_pitcher_advanced (
    id integer NOT NULL,
    season_year integer NOT NULL,
    team_id integer,
    expected_win_rate numeric(6,3),
    ra_per_game numeric(6,2),
    hr9 numeric(6,2),
    lob_rate numeric(6,2),
    fip numeric(6,2),
    kfip numeric(6,2),
    fip_war numeric(8,2),
    ra9_war numeric(8,2),
    k_rate numeric(6,2),
    bb_rate numeric(6,2),
    avg_against numeric(6,3),
    obp_against numeric(6,3),
    slg_against numeric(6,3),
    ops_against numeric(6,3)
);


ALTER TABLE public.kbreport_team_pitcher_advanced OWNER TO postgres;

--
-- TOC entry 248 (class 1259 OID 16647)
-- Name: kbreport_team_pitcher_advanced_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.kbreport_team_pitcher_advanced_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.kbreport_team_pitcher_advanced_id_seq OWNER TO postgres;

--
-- TOC entry 5078 (class 0 OID 0)
-- Dependencies: 248
-- Name: kbreport_team_pitcher_advanced_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.kbreport_team_pitcher_advanced_id_seq OWNED BY public.kbreport_team_pitcher_advanced.id;


--
-- TOC entry 229 (class 1259 OID 16477)
-- Name: player_defense_stats; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.player_defense_stats (
    id integer NOT NULL,
    season_year integer NOT NULL,
    player_id character varying(30) NOT NULL,
    team_id integer NOT NULL,
    "position" character varying(10) NOT NULL,
    g integer,
    gs integer,
    ip character varying(20),
    e integer,
    pko integer,
    po integer,
    a integer,
    dp integer,
    fpct numeric(6,3),
    pb integer,
    sb integer,
    cs integer,
    cs_rate numeric(6,2)
);


ALTER TABLE public.player_defense_stats OWNER TO postgres;

--
-- TOC entry 228 (class 1259 OID 16476)
-- Name: player_defense_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.player_defense_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.player_defense_stats_id_seq OWNER TO postgres;

--
-- TOC entry 5079 (class 0 OID 0)
-- Dependencies: 228
-- Name: player_defense_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.player_defense_stats_id_seq OWNED BY public.player_defense_stats.id;


--
-- TOC entry 225 (class 1259 OID 16431)
-- Name: player_hitter_stats; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.player_hitter_stats (
    id integer NOT NULL,
    season_year integer NOT NULL,
    player_id character varying(30) NOT NULL,
    team_id integer NOT NULL,
    avg numeric(6,3),
    g integer,
    pa integer,
    ab integer,
    r integer,
    h integer,
    double_hit integer,
    triple_hit integer,
    hr integer,
    tb integer,
    rbi integer,
    sac integer,
    sf integer,
    bb integer,
    ibb integer,
    hbp integer,
    so integer,
    gdp integer,
    slg numeric(6,3),
    obp numeric(6,3),
    ops numeric(6,3),
    mh integer,
    risp numeric(6,3),
    ph_ba numeric(6,3),
    xbh integer,
    go integer,
    ao integer,
    go_ao numeric(6,2),
    gw_rbi integer,
    bb_k numeric(6,2),
    p_pa numeric(6,2),
    isop numeric(6,3),
    xr numeric(8,2),
    gpa numeric(6,3)
);


ALTER TABLE public.player_hitter_stats OWNER TO postgres;

--
-- TOC entry 224 (class 1259 OID 16430)
-- Name: player_hitter_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.player_hitter_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.player_hitter_stats_id_seq OWNER TO postgres;

--
-- TOC entry 5080 (class 0 OID 0)
-- Dependencies: 224
-- Name: player_hitter_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.player_hitter_stats_id_seq OWNED BY public.player_hitter_stats.id;


--
-- TOC entry 227 (class 1259 OID 16454)
-- Name: player_pitcher_stats; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.player_pitcher_stats (
    id integer NOT NULL,
    season_year integer NOT NULL,
    player_id character varying(30) NOT NULL,
    team_id integer NOT NULL,
    era numeric(6,2),
    g integer,
    w integer,
    l integer,
    sv integer,
    hld integer,
    wpct numeric(6,3),
    ip character varying(20),
    h integer,
    hr integer,
    bb integer,
    hbp integer,
    so integer,
    r integer,
    er integer,
    whip numeric(6,2),
    cg integer,
    sho integer,
    qs integer,
    bsv integer,
    tbf integer,
    np integer,
    avg numeric(6,3),
    double_hit integer,
    triple_hit integer,
    sac integer,
    sf integer,
    ibb integer,
    wp integer,
    bk integer,
    gs integer,
    gf integer,
    svo integer,
    ts integer,
    gdp integer,
    go integer,
    ao integer,
    go_ao numeric(6,2),
    babip numeric(6,3),
    p_g numeric(6,2),
    p_ip numeric(6,2),
    k9 numeric(6,2),
    bb9 numeric(6,2),
    k_bb numeric(6,2),
    obp numeric(6,3),
    slg numeric(6,3),
    ops numeric(6,3)
);


ALTER TABLE public.player_pitcher_stats OWNER TO postgres;

--
-- TOC entry 226 (class 1259 OID 16453)
-- Name: player_pitcher_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.player_pitcher_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.player_pitcher_stats_id_seq OWNER TO postgres;

--
-- TOC entry 5081 (class 0 OID 0)
-- Dependencies: 226
-- Name: player_pitcher_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.player_pitcher_stats_id_seq OWNED BY public.player_pitcher_stats.id;


--
-- TOC entry 231 (class 1259 OID 16501)
-- Name: player_runner_stats; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.player_runner_stats (
    id integer NOT NULL,
    season_year integer NOT NULL,
    player_id character varying(30) NOT NULL,
    team_id integer NOT NULL,
    g integer,
    sba integer,
    sb integer,
    cs integer,
    sb_rate numeric(6,2),
    oob integer,
    pko integer
);


ALTER TABLE public.player_runner_stats OWNER TO postgres;

--
-- TOC entry 230 (class 1259 OID 16500)
-- Name: player_runner_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.player_runner_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.player_runner_stats_id_seq OWNER TO postgres;

--
-- TOC entry 5082 (class 0 OID 0)
-- Dependencies: 230
-- Name: player_runner_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.player_runner_stats_id_seq OWNED BY public.player_runner_stats.id;


--
-- TOC entry 223 (class 1259 OID 16408)
-- Name: player_season_teams; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.player_season_teams (
    id integer NOT NULL,
    season_year integer NOT NULL,
    player_id character varying(30) NOT NULL,
    team_id integer NOT NULL
);


ALTER TABLE public.player_season_teams OWNER TO postgres;

--
-- TOC entry 222 (class 1259 OID 16407)
-- Name: player_season_teams_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.player_season_teams_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.player_season_teams_id_seq OWNER TO postgres;

--
-- TOC entry 5083 (class 0 OID 0)
-- Dependencies: 222
-- Name: player_season_teams_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.player_season_teams_id_seq OWNED BY public.player_season_teams.id;


--
-- TOC entry 221 (class 1259 OID 16400)
-- Name: players; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.players (
    player_id character varying(30) NOT NULL,
    player_name character varying(50) NOT NULL
);


ALTER TABLE public.players OWNER TO postgres;

--
-- TOC entry 237 (class 1259 OID 16558)
-- Name: team_defense_stats; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.team_defense_stats (
    id integer NOT NULL,
    season_year integer NOT NULL,
    team_id integer NOT NULL,
    e integer,
    fpct numeric(6,3)
);


ALTER TABLE public.team_defense_stats OWNER TO postgres;

--
-- TOC entry 236 (class 1259 OID 16557)
-- Name: team_defense_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.team_defense_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.team_defense_stats_id_seq OWNER TO postgres;

--
-- TOC entry 5084 (class 0 OID 0)
-- Dependencies: 236
-- Name: team_defense_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.team_defense_stats_id_seq OWNED BY public.team_defense_stats.id;


--
-- TOC entry 233 (class 1259 OID 16524)
-- Name: team_hitter_stats; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.team_hitter_stats (
    id integer NOT NULL,
    season_year integer NOT NULL,
    team_id integer NOT NULL,
    avg numeric(6,3),
    pa integer,
    hr integer,
    rbi integer,
    ops numeric(6,3)
);


ALTER TABLE public.team_hitter_stats OWNER TO postgres;

--
-- TOC entry 232 (class 1259 OID 16523)
-- Name: team_hitter_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.team_hitter_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.team_hitter_stats_id_seq OWNER TO postgres;

--
-- TOC entry 5085 (class 0 OID 0)
-- Dependencies: 232
-- Name: team_hitter_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.team_hitter_stats_id_seq OWNED BY public.team_hitter_stats.id;


--
-- TOC entry 235 (class 1259 OID 16541)
-- Name: team_pitcher_stats; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.team_pitcher_stats (
    id integer NOT NULL,
    season_year integer NOT NULL,
    team_id integer NOT NULL,
    era numeric(6,2),
    so integer,
    bb integer,
    whip numeric(6,2)
);


ALTER TABLE public.team_pitcher_stats OWNER TO postgres;

--
-- TOC entry 234 (class 1259 OID 16540)
-- Name: team_pitcher_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.team_pitcher_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.team_pitcher_stats_id_seq OWNER TO postgres;

--
-- TOC entry 5086 (class 0 OID 0)
-- Dependencies: 234
-- Name: team_pitcher_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.team_pitcher_stats_id_seq OWNED BY public.team_pitcher_stats.id;


--
-- TOC entry 241 (class 1259 OID 16592)
-- Name: team_rank_stats; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.team_rank_stats (
    id integer NOT NULL,
    season_year integer NOT NULL,
    team_id integer NOT NULL,
    games integer,
    wins integer,
    losses integer,
    draws integer,
    win_rate numeric(6,3),
    game_gap character varying(20),
    last10 character varying(20),
    streak character varying(20),
    home character varying(20),
    away character varying(20)
);


ALTER TABLE public.team_rank_stats OWNER TO postgres;

--
-- TOC entry 240 (class 1259 OID 16591)
-- Name: team_rank_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.team_rank_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.team_rank_stats_id_seq OWNER TO postgres;

--
-- TOC entry 5087 (class 0 OID 0)
-- Dependencies: 240
-- Name: team_rank_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.team_rank_stats_id_seq OWNED BY public.team_rank_stats.id;


--
-- TOC entry 239 (class 1259 OID 16575)
-- Name: team_runner_stats; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.team_runner_stats (
    id integer NOT NULL,
    season_year integer NOT NULL,
    team_id integer NOT NULL,
    sb integer,
    cs integer,
    sb_rate numeric(6,2)
);


ALTER TABLE public.team_runner_stats OWNER TO postgres;

--
-- TOC entry 238 (class 1259 OID 16574)
-- Name: team_runner_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.team_runner_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.team_runner_stats_id_seq OWNER TO postgres;

--
-- TOC entry 5088 (class 0 OID 0)
-- Dependencies: 238
-- Name: team_runner_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.team_runner_stats_id_seq OWNED BY public.team_runner_stats.id;


--
-- TOC entry 220 (class 1259 OID 16390)
-- Name: teams; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.teams (
    team_id integer NOT NULL,
    team_name character varying(20) NOT NULL,
    team_code character varying(10)
);


ALTER TABLE public.teams OWNER TO postgres;

--
-- TOC entry 219 (class 1259 OID 16389)
-- Name: teams_team_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.teams_team_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.teams_team_id_seq OWNER TO postgres;

--
-- TOC entry 5089 (class 0 OID 0)
-- Dependencies: 219
-- Name: teams_team_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.teams_team_id_seq OWNED BY public.teams.team_id;


--
-- TOC entry 4840 (class 2604 OID 16612)
-- Name: kbreport_player_hitter_advanced id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kbreport_player_hitter_advanced ALTER COLUMN id SET DEFAULT nextval('public.kbreport_player_hitter_advanced_id_seq'::regclass);


--
-- TOC entry 4841 (class 2604 OID 16623)
-- Name: kbreport_player_pitcher_advanced id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kbreport_player_pitcher_advanced ALTER COLUMN id SET DEFAULT nextval('public.kbreport_player_pitcher_advanced_id_seq'::regclass);


--
-- TOC entry 4842 (class 2604 OID 16635)
-- Name: kbreport_team_hitter_advanced id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kbreport_team_hitter_advanced ALTER COLUMN id SET DEFAULT nextval('public.kbreport_team_hitter_advanced_id_seq'::regclass);


--
-- TOC entry 4843 (class 2604 OID 16651)
-- Name: kbreport_team_pitcher_advanced id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kbreport_team_pitcher_advanced ALTER COLUMN id SET DEFAULT nextval('public.kbreport_team_pitcher_advanced_id_seq'::regclass);


--
-- TOC entry 4833 (class 2604 OID 16480)
-- Name: player_defense_stats id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_defense_stats ALTER COLUMN id SET DEFAULT nextval('public.player_defense_stats_id_seq'::regclass);


--
-- TOC entry 4831 (class 2604 OID 16434)
-- Name: player_hitter_stats id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_hitter_stats ALTER COLUMN id SET DEFAULT nextval('public.player_hitter_stats_id_seq'::regclass);


--
-- TOC entry 4832 (class 2604 OID 16457)
-- Name: player_pitcher_stats id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_pitcher_stats ALTER COLUMN id SET DEFAULT nextval('public.player_pitcher_stats_id_seq'::regclass);


--
-- TOC entry 4834 (class 2604 OID 16504)
-- Name: player_runner_stats id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_runner_stats ALTER COLUMN id SET DEFAULT nextval('public.player_runner_stats_id_seq'::regclass);


--
-- TOC entry 4830 (class 2604 OID 16411)
-- Name: player_season_teams id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_season_teams ALTER COLUMN id SET DEFAULT nextval('public.player_season_teams_id_seq'::regclass);


--
-- TOC entry 4837 (class 2604 OID 16561)
-- Name: team_defense_stats id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_defense_stats ALTER COLUMN id SET DEFAULT nextval('public.team_defense_stats_id_seq'::regclass);


--
-- TOC entry 4835 (class 2604 OID 16527)
-- Name: team_hitter_stats id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_hitter_stats ALTER COLUMN id SET DEFAULT nextval('public.team_hitter_stats_id_seq'::regclass);


--
-- TOC entry 4836 (class 2604 OID 16544)
-- Name: team_pitcher_stats id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_pitcher_stats ALTER COLUMN id SET DEFAULT nextval('public.team_pitcher_stats_id_seq'::regclass);


--
-- TOC entry 4839 (class 2604 OID 16595)
-- Name: team_rank_stats id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_rank_stats ALTER COLUMN id SET DEFAULT nextval('public.team_rank_stats_id_seq'::regclass);


--
-- TOC entry 4838 (class 2604 OID 16578)
-- Name: team_runner_stats id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_runner_stats ALTER COLUMN id SET DEFAULT nextval('public.team_runner_stats_id_seq'::regclass);


--
-- TOC entry 4829 (class 2604 OID 16393)
-- Name: teams team_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teams ALTER COLUMN team_id SET DEFAULT nextval('public.teams_team_id_seq'::regclass);


--
-- TOC entry 4891 (class 2606 OID 16618)
-- Name: kbreport_player_hitter_advanced kbreport_player_hitter_advanc_season_year_player_name_team__key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kbreport_player_hitter_advanced
    ADD CONSTRAINT kbreport_player_hitter_advanc_season_year_player_name_team__key UNIQUE (season_year, player_name, team_id);


--
-- TOC entry 4893 (class 2606 OID 16616)
-- Name: kbreport_player_hitter_advanced kbreport_player_hitter_advanced_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kbreport_player_hitter_advanced
    ADD CONSTRAINT kbreport_player_hitter_advanced_pkey PRIMARY KEY (id);


--
-- TOC entry 4895 (class 2606 OID 16629)
-- Name: kbreport_player_pitcher_advanced kbreport_player_pitcher_advan_season_year_player_name_team__key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kbreport_player_pitcher_advanced
    ADD CONSTRAINT kbreport_player_pitcher_advan_season_year_player_name_team__key UNIQUE (season_year, player_name, team_id);


--
-- TOC entry 4897 (class 2606 OID 16627)
-- Name: kbreport_player_pitcher_advanced kbreport_player_pitcher_advanced_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kbreport_player_pitcher_advanced
    ADD CONSTRAINT kbreport_player_pitcher_advanced_pkey PRIMARY KEY (id);


--
-- TOC entry 4899 (class 2606 OID 16639)
-- Name: kbreport_team_hitter_advanced kbreport_team_hitter_advanced_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kbreport_team_hitter_advanced
    ADD CONSTRAINT kbreport_team_hitter_advanced_pkey PRIMARY KEY (id);


--
-- TOC entry 4901 (class 2606 OID 16641)
-- Name: kbreport_team_hitter_advanced kbreport_team_hitter_advanced_season_year_team_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kbreport_team_hitter_advanced
    ADD CONSTRAINT kbreport_team_hitter_advanced_season_year_team_id_key UNIQUE (season_year, team_id);


--
-- TOC entry 4903 (class 2606 OID 16655)
-- Name: kbreport_team_pitcher_advanced kbreport_team_pitcher_advanced_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kbreport_team_pitcher_advanced
    ADD CONSTRAINT kbreport_team_pitcher_advanced_pkey PRIMARY KEY (id);


--
-- TOC entry 4905 (class 2606 OID 16657)
-- Name: kbreport_team_pitcher_advanced kbreport_team_pitcher_advanced_season_year_team_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kbreport_team_pitcher_advanced
    ADD CONSTRAINT kbreport_team_pitcher_advanced_season_year_team_id_key UNIQUE (season_year, team_id);


--
-- TOC entry 4863 (class 2606 OID 16487)
-- Name: player_defense_stats player_defense_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_defense_stats
    ADD CONSTRAINT player_defense_stats_pkey PRIMARY KEY (id);


--
-- TOC entry 4865 (class 2606 OID 16489)
-- Name: player_defense_stats player_defense_stats_season_year_player_id_team_id_position_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_defense_stats
    ADD CONSTRAINT player_defense_stats_season_year_player_id_team_id_position_key UNIQUE (season_year, player_id, team_id, "position");


--
-- TOC entry 4855 (class 2606 OID 16440)
-- Name: player_hitter_stats player_hitter_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_hitter_stats
    ADD CONSTRAINT player_hitter_stats_pkey PRIMARY KEY (id);


--
-- TOC entry 4857 (class 2606 OID 16442)
-- Name: player_hitter_stats player_hitter_stats_season_year_player_id_team_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_hitter_stats
    ADD CONSTRAINT player_hitter_stats_season_year_player_id_team_id_key UNIQUE (season_year, player_id, team_id);


--
-- TOC entry 4859 (class 2606 OID 16463)
-- Name: player_pitcher_stats player_pitcher_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_pitcher_stats
    ADD CONSTRAINT player_pitcher_stats_pkey PRIMARY KEY (id);


--
-- TOC entry 4861 (class 2606 OID 16465)
-- Name: player_pitcher_stats player_pitcher_stats_season_year_player_id_team_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_pitcher_stats
    ADD CONSTRAINT player_pitcher_stats_season_year_player_id_team_id_key UNIQUE (season_year, player_id, team_id);


--
-- TOC entry 4867 (class 2606 OID 16510)
-- Name: player_runner_stats player_runner_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_runner_stats
    ADD CONSTRAINT player_runner_stats_pkey PRIMARY KEY (id);


--
-- TOC entry 4869 (class 2606 OID 16512)
-- Name: player_runner_stats player_runner_stats_season_year_player_id_team_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_runner_stats
    ADD CONSTRAINT player_runner_stats_season_year_player_id_team_id_key UNIQUE (season_year, player_id, team_id);


--
-- TOC entry 4851 (class 2606 OID 16417)
-- Name: player_season_teams player_season_teams_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_season_teams
    ADD CONSTRAINT player_season_teams_pkey PRIMARY KEY (id);


--
-- TOC entry 4853 (class 2606 OID 16419)
-- Name: player_season_teams player_season_teams_season_year_player_id_team_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_season_teams
    ADD CONSTRAINT player_season_teams_season_year_player_id_team_id_key UNIQUE (season_year, player_id, team_id);


--
-- TOC entry 4849 (class 2606 OID 16406)
-- Name: players players_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.players
    ADD CONSTRAINT players_pkey PRIMARY KEY (player_id);


--
-- TOC entry 4879 (class 2606 OID 16566)
-- Name: team_defense_stats team_defense_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_defense_stats
    ADD CONSTRAINT team_defense_stats_pkey PRIMARY KEY (id);


--
-- TOC entry 4881 (class 2606 OID 16568)
-- Name: team_defense_stats team_defense_stats_season_year_team_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_defense_stats
    ADD CONSTRAINT team_defense_stats_season_year_team_id_key UNIQUE (season_year, team_id);


--
-- TOC entry 4871 (class 2606 OID 16532)
-- Name: team_hitter_stats team_hitter_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_hitter_stats
    ADD CONSTRAINT team_hitter_stats_pkey PRIMARY KEY (id);


--
-- TOC entry 4873 (class 2606 OID 16534)
-- Name: team_hitter_stats team_hitter_stats_season_year_team_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_hitter_stats
    ADD CONSTRAINT team_hitter_stats_season_year_team_id_key UNIQUE (season_year, team_id);


--
-- TOC entry 4875 (class 2606 OID 16549)
-- Name: team_pitcher_stats team_pitcher_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_pitcher_stats
    ADD CONSTRAINT team_pitcher_stats_pkey PRIMARY KEY (id);


--
-- TOC entry 4877 (class 2606 OID 16551)
-- Name: team_pitcher_stats team_pitcher_stats_season_year_team_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_pitcher_stats
    ADD CONSTRAINT team_pitcher_stats_season_year_team_id_key UNIQUE (season_year, team_id);


--
-- TOC entry 4887 (class 2606 OID 16600)
-- Name: team_rank_stats team_rank_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_rank_stats
    ADD CONSTRAINT team_rank_stats_pkey PRIMARY KEY (id);


--
-- TOC entry 4889 (class 2606 OID 16602)
-- Name: team_rank_stats team_rank_stats_season_year_team_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_rank_stats
    ADD CONSTRAINT team_rank_stats_season_year_team_id_key UNIQUE (season_year, team_id);


--
-- TOC entry 4883 (class 2606 OID 16583)
-- Name: team_runner_stats team_runner_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_runner_stats
    ADD CONSTRAINT team_runner_stats_pkey PRIMARY KEY (id);


--
-- TOC entry 4885 (class 2606 OID 16585)
-- Name: team_runner_stats team_runner_stats_season_year_team_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_runner_stats
    ADD CONSTRAINT team_runner_stats_season_year_team_id_key UNIQUE (season_year, team_id);


--
-- TOC entry 4845 (class 2606 OID 16397)
-- Name: teams teams_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT teams_pkey PRIMARY KEY (team_id);


--
-- TOC entry 4847 (class 2606 OID 16399)
-- Name: teams teams_team_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT teams_team_name_key UNIQUE (team_name);


--
-- TOC entry 4921 (class 2606 OID 16642)
-- Name: kbreport_team_hitter_advanced kbreport_team_hitter_advanced_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kbreport_team_hitter_advanced
    ADD CONSTRAINT kbreport_team_hitter_advanced_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 4922 (class 2606 OID 16658)
-- Name: kbreport_team_pitcher_advanced kbreport_team_pitcher_advanced_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kbreport_team_pitcher_advanced
    ADD CONSTRAINT kbreport_team_pitcher_advanced_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 4912 (class 2606 OID 16490)
-- Name: player_defense_stats player_defense_stats_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_defense_stats
    ADD CONSTRAINT player_defense_stats_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.players(player_id);


--
-- TOC entry 4913 (class 2606 OID 16495)
-- Name: player_defense_stats player_defense_stats_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_defense_stats
    ADD CONSTRAINT player_defense_stats_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 4908 (class 2606 OID 16443)
-- Name: player_hitter_stats player_hitter_stats_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_hitter_stats
    ADD CONSTRAINT player_hitter_stats_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.players(player_id);


--
-- TOC entry 4909 (class 2606 OID 16448)
-- Name: player_hitter_stats player_hitter_stats_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_hitter_stats
    ADD CONSTRAINT player_hitter_stats_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 4910 (class 2606 OID 16466)
-- Name: player_pitcher_stats player_pitcher_stats_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_pitcher_stats
    ADD CONSTRAINT player_pitcher_stats_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.players(player_id);


--
-- TOC entry 4911 (class 2606 OID 16471)
-- Name: player_pitcher_stats player_pitcher_stats_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_pitcher_stats
    ADD CONSTRAINT player_pitcher_stats_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 4914 (class 2606 OID 16513)
-- Name: player_runner_stats player_runner_stats_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_runner_stats
    ADD CONSTRAINT player_runner_stats_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.players(player_id);


--
-- TOC entry 4915 (class 2606 OID 16518)
-- Name: player_runner_stats player_runner_stats_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_runner_stats
    ADD CONSTRAINT player_runner_stats_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 4906 (class 2606 OID 16420)
-- Name: player_season_teams player_season_teams_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_season_teams
    ADD CONSTRAINT player_season_teams_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.players(player_id);


--
-- TOC entry 4907 (class 2606 OID 16425)
-- Name: player_season_teams player_season_teams_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.player_season_teams
    ADD CONSTRAINT player_season_teams_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 4918 (class 2606 OID 16569)
-- Name: team_defense_stats team_defense_stats_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_defense_stats
    ADD CONSTRAINT team_defense_stats_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 4916 (class 2606 OID 16535)
-- Name: team_hitter_stats team_hitter_stats_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_hitter_stats
    ADD CONSTRAINT team_hitter_stats_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 4917 (class 2606 OID 16552)
-- Name: team_pitcher_stats team_pitcher_stats_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_pitcher_stats
    ADD CONSTRAINT team_pitcher_stats_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 4920 (class 2606 OID 16603)
-- Name: team_rank_stats team_rank_stats_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_rank_stats
    ADD CONSTRAINT team_rank_stats_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 4919 (class 2606 OID 16586)
-- Name: team_runner_stats team_runner_stats_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_runner_stats
    ADD CONSTRAINT team_runner_stats_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


-- Completed on 2026-05-01 17:37:26

--
-- PostgreSQL database dump complete
--

\unrestrict QP91GmIQRwqOvLfScIQAw3CvNmz31caSsq82EnwM5GYE9xiyBuRs8BB9n6pVzlx

