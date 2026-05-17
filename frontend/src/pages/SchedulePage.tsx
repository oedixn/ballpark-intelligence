import { useState, useEffect } from 'react';
import axios from 'axios';

const api = axios.create({ baseURL: 'http://localhost:8000' });

interface Game {
  date: string;
  time: string;
  team_a: string;
  team_b: string;
  score_a: string | null;
  score_b: string | null;
  result: string | null;
  stadium: string;
  status: string | null;
}

interface GroupedGames {
  [date: string]: Game[];
}

const MONTHS = ['03', '04', '05', '06', '07', '08', '09', '10'];
const MONTH_LABELS: Record<string, string> = {
  '03': '3월', '04': '4월', '05': '5월', '06': '6월',
  '07': '7월', '08': '8월', '09': '9월', '10': '10월',
};

const TEAM_COLORS: Record<string, string> = {
  'LG':  'bg-red-600',
  'KT':  'bg-black',
  'SSG': 'bg-red-500',
  'NC':  'bg-blue-700',
  '두산': 'bg-blue-600',
  'KIA': 'bg-red-700',
  '삼성': 'bg-blue-500',
  '한화': 'bg-orange-500',
  '롯데': 'bg-red-400',
  '키움': 'bg-purple-600',
};

function TeamBadge({ name }: { name: string }) {
  const color = TEAM_COLORS[name] ?? 'bg-gray-600';
  return (
    <span className={`${color} text-white text-xs font-black px-2 py-0.5 rounded`}>
      {name}
    </span>
  );
}

export default function SchedulePage() {
  const now = new Date();
  const currentMonth = String(now.getMonth() + 1).padStart(2, '0');
  const validMonth = MONTHS.includes(currentMonth) ? currentMonth : '05';

  const [selectedMonth, setSelectedMonth] = useState(validMonth);
  const [games, setGames]                 = useState<Game[]>([]);
  const [loading, setLoading]             = useState(false);
  const [error, setError]                 = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(false);
    api.get(`/api/schedule?month=${selectedMonth}`)
      .then(res => setGames(res.data.games))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [selectedMonth]);

  // 날짜별 그룹핑
  const grouped: GroupedGames = {};
  for (const game of games) {
    if (!grouped[game.date]) grouped[game.date] = [];
    grouped[game.date].push(game);
  }

  const today = `${String(now.getMonth() + 1).padStart(2, '0')}.${String(now.getDate()).padStart(2, '0')}`;

  return (
    <div className="min-h-screen bg-gray-900 pb-20">

      {/* 헤더 */}
      <div className="bg-gradient-to-r from-gray-800 to-gray-900 border-b border-gray-700 px-10 py-10">
        <h1 className="text-white text-3xl font-black">2026 KBO 경기 일정</h1>
        <p className="text-gray-400 text-sm mt-1">KBO 공식 사이트 실시간 연동</p>
      </div>

      {/* 월 선택 탭 */}
      <div className="px-10 pt-8 pb-2 flex gap-2 flex-wrap">
        {MONTHS.map((m) => (
          <button
            key={m}
            onClick={() => setSelectedMonth(m)}
            className={`px-5 py-2 rounded-xl text-sm font-bold transition-colors ${
              selectedMonth === m
                ? 'bg-orange-500 text-white'
                : 'bg-gray-800 text-gray-400 hover:text-white'
            }`}
          >
            {MONTH_LABELS[m]}
          </button>
        ))}
      </div>

      <div className="px-10 py-8">
        {loading && (
          <div className="flex justify-center py-20">
            <p className="text-gray-400 animate-pulse">⚾ 경기 일정 불러오는 중...</p>
          </div>
        )}

        {error && (
          <div className="flex justify-center py-20">
            <p className="text-red-400">일정을 불러오지 못했습니다.</p>
          </div>
        )}

        {!loading && !error && (
          <div className="space-y-8">
            {Object.entries(grouped).map(([date, dayGames]) => {
              const isToday = date.includes(today);
              return (
                <div key={date}>
                  {/* 날짜 헤더 */}
                  <div className={`flex items-center gap-3 mb-3`}>
                    <span className={`text-sm font-black px-3 py-1 rounded-lg ${
                      isToday
                        ? 'bg-orange-500 text-white'
                        : 'bg-gray-700 text-gray-300'
                    }`}>
                      {date}
                    </span>
                    {isToday && (
                      <span className="text-orange-400 text-xs font-bold">TODAY</span>
                    )}
                    <div className="flex-1 h-px bg-gray-700" />
                  </div>

                  {/* 경기 카드들 */}
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
                    {dayGames.map((game, i) => {
                      const finished = game.score_a !== null && game.score_b !== null;
                      const scoreA   = Number(game.score_a ?? 0);
                      const scoreB   = Number(game.score_b ?? 0);
                      const aWin     = finished && scoreA > scoreB;
                      const bWin     = finished && scoreB > scoreA;
                      const draw     = finished && scoreA === scoreB;
                      const canceled = game.status && (game.status.includes('우천') || game.status.includes('취소'));

                      return (
                        <div
                          key={i}
                          className={`bg-gray-800 rounded-xl p-4 border transition-colors ${
                            isToday
                              ? 'border-orange-500/40'
                              : 'border-gray-700'
                          }`}
                        >
                          {/* 시간 + 구장 */}
                          <div className="flex items-center justify-between mb-3">
                            <span className="text-gray-400 text-xs">{game.time}</span>
                            <span className="text-gray-500 text-xs">{game.stadium}</span>
                          </div>

                          {/* 팀 + 스코어 */}
                          <div className="flex items-center justify-between gap-2">
                            {/* 팀 A */}
                            <div className="flex flex-col items-center gap-1 flex-1">
                              <TeamBadge name={game.team_a} />
                              {finished && (
                                <span className={`text-xl font-black ${aWin ? 'text-white' : draw ? 'text-gray-400' : 'text-gray-500'}`}>
                                  {game.score_a}
                                </span>
                              )}
                            </div>

                            {/* 가운데 */}
                            <div className="text-center">
                              {canceled ? (
                                <span className="text-yellow-500 text-xs font-bold">{game.status}</span>
                              ) : finished ? (
                                <div className="flex flex-col items-center">
                                  <span className="text-gray-500 text-xs">vs</span>
                                  {draw && <span className="text-gray-400 text-xs mt-0.5">무</span>}
                                </div>
                              ) : (
                                <span className="text-gray-500 text-xs">vs</span>
                              )}
                            </div>

                            {/* 팀 B */}
                            <div className="flex flex-col items-center gap-1 flex-1">
                              <TeamBadge name={game.team_b} />
                              {finished && (
                                <span className={`text-xl font-black ${bWin ? 'text-white' : draw ? 'text-gray-400' : 'text-gray-500'}`}>
                                  {game.score_b}
                                </span>
                              )}
                            </div>
                          </div>

                          {/* 결과 */}
                          {game.result && !canceled && (
                            <div className="mt-3 text-center">
                              <span className="text-orange-400 text-xs font-bold">{game.result}</span>
                            </div>
                          )}

                          {/* 예정 경기 */}
                          {!finished && !canceled && (
                            <div className="mt-3 text-center">
                              <span className="text-gray-600 text-xs">예정</span>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}