import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import PercentileBar from '../components/player/PercentileBar';
import PlayerRadarChart from '../components/player/RadarChart';
import InsightBox from '../components/player/InsightBox';
import PlayerCard from '../components/player/PlayerCard';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorBox from '../components/common/ErrorBox';
import { mockPlayers } from '../data/mockPlayers';
import type { Player } from '../data/mockPlayers';

export default function PlayerPage() {
  const [player, setPlayer] = useState<Player | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [query, setQuery] = useState('');
  const [showList, setShowList] = useState(true);
  const [searchParams] = useSearchParams();

  // URL 검색 파라미터 반영
  useEffect(() => {
    const q = searchParams.get('search');
    if (q) {
      setQuery(q);
      setShowList(true);
      setPlayer(null);
    }
  }, [searchParams]);

  // 검색 필터
  const filtered = mockPlayers.filter((p) =>
    p.name.includes(query) || p.team.includes(query) || p.position.includes(query)
  );

  const selectPlayer = (p: Player) => {
    setLoading(true);
    setError(false);
    setShowList(false);
    setTimeout(() => {
      setPlayer(p);
      setLoading(false);
    }, 400);
  };

  const handleBack = () => {
    setPlayer(null);
    setShowList(true);
    setQuery('');
  };

  // 선수 목록 화면
  if (showList) {
    return (
      <div className="min-h-screen bg-gray-900 px-10 py-8">
        <h1 className="text-white text-3xl font-black mb-2">선수 프로필</h1>
        <p className="text-gray-400 text-sm mb-6">선수를 검색하거나 선택하세요</p>

        {/* 검색 결과 표시 */}
        {query && (
          <p className="text-gray-400 text-sm mb-4">
            "<span className="text-orange-400">{query}</span>" 검색 결과
            <button
              onClick={() => setQuery('')}
              className="ml-3 text-gray-600 hover:text-gray-400 text-xs"
            >
              ✕ 초기화
            </button>
          </p>
        )}

        {/* 선수 목록 */}
        <div className="max-w-lg space-y-2">
          {filtered.length > 0 ? (
            filtered.map((p) => (
              <PlayerCard key={p.id} player={p} onClick={selectPlayer} />
            ))
          ) : (
            <p className="text-gray-500 text-sm py-10 text-center">
              검색 결과가 없습니다
            </p>
          )}
        </div>
      </div>
    );
  }

  // 로딩
  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorBox onRetry={() => player && selectPlayer(player)} />;
  if (!player) return null;

  // 선수 프로필 화면
  return (
    <div className="min-h-screen bg-gray-900">

      {/* 상단 헤더 */}
      <div className="bg-gradient-to-r from-gray-800 to-gray-900 border-b border-gray-700 px-10 py-8">
        <div className="flex items-center gap-6">

          {/* 뒤로가기 */}
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

      {/* 본문 */}
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