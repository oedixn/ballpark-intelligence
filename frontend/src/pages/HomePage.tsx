import { useNavigate } from 'react-router-dom';

const features = [
  {
    icon: '👤',
    title: '선수 프로필',
    desc: '퍼센타일 바, 레이더 차트, AI 자연어 해석으로 선수 기량을 한눈에 확인',
    path: '/',
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

const todayGames = [
  { time: '18:30', away: 'KIA 타이거즈', home: 'SSG 랜더스',   stadium: '인천SSG랜더스필드' },
  { time: '18:30', away: 'LG 트윈스',    home: '두산 베어스',   stadium: '서울종합운동장' },
  { time: '18:30', away: 'NC 다이노스',  home: '롯데 자이언츠', stadium: '사직야구장' },
  { time: '18:30', away: 'KT 위즈',      home: '삼성 라이온즈', stadium: '대구삼성라이온즈파크' },
  { time: '18:30', away: '키움 히어로즈', home: '한화 이글스',   stadium: '대전한화생명볼파크' },
];

export default function HomePage() {
  const navigate = useNavigate();

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

        {/* 오늘의 KBO 경기 일정 */}
        <h2 className="text-white text-2xl font-black mb-6">
          오늘의 KBO 경기 일정
          <span className="text-gray-500 text-sm font-normal ml-3">
            {new Date().toLocaleDateString('ko-KR', { month: 'long', day: 'numeric', weekday: 'short' })}
          </span>
        </h2>
        <div className="space-y-3 max-w-2xl">
          {todayGames.map((game, i) => (
            <div
              key={i}
              className="bg-gray-800 rounded-xl px-6 py-4 flex items-center gap-6"
            >
              {/* 시간 */}
              <span className="text-orange-400 font-bold text-sm w-14 shrink-0">
                {game.time}
              </span>

              {/* 매치업 */}
              <div className="flex items-center gap-3 flex-1">
                <span className="text-gray-300 font-semibold">{game.away}</span>
                <span className="text-gray-600 text-sm">vs</span>
                <span className="text-white font-bold">{game.home}</span>
              </div>

              {/* 구장 */}
              <span className="text-gray-500 text-xs shrink-0">{game.stadium}</span>

              {/* 시뮬레이션 버튼 */}
              <button
                onClick={() => navigate('/simulator')}
                className="bg-gray-700 hover:bg-orange-500 text-gray-300 hover:text-white text-xs font-bold px-4 py-2 rounded-lg transition-colors shrink-0"
              >
                시뮬레이션 →
              </button>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}