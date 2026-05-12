import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  arrayMove,
} from '@dnd-kit/sortable';
import LineupCard from '../components/lineup/LineupCard';
import type { Player } from '../data/mockPlayers';
import { fetchPlayers } from '../api/playerApi';
import type { PlayerDB } from '../api/playerApi';

function dbToPlayer(p: PlayerDB): Player {
  return {
    id: Number(p.player_id),
    name: p.player_name,
    team: p.team_name,
    position: p.position ?? '-',
    stats: [
      { label: 'wOBA', value: p.woba    ?? 0, percentile: 0, unit: 'wOBA' },
      { label: 'OPS',  value: p.ops     ?? 0, percentile: 0, unit: 'OPS'  },
      { label: 'HR',   value: p.hr      ?? 0, percentile: 0, unit: 'HR'   },
      { label: 'BB%',  value: p.bb_rate ?? 0, percentile: 0, unit: '%'    },
      { label: 'K%',   value: p.k_rate  ?? 0, percentile: 0, unit: '%'    },
    ],
    radar: [
      { stat: '컨택',   value: Math.min(99, Math.round((p.avg     ?? 0) * 300)) },
      { stat: '파워',   value: Math.min(99, Math.round((p.iso     ?? 0) * 400)) },
      { stat: '선구안', value: Math.min(99, Math.round((p.bb_rate ?? 0) * 5))   },
      { stat: '스피드', value: Math.min(99, Math.round((p.spd     ?? 0) * 10))  },
      { stat: '수비',   value: 60 },
      { stat: '출루',   value: Math.min(99, Math.round((p.obp     ?? 0) * 200)) },
    ],
    // 시뮬레이터 연동용 원본 타격 기록
    raw: {
      ab:     p.ab          ?? 300,
      hits:   p.h           ?? 80,
      double: p.double_hit  ?? 15,
      triple: p.triple_hit  ?? 2,
      hr:     p.hr          ?? 5,
      bb:     p.bb          ?? 30,
      hbp:    p.hbp         ?? 3,
    },
  };
}

export interface GameRecord {
  date: string;
  opponent: string;
  result: '승' | '패' | '무';
  myScore: number;
  oppScore: number;
}

const MOCK_RECORDS: GameRecord[] = [
  { date: '2025.04.21', opponent: 'SSG 랜더스',  result: '승', myScore: 7, oppScore: 3 },
  { date: '2025.04.19', opponent: '두산 베어스', result: '패', myScore: 2, oppScore: 5 },
  { date: '2025.04.17', opponent: 'NC 다이노스',  result: '승', myScore: 4, oppScore: 2 },
];

export default function MyTeamPage() {
  const navigate = useNavigate();

  const [query, setQuery]               = useState('');
  const [results, setResults]           = useState<Player[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [lineup, setLineup]             = useState<(Player | null)[]>(Array(9).fill(null));
  const [records]                       = useState<GameRecord[]>(MOCK_RECORDS);

  const searchRef = useRef<HTMLDivElement>(null);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      setShowDropdown(false);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const data = await fetchPlayers(query);
        setResults(data.map(dbToPlayer));
        setShowDropdown(true);
      } catch {
        setResults([]);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  function handleSelect(player: Player) {
    if (lineup.some((p) => p?.id === player.id)) {
      alert('이미 추가된 선수입니다.');
      return;
    }
    const emptyIdx = lineup.findIndex((p) => p === null);
    if (emptyIdx === -1) {
      alert('타순이 모두 찼습니다. 선수를 먼저 제거해주세요.');
      return;
    }
    const next = [...lineup];
    next[emptyIdx] = player;
    setLineup(next);
    setQuery('');
    setShowDropdown(false);
  }

  function handleRemove(idx: number) {
    const next = [...lineup];
    next[idx] = null;
    setLineup(next);
  }

  function handleDragEnd(event: any) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    setLineup((prev) => arrayMove(prev, Number(active.id), Number(over.id)));
  }

  // 시뮬레이터로 이동 — raw 타격 기록 전달
  function handleSimulate() {
    if (filledCount !== 9) return;
    const lineupData = filledPlayers.map((p) => ({
      name:   p.name,
      ab:     p.raw?.ab     ?? 300,
      hits:   p.raw?.hits   ?? 80,
      double: p.raw?.double ?? 15,
      triple: p.raw?.triple ?? 2,
      hr:     p.raw?.hr     ?? 5,
      bb:     p.raw?.bb     ?? 30,
      hbp:    p.raw?.hbp    ?? 3,
    }));
    navigate('/simulator', {
      state: {
        lineup:   lineupData,
        teamName: '나만의 팀',
      },
    });
  }

  const filledPlayers = lineup.filter((p): p is Player => p !== null);
  const filledCount   = filledPlayers.length;

  const avgOPS = filledCount > 0
    ? (filledPlayers.reduce((sum, p) => {
        const ops = p.stats.find((s) => s.label === 'OPS');
        return sum + (ops?.value ?? 0);
      }, 0) / filledCount).toFixed(3)
    : '-';

  const wins   = records.filter((r) => r.result === '승').length;
  const losses = records.filter((r) => r.result === '패').length;

  return (
    <div className="min-h-screen bg-gray-900">

      {/* 헤더 */}
      <div className="bg-gradient-to-r from-gray-800 to-gray-900 border-b border-gray-700 px-10 py-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-white text-3xl font-black">나만의 팀 만들기</h1>
            <p className="text-gray-400 text-sm mt-1">
              KBO 선수로 드림팀을 구성하고 시뮬레이션을 돌려보세요
            </p>
          </div>
          <button
            onClick={handleSimulate}
            className={`font-black px-8 py-3 rounded-xl transition-colors ${
              filledCount === 9
                ? 'bg-orange-500 hover:bg-orange-600 text-white'
                : 'bg-gray-700 text-gray-500 cursor-not-allowed'
            }`}
            disabled={filledCount !== 9}
          >
            ▶ 이 타순으로 시뮬레이션
          </button>
        </div>
      </div>

      {/* 본문 */}
      <div className="px-10 py-8 flex gap-8">

        {/* 왼쪽 */}
        <div className="flex-1 space-y-6">

          {/* 선수 검색 */}
          <div>
            <p className="text-gray-400 text-xs mb-3 uppercase tracking-widest">선수 검색</p>
            <div ref={searchRef} className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm z-10">🔍</span>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onFocus={() => query && setShowDropdown(true)}
                placeholder="선수 이름 또는 팀명으로 검색..."
                className="w-full bg-gray-800 text-white placeholder-gray-500 rounded-lg pl-9 pr-4 py-2.5 text-sm border border-gray-700 focus:outline-none focus:border-orange-400 transition-colors"
              />

              {showDropdown && results.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-gray-800 border border-gray-700 rounded-xl shadow-xl overflow-hidden z-50 max-h-64 overflow-y-auto">
                  {results.map((player) => {
                    const alreadyAdded = lineup.some((p) => p?.id === player.id);
                    const ops = player.stats.find((s) => s.label === 'OPS');
                    return (
                      <button
                        key={player.id}
                        onClick={() => !alreadyAdded && handleSelect(player)}
                        disabled={alreadyAdded}
                        className={`w-full flex items-center justify-between px-4 py-3 text-left border-b border-gray-700 last:border-0 transition-colors ${
                          alreadyAdded
                            ? 'opacity-40 cursor-not-allowed'
                            : 'hover:bg-gray-700 cursor-pointer'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <span className="text-xs font-bold text-orange-400 bg-orange-400/10 px-2 py-0.5 rounded">
                            {player.position}
                          </span>
                          <div>
                            <div className="text-white font-semibold text-sm">
                              {player.name}
                              {alreadyAdded && <span className="ml-2 text-xs text-gray-500">추가됨</span>}
                            </div>
                            <div className="text-gray-400 text-xs">{player.team}</div>
                          </div>
                        </div>
                        {ops && (
                          <div className="text-xs text-right">
                            <div className="text-gray-500">OPS</div>
                            <div className="text-orange-400 font-bold">{ops.value.toFixed(3)}</div>
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}

              {showDropdown && results.length === 0 && query.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-gray-500 text-sm z-50">
                  검색 결과가 없습니다.
                </div>
              )}
            </div>

            <div className="mt-3 flex items-center gap-3">
              <div className="flex-1 h-1 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-orange-500 rounded-full transition-all duration-300"
                  style={{ width: `${(filledCount / 9) * 100}%` }}
                />
              </div>
              <span className="text-xs text-gray-400 flex-shrink-0">
                <span className="text-orange-400 font-bold">{filledCount}</span> / 9명
              </span>
            </div>
          </div>

          {/* 타순 배치 */}
          <div>
            <p className="text-gray-400 text-xs mb-3 uppercase tracking-widest">타순 배치</p>
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext
                items={lineup.map((_, i) => i)}
                strategy={verticalListSortingStrategy}
              >
                <div className="space-y-2">
                  {lineup.map((player, idx) =>
                    player ? (
                      <div key={idx} className="flex items-center gap-3">
                        <div className="w-7 h-7 rounded-full bg-orange-500 flex items-center justify-center flex-shrink-0">
                          <span className="text-white font-bold text-xs">{idx + 1}</span>
                        </div>
                        <div className="flex-1">
                          <LineupCard player={player} order={idx + 1} />
                        </div>
                        <button
                          onClick={() => handleRemove(idx)}
                          className="text-gray-600 hover:text-red-400 transition-colors text-lg leading-none"
                        >
                          ✕
                        </button>
                      </div>
                    ) : (
                      <div key={idx} className="flex items-center gap-3">
                        <div className="w-7 h-7 rounded-full bg-gray-700 flex items-center justify-center flex-shrink-0">
                          <span className="text-gray-500 font-bold text-xs">{idx + 1}</span>
                        </div>
                        <div className="flex-1 h-12 bg-gray-800 border border-dashed border-gray-700 rounded-xl flex items-center px-4">
                          <span className="text-gray-600 text-sm">{idx + 1}번 타자를 검색해서 추가하세요</span>
                        </div>
                      </div>
                    )
                  )}
                </div>
              </SortableContext>
            </DndContext>
          </div>
        </div>

        {/* 오른쪽 */}
        <div className="w-72 space-y-6">

          {/* 팀 스탯 요약 */}
          <div>
            <p className="text-gray-400 text-xs mb-3 uppercase tracking-widest">팀 스탯 요약</p>
            <div className="bg-gray-800 rounded-xl p-5 space-y-3">
              <div className="flex justify-between items-center border-b border-gray-700 pb-3">
                <span className="text-gray-400 text-sm">선수 구성</span>
                <span className="text-white font-bold">{filledCount} / 9</span>
              </div>
              <div className="flex justify-between items-center border-b border-gray-700 pb-3">
                <span className="text-gray-400 text-sm">평균 OPS</span>
                <span className="text-orange-400 font-bold">{avgOPS}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400 text-sm">전적</span>
                <span className="text-white font-bold">
                  <span className="text-blue-400">{wins}승</span>
                  {' / '}
                  <span className="text-red-400">{losses}패</span>
                </span>
              </div>
            </div>
          </div>

          {/* 타순 요약 테이블 */}
          <div>
            <p className="text-gray-400 text-xs mb-3 uppercase tracking-widest">현재 타순 요약</p>
            <div className="bg-gray-800 rounded-xl p-5">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-400 border-b border-gray-700">
                    <th className="text-left py-2 w-8">순번</th>
                    <th className="text-left py-2 w-12">포지션</th>
                    <th className="text-left py-2">선수명</th>
                  </tr>
                </thead>
                <tbody>
                  {lineup.map((player, idx) => (
                    <tr key={idx} className="border-b border-gray-700 last:border-0">
                      <td className="py-2 text-orange-400 font-bold">{idx + 1}</td>
                      <td className="py-2 text-gray-400 text-xs">{player?.position ?? '-'}</td>
                      <td className="py-2 text-white">{player?.name ?? <span className="text-gray-600">-</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* 전적 기록 */}
          <div>
            <p className="text-gray-400 text-xs mb-3 uppercase tracking-widest">전적 기록</p>
            <div className="space-y-2">
              {records.length === 0 ? (
                <div className="bg-gray-800 rounded-xl p-5 text-center text-gray-600 text-sm">
                  아직 경기 기록이 없습니다
                </div>
              ) : (
                records.map((rec, i) => (
                  <div key={i} className="bg-gray-800 rounded-xl px-4 py-3 flex items-center justify-between">
                    <div>
                      <div className="text-white text-sm font-semibold">{rec.opponent}</div>
                      <div className="text-gray-500 text-xs mt-0.5">{rec.date}</div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-gray-300 text-sm font-bold">
                        {rec.myScore} : {rec.oppScore}
                      </span>
                      <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                        rec.result === '승' ? 'bg-blue-500/20 text-blue-400'
                        : rec.result === '패' ? 'bg-red-500/20 text-red-400'
                        : 'bg-gray-500/20 text-gray-400'
                      }`}>
                        {rec.result}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}