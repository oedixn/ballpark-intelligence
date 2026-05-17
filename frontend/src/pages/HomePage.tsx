import { useNavigate } from 'react-router-dom';
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

const KBO_TEAM_MAP: Record<string, string> = {
  'KIA 타이거즈':  'KIA',
  'SSG 랜더스':    'SSG',
  'LG 트윈스':     'LG',
  'KT 위즈':       'KT',
  'NC 다이노스':   'NC',
  '두산 베어스':   '두산',
  '삼성 라이온즈': '삼성',
  '한화 이글스':   '한화',
  '롯데 자이언츠': '롯데',
  '키움 히어로즈': '키움',
};

function toDbTeamName(name: string): string {
  return KBO_TEAM_MAP[name] ?? name;
}

const features = [
  {
    icon: '👤',
    title: '선수 프로필',
    desc: '퍼센타일 바, 레이더 차트, AI 자연어 해석으로 선수 기량을 한눈에 확인',
    path: '/player',
  },
  {
    icon: '⚾',
    title: '경기 시뮬레이터',
    desc: '마르코프 체인 기반으로 실제 경기를 타석 단위로 시뮬레이션',
    path: '/simulator',
  },
  {
    icon: '📋',
    title: '타순 배치',
    desc: '드래그앤드롭으로 최적 타순을 직접 구성하고 득점 기대값 확인',
    path: '/lineup',
  },
];

export default function HomePage() {
  const navigate = useNavigate();

  const now = new Date();

  const [selectedDate, setSelectedDate]   = useState<Date>(now);
  const [monthCache, setMonthCache]       = useState<Record<string, Game[]>>({});
  const [loadingGames, setLoadingGames]   = useState(false);
  const [lastUpdated, setLastUpdated]     = useState<Date | null>(null);

  const getMonth   = (d: Date) => String(d.getMonth() + 1).padStart(2, '0');
  const getDay     = (d: Date) => String(d.getDate()).padStart(2, '0');
  const getDateKey = (d: Date) => `${getMonth(d)}.${getDay(d)}`;

  const selectedMonth = getMonth(selectedDate);
  const selectedKey   = getDateKey(selectedDate);

  useEffect(() => {
    const fetchMonth = () => {
      api.get(`/api/schedule?month=${selectedMonth}`)
        .then(res => {
          setMonthCache(prev => ({ ...prev, [selectedMonth]: res.data.games }));
          setLastUpdated(new Date());
        })
        .catch(() => {})
        .finally(() => setLoadingGames(false));
    };

    setLoadingGames(true);
    fetchMonth();

    const interval = setInterval(fetchMonth, 60000);
    return () => clearInterval(interval);
  }, [selectedMonth]);

  const allGames   = monthCache[selectedMonth] ?? [];
  const todayGames = allGames.filter(g => g.date.startsWith(selectedKey));

  const moveDay = (delta: number) => {
    setSelectedDate(prev => {
      const next = new Date(prev);
      next.setDate(next.getDate() + delta);
      return next;
    });
  };

  const isToday = getDateKey(selectedDate) === getDateKey(now);

  const dateLabel = selectedDate.toLocaleDateString('ko-KR', {
    month: 'long', day: 'numeric', weekday: 'short',
  });

  return (
    <div className="min-h-screen bg-gray-900">

      {/* 히어로 배너 */}
      <div className="bg-gradient-to-br from-gray-800 via-gray-900 to-gray-950 px-10 py-20 text-center border-b border-gray-700">
        <div className="mb-4 text-6xl">⚾</div>
        <h1 className="text-white text-5xl font-black mb-4">
          BallPark Intelligence
        </h1>
        <p className="text-gray-400 text-lg mb-2">
          KBO 데이터 기반 경기 예측 · 선수 분석 · 시뮬레이션 플랫폼
        </p>
        <p className="text-gray-500 text-sm mb-10">
          마르코프 체인 · 몬테카를로 · K-Means 클러스터링
        </p>
        <div className="flex justify-center gap-4">
          <button
            onClick={() => navigate('/simulator')}
            className="bg-orange-500 hover:bg-orange-600 text-white font-black px-8 py-3 rounded-xl transition-colors"
          >
            ▶ 경기 시뮬레이션
          </button>
          <button
            onClick={() => navigate('/player')}
            className="bg-gray-700 hover:bg-gray-600 text-white font-bold px-8 py-3 rounded-xl transition-colors"
          >
            선수 프로필 보기
          </button>
        </div>
      </div>

      {/* 기능 소개 카드 */}
      <div className="px-10 py-12">
        <h2 className="text-white text-2xl font-black mb-6">주요 기능</h2>
        <div className="grid grid-cols-3 gap-4 mb-12">
          {features.map((f) => (
            <div
              key={f.title}
              onClick={() => navigate(f.path)}
              className="bg-gray-800 hover:bg-gray-700 rounded-xl p-6 cursor-pointer transition-colors border border-transparent hover:border-orange-400"
            >
              <div className="text-4xl mb-4">{f.icon}</div>
              <h3 className="text-white font-bold text-lg mb-2">{f.title}</h3>
              <p className="text-gray-400 text-sm leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>

        {/* 경기 일정 헤더 */}
        <div className="flex items-center gap-4 mb-6 flex-wrap">
          <h2 className="text-white text-2xl font-black">KBO 경기 일정</h2>

          {/* 날짜 네비게이터 */}
          <div className="flex items-center gap-2 ml-2">
            <button
              onClick={() => moveDay(-1)}
              className="w-8 h-8 flex items-center justify-center bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors text-sm"
            >
              ←
            </button>

            <div className="flex items-center gap-2 px-4 py-1.5 bg-gray-800 rounded-lg">
              <span className={`text-sm font-bold ${isToday ? 'text-orange-400' : 'text-white'}`}>
                {dateLabel}
              </span>
              {isToday && (
                <span className="text-orange-400 text-xs font-black">TODAY</span>
              )}
            </div>

            <button
              onClick={() => moveDay(1)}
              className="w-8 h-8 flex items-center justify-center bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors text-sm"
            >
              →
            </button>

            {!isToday && (
              <button
                onClick={() => setSelectedDate(now)}
                className="text-xs text-orange-400 hover:text-orange-300 font-bold transition-colors ml-1"
              >
                오늘로
              </button>
            )}
          </div>

          {/* 마지막 업데이트 시간 */}
          {lastUpdated && (
            <span className="ml-auto text-gray-600 text-xs">
              🔄 {lastUpdated.toLocaleTimeString('ko-KR', {
                hour: '2-digit', minute: '2-digit', second: '2-digit'
              })} 업데이트
            </span>
          )}
        </div>

        {/* 경기 목록 */}
        {loadingGames && (
          <p className="text-gray-500 text-sm animate-pulse">⚾ 경기 일정 불러오는 중...</p>
        )}

        {!loadingGames && todayGames.length === 0 && (
          <p className="text-gray-600 text-sm">이 날 예정된 경기가 없습니다.</p>
        )}

        <div className="space-y-3 max-w-2xl">
          {todayGames.map((game, i) => {
            const finished = game.score_a !== null && game.score_b !== null;
            const scoreA   = Number(game.score_a ?? 0);
            const scoreB   = Number(game.score_b ?? 0);
            const aWin     = finished && scoreA > scoreB;
            const bWin     = finished && scoreB > scoreA;
            const canceled = game.status && (game.status.includes('우천') || game.status.includes('취소'));

            return (
              <div
                key={i}
                className="bg-gray-800 rounded-xl px-6 py-4 flex items-center gap-6"
              >
                <span className="text-orange-400 font-bold text-sm w-14 shrink-0">
                  {game.time}
                </span>

                <div className="flex items-center gap-3 flex-1">
                  <span className={`font-semibold ${aWin ? 'text-white' : 'text-gray-400'}`}>
                    {game.team_a}
                  </span>

                  {finished && !canceled ? (
                    <span className="text-white font-black text-lg">
                      {game.score_a} : {game.score_b}
                    </span>
                  ) : canceled ? (
                    <span className="text-yellow-500 text-xs font-bold">{game.status}</span>
                  ) : (
                    <span className="text-gray-600 text-sm">vs</span>
                  )}

                  <span className={`font-semibold ${bWin ? 'text-white' : 'text-gray-400'}`}>
                    {game.team_b}
                  </span>
                </div>

                <span className="text-gray-500 text-xs shrink-0">{game.stadium}</span>

                {finished ? (
                  <span className="text-orange-400 text-xs font-bold shrink-0 w-20 text-right">
                    {game.result}
                  </span>
                ) : (
                  <button
                    onClick={() => navigate(
                      `/simulator?team_a=${encodeURIComponent(toDbTeamName(game.team_a))}&team_b=${encodeURIComponent(toDbTeamName(game.team_b))}`
                    )}
                    className="bg-gray-700 hover:bg-orange-500 text-gray-300 hover:text-white text-xs font-bold px-4 py-2 rounded-lg transition-colors shrink-0"
                  >
                    시뮬레이션 →
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}