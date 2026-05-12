import { useState, useEffect, useRef } from 'react';
import type { InningLog, PlateAppearance } from '../../api/simulatorApi';

interface Props {
  gameLog: InningLog[];
}

interface FlatEvent {
  type: 'inning_header' | 'pa';
  inning: number;
  half: string;
  teamName?: string;
  pa?: PlateAppearance;
}

const eventToKorean: Record<string, string> = {
  '1B': '단타', '2B': '2루타', '3B': '3루타',
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

const bannerStyle: Record<string, {
  background: string; border: string;
  playerColor: string; eventColor: string; fontSize: string;
}> = {
  '1B': { background: '#052e16', border: '2px solid #16a34a', playerColor: '#86efac', eventColor: '#4ade80',  fontSize: '1.5rem'   },
  '2B': { background: '#052e16', border: '2px solid #22c55e', playerColor: '#4ade80', eventColor: '#22c55e',  fontSize: '1.875rem' },
  '3B': { background: '#14532d', border: '2px solid #4ade80', playerColor: '#bbf7d0', eventColor: '#86efac',  fontSize: '2rem'     },
  'HR': { background: '#431407', border: '2px solid #f97316', playerColor: '#fdba74', eventColor: '#f97316',  fontSize: '2.5rem'   },
  'BB': { background: '#0c1a3a', border: '2px solid #3b82f6', playerColor: '#93c5fd', eventColor: '#60a5fa',  fontSize: '1.5rem'   },
  'K':  { background: '#1e1b4b', border: '2px solid #818cf8', playerColor: '#c7d2fe', eventColor: '#a5b4fc',  fontSize: '1.5rem'   },
};

const SPEEDS = [1000, 500, 150];

function buildEvents(gameLog: InningLog[]): FlatEvent[] {
  const events: FlatEvent[] = [];
  const innings: { top?: InningLog; bottom?: InningLog }[] = [];
  gameLog.forEach((log) => {
    const idx = log.inning - 1;
    if (!innings[idx]) innings[idx] = {};
    if (log.half === '초') innings[idx].top = log;
    else innings[idx].bottom = log;
  });
  innings.forEach((inning, i) => {
    (['top', 'bottom'] as const).forEach((side) => {
      const log = side === 'top' ? inning.top : inning.bottom;
      if (!log) return;
      events.push({ type: 'inning_header', inning: i + 1, half: log.half, teamName: log.team_name });
      log.plate_appearances.forEach((pa) => {
        events.push({ type: 'pa', inning: i + 1, half: log.half, pa });
      });
    });
  });
  return events;
}

export default function GameLogView({ gameLog }: Props) {
  const [displayed, setDisplayed]   = useState<FlatEvent[]>([]);
  const [speed, setSpeed]           = useState(1);
  const [paused, setPaused]         = useState(false);
  const [done, setDone]             = useState(false);
  const [banner, setBanner]         = useState<PlateAppearance | null>(null);
  const [currentPA, setCurrentPA]   = useState<PlateAppearance | null>(null);
  const bottomRef                   = useRef<HTMLDivElement>(null);

  // 모든 상태를 ref로 관리해서 클로저 문제 완전 차단
  const eventsRef   = useRef<FlatEvent[]>([]);
  const idxRef      = useRef(0);
  const pausedRef   = useRef(false);
  const speedRef    = useRef(1);
  const timerRef    = useRef<ReturnType<typeof setTimeout> | null>(null);
  const bannerRef   = useRef<ReturnType<typeof setTimeout> | null>(null);

  function scheduleNext() {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      if (pausedRef.current) return;
      const idx = idxRef.current;
      const events = eventsRef.current;
      if (idx >= events.length) {
        setDone(true);
        return;
      }
      const ev = events[idx];
      idxRef.current = idx + 1;
      setDisplayed((prev) => [...prev, ev]);
      if (ev.type === 'pa' && ev.pa) {
        setCurrentPA(ev.pa);
        if (bannerStyle[ev.pa.event]) {
          setBanner(ev.pa);
          if (bannerRef.current) clearTimeout(bannerRef.current);
          bannerRef.current = setTimeout(() => setBanner(null), 2000);
        }
      }
      scheduleNext();
    }, SPEEDS[speedRef.current]);
  }

  // gameLog 바뀌면 전체 리셋 후 시작
  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (bannerRef.current) clearTimeout(bannerRef.current);
    eventsRef.current = buildEvents(gameLog);
    idxRef.current = 0;
    pausedRef.current = false;
    setDisplayed([]);
    setCurrentPA(null);
    setBanner(null);
    setPaused(false);
    setDone(false);
    scheduleNext();
  }, [gameLog]);

  // 자동 스크롤
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [displayed]);

  function handleToggle() {
    if (done) {
      // 처음부터
      if (timerRef.current) clearTimeout(timerRef.current);
      if (bannerRef.current) clearTimeout(bannerRef.current);
      eventsRef.current = buildEvents(gameLog);
      idxRef.current = 0;
      pausedRef.current = false;
      setDisplayed([]);
      setCurrentPA(null);
      setBanner(null);
      setPaused(false);
      setDone(false);
      scheduleNext();
    } else if (paused) {
      pausedRef.current = false;
      setPaused(false);
      scheduleNext();
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

  return (
    <div className="relative">
      <style>{`
        @keyframes bannerIn {
          from { opacity: 0; transform: scale(0.8); }
          to   { opacity: 1; transform: scale(1); }
        }
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(-6px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .pa-row { animation: fadeSlideIn 0.3s ease forwards; opacity: 0; }
      `}</style>

      {/* 이벤트 배너 */}
      {banner && bannerStyle[banner.event] && (() => {
        const cfg = bannerStyle[banner.event];
        return (
          <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 9999, pointerEvents: 'none',
          }}>
            <div style={{
              background: cfg.background,
              border: cfg.border,
              borderRadius: '1rem',
              padding: '1.25rem 2.5rem',
              textAlign: 'center',
              minWidth: '220px',
              animation: 'bannerIn 0.35s cubic-bezier(0.34,1.56,0.64,1) forwards',
            }}>
              <div style={{ color: cfg.playerColor, fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.25rem' }}>
                {banner.batter_name}
              </div>
              <div style={{ color: cfg.eventColor, fontSize: cfg.fontSize, fontWeight: 900 }}>
                {eventToKorean[banner.event]}!
              </div>
            </div>
          </div>
        );
      })()}

      {/* 현황 패널 */}
      {currentPA && (
        <div className="bg-gray-800 rounded-xl px-6 py-3 mb-4 flex items-center gap-6 border border-gray-700">
          <div>
            <p className="text-gray-500 text-xs mb-1">아웃</p>
            <div className="flex gap-1.5">
              {[0, 1].map((dotIdx) => (
                <div key={dotIdx} style={{
                  width: '12px', height: '12px', borderRadius: '50%',
                  border: `2px solid ${dotIdx < (currentPA.outs_after >= 3 ? 0 : currentPA.outs_after) ? '#f97316' : '#4b5563'}`,
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

      {/* 경기 로그 */}
      <div className="bg-gray-800 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <p className="text-gray-400 text-xs uppercase tracking-widest">경기 로그</p>
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              {['느리게', '보통', '빠르게'].map((label, sIdx) => (
                <button
                  key={sIdx}
                  onClick={() => handleSpeed(sIdx)}
                  className="text-xs px-2 py-1 rounded transition-colors"
                  style={{
                    background: speed === sIdx ? '#f97316' : '#374151',
                    color: speed === sIdx ? '#fff' : '#9ca3af',
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            <button
              onClick={handleToggle}
              className="text-xs px-3 py-1 rounded transition-colors"
              style={{ background: '#374151', color: '#d1d5db' }}
            >
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
                  <span className="text-xs font-bold px-2 py-0.5 rounded" style={{
                    background: ev.half === '초' ? '#1e3a5f' : '#3b1f1f',
                    color: ev.half === '초' ? '#60a5fa' : '#f87171',
                  }}>
                    {ev.inning}회{ev.half}
                  </span>
                  <span className="text-gray-500 text-xs">{ev.teamName}</span>
                </div>
              );
            }
            if (!ev.pa) return null;
            const pa = ev.pa;
            const badge = eventBadgeStyle[pa.event] ?? { background: '#374151', color: '#9ca3af' };
            return (
              <div key={evKey} className="pa-row flex items-center gap-3 text-sm py-1.5 border-b border-gray-700/50 last:border-0">
                <span className="text-gray-400 w-16 shrink-0 text-xs">{pa.batter_name}</span>
                <span className="text-xs font-bold px-2 py-0.5 rounded shrink-0"
                  style={{ background: badge.background, color: badge.color }}>
                  {eventToKorean[pa.event] ?? pa.event}
                </span>
                <span className="text-gray-600 text-xs flex-1">
                  {pa.outs_after}아웃 · {pa.bases_after}
                </span>
                {pa.runs_scored > 0 && (
                  <span style={{ color: '#f97316', fontSize: '0.75rem', fontWeight: 700, marginLeft: 'auto' }}>
                    +{pa.runs_scored}점 ★
                  </span>
                )}
              </div>
            );
          })}
          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  );
}