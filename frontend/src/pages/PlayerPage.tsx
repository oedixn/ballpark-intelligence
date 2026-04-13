import { useState, useEffect } from 'react';
import PercentileBar from '../components/player/PercentileBar';
import PlayerRadarChart from '../components/player/RadarChart';
import InsightBox from '../components/player/InsightBox';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorBox from '../components/common/ErrorBox';
import { mockPlayers } from '../data/mockPlayers';
import type { Player } from '../data/mockPlayers';

export default function PlayerPage() {
  const [player, setPlayer] = useState<Player | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const fetchPlayer = () => {
    setLoading(true);
    setError(false);

    // 나중에 API 연동 시 아래 주석 해제하고 mock 코드 제거
    // getPlayerById(1).then(setPlayer).catch(() => setError(true)).finally(() => setLoading(false));

    // mock 데이터 (API 연동 전까지 사용)
    setTimeout(() => {
      try {
        setPlayer(mockPlayers[0]);
      } catch {
        setError(true);
      } finally {
        setLoading(false);
      }
    }, 500); // 0.5초 로딩 효과
  };

  useEffect(() => {
    fetchPlayer();
  }, []);

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorBox onRetry={fetchPlayer} />;
  if (!player) return null;

  return (
    <div className="min-h-screen bg-gray-900">

      {/* 상단 헤더 */}
      <div className="bg-gradient-to-r from-gray-800 to-gray-900 border-b border-gray-700 px-10 py-8">
        <div className="flex items-center gap-6">
          <div className="w-20 h-20 rounded-full bg-orange-500 flex items-center justify-center shrink-0">
            <span className="text-white text-2xl font-black">1</span>
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