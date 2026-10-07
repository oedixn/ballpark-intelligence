import { useState, useRef, useEffect } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import Scoreboard from '../components/simulator/Scoreboard';
import StatsModal from '../components/simulator/StatsModal';
import FieldAnimation from '../components/simulator/FieldAnimation';
import Fireworks from '../components/simulator/Fireworks';
import PitchZone from '../components/simulator/PitchZone';
import TeamSetup from '../components/simulator/TeamSetup';
import { simulateGame, simulateMulti, fetchTeamPitchers } from '../api/simulatorApi';
import { saveRecord } from '../api/recordApi';
import { fetchTeamLineup } from '../api/playerApi';
import type { GameLog, InningLog, PlateAppearance, MultiSimulateResponse, PitcherInfo } from '../api/simulatorApi';
import { useAuth } from '../context/AuthContext';
import { getTeamLogo } from '../utils/teamLogo';
import { buildSequence } from '../utils/pitchSequence';
import type { Pitch } from '../utils/pitchSequence';

const KBO_TEAMS = ['LG', '한화', 'SSG', '삼성', 'NC', 'KT', '롯데', 'KIA', '두산', '키움'];

const DEFAULT_LINEUP_A = [
  { name: "박성한", ab: 400, hits: 120, double: 20, triple: 2, hr: 5, bb: 40, hbp: 3 },
  { name: "정준재", ab: 380, hits: 100, double: 18, triple: 1, hr: 25, bb: 55, hbp: 5 },
  { name: "최정", ab: 360, hits: 105, double: 22, triple: 0, hr: 18, bb: 35, hbp: 2 },
  { name: "김재환", ab: 350, hits: 98, double: 19, triple: 1, hr: 20, bb: 30, hbp: 1 },
  { name: "에레디아", ab: 370, hits: 108, double: 21, triple: 2, hr: 8, bb: 38, hbp: 4 },
  { name: "전의산", ab: 300, hits: 85, double: 15, triple: 1, hr: 10, bb: 28, hbp: 2 },
  { name: "최지훈", ab: 280, hits: 75, double: 12, triple: 0, hr: 7, bb: 22, hbp: 1 },
  { name: "조형우", ab: 260, hits: 68, double: 10, triple: 0, hr: 5, bb: 18, hbp: 1 },
  { name: "홍대인", ab: 240, hits: 60, double: 8, triple: 0, hr: 3, bb: 15, hbp: 0 },
];
const DEFAULT_LINEUP_B = [
  { name: "황성빈", ab: 48, hits: 16, double: 1, triple: 1, hr: 0, bb: 1, hbp: 1 },
  { name: "고승민", ab: 75, hits: 14, double: 4, triple: 0, hr: 3, bb: 6, hbp: 1 },
  { name: "레이예스", ab: 113, hits: 39, double: 8, triple: 0, hr: 5, bb: 11, hbp: 2 },
  { name: "나승엽", ab: 62, hits: 16, double: 4, triple: 0, hr: 2, bb: 1, hbp: 0 },
  { name: "전민재", ab: 14, hits: 1, double: 0, triple: 0, hr: 1, bb: 3, hbp: 0 },
  { name: "손호영", ab: 32, hits: 11, double: 2, triple: 0, hr: 1, bb: 1, hbp: 0 },
  { name: "최항", ab: 77, hits: 18, double: 3, triple: 0, hr: 0, bb: 7, hbp: 0 },
  { name: "손성빈", ab: 48, hits: 10, double: 2, triple: 0, hr: 1, bb: 6, hbp: 0 },
  { name: "장두성", ab: 74, hits: 18, double: 3, triple: 0, hr: 0, bb: 7, hbp: 1 },
];

interface FlatEvent { type: 'inning_header' | 'pa'; inning: number; half: string; teamName?: string; pa?: PlateAppearance; }

const eventToKorean: Record<string, string> = { '1B': '안타', '2B': '2루타', '3B': '3루타', 'HR': '홈런', 'BB': '볼넷', 'OUT': '아웃', 'K': '삼진' };
const eventBadgeStyle: Record<string, { background: string; color: string }> = {
  '1B': { background: '#14532d', color: '#86efac' }, '2B': { background: '#14532d', color: '#4ade80' },
  '3B': { background: '#166534', color: '#22c55e' }, 'HR': { background: '#7c2d12', color: '#fdba74' },
  'BB': { background: '#1e3a5f', color: '#60a5fa' }, 'K': { background: '#3b0764', color: '#c4b5fd' },
  'OUT': { background: '#374151', color: '#9ca3af' },
};
const bannerCfg: Record<string, { bg: string; border: string; pc: string; ec: string; fs: string }> = {
  '1B': { bg: '#052e16', border: '2px solid #16a34a', pc: '#86efac', ec: '#4ade80', fs: '1.5rem' },
  '2B': { bg: '#052e16', border: '2px solid #22c55e', pc: '#4ade80', ec: '#22c55e', fs: '1.875rem' },
  '3B': { bg: '#14532d', border: '2px solid #4ade80', pc: '#bbf7d0', ec: '#86efac', fs: '2rem' },
  'HR': { bg: '#431407', border: '2px solid #f97316', pc: '#fdba74', ec: '#f97316', fs: '2.5rem' },
  'BB': { bg: '#0c1a3a', border: '2px solid #3b82f6', pc: '#93c5fd', ec: '#60a5fa', fs: '1.5rem' },
  'K': { bg: '#1e1b4b', border: '2px solid #818cf8', pc: '#c7d2fe', ec: '#a5b4fc', fs: '1.5rem' },
};

const PITCH_MS = [800, 520, 190];
const HOLD_MS = [1000, 600, 150];
const HEADER_MS = [800, 450, 120];
const SPARKLES = ['✦', '★', '✦', '★', '✦'];
const PX = "'Press Start 2P',cursive";

function buildEvents(innings: InningLog[]): FlatEvent[] {
  const events: FlatEvent[] = [];
  const grouped: { top?: InningLog; bottom?: InningLog }[] = [];
  innings.forEach((log) => {
    const i = log.inning - 1;
    if (!grouped[i]) grouped[i] = {};
    if (log.half === '초') grouped[i].top = log; else grouped[i].bottom = log;
  });
  grouped.forEach((g, i) => {
    (['top', 'bottom'] as const).forEach((side) => {
      const log = side === 'top' ? g.top : g.bottom;
      if (!log) return;
      events.push({ type: 'inning_header', inning: i + 1, half: log.half, teamName: log.team_name });
      log.plate_appearances.forEach((pa) => events.push({ type: 'pa', inning: i + 1, half: log.half, pa }));
    });
  });
  return events;
}

export default function SimulatorPage() {
  const { isAuthenticated } = useAuth();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const fromMyTeam = location.state as { lineup: typeof DEFAULT_LINEUP_A; teamName: string; opponent: string; pitchers?: { starters: string[]; bullpen: Record<string, string> } } | null;
  const urlTeamA = searchParams.get('team_a');
  const urlTeamB = searchParams.get('team_b');

  const [teamAName, setTeamAName] = useState(fromMyTeam?.teamName ?? urlTeamA ?? 'SSG');
  const [teamBName, setTeamBName] = useState(fromMyTeam?.opponent ?? urlTeamB ?? '롯데');
  const [teamALineup, setTeamALineup] = useState(fromMyTeam?.lineup ?? DEFAULT_LINEUP_A);
  const [teamBLineup, setTeamBLineup] = useState(DEFAULT_LINEUP_B);
  const [lineupLoading, setLineupLoading] = useState(false);
  const [pitchersA, setPitchersA] = useState<PitcherInfo[]>([]);
  const [pitchersB, setPitchersB] = useState<PitcherInfo[]>([]);
  const [pitcherAId, setPitcherAId] = useState('');
  const [pitcherBId, setPitcherBId] = useState('');
  const [customStarter, setCustomStarter] = useState(fromMyTeam?.pitchers?.starters?.[0] ?? '');
  const [loading, setLoading] = useState(false);
  const [showStats, setShowStats] = useState(false);
  const [gameLog, setGameLog] = useState<GameLog | null>(null);
  const [multiStats, setMultiStats] = useState<MultiSimulateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [displayed, setDisplayed] = useState<FlatEvent[]>([]);
  const [currentPA, setCurrentPA] = useState<PlateAppearance | null>(null);
  const [pitchView, setPitchView] = useState<{ pa: PlateAppearance; pitches: Pitch[]; key: number; step: number } | null>(null);
  const [banner, setBanner] = useState<PlateAppearance | null>(null);
  const [paused, setPaused] = useState(false);
  const [done, setDone] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [hrShake, setHrShake] = useState(false);
  const [paSeq, setPaSeq] = useState(0);

  const eventsRef = useRef<FlatEvent[]>([]);
  const idxRef = useRef(0);
  const pausedRef = useRef(false);
  const speedRef = useRef(1);
  const pendingRef = useRef<(() => void) | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const bannerTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const shakeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const logScrollRef = useRef<HTMLDivElement>(null);

  // 나만의 팀에서 넘어온 투수진 (AWAY가 그 팀일 때만 사용)
  const staffA = fromMyTeam && teamAName === fromMyTeam.teamName ? fromMyTeam.pitchers : undefined;

  useEffect(() => {
    if (!urlTeamA && !urlTeamB) return;
    if (urlTeamA) setTeamAName(urlTeamA);
    if (urlTeamB) setTeamBName(urlTeamB);
    setLineupLoading(true);
    const promises: Promise<void>[] = [];
    if (urlTeamA && !fromMyTeam) promises.push(fetchTeamLineup(urlTeamA).then(setTeamALineup).catch(() => setTeamALineup(DEFAULT_LINEUP_A)));
    if (urlTeamB) promises.push(fetchTeamLineup(urlTeamB).then(setTeamBLineup).catch(() => setTeamBLineup(DEFAULT_LINEUP_B)));
    Promise.all(promises).finally(() => setLineupLoading(false));
  }, [urlTeamA, urlTeamB]);

  useEffect(() => {
    if (urlTeamA || urlTeamB) return;
    fetchTeamLineup(fromMyTeam?.opponent ?? '롯데').then(setTeamBLineup).catch(() => setTeamBLineup(DEFAULT_LINEUP_B));
  }, []);

  useEffect(() => {
    setPitcherAId(''); setPitcherBId('');
    fetchTeamPitchers(teamAName).then(setPitchersA).catch(() => setPitchersA([]));
    fetchTeamPitchers(teamBName).then(setPitchersB).catch(() => setPitchersB([]));
  }, [teamAName, teamBName]);

  useEffect(() => {
    if (logScrollRef.current) logScrollRef.current.scrollTop = logScrollRef.current.scrollHeight;
  }, [displayed]);

  async function changeTeam(side: 'A' | 'B', name: string) {
    if (side === 'A') setTeamAName(name); else setTeamBName(name);
    try {
      const lineup = await fetchTeamLineup(name);
      if (side === 'A') setTeamALineup(lineup); else setTeamBLineup(lineup);
    } catch { /* 기존 타순 유지 */ }
  }

  function reveal(ev: FlatEvent) {
    setDisplayed((prev) => [...prev, ev]);
    if (ev.type === 'pa' && ev.pa) {
      setPaSeq((s) => s + 1);
      setCurrentPA(ev.pa);
      if (bannerCfg[ev.pa.event]) {
        setBanner(ev.pa);
        if (ev.pa.event === 'HR') {
          setHrShake(true);
          if (shakeTimer.current) clearTimeout(shakeTimer.current);
          shakeTimer.current = setTimeout(() => setHrShake(false), 650);
        }
        if (bannerTimer.current) clearTimeout(bannerTimer.current);
        bannerTimer.current = setTimeout(() => setBanner(null), 2000);
      }
    }
  }

  function tick() {
    if (pausedRef.current) return;
    const idx = idxRef.current, events = eventsRef.current;
    if (idx >= events.length) { setDone(true); return; }
    const ev = events[idx];
    idxRef.current = idx + 1;
    const sp = speedRef.current;

    if (ev.type !== 'pa' || !ev.pa) {
      setDisplayed((prev) => [...prev, ev]);
      timerRef.current = setTimeout(tick, HEADER_MS[sp]);
      return;
    }

    const pitches = buildSequence(ev.pa.event, `${idx}-${ev.pa.batter_name}`);
    setPitchView({ pa: ev.pa, pitches, key: idx, step: PITCH_MS[sp] });
    const finish = () => {
      pendingRef.current = null;
      reveal(ev);
      timerRef.current = setTimeout(tick, HOLD_MS[sp]);
    };
    pendingRef.current = finish;
    timerRef.current = setTimeout(finish, (pitches.length + 1) * PITCH_MS[sp]);
  }

  function startAnimation(innings: InningLog[]) {
    if (timerRef.current) clearTimeout(timerRef.current);
    eventsRef.current = buildEvents(innings);
    idxRef.current = 0; pausedRef.current = false; pendingRef.current = null;
    setDisplayed([]); setCurrentPA(null); setPitchView(null); setBanner(null); setPaused(false); setDone(false);
    timerRef.current = setTimeout(tick, HEADER_MS[speedRef.current]);
  }

  const pitcherParams = () => {
    const a = pitchersA.find(p => p.player_id === pitcherAId), b = pitchersB.find(p => p.player_id === pitcherBId);
    return {
      pitcher_a: staffA ? (customStarter || undefined) : a?.player_name,
      pitcher_b: b?.player_name,
      pitcher_a_id: staffA ? undefined : a?.player_id,
      pitcher_b_id: b?.player_id,
    };
  };

  async function handleStart() {
    setLoading(true); setError(null); setGameLog(null); setDisplayed([]);
    try {
      const res = await simulateGame({ team_a_name: teamAName, team_a_lineup: teamALineup, team_b_name: teamBName, team_b_lineup: teamBLineup, ...pitcherParams() });
      setGameLog(res.game_log);
      startAnimation(res.game_log.innings);
      const [sa, sb] = res.game_log.final_score;
      if (isAuthenticated) {
        try { await saveRecord({ team_name: teamAName, opponent_name: teamBName, result: sa > sb ? '승' : sa < sb ? '패' : '무', my_score: sa, opp_score: sb }); }
        catch { console.warn('경기 결과는 생성됐지만 전적 저장에 실패했습니다.'); }
      }
    } catch { setError('시뮬레이션 중 오류가 발생했습니다.'); }
    finally { setLoading(false); }
  }

  async function handleMultiStats() {
    setLoading(true);
    try {
      const res = await simulateMulti({ team_a_name: teamAName, team_a_lineup: teamALineup, team_b_name: teamBName, team_b_lineup: teamBLineup, n_games: 1000, ...pitcherParams() });
      setMultiStats(res); setShowStats(true);
    } catch { setError('통계 계산 중 오류가 발생했습니다.'); }
    finally { setLoading(false); }
  }

  function handleReset() {
    if (timerRef.current) clearTimeout(timerRef.current);
    pendingRef.current = null;
    setGameLog(null); setDisplayed([]); setCurrentPA(null); setPitchView(null); setBanner(null);
    setMultiStats(null); setError(null); setDone(false); setPaused(false); setHrShake(false);
  }

  function handleToggle() {
    if (done) startAnimation(gameLog!.innings);
    else if (paused) {
      pausedRef.current = false; setPaused(false);
      if (pendingRef.current) pendingRef.current();
      else timerRef.current = setTimeout(tick, HOLD_MS[speedRef.current]);
    } else {
      pausedRef.current = true; setPaused(true);
      if (timerRef.current) clearTimeout(timerRef.current);
    }
  }

  function handleSpeed(s: number) { speedRef.current = s; setSpeed(s); }

  const shown = new Set(displayed.filter(e => e.type === 'inning_header').map(e => `${e.inning}-${e.half}`));
  const side = (half: string, team: string) => {
    const rows = gameLog!.innings.filter(i => i.half === half && shown.has(`${i.inning}-${half}`));
    return { team, innings: rows.map(i => i.runs), total: rows.reduce((s, i) => s + i.runs, 0) };
  };
  const scoreboard = gameLog ? { away: side('초', teamAName), home: side('말', teamBName) } : null;

  const logoA = getTeamLogo(teamAName), logoB = getTeamLogo(teamBName);
  const lbl = { color: '#9ca3af', fontSize: '11px', letterSpacing: '1px' } as const;
  const outs = currentPA ? (currentPA.outs_after >= 3 ? 0 : currentPA.outs_after) : 0;
  const batterName = pitchView?.pa.batter_name ?? currentPA?.batter_name;
  const ready = teamALineup.length === 9 && teamBLineup.length === 9;

  return (
    <div className={hrShake ? 'shake' : ''} style={{ minHeight: '100vh', background: '#0a0a0a', fontFamily: PX }}>
      <style>{`
        @keyframes bannerIn { from { opacity:0; transform:scale(0.8); } to { opacity:1; transform:scale(1); } }
        @keyframes fadeSlideIn { from { opacity:0; transform:translateY(-6px); } to { opacity:1; transform:translateY(0); } }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
        @keyframes shake { 0%,100%{transform:translateX(0)} 15%{transform:translateX(-8px) rotate(-0.3deg)} 30%{transform:translateX(7px) rotate(0.3deg)} 45%{transform:translateX(-6px)} 60%{transform:translateX(5px)} 75%{transform:translateX(-3px)} 90%{transform:translateX(2px)} }
        @keyframes runPop { 0%{transform:scale(0.3) translateY(6px);opacity:0} 60%{transform:scale(1.3) translateY(-2px);opacity:1} 100%{transform:scale(1) translateY(0);opacity:1} }
        @keyframes sparkleFloat { 0%{transform:translateY(0) scale(0.6);opacity:0} 20%{opacity:1} 100%{transform:translateY(-60px) scale(1.1);opacity:0} }
        .pa-row { animation: fadeSlideIn 0.3s ease forwards; opacity:0; }
        .retro-box { background:#0a0a0a; border:3px solid #f97316; box-shadow:4px 4px 0 #7c2d12; border-radius:2px; }
        .retro-btn { font-family:${PX}; border:2px solid currentColor; box-shadow:3px 3px 0 rgba(0,0,0,0.5); cursor:pointer; transition:transform 0.1s,box-shadow 0.1s; }
        .retro-btn:active { transform:translate(2px,2px); box-shadow:1px 1px 0 rgba(0,0,0,0.5); }
        .shake { animation: shake 0.5s ease-in-out; }
        .run-badge { animation: runPop 0.4s cubic-bezier(0.34,1.56,0.64,1) forwards; }
        .sparkle { position:absolute; animation: sparkleFloat 1.1s ease-out forwards; pointer-events:none; }
        ::-webkit-scrollbar { width:6px; } ::-webkit-scrollbar-track { background:#000; } ::-webkit-scrollbar-thumb { background:#f97316; border-radius:0; }
      `}</style>

      <div style={{ background: '#0f0f0f', borderBottom: '3px solid #f97316', padding: '24px 40px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h1 style={{ color: '#f97316', fontSize: '18px', marginBottom: '10px', textShadow: '2px 2px 0 #7c2d12' }}>GAME SIMULATOR</h1>
            <p style={{ color: '#6b7280', fontSize: '11px' }}>MARKOV CHAIN BASE BALL</p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
            <div style={{ textAlign: 'right', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div>
                <p style={{ color: '#fff', fontSize: '14px', marginBottom: '6px' }}>{teamAName}</p>
                <p style={{ color: '#6b7280', fontSize: '10px' }}>AWAY</p>
              </div>
              {logoA && <img src={logoA} alt={teamAName} style={{ width: '34px', height: '34px', objectFit: 'contain' }} />}
            </div>
            <div style={{ background: '#000', border: '3px solid #f97316', boxShadow: '4px 4px 0 #7c2d12', padding: '12px 24px', textAlign: 'center', minWidth: '120px' }}>
              {done && gameLog ? (
                <>
                  <span style={{ color: '#f97316', fontSize: '26px', textShadow: '2px 2px 0 #7c2d12' }}>{gameLog.final_score[0]}</span>
                  <span style={{ color: '#374151', margin: '0 8px', fontSize: '20px' }}>:</span>
                  <span style={{ color: '#f97316', fontSize: '26px', textShadow: '2px 2px 0 #7c2d12' }}>{gameLog.final_score[1]}</span>
                </>
              ) : (
                <span style={{ color: '#374151', fontSize: '16px', animation: gameLog ? 'blink 0.8s infinite' : 'none' }}>{gameLog ? '...' : '-  :  -'}</span>
              )}
            </div>
            <div style={{ textAlign: 'left', display: 'flex', alignItems: 'center', gap: '10px' }}>
              {logoB && <img src={logoB} alt={teamBName} style={{ width: '34px', height: '34px', objectFit: 'contain' }} />}
              <div>
                <p style={{ color: '#fff', fontSize: '14px', marginBottom: '6px' }}>{teamBName}</p>
                <p style={{ color: '#6b7280', fontSize: '10px' }}>HOME</p>
              </div>
            </div>
          </div>
        </div>

        {lineupLoading && <p style={{ color: '#6b7280', fontSize: '11px', marginTop: '12px', animation: 'blink 1s infinite' }}>LOADING LINEUP...</p>}

        {!gameLog && (
          <div style={{ marginTop: '20px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '20px' }}>
            <TeamSetup side="AWAY" teamName={teamAName} teams={KBO_TEAMS} excludeTeam={teamBName}
              onTeamChange={(n) => changeTeam('A', n)} pitchers={pitchersA} pitcherId={pitcherAId} onPitcherChange={setPitcherAId}
              lineup={teamALineup} onLineupChange={setTeamALineup}
              staff={staffA} staffStarter={customStarter} onStaffStarterChange={setCustomStarter} />
            <TeamSetup side="HOME" teamName={teamBName} teams={KBO_TEAMS} excludeTeam={teamAName}
              onTeamChange={(n) => changeTeam('B', n)} pitchers={pitchersB} pitcherId={pitcherBId} onPitcherChange={setPitcherBId}
              lineup={teamBLineup} onLineupChange={setTeamBLineup} />
          </div>
        )}
      </div>

      <div style={{ padding: '32px 40px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {error && <div style={{ background: '#1a0a0a', border: '3px solid #ef4444', padding: '16px', color: '#ef4444', fontSize: '12px' }}>!! ERROR: {error}</div>}

        {!gameLog && !loading && !lineupLoading && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '14px', padding: '40px 0' }}>
            <button onClick={handleStart} disabled={!ready} className="retro-btn"
              style={{ background: '#f97316', color: '#000', fontSize: '16px', padding: '22px 52px', border: '3px solid #fff', boxShadow: '6px 6px 0 #7c2d12', opacity: ready ? 1 : 0.4, cursor: ready ? 'pointer' : 'not-allowed' }}>▶ PLAY BALL</button>
            {!ready && <p style={{ color: '#ef4444', fontSize: '12px' }}>양 팀 타순을 9명으로 맞춰주세요 ({teamALineup.length}/9 · {teamBLineup.length}/9)</p>}
          </div>
        )}

        {(loading || lineupLoading) && (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '60px 0' }}>
            <p style={{ color: '#f97316', fontSize: '14px', animation: 'blink 0.8s infinite' }}>{lineupLoading ? 'LOADING...' : 'SIMULATING...'}</p>
          </div>
        )}

        {gameLog && scoreboard && (
          <>
            <Scoreboard away={scoreboard.away} home={scoreboard.home} />

            {(currentPA || pitchView) && (
              <div className="retro-box" style={{ padding: '20px 24px', display: 'flex', alignItems: 'flex-start', gap: '32px', flexWrap: 'wrap' }}>
                <div>
                  <p style={{ ...lbl, marginBottom: '12px' }}>OUT</p>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    {[0, 1].map((d) => (
                      <div key={d} style={{ width: '18px', height: '18px', borderRadius: '50%', border: `2px solid ${d < outs ? '#f97316' : '#374151'}`, background: d < outs ? '#f97316' : 'transparent', boxShadow: d < outs ? '0 0 8px #f97316' : 'none' }} />
                    ))}
                  </div>
                </div>
                {currentPA && (
                  <div>
                    <p style={{ ...lbl, marginBottom: '8px' }}>FIELD</p>
                    <div style={{ width: 136, height: 136 }}><FieldAnimation key={paSeq} event={currentPA.event} /></div>
                  </div>
                )}
                {pitchView && (
                  <div>
                    <p style={{ ...lbl, marginBottom: '8px' }}>ABS ZONE</p>
                    <PitchZone key={pitchView.key} event={pitchView.pa.event} pitches={pitchView.pitches} stepMs={pitchView.step} />
                  </div>
                )}
                <div>
                  <p style={{ ...lbl, marginBottom: '8px' }}>RUNNER</p>
                  <p style={{ color: '#e5e7eb', fontSize: '13px' }}>{currentPA?.bases_after || '없음'}</p>
                </div>
                <div style={{ marginLeft: 'auto' }}>
                  <p style={{ ...lbl, marginBottom: '8px' }}>AT BAT</p>
                  <p style={{ color: '#f97316', fontSize: '15px', textShadow: '1px 1px 0 #7c2d12' }}>{batterName}</p>
                </div>
              </div>
            )}

            <div className="retro-box" style={{ padding: '24px', position: 'relative', overflow: 'hidden' }}>
              {banner && bannerCfg[banner.event] && (() => {
                const cfg = bannerCfg[banner.event];
                const isHR = banner.event === 'HR';
                return (
                  <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 99, pointerEvents: 'none', background: 'rgba(0,0,0,0.75)' }}>
                    {isHR && SPARKLES.map((s, si) => (
                      <span key={si} className="sparkle" style={{ left: `${35 + si * 8}%`, bottom: '45%', color: '#fdba74', fontSize: '18px', animationDelay: `${si * 0.08}s` }}>{s}</span>
                    ))}
                    {isHR && <Fireworks />}
                    <div style={{ background: cfg.bg, border: cfg.border, borderRadius: '2px', padding: '1.5rem 2.5rem', textAlign: 'center', minWidth: '220px', animation: 'bannerIn 0.35s cubic-bezier(0.34,1.56,0.64,1) forwards', boxShadow: '6px 6px 0 #000', fontFamily: PX }}>
                      <div style={{ color: cfg.pc, fontSize: '14px', marginBottom: '12px', letterSpacing: '1px' }}>{banner.batter_name}</div>
                      <div style={{ color: cfg.ec, fontSize: cfg.fs, fontWeight: 900, textShadow: '2px 2px 0 #000' }}>{eventToKorean[banner.event]}!</div>
                    </div>
                  </div>
                );
              })()}

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                <p style={{ color: '#f97316', fontSize: '12px', letterSpacing: '3px' }}>GAME LOG</p>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    {[['SLOW', 0], ['NORM', 1], ['FAST', 2]].map(([label, s]) => (
                      <button key={s} onClick={() => handleSpeed(Number(s))} className="retro-btn"
                        style={{ fontSize: '10px', padding: '6px 12px', background: speed === Number(s) ? '#f97316' : '#1a1a1a', color: speed === Number(s) ? '#000' : '#9ca3af', border: `2px solid ${speed === Number(s) ? '#f97316' : '#374151'}`, boxShadow: speed === Number(s) ? '2px 2px 0 #7c2d12' : '2px 2px 0 #000' }}>{label}</button>
                    ))}
                  </div>
                  <button onClick={handleToggle} className="retro-btn"
                    style={{ fontSize: '10px', padding: '6px 14px', background: '#1a1a1a', color: '#d1d5db', border: '2px solid #374151', boxShadow: '2px 2px 0 #000' }}>
                    {done ? 'RETRY' : paused ? '▶ PLAY' : '⏸ PAUSE'}
                  </button>
                </div>
              </div>

              <div ref={logScrollRef} style={{ maxHeight: '400px', overflowY: 'auto', paddingRight: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {displayed.map((ev, i) => {
                  if (ev.type === 'inning_header') {
                    const top = ev.half === '초';
                    return (
                      <div key={`ev-${i}`} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 0', marginTop: '8px', borderBottom: '2px solid #1f2937' }}>
                        <span style={{ fontSize: '11px', fontFamily: PX, padding: '5px 12px', background: top ? '#0c1a3a' : '#2d0a0a', color: top ? '#60a5fa' : '#f87171', border: `1px solid ${top ? '#3b82f6' : '#ef4444'}` }}>{ev.inning}회{ev.half}</span>
                        <span style={{ color: '#9ca3af', fontSize: '12px' }}>{ev.teamName}</span>
                      </div>
                    );
                  }
                  if (!ev.pa) return null;
                  const pa = ev.pa, badge = eventBadgeStyle[pa.event] ?? { background: '#374151', color: '#9ca3af' };
                  return (
                    <div key={`ev-${i}`} className="pa-row" style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '8px 0', borderBottom: '1px solid #151515' }}>
                      <span style={{ color: '#d1d5db', width: '96px', flexShrink: 0, fontSize: '12px' }}>{pa.batter_name}</span>
                      <span style={{ fontSize: '11px', fontFamily: PX, padding: '4px 10px', flexShrink: 0, background: badge.background, color: badge.color }}>{eventToKorean[pa.event] ?? pa.event}</span>
                      <span style={{ color: '#9ca3af', fontSize: '11px', flex: 1 }}>{pa.outs_after}아웃 · {pa.bases_after}</span>
                      {pa.runs_scored > 0 && <span className="run-badge" style={{ color: '#f97316', fontSize: '12px', fontWeight: 700, marginLeft: 'auto', textShadow: '1px 1px 0 #7c2d12' }}>+{pa.runs_scored}★</span>}
                    </div>
                  );
                })}
              </div>
            </div>

            <div style={{ display: 'flex', gap: '16px' }}>
              <button onClick={handleReset} className="retro-btn" style={{ background: '#1a1a1a', color: '#9ca3af', fontSize: '12px', padding: '14px 28px', border: '2px solid #374151', boxShadow: '4px 4px 0 #000' }}>↺ RESET</button>
              <button onClick={handleMultiStats} disabled={loading} className="retro-btn"
                style={{ background: '#0c1a3a', color: '#60a5fa', fontSize: '12px', padding: '14px 28px', border: '2px solid #3b82f6', boxShadow: '4px 4px 0 #1e3a5f', opacity: loading ? 0.5 : 1 }}>▣ 1000 GAMES STAT</button>
            </div>
          </>
        )}
      </div>

      {showStats && multiStats && <StatsModal onClose={() => setShowStats(false)} stats={multiStats} />}
    </div>
  );
}