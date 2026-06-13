import { useState, useRef, useEffect } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import Scoreboard from '../components/simulator/Scoreboard';
import StatsModal from '../components/simulator/StatsModal';
import { simulateGame, simulateMulti, fetchTeamPitchers } from '../api/simulatorApi';
import { saveRecord } from '../api/recordApi';
import { fetchTeamLineup } from '../api/playerApi';
import type { GameLog, InningLog, PlateAppearance, MultiSimulateResponse, PitcherInfo } from '../api/simulatorApi';

const DEFAULT_LINEUP_A = [
  { name: "박성한",   ab: 400, hits: 120, double: 20, triple: 2, hr: 5,  bb: 40, hbp: 3 },
  { name: "정준재",     ab: 380, hits: 100, double: 18, triple: 1, hr: 25, bb: 55, hbp: 5 },
  { name: "최정",   ab: 360, hits: 105, double: 22, triple: 0, hr: 18, bb: 35, hbp: 2 },
  { name: "김재환", ab: 350, hits: 98,  double: 19, triple: 1, hr: 20, bb: 30, hbp: 1 },
  { name: "에레디아",   ab: 370, hits: 108, double: 21, triple: 2, hr: 8,  bb: 38, hbp: 4 },
  { name: "전의산",   ab: 300, hits: 85,  double: 15, triple: 1, hr: 10, bb: 28, hbp: 2 },
  { name: "최지훈",   ab: 280, hits: 75,  double: 12, triple: 0, hr: 7,  bb: 22, hbp: 1 },
  { name: "조형우",   ab: 260, hits: 68,  double: 10, triple: 0, hr: 5,  bb: 18, hbp: 1 },
  { name: "홍대인",   ab: 240, hits: 60,  double: 8,  triple: 0, hr: 3,  bb: 15, hbp: 0 },
];

const DEFAULT_LINEUP_B = [
  { name: "황성빈",   ab: 48,  hits: 16, double: 1, triple: 1, hr: 0, bb: 1,  hbp: 1 },
  { name: "고승민",   ab: 75,  hits: 14, double: 4, triple: 0, hr: 3, bb: 6,  hbp: 1 },
  { name: "레이예스", ab: 113, hits: 39, double: 8, triple: 0, hr: 5, bb: 11, hbp: 2 },
  { name: "나승엽",   ab: 62,  hits: 16, double: 4, triple: 0, hr: 2, bb: 1,  hbp: 0 },
  { name: "전민재",   ab: 14,  hits: 1,  double: 0, triple: 0, hr: 1, bb: 3,  hbp: 0 },
  { name: "손호영",   ab: 32,  hits: 11, double: 2, triple: 0, hr: 1, bb: 1,  hbp: 0 },
  { name: "최항",   ab: 77,  hits: 18, double: 3, triple: 0, hr: 0, bb: 7,  hbp: 0 },
  { name: "손성빈",   ab: 48,  hits: 10, double: 2, triple: 0, hr: 1, bb: 6,  hbp: 0 },
  { name: "장두성",   ab: 74,  hits: 18, double: 3, triple: 0, hr: 0, bb: 7,  hbp: 1 },
];

interface FlatEvent {
  type: 'inning_header' | 'pa';
  inning: number;
  half: string;
  teamName?: string;
  pa?: PlateAppearance;
}

const eventToKorean: Record<string, string> = {
  '1B': '안타', '2B': '2루타', '3B': '3루타',
  'HR': '홈런', 'BB': '볼넷', 'OUT': '아웃', 'K': '삼진',
};

const eventBadgeStyle: Record<string, { background: string; color: string }> = {
  '1B':  { background: '#14532d', color: '#86efac' },
  '2B':  { background: '#14532d', color: '#4ade80' },
  '3B':  { background: '#166534', color: '#22c55e' },
  'HR':  { background: '#7c2d12', color: '#fdba74' },
  'BB':  { background: '#1e3a5f', color: '#60a5fa' },
  'K':   { background: '#3b0764', color: '#c4b5fd' },
  'OUT': { background: '#374151', color: '#9ca3af' },
};

const bannerCfg: Record<string, { bg: string; border: string; pc: string; ec: string; fs: string }> = {
  '1B': { bg: '#052e16', border: '2px solid #16a34a', pc: '#86efac', ec: '#4ade80',  fs: '1.5rem'   },
  '2B': { bg: '#052e16', border: '2px solid #22c55e', pc: '#4ade80', ec: '#22c55e',  fs: '1.875rem' },
  '3B': { bg: '#14532d', border: '2px solid #4ade80', pc: '#bbf7d0', ec: '#86efac',  fs: '2rem'     },
  'HR': { bg: '#431407', border: '2px solid #f97316', pc: '#fdba74', ec: '#f97316',  fs: '2.5rem'   },
  'BB': { bg: '#0c1a3a', border: '2px solid #3b82f6', pc: '#93c5fd', ec: '#60a5fa',  fs: '1.5rem'   },
  'K':  { bg: '#1e1b4b', border: '2px solid #818cf8', pc: '#c7d2fe', ec: '#a5b4fc',  fs: '1.5rem'   },
};

const SPEEDS = [1000, 500, 150];

function buildEvents(innings: InningLog[]): FlatEvent[] {
  const events: FlatEvent[] = [];
  const grouped: { top?: InningLog; bottom?: InningLog }[] = [];
  innings.forEach((log) => {
    const i = log.inning - 1;
    if (!grouped[i]) grouped[i] = {};
    if (log.half === '초') grouped[i].top = log;
    else grouped[i].bottom = log;
  });
  grouped.forEach((g, i) => {
    (['top', 'bottom'] as const).forEach((side) => {
      const log = side === 'top' ? g.top : g.bottom;
      if (!log) return;
      events.push({ type: 'inning_header', inning: i + 1, half: log.half, teamName: log.team_name });
      log.plate_appearances.forEach((pa) => {
        events.push({ type: 'pa', inning: i + 1, half: log.half, pa });
      });
    });
  });
  return events;
}

export default function SimulatorPage() {
  const location       = useLocation();
  const [searchParams] = useSearchParams();

  const fromMyTeam = location.state as {
    lineup:   typeof DEFAULT_LINEUP_A;
    teamName: string;
    opponent: string;
  } | null;

  const urlTeamA = searchParams.get('team_a');
  const urlTeamB = searchParams.get('team_b');

  const [teamAName, setTeamAName] = useState(fromMyTeam?.teamName ?? urlTeamA ?? 'SSG');
  const [teamBName, setTeamBName] = useState(fromMyTeam?.opponent ?? urlTeamB ?? '롯데');
  const [teamALineup, setTeamALineup] = useState(fromMyTeam?.lineup ?? DEFAULT_LINEUP_A);
  const [teamBLineup, setTeamBLineup] = useState(DEFAULT_LINEUP_B);
  const [lineupLoading, setLineupLoading] = useState(false);
  const [pitchersA, setPitchersA] = useState<PitcherInfo[]>([]);
  const [pitchersB, setPitchersB] = useState<PitcherInfo[]>([]);
  const [pitcherA, setPitcherA] = useState<string>('');
  const [pitcherB, setPitcherB] = useState<string>('');

  const [loading, setLoading]       = useState(false);
  const [showStats, setShowStats]   = useState(false);
  const [gameLog, setGameLog]       = useState<GameLog | null>(null);
  const [multiStats, setMultiStats] = useState<MultiSimulateResponse | null>(null);
  const [error, setError]           = useState<string | null>(null);

  const [displayed, setDisplayed] = useState<FlatEvent[]>([]);
  const [currentPA, setCurrentPA] = useState<PlateAppearance | null>(null);
  const [banner, setBanner]       = useState<PlateAppearance | null>(null);
  const [paused, setPaused]       = useState(false);
  const [done, setDone]           = useState(false);
  const [speed, setSpeed]         = useState(1);

  const eventsRef    = useRef<FlatEvent[]>([]);
  const idxRef       = useRef(0);
  const pausedRef    = useRef(false);
  const speedRef     = useRef(1);
  const timerRef     = useRef<ReturnType<typeof setTimeout> | null>(null);
  const bannerTimer  = useRef<ReturnType<typeof setTimeout> | null>(null);
  const logScrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!urlTeamA && !urlTeamB) return;
    if (urlTeamA) setTeamAName(urlTeamA);
    if (urlTeamB) setTeamBName(urlTeamB);
    setLineupLoading(true);
    const promises: Promise<void>[] = [];
    if (urlTeamA && !fromMyTeam) {
      promises.push(fetchTeamLineup(urlTeamA).then(setTeamALineup).catch(() => setTeamALineup(DEFAULT_LINEUP_A)));
    }
    if (urlTeamB) {
      promises.push(fetchTeamLineup(urlTeamB).then(setTeamBLineup).catch(() => setTeamBLineup(DEFAULT_LINEUP_B)));
    }
    Promise.all(promises).finally(() => setLineupLoading(false));
  }, [urlTeamA, urlTeamB]);

  useEffect(() => {
    if (urlTeamA || urlTeamB) return;
    fetchTeamLineup(fromMyTeam?.opponent ?? '롯데').then(setTeamBLineup).catch(() => setTeamBLineup(DEFAULT_LINEUP_B));
  }, []);

  useEffect(() => {
    fetchTeamPitchers(teamAName).then(setPitchersA).catch(() => setPitchersA([]));
    fetchTeamPitchers(teamBName).then(setPitchersB).catch(() => setPitchersB([]));
  }, [teamAName, teamBName]);

  useEffect(() => {
    if (logScrollRef.current) {
      logScrollRef.current.scrollTop = logScrollRef.current.scrollHeight;
    }
  }, [displayed]);

  function tick() {
    if (pausedRef.current) return;
    const idx    = idxRef.current;
    const events = eventsRef.current;
    if (idx >= events.length) { setDone(true); return; }
    const ev = events[idx];
    idxRef.current = idx + 1;
    setDisplayed((prev) => [...prev, ev]);
    if (ev.type === 'pa' && ev.pa) {
      setCurrentPA(ev.pa);
      if (bannerCfg[ev.pa.event]) {
        setBanner(ev.pa);
        if (bannerTimer.current) clearTimeout(bannerTimer.current);
        bannerTimer.current = setTimeout(() => setBanner(null), 2000);
      }
    }
    timerRef.current = setTimeout(tick, SPEEDS[speedRef.current]);
  }

  function startAnimation(innings: InningLog[]) {
    if (timerRef.current) clearTimeout(timerRef.current);
    eventsRef.current = buildEvents(innings);
    idxRef.current    = 0;
    pausedRef.current = false;
    setDisplayed([]);
    setCurrentPA(null);
    setBanner(null);
    setPaused(false);
    setDone(false);
    timerRef.current = setTimeout(tick, SPEEDS[speedRef.current]);
  }

  async function handleStart() {
    setLoading(true); setError(null); setGameLog(null); setDisplayed([]);
    try {
      const res = await simulateGame({
        team_a_name: teamAName, team_a_lineup: teamALineup,
        team_b_name: teamBName, team_b_lineup: teamBLineup,
        pitcher_a: pitcherA || undefined, pitcher_b: pitcherB || undefined,
      });
      setGameLog(res.game_log);
      startAnimation(res.game_log.innings);
      const scoreA = res.game_log.final_score[0];
      const scoreB = res.game_log.final_score[1];
      await saveRecord({ team_name: teamAName, opponent_name: teamBName, result: scoreA > scoreB ? '승' : scoreA < scoreB ? '패' : '무', my_score: scoreA, opp_score: scoreB });
    } catch { setError('시뮬레이션 중 오류가 발생했습니다.'); }
    finally { setLoading(false); }
  }

  async function handleMultiStats() {
    setLoading(true);
    try {
      const res = await simulateMulti({
        team_a_name: teamAName, team_a_lineup: teamALineup,
        team_b_name: teamBName, team_b_lineup: teamBLineup,
        n_games: 1000,
        pitcher_a: pitcherA || undefined, pitcher_b: pitcherB || undefined,
      });
      setMultiStats(res); setShowStats(true);
    } catch { setError('통계 계산 중 오류가 발생했습니다.'); }
    finally { setLoading(false); }
  }

  function handleReset() {
    if (timerRef.current) clearTimeout(timerRef.current);
    setGameLog(null); setDisplayed([]); setCurrentPA(null); setBanner(null);
    setMultiStats(null); setError(null); setDone(false); setPaused(false);
  }

  function handleToggle() {
    if (done) {
      startAnimation(gameLog!.innings);
    } else if (paused) {
      pausedRef.current = false; setPaused(false);
      timerRef.current = setTimeout(tick, SPEEDS[speedRef.current]);
    } else {
      pausedRef.current = true; setPaused(true);
      if (timerRef.current) clearTimeout(timerRef.current);
    }
  }

  function handleSpeed(s: number) { speedRef.current = s; setSpeed(s); }

  const displayedInningSet = new Set(
    displayed.filter(e => e.type === 'inning_header').map(e => `${e.inning}-${e.half}`)
  );

  const scoreboard = gameLog ? {
    away: {
      team: teamAName,
      innings: gameLog.innings.filter(i => i.half === '초' && displayedInningSet.has(`${i.inning}-초`)).map(i => i.runs),
      total: gameLog.innings.filter(i => i.half === '초' && displayedInningSet.has(`${i.inning}-초`)).reduce((s, i) => s + i.runs, 0),
    },
    home: {
      team: teamBName,
      innings: gameLog.innings.filter(i => i.half === '말' && displayedInningSet.has(`${i.inning}-말`)).map(i => i.runs),
      total: gameLog.innings.filter(i => i.half === '말' && displayedInningSet.has(`${i.inning}-말`)).reduce((s, i) => s + i.runs, 0),
    },
  } : null;

  const selectStyle = {
    background: '#1a1a1a', color: '#f97316', border: '2px solid #374151',
    padding: '8px 12px', fontSize: '11px', fontFamily: "'Press Start 2P',cursive",
    outline: 'none', cursor: 'pointer',
  };

  return (
    <div className="min-h-screen" style={{ background: '#0a0a0a', fontFamily: "'Press Start 2P', cursive" }}>
      <style>{`
        @keyframes bannerIn { from { opacity:0; transform:scale(0.8); } to { opacity:1; transform:scale(1); } }
        @keyframes fadeSlideIn { from { opacity:0; transform:translateY(-6px); } to { opacity:1; transform:translateY(0); } }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
        .pa-row { animation: fadeSlideIn 0.3s ease forwards; opacity:0; }
        .retro-box { background:#0a0a0a; border:3px solid #f97316; box-shadow:4px 4px 0 #7c2d12; border-radius:2px; }
        .retro-btn { font-family:'Press Start 2P',cursive; border:2px solid currentColor; box-shadow:3px 3px 0 rgba(0,0,0,0.5); cursor:pointer; transition:transform 0.1s,box-shadow 0.1s; }
        .retro-btn:active { transform:translate(2px,2px); box-shadow:1px 1px 0 rgba(0,0,0,0.5); }
        ::-webkit-scrollbar { width:6px; }
        ::-webkit-scrollbar-track { background:#000; }
        ::-webkit-scrollbar-thumb { background:#f97316; border-radius:0; }
      `}</style>

      {/* 헤더 */}
      <div style={{ background:'#0f0f0f', borderBottom:'3px solid #f97316', padding:'24px 40px' }}>
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
          <div>
            <h1 style={{ color:'#f97316', fontSize:'14px', marginBottom:'8px', textShadow:'2px 2px 0 #7c2d12' }}>GAME SIMULATOR</h1>
            <p style={{ color:'#4b5563', fontSize:'8px' }}>MARKOV CHAIN BASE BALL</p>
          </div>
          <div style={{ display:'flex', alignItems:'center', gap:'24px' }}>
            <div style={{ textAlign:'right' }}>
              <p style={{ color:'#fff', fontSize:'10px', marginBottom:'4px' }}>{teamAName}</p>
              <p style={{ color:'#4b5563', fontSize:'8px' }}>AWAY</p>
            </div>
            <div style={{ background:'#000', border:'3px solid #f97316', boxShadow:'4px 4px 0 #7c2d12', padding:'12px 24px', textAlign:'center', minWidth:'100px' }}>
              {done && gameLog ? (
                <>
                  <span style={{ color:'#f97316', fontSize:'22px', textShadow:'2px 2px 0 #7c2d12' }}>{gameLog.final_score[0]}</span>
                  <span style={{ color:'#374151', margin:'0 8px', fontSize:'18px' }}>:</span>
                  <span style={{ color:'#f97316', fontSize:'22px', textShadow:'2px 2px 0 #7c2d12' }}>{gameLog.final_score[1]}</span>
                </>
              ) : (
                <span style={{ color:'#374151', fontSize:'14px', animation: gameLog ? 'blink 0.8s infinite' : 'none' }}>
                  {gameLog ? '...' : '-  :  -'}
                </span>
              )}
            </div>
            <div style={{ textAlign:'left' }}>
              <p style={{ color:'#fff', fontSize:'10px', marginBottom:'4px' }}>{teamBName}</p>
              <p style={{ color:'#4b5563', fontSize:'8px' }}>HOME</p>
            </div>
          </div>
        </div>

        {lineupLoading && (
          <p style={{ color:'#4b5563', fontSize:'8px', marginTop:'12px', animation:'blink 1s infinite' }}>LOADING LINEUP...</p>
        )}

        {!lineupLoading && (urlTeamA || fromMyTeam) && (
          <div style={{ marginTop:'16px', display:'flex', flexWrap:'wrap', gap:'8px' }}>
            {teamALineup.map((p, i) => (
              <span key={i} style={{ fontSize:'8px', background:'#1a1a1a', color:'#9ca3af', padding:'4px 8px', border:'1px solid #374151' }}>
                {i+1}. {p.name}
              </span>
            ))}
          </div>
        )}

        {/* 투수 선택 */}
        {!gameLog && (
          <div style={{ marginTop:'16px', display:'flex', gap:'24px', flexWrap:'wrap' }}>
            <div style={{ display:'flex', flexDirection:'column', gap:'6px' }}>
              <p style={{ color:'#6b7280', fontSize:'11px', letterSpacing:'1px' }}>{teamAName} 선발투수</p>
              <select value={pitcherA} onChange={e => setPitcherA(e.target.value)} style={selectStyle}>
                <option value="">선택 안함</option>
                {pitchersA.map(p => (
                  <option key={p.player_name} value={p.player_name}>
                    {p.player_name} (ERA {p.era} / GS {p.gs})
                  </option>
                ))}
              </select>
            </div>
            <div style={{ display:'flex', flexDirection:'column', gap:'6px' }}>
              <p style={{ color:'#6b7280', fontSize:'8px', letterSpacing:'1px' }}>{teamBName} 선발투수</p>
              <select value={pitcherB} onChange={e => setPitcherB(e.target.value)} style={selectStyle}>
                <option value="">선택 안함</option>
                {pitchersB.map(p => (
                  <option key={p.player_name} value={p.player_name}>
                    {p.player_name} (ERA {p.era} / GS {p.gs})
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}
      </div>

      <div style={{ padding:'32px 40px', display:'flex', flexDirection:'column', gap:'20px' }}>
        {error && (
          <div style={{ background:'#1a0a0a', border:'3px solid #ef4444', padding:'16px', color:'#ef4444', fontSize:'9px' }}>
            !! ERROR: {error}
          </div>
        )}

        {!gameLog && !loading && !lineupLoading && (
          <div style={{ display:'flex', justifyContent:'center', padding:'60px 0' }}>
            <button onClick={handleStart} className="retro-btn"
              style={{ background:'#f97316', color:'#000', fontSize:'13px', padding:'20px 48px', border:'3px solid #fff', boxShadow:'6px 6px 0 #7c2d12' }}>
              ▶ PLAY BALL
            </button>
          </div>
        )}

        {(loading || lineupLoading) && (
          <div style={{ display:'flex', justifyContent:'center', padding:'60px 0' }}>
            <p style={{ color:'#f97316', fontSize:'11px', animation:'blink 0.8s infinite' }}>
              {lineupLoading ? 'LOADING...' : 'SIMULATING...'}
            </p>
          </div>
        )}

        {gameLog && scoreboard && (
          <>
            <Scoreboard away={scoreboard.away} home={scoreboard.home} />

            {currentPA && (
              <div className="retro-box" style={{ padding:'20px 24px', display:'flex', alignItems:'center', gap:'32px' }}>
                <div>
                  <p style={{ color:'#6b7280', fontSize:'9px', marginBottom:'10px', letterSpacing:'1px' }}>OUT</p>
                  <div style={{ display:'flex', gap:'8px' }}>
                    {[0,1].map((dotIdx) => (
                      <div key={dotIdx} style={{
                        width:'16px', height:'16px', borderRadius:'50%',
                        border:`2px solid ${dotIdx < (currentPA.outs_after >= 3 ? 0 : currentPA.outs_after) ? '#f97316' : '#374151'}`,
                        background: dotIdx < (currentPA.outs_after >= 3 ? 0 : currentPA.outs_after) ? '#f97316' : 'transparent',
                        boxShadow: dotIdx < (currentPA.outs_after >= 3 ? 0 : currentPA.outs_after) ? '0 0 8px #f97316' : 'none',
                      }} />
                    ))}
                  </div>
                </div>
                <div>
                  <p style={{ color:'#6b7280', fontSize:'9px', marginBottom:'10px', letterSpacing:'1px' }}>BASE</p>
                  <svg viewBox="0 0 70 70" width="70" height="70">
                    <polygon points="35,8 62,35 35,62 8,35" fill="none" stroke="#374151" strokeWidth="1.5"/>
                    <rect x="55" y="28" width="12" height="12" rx="1"
                      fill={currentPA.bases_after?.includes('1루') ? '#f97316' : '#1f2937'}
                      stroke={currentPA.bases_after?.includes('1루') ? '#f97316' : '#4b5563'} strokeWidth="1.5"/>
                    <rect x="28" y="1" width="12" height="12" rx="1"
                      fill={currentPA.bases_after?.includes('2루') ? '#f97316' : '#1f2937'}
                      stroke={currentPA.bases_after?.includes('2루') ? '#f97316' : '#4b5563'} strokeWidth="1.5"/>
                    <rect x="1" y="28" width="12" height="12" rx="1"
                      fill={currentPA.bases_after?.includes('3루') ? '#f97316' : '#1f2937'}
                      stroke={currentPA.bases_after?.includes('3루') ? '#f97316' : '#4b5563'} strokeWidth="1.5"/>
                    <rect x="28" y="57" width="12" height="12" rx="1" fill="#1f2937" stroke="#4b5563" strokeWidth="1.5"/>
                  </svg>
                </div>
                <div>
                  <p style={{ color:'#6b7280', fontSize:'9px', marginBottom:'6px', letterSpacing:'1px' }}>RUNNER</p>
                  <p style={{ color:'#e5e7eb', fontSize:'10px' }}>{currentPA.bases_after || '없음'}</p>
                </div>
                <div style={{ marginLeft:'auto' }}>
                  <p style={{ color:'#6b7280', fontSize:'9px', marginBottom:'6px', letterSpacing:'1px' }}>AT BAT</p>
                  <p style={{ color:'#f97316', fontSize:'11px', textShadow:'1px 1px 0 #7c2d12' }}>{currentPA.batter_name}</p>
                </div>
              </div>
            )}

            <div className="retro-box" style={{ padding:'24px', position:'relative', overflow:'hidden' }}>
              {banner && bannerCfg[banner.event] && (() => {
                const cfg = bannerCfg[banner.event];
                return (
                  <div style={{ position:'absolute', top:0, left:0, right:0, bottom:0, display:'flex', alignItems:'center', justifyContent:'center', zIndex:99, pointerEvents:'none', background:'rgba(0,0,0,0.75)' }}>
                    <div style={{ background:cfg.bg, border:cfg.border, borderRadius:'2px', padding:'1.5rem 2.5rem', textAlign:'center', minWidth:'220px', animation:'bannerIn 0.35s cubic-bezier(0.34,1.56,0.64,1) forwards', boxShadow:'6px 6px 0 #000', fontFamily:"'Press Start 2P',cursive" }}>
                      <div style={{ color:cfg.pc, fontSize:'11px', marginBottom:'12px', letterSpacing:'1px' }}>{banner.batter_name}</div>
                      <div style={{ color:cfg.ec, fontSize:cfg.fs, fontWeight:900, textShadow:'2px 2px 0 #000' }}>{eventToKorean[banner.event]}!</div>
                    </div>
                  </div>
                );
              })()}

              <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:'16px' }}>
                <p style={{ color:'#f97316', fontSize:'9px', letterSpacing:'3px' }}>GAME LOG</p>
                <div style={{ display:'flex', alignItems:'center', gap:'8px' }}>
                  <div style={{ display:'flex', gap:'4px' }}>
                    {[['SLOW',0],['NORM',1],['FAST',2]].map(([label,sIdx]) => (
                      <button key={sIdx} onClick={() => handleSpeed(Number(sIdx))} className="retro-btn"
                        style={{
                          fontSize:'8px', padding:'5px 10px',
                          background: speed === Number(sIdx) ? '#f97316' : '#1a1a1a',
                          color: speed === Number(sIdx) ? '#000' : '#6b7280',
                          border: `2px solid ${speed === Number(sIdx) ? '#f97316' : '#374151'}`,
                          boxShadow: speed === Number(sIdx) ? '2px 2px 0 #7c2d12' : '2px 2px 0 #000',
                        }}>
                        {label}
                      </button>
                    ))}
                  </div>
                  <button onClick={handleToggle} className="retro-btn"
                    style={{ fontSize:'8px', padding:'5px 12px', background:'#1a1a1a', color:'#d1d5db', border:'2px solid #374151', boxShadow:'2px 2px 0 #000' }}>
                    {done ? 'RETRY' : paused ? '▶ PLAY' : '⏸ PAUSE'}
                  </button>
                </div>
              </div>

              <div ref={logScrollRef} style={{ maxHeight:'400px', overflowY:'auto', paddingRight:'8px', display:'flex', flexDirection:'column', gap:'4px' }}>
                {displayed.map((ev, evIdx) => {
                  const evKey = `ev-${evIdx}`;
                  if (ev.type === 'inning_header') {
                    return (
                      <div key={evKey} style={{ display:'flex', alignItems:'center', gap:'10px', padding:'10px 0', marginTop:'8px', borderBottom:'2px solid #1f2937' }}>
                        <span style={{
                          fontSize:'8px', fontFamily:"'Press Start 2P',cursive", padding:'4px 10px',
                          background: ev.half === '초' ? '#0c1a3a' : '#2d0a0a',
                          color: ev.half === '초' ? '#60a5fa' : '#f87171',
                          border: `1px solid ${ev.half === '초' ? '#3b82f6' : '#ef4444'}`,
                        }}>
                          {ev.inning}회{ev.half}
                        </span>
                        <span style={{ color:'#9ca3af', fontSize:'9px' }}>{ev.teamName}</span>
                      </div>
                    );
                  }
                  if (!ev.pa) return null;
                  const pa    = ev.pa;
                  const badge = eventBadgeStyle[pa.event] ?? { background:'#374151', color:'#9ca3af' };
                  return (
                    <div key={evKey} className="pa-row" style={{ display:'flex', alignItems:'center', gap:'12px', padding:'7px 0', borderBottom:'1px solid #151515' }}>
                      <span style={{ color:'#9ca3af', width:'72px', flexShrink:0, fontSize:'9px' }}>{pa.batter_name}</span>
                      <span style={{ fontSize:'8px', fontFamily:"'Press Start 2P',cursive", padding:'3px 8px', flexShrink:0, background:badge.background, color:badge.color }}>
                        {eventToKorean[pa.event] ?? pa.event}
                      </span>
                      <span style={{ color:'#6b7280', fontSize:'8px', flex:1 }}>{pa.outs_after}아웃 · {pa.bases_after}</span>
                      {pa.runs_scored > 0 && (
                        <span style={{ color:'#f97316', fontSize:'9px', fontWeight:700, marginLeft:'auto', textShadow:'1px 1px 0 #7c2d12' }}>
                          +{pa.runs_scored}★
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            <div style={{ display:'flex', gap:'16px' }}>
              <button onClick={handleReset} className="retro-btn"
                style={{ background:'#1a1a1a', color:'#9ca3af', fontSize:'9px', padding:'14px 28px', border:'2px solid #374151', boxShadow:'4px 4px 0 #000' }}>
                ↺ RESET
              </button>
              <button onClick={handleMultiStats} disabled={loading} className="retro-btn"
                style={{ background:'#0c1a3a', color:'#60a5fa', fontSize:'9px', padding:'14px 28px', border:'2px solid #3b82f6', boxShadow:'4px 4px 0 #1e3a5f', opacity: loading ? 0.5 : 1 }}>
                ▣ 100 GAMES STAT
              </button>
            </div>
          </>
        )}
      </div>

      {showStats && multiStats && (
        <StatsModal onClose={() => setShowStats(false)} stats={multiStats} />
      )}
    </div>
  );
}