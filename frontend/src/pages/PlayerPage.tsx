import { useState, useEffect } from 'react';
import { useSearchParams, useParams } from 'react-router-dom';
import PercentileBar from '../components/player/PercentileBar';
import PlayerRadarChart from '../components/player/RadarChart';
import InsightBox from '../components/player/InsightBox';
import PlayerCard from '../components/player/PlayerCard';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorBox from '../components/common/ErrorBox';
import { fetchPlayers, fetchPlayerById } from '../api/playerApi';
import type { PlayerDB } from '../api/playerApi';
import type { Player } from '../data/mockPlayers';

function dbToPlayer(p: PlayerDB): Player {
  return {
    id: Number(p.player_id),
    name: p.player_name,
    team: p.team_name,
    position: p.position ?? '-',
    stats: [
      { label: 'wOBA', value: Number(p.woba    ?? 0), percentile: 0, unit: 'wOBA' },
      { label: 'OPS',  value: Number(p.ops     ?? 0), percentile: 0, unit: 'OPS'  },
      { label: 'HR',   value: Number(p.hr      ?? 0), percentile: 0, unit: 'HR'   },
      { label: 'BB%',  value: Number(p.bb_rate ?? 0), percentile: 0, unit: '%'    },
      { label: 'K%',   value: Number(p.k_rate  ?? 0), percentile: 0, unit: '%'    },
    ],
    radar: [
      { stat: '컨택',   value: Math.min(99, Math.round(Number(p.avg     ?? 0) * 300)) },
      { stat: '파워',   value: Math.min(99, Math.round(Number(p.iso     ?? 0) * 400)) },
      { stat: '선구안', value: Math.min(99, Math.round(Number(p.bb_rate ?? 0) * 5))   },
      { stat: '스피드', value: Math.min(99, Math.round(Number(p.spd     ?? 0) * 10))  },
      { stat: '수비',   value: 60 },
      { stat: '출루',   value: Math.min(99, Math.round(Number(p.obp     ?? 0) * 200)) },
    ],
  };
}

function calcPercentile(label: string, value: number): number {
  const benchmarks: Record<string, { min: number; max: number }> = {
    'wOBA': { min: 0.250, max: 0.450 },
    'OPS':  { min: 0.550, max: 1.000 },
    'HR':   { min: 0,     max: 40    },
    'BB%':  { min: 3,     max: 20    },
    'K%':   { min: 5,     max: 35    },
  };
  const b = benchmarks[label];
  if (!b) return 50;
  const pct = ((value - b.min) / (b.max - b.min)) * 100;
  return label === 'K%'
    ? Math.min(99, Math.max(1, Math.round(100 - pct)))
    : Math.min(99, Math.max(1, Math.round(pct)));
}

export default function PlayerPage() {
  const [player, setPlayer]           = useState<Player | null>(null);
  const [players, setPlayers]         = useState<Player[]>([]);
  const [loading, setLoading]         = useState(false);
  const [listLoading, setListLoading] = useState(false);
  const [error, setError]             = useState(false);
  const [query, setQuery]             = useState('');
  const [showList, setShowList]       = useState(true);
  const [searchParams]                = useSearchParams();
  const { playerId }                  = useParams<{ playerId: string }>();

  // URL playerId 파라미터로 바로 선수 로드
  useEffect(() => {
    if (!playerId) return;
    setShowList(false);
    setLoading(true);
    setError(false);
    fetchPlayerById(playerId)
      .then((data) => {
        const converted = dbToPlayer(data);
        converted.stats = converted.stats.map((s) => ({
          ...s,
          percentile: calcPercentile(s.label, s.value),
        }));
        setPlayer(converted);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [playerId]);

  // URL 검색 파라미터 반영
  useEffect(() => {
    if (playerId) return;
    const q = searchParams.get('search');
    if (q) {
      setQuery(q);
      setShowList(true);
      setPlayer(null);
    }
  }, [searchParams, playerId]);

  // 검색어 변경 시 API 호출
  useEffect(() => {
    if (!query.trim()) {
      setPlayers([]);
      return;
    }
    const timer = setTimeout(async () => {
      setListLoading(true);
      try {
        const data = await fetchPlayers(query);
        const converted = data.map((p) => {
          const player = dbToPlayer(p);
          player.stats = player.stats.map((s) => ({
            ...s,
            percentile: calcPercentile(s.label, s.value),
          }));
          return player;
        });
        setPlayers(converted);
      } catch {
        setPlayers([]);
      } finally {
        setListLoading(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  const selectPlayer = async (p: Player) => {
    setLoading(true);
    setError(false);
    setShowList(false);
    try {
      const data = await fetchPlayerById(String(p.id));
      const converted = dbToPlayer(data);
      converted.stats = converted.stats.map((s) => ({
        ...s,
        percentile: calcPercentile(s.label, s.value),
      }));
      setPlayer(converted);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    setPlayer(null);
    setShowList(true);
  };

  // 선수 목록 화면
  if (showList && !playerId) {
    return (
      <div className="min-h-screen bg-gray-900 px-10 py-8">
        <h1 className="text-white text-3xl font-black mb-2">선수 프로필</h1>
        <p className="text-gray-400 text-sm mb-6">선수 이름 또는 팀명으로 검색하세요</p>

        <div className="relative max-w-lg mb-6">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">🔍</span>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="선수 이름 또는 팀명 검색..."
            className="w-full bg-gray-800 text-white placeholder-gray-500 rounded-lg pl-9 pr-4 py-2.5 text-sm border border-gray-700 focus:outline-none focus:border-orange-400 transition-colors"
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-400 text-xs"
            >
              ✕
            </button>
          )}
        </div>

        <div className="max-w-lg space-y-2">
          {listLoading ? (
            <p className="text-gray-500 text-sm text-center py-10 animate-pulse">검색 중...</p>
          ) : query && players.length === 0 ? (
            <p className="text-gray-500 text-sm text-center py-10">검색 결과가 없습니다</p>
          ) : !query ? (
            <p className="text-gray-600 text-sm text-center py-10">선수 이름을 입력해서 검색하세요</p>
          ) : (
            players.map((p) => (
              <PlayerCard key={p.id} player={p} onClick={selectPlayer} />
            ))
          )}
        </div>
      </div>
    );
  }

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorBox onRetry={handleBack} />;
  if (!player) return null;

  return (
    <div className="min-h-screen bg-gray-900">
      <div className="bg-gradient-to-r from-gray-800 to-gray-900 border-b border-gray-700 px-10 py-8">
        <div className="flex items-center gap-6">
          <button
            onClick={handleBack}
            className="text-gray-400 hover:text-white text-sm transition-colors mr-2"
          >
            ← 목록
          </button>
          <div className="w-20 h-20 rounded-full bg-orange-500 flex items-center justify-center shrink-0">
            <span className="text-white text-xs font-black">{player.position}</span>
          </div>
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-white text-4xl font-black">{player.name}</h1>
              <span className="bg-orange-500 text-white text-xs font-bold px-2 py-1 rounded">
                {player.position}
              </span>
            </div>
            <p className="text-gray-400 text-sm">{player.team}</p>
          </div>
          <div className="ml-auto flex gap-8">
            {player.stats.slice(0, 3).map((s) => (
              <div key={s.label} className="text-center">
                <p className="text-orange-400 text-2xl font-black">{s.value}</p>
                <p className="text-gray-400 text-xs mt-1">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="px-10 py-8">
        <div className="flex gap-6 mb-6">
          <div className="bg-gray-800 rounded-xl p-6 w-96">
            <p className="text-gray-400 text-xs mb-4 uppercase tracking-widest">주요 지표</p>
            {player.stats.map((s) => (
              <PercentileBar
                key={s.label}
                label={s.label}
                value={s.value}
                percentile={s.percentile}
                unit={s.unit}
              />
            ))}
          </div>
          <div className="bg-gray-800 rounded-xl p-6 w-80">
            <p className="text-gray-400 text-xs mb-2 uppercase tracking-widest text-center">능력치 레이더</p>
            <PlayerRadarChart data={player.radar} />
          </div>
        </div>
        <div className="max-w-xl">
          <InsightBox name={player.name} stats={player.stats} />
        </div>
      </div>
    </div>
  );
}