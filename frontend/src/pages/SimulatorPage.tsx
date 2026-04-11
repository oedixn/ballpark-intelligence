import { useState } from 'react';
import Scoreboard from '../components/simulator/Scoreboard';
import GameLogView from '../components/simulator/GameLog';
import { mockGameLog, mockScoreboard } from '../data/mockGame';

export default function SimulatorPage() {
  const [started, setStarted] = useState(false);

  return (
    <div className="min-h-screen bg-gray-900">

      {/* 헤더 */}
      <div className="bg-gradient-to-r from-gray-800 to-gray-900 border-b border-gray-700 px-10 py-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-white text-3xl font-black">경기 시뮬레이터</h1>
            <p className="text-gray-400 text-sm mt-1">마르코프 체인 기반 경기 예측</p>
          </div>

          {/* 팀 매치업 */}
          <div className="flex items-center gap-6">
            <div className="text-right">
              <p className="text-white font-bold">{mockScoreboard.away.team}</p>
              <p className="text-gray-400 text-xs">원정</p>
            </div>
            <div className="bg-gray-700 rounded-full px-4 py-2">
              <span className="text-orange-400 font-black text-xl">
                {mockScoreboard.away.total}
              </span>
              <span className="text-gray-500 mx-2">:</span>
              <span className="text-orange-400 font-black text-xl">
                {mockScoreboard.home.total}
              </span>
            </div>
            <div className="text-left">
              <p className="text-white font-bold">{mockScoreboard.home.team}</p>
              <p className="text-gray-400 text-xs">홈</p>
            </div>
          </div>
        </div>
      </div>

      {/* 본문 */}
      <div className="px-10 py-8 space-y-6">

        {/* 시작 버튼 */}
        {!started ? (
          <div className="flex justify-center py-10">
            <button
              onClick={() => setStarted(true)}
              className="bg-orange-500 hover:bg-orange-600 text-white font-black text-lg px-12 py-4 rounded-xl transition-colors"
            >
              ▶ 경기 시작
            </button>
          </div>
        ) : (
          <>
            {/* 스코어보드 */}
            <Scoreboard
              away={mockScoreboard.away}
              home={mockScoreboard.home}
            />

            {/* 경기 로그 */}
            <GameLogView gameLog={mockGameLog} />

            {/* 하단 버튼 */}
            <div className="flex gap-4">
              <button
                onClick={() => setStarted(false)}
                className="bg-gray-700 hover:bg-gray-600 text-white font-bold px-8 py-3 rounded-xl transition-colors"
              >
                🔄 다시 시뮬
              </button>
              <button
                className="bg-blue-600 hover:bg-blue-700 text-white font-bold px-8 py-3 rounded-xl transition-colors"
              >
                📊 100경기 통계
              </button>
            </div>
          </>
        )}

      </div>
    </div>
  );
}