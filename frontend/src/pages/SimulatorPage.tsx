import { useState, useRef, useEffect } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import Scoreboard from '../components/simulator/Scoreboard';
import StatsModal from '../components/simulator/StatsModal';
import { simulateGame, simulateMulti } from '../api/simulatorApi';
import { saveRecord } from '../api/recordApi';
import { fetchTeamLineup } from '../api/playerApi';
import type { GameLog, InningLog, PlateAppearance, MultiSimulateResponse } from '../api/simulatorApi';

const DEFAULT_LINEUP_A = [
  { name: "최지훈",   ab: 400, hits: 120, double: 20, triple: 2, hr: 5,  bb: 40, hbp: 3 },
  { name: "최정",     ab: 380, hits: 100, double: 18, triple: 1, hr: 25, bb: 55, hbp: 5 },
  { name: "한유섬",   ab: 360, hits: 105, double: 22, triple: 0, hr: 18, bb: 35, hbp: 2 },
  { name: "기예르모", ab: 350, hits: 98,  double: 19, triple: 1, hr: 20, bb: 30, hbp: 1 },
  { name: "박성한",   ab: 370, hits: 108, double: 21, triple: 2, hr: 8,  bb: 38, hbp: 4 },
  { name: "오태곤",   ab: 300, hits: 85,  double: 15, triple: 1, hr: 10, bb: 28, hbp: 2 },
  { name: "김민식",   ab: 280, hits: 75,  double: 12, triple: 0, hr: 7,  bb: 22, hbp: 1 },
  { name: "이재원",   ab: 260, hits: 68,  double: 10, triple: 0, hr: 5,  bb: 18, hbp: 1 },
  { name: "고효준",   ab: 240, hits: 60,  double: 8,  triple: 0, hr: 3,  bb: 15, hbp: 0 },
];

const DEFAULT_LINEUP_B = [
  { name: "장두성",   ab: 48,  hits: 16, double: 1, triple: 1, hr: 0, bb: 1,  hbp: 1 },
  { name: "윤동희",   ab: 75,  hits: 14, double: 4, triple: 0, hr: 3, bb: 6,  hbp: 1 },
  { name: "레이예스", ab: 113, hits: 39, double: 8, triple: 0, hr: 5, bb: 11, hbp: 2 },
  { name: "유강남",   ab: 62,  hits: 16, double: 4, triple: 0, hr: 2, bb: 1,  hbp: 0 },
  { name: "김민성",   ab: 14,  hits: 1,  double: 0, triple: 0, hr: 1, bb: 3,  hbp: 0 },
  { name: "박승욱",   ab: 32,  hits: 11, double: 2, triple: 0, hr: 1, bb: 1,  hbp: 0 },
  { name: "전민재",   ab: 77,  hits: 18, double: 3, triple: 0, hr: 0, bb: 7,  hbp: 0 },
  { name: "손성빈",   ab: 48,  hits: 10, double: 2, triple: 0, hr: 1, bb: 6,  hbp: 0 },
  { name: "한태양",   ab: 74,  hits: 18, double: 3, triple: 0, hr: 0, bb: 7,  hbp: 1 },
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

  // 팀 이름 state로 관리
  const [teamAName, setTeamAName] = useState(
    fromMyTeam?.teamName ?? urlTeamA ?? 'SSG 랜더스'
  );
  const [teamBName, setTeamBName] = useState(
    fromMyTeam?.opponent ?? urlTeamB ?? '롯데'
  );

  const [teamALineup, setTeamALineup] = useState(fromMyTeam?.lineup ?? DEFAULT_LINEUP_A);
  const [teamBLineup, setTeamBLineup] = useState(DEFAULT_LINEUP_B);
  const [lineupLoading, setLineupLoading] = useState(false);

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

  const eventsRef   = useRef<FlatEvent[]>([]);
  const idxRef      = useRef(0);
  const pausedRef   = useRef(false);
  const speedRef    = useRef(1);
  const timerRef    = useRef<ReturnType<typeof setTimeout> | null>(null);
  const bannerTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const bottomRef   = useRef<HTMLDivElement>(null);

  // URL 파라미터로 왔을 때 팀 이름 + 라인업 로드
  useEffect(() => {
    if (!urlTeamA && !urlTeamB) return;

    if (urlTeamA) setTeamAName(urlTeamA);
    if (urlTeamB) setTeamBName(urlTeamB);

    setLineupLoading(true);
    const promises: Promise<void>[] = [];

    if (urlTeamA && !fromMyTeam) {
      promises.push(
        fetchTeamLineup(urlTeamA)
          .then(setTeamALineup)
          .catch(() => setTeamALineup(DEFAULT_LINEUP_A))
      );
    }

    if (urlTeamB) {
      promises.push(
        fetchTeamLineup(urlTeamB)
          .then(setTeamBLineup)
          .catch(() => setTeamBLineup(DEFAULT_LINEUP_B))
      );
    }

    Promise.all(promises).finally(() => setLineupLoading(false));
  }, [urlTeamA, urlTeamB]);

  // MyTeam에서 왔을 때 상대팀 라인업 로드
  useEffect(() => {
    if (urlTeamA || urlTeamB) return;
    fetchTeamLineup(fromMyTeam?.opponent ?? '롯데')
      .then(setTeamBLineup)
      .catch(() => setTeamBLineup(DEFAULT_LINEUP_B));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
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
    setLoading(true);
    setError(null);
    setGameLog(null);
    setDisplayed([]);
    try {
      const res = await simulateGame({
        team_a_name:   teamAName,
        team_a_lineup: teamALineup,
        team_b_name:   teamBName,
        team_b_lineup: teamBLineup,
      });
      setGameLog(res.game_log);
      startAnimation(res.game_log.innings);
      const scoreA = res.game_log.final_score[0];
      const scoreB = res.game_log.final_score[1];
      const result = scoreA > scoreB ? '승' : scoreA < scoreB ? '패' : '무';
      await saveRecord({
        team_name:     teamAName,
        opponent_name: teamBName,
        result,
        my_score:  scoreA,
        opp_score: scoreB,
      });
    } catch {
      setError('시뮬레이션 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  }

  async function handleMultiStats() {
    setLoading(true);
    try {
      const res = await simulateMulti({
        team_a_name:   teamAName,
        team_a_lineup: teamALineup,
        team_b_name:   teamBName,
        team_b_lineup: teamBLineup,
        n_games: 1000,
      });
      setMultiStats(res);
      setShowStats(true);
    } catch {
      setError('통계 계산 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    if (timerRef.current) clearTimeout(timerRef.current);
    setGameLog(null);
    setDisplayed([]);
    setCurrentPA(null);
    setBanner(null);
    setMultiStats(null);
    setError(null);
    setDone(false);
    setPaused(false);
  }

  function handleToggle() {
    if (done) {
      startAnimation(gameLog!.innings);
    } else if (paused) {
      pausedRef.current = false;
      setPaused(false);
      timerRef.current = setTimeout(tick, SPEEDS[speedRef.current]);
    } else {
      pausedRef.current = true;
      setPaused(true);
      if (timerRef.current) clearTimeout(timerRef.current);
    }
  }

  function handleSpeed(s: number) {
    speedRef.current = s;
    setSpeed(s);
  }

  const scoreboard = gameLog ? {
    away: {
      team:    teamAName,
      innings: gameLog.innings.filter(i => i.half === '초').map(i => i.runs),
      total:   gameLog.final_score[0],
    },
    home: {
      team:    teamBName,
      innings: gameLog.innings.filter(i => i.half === '말').map(i => i.runs),
      total:   gameLog.final_score[1],
    },
  } : null;

  return (
    <div className="min-h-screen bg-gray-900">
      <style>{`
        @keyframes bannerIn { from { opacity:0; transform:scale(0.8); } to { opacity:1; transform:scale(1); } }
        @keyframes fadeSlideIn { from { opacity:0; transform:translateY(-6px); } to { opacity:1; transform:translateY(0); } }
        .pa-row { animation: fadeSlideIn 0.3s ease forwards; opacity:0; }
      `}</style>

      {banner && bannerCfg[banner.event] && (() => {
        const cfg = bannerCfg[banner.event];
        return (
          <div style={{ position:'fixed', top:0, left:0, right:0, bottom:0, display:'flex', alignItems:'center', justifyContent:'center', zIndex:9999, pointerEvents:'none' }}>
            <div style={{ background:cfg.bg, border:cfg.border, borderRadius:'1rem', padding:'1.25rem 2.5rem', textAlign:'center', minWidth:'220px', animation:'bannerIn 0.35s cubic-bezier(0.34,1.56,0.64,1) forwards' }}>
              <div style={{ color:cfg.pc, fontSize:'1.1rem', fontWeight:700, marginBottom:'0.25rem' }}>{banner.batter_name}</div>
              <div style={{ color:cfg.ec, fontSize:cfg.fs, fontWeight:900 }}>{eventToKorean[banner.event]}!</div>
            </div>
          </div>
        );
      })()}

      <div className="bg-gradient-to-r from-gray-800 to-gray-900 border-b border-gray-700 px-10 py-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-white text-3xl font-black">경기 시뮬레이터</h1>
            <p className="text-gray-400 text-sm mt-1">마르코프 체인 기반 경기 예측</p>
          </div>
          <div className="flex items-center gap-6">
            <div className="text-right">
              <p className="text-white font-bold">{teamAName}</p>
              <p className="text-gray-400 text-xs">원정</p>
            </div>
            <div className="bg-gray-700 rounded-full px-4 py-2">
              <span className="text-orange-400 font-black text-xl">{gameLog ? gameLog.final_score[0] : '-'}</span>
              <span className="text-gray-500 mx-2">:</span>
              <span className="text-orange-400 font-black text-xl">{gameLog ? gameLog.final_score[1] : '-'}</span>
            </div>
            <div className="text-left">
              <p className="text-white font-bold">{teamBName}</p>
              <p className="text-gray-400 text-xs">홈</p>
            </div>
          </div>
        </div>

        {lineupLoading && (
          <p className="text-gray-500 text-xs mt-3 animate-pulse">⚾ 라인업 불러오는 중...</p>
        )}

        {!lineupLoading && (urlTeamA || fromMyTeam) && (
          <div className="mt-4 flex flex-wrap gap-2">
            {teamALineup.map((p, i) => (
              <span key={i} className="text-xs bg-gray-700 text-gray-300 px-3 py-1 rounded-full">
                {i + 1}. {p.name}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="px-10 py-8 space-y-6">
        {error && (
          <div className="bg-red-900/30 border border-red-700 rounded-xl px-6 py-4 text-red-400">{error}</div>
        )}

        {!gameLog && !loading && !lineupLoading && (
          <div className="flex justify-center py-10">
            <button onClick={handleStart} className="bg-orange-500 hover:bg-orange-600 text-white font-black text-lg px-12 py-4 rounded-xl transition-colors">
              ▶ 경기 시작
            </button>
          </div>
        )}

        {(loading || lineupLoading) && (
          <div className="flex justify-center py-10">
            <p className="text-gray-400 text-lg animate-pulse">
              {lineupLoading ? '⚾ 라인업 로딩 중...' : '⚾ 시뮬레이션 중...'}
            </p>
          </div>
        )}

        {gameLog && scoreboard && (
          <>
            <Scoreboard away={scoreboard.away} home={scoreboard.home} />

            {currentPA && (
              <div className="bg-gray-800 rounded-xl px-6 py-3 flex items-center gap-6 border border-gray-700">
                <div>
                  <p className="text-gray-500 text-xs mb-1">아웃</p>
                  <div className="flex gap-1.5">
                    {[0, 1].map((dotIdx) => (
                      <div key={dotIdx} style={{
                        width:'12px', height:'12px', borderRadius:'50%',
                        border:`2px solid ${dotIdx < (currentPA.outs_after >= 3 ? 0 : currentPA.outs_after) ? '#f97316' : '#4b5563'}`,
                        background: dotIdx < (currentPA.outs_after >= 3 ? 0 : currentPA.outs_after) ? '#f97316' : 'transparent',
                      }} />
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-gray-500 text-xs mb-1">주자</p>
                  <p className="text-white text-sm font-bold">{currentPA.bases_after}</p>
                </div>
                <div className="ml-auto">
                  <p className="text-gray-500 text-xs mb-1">현재 타자</p>
                  <p className="text-white text-sm font-bold">{currentPA.batter_name}</p>
                </div>
              </div>
            )}

            <div className="bg-gray-800 rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <p className="text-gray-400 text-xs uppercase tracking-widest">경기 로그</p>
                <div className="flex items-center gap-2">
                  <div className="flex gap-1">
                    {['느리게', '보통', '빠르게'].map((label, sIdx) => (
                      <button key={sIdx} onClick={() => handleSpeed(sIdx)} className="text-xs px-2 py-1 rounded"
                        style={{ background: speed === sIdx ? '#f97316' : '#374151', color: speed === sIdx ? '#fff' : '#9ca3af' }}>
                        {label}
                      </button>
                    ))}
                  </div>
                  <button onClick={handleToggle} className="text-xs px-3 py-1 rounded"
                    style={{ background:'#374151', color:'#d1d5db' }}>
                    {done ? '처음부터' : paused ? '재생' : '일시정지'}
                  </button>
                </div>
              </div>

              <div className="space-y-1 max-h-96 overflow-y-auto pr-2">
                {displayed.map((ev, evIdx) => {
                  const evKey = `ev-${evIdx}`;
                  if (ev.type === 'inning_header') {
                    return (
                      <div key={evKey} className="flex items-center gap-2 py-2 mt-2 border-b border-gray-700">
                        <span className="text-xs font-bold px-2 py-0.5 rounded"
                          style={{ background: ev.half === '초' ? '#1e3a5f' : '#3b1f1f', color: ev.half === '초' ? '#60a5fa' : '#f87171' }}>
                          {ev.inning}회{ev.half}
                        </span>
                        <span className="text-gray-500 text-xs">{ev.teamName}</span>
                      </div>
                    );
                  }
                  if (!ev.pa) return null;
                  const pa    = ev.pa;
                  const badge = eventBadgeStyle[pa.event] ?? { background:'#374151', color:'#9ca3af' };
                  return (
                    <div key={evKey} className="pa-row flex items-center gap-3 text-sm py-1.5 border-b border-gray-700/50 last:border-0">
                      <span className="text-gray-400 w-16 shrink-0 text-xs">{pa.batter_name}</span>
                      <span className="text-xs font-bold px-2 py-0.5 rounded shrink-0"
                        style={{ background:badge.background, color:badge.color }}>
                        {eventToKorean[pa.event] ?? pa.event}
                      </span>
                      <span className="text-gray-600 text-xs flex-1">{pa.outs_after}아웃 · {pa.bases_after}</span>
                      {pa.runs_scored > 0 && (
                        <span style={{ color:'#f97316', fontSize:'0.75rem', fontWeight:700, marginLeft:'auto' }}>
                          +{pa.runs_scored}점 ★
                        </span>
                      )}
                    </div>
                  );
                })}
                <div ref={bottomRef} />
              </div>
            </div>

            <div className="flex gap-4">
              <button onClick={handleReset} className="bg-gray-700 hover:bg-gray-600 text-white font-bold px-8 py-3 rounded-xl transition-colors">
                🔄 다시 시뮬
              </button>
              <button onClick={handleMultiStats} disabled={loading} className="bg-blue-600 hover:bg-blue-700 text-white font-bold px-8 py-3 rounded-xl transition-colors disabled:opacity-50">
                📊 100경기 통계
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