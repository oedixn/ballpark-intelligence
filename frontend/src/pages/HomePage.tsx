import { useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import axios from 'axios';
import { getTeamLogo } from '../utils/teamLogo';

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL });

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
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="w-8 h-8" stroke="currentColor" strokeWidth={1.5}>
        <circle cx="12" cy="8" r="4" />
        <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
      </svg>
    ),
    title: '선수 프로필',
    desc: '퍼센타일 바, 레이더 차트, AI 자연어 해석으로 선수 기량을 한눈에 확인',
    path: '/player',
    color: 'from-orange-500/10 to-transparent',
    border: 'hover:border-orange-400',
    iconColor: 'text-orange-400',
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="w-8 h-8" stroke="currentColor" strokeWidth={1.5}>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 3c0 0 3 4 3 9s-3 9-3 9" />
        <path d="M3 12h18" />
        <path d="M4.5 7.5c2 1.5 4.5 2.5 7.5 2.5s5.5-1 7.5-2.5" />
        <path d="M4.5 16.5c2-1.5 4.5-2.5 7.5-2.5s5.5 1 7.5 2.5" />
      </svg>
    ),
    title: '경기 시뮬레이터',
    desc: '마르코프 체인 기반으로 실제 경기를 타석 단위로 시뮬레이션',
    path: '/simulator',
    color: 'from-blue-500/10 to-transparent',
    border: 'hover:border-blue-400',
    iconColor: 'text-blue-400',
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="w-8 h-8" stroke="currentColor" strokeWidth={1.5}>
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <path d="M3 9h18M9 21V9" />
        <path d="M15 3v6" />
      </svg>
    ),
    title: '타순 배치',
    desc: '드래그앤드롭으로 최적 타순을 직접 구성하고 득점 기대값 확인',
    path: '/lineup',
    color: 'from-green-500/10 to-transparent',
    border: 'hover:border-green-400',
    iconColor: 'text-green-400',
  },
];

const stats = [
  { label: '시즌 데이터', value: '9개',      sub: '2018 ~ 2026' },
  { label: '등록 선수',   value: '800+',     sub: 'KBO 전체' },
  { label: '시뮬레이션',  value: '10,000회', sub: '몬테카를로' },
  { label: '알고리즘',    value: '3종',      sub: 'Markov · ML · LSTM' },
];

const TYPING_TEXTS = ['경기 예측', '선수 분석', '시뮬레이션'];

function TeamLabel({ name, bold }: { name: string; bold: boolean }) {
  const logo = getTeamLogo(name);
  return (
    <span className={`inline-flex items-center gap-1.5 font-semibold ${bold ? 'text-white' : 'text-gray-400'}`}>
      {logo && <img src={logo} alt={name} className="w-4 h-4 object-contain" />}
      {name}
    </span>
  );
}

function TickerItem({ game }: { game: Game }) {
  const logoA = getTeamLogo(game.team_a);
  const logoB = getTeamLogo(game.team_b);
  const scoreA = Number(game.score_a ?? 0);
  const scoreB = Number(game.score_b ?? 0);
  const aWin = scoreA > scoreB;
  const bWin = scoreB > scoreA;
  return (
    <span className="inline-flex items-center gap-2 px-4 shrink-0">
      {logoA && <img src={logoA} alt={game.team_a} className="w-4 h-4 object-contain" />}
      <span className={`text-xs font-bold ${aWin ? 'text-white' : 'text-gray-500'}`}>{game.team_a} {game.score_a}</span>
      <span className="text-gray-600 text-xs">:</span>
      <span className={`text-xs font-bold ${bWin ? 'text-white' : 'text-gray-500'}`}>{game.score_b} {game.team_b}</span>
      {logoB && <img src={logoB} alt={game.team_b} className="w-4 h-4 object-contain" />}
      <span className="text-gray-700 text-xs mx-2">·</span>
    </span>
  );
}

function SpotlightCard({ navigate }: { navigate: (path: string) => void }) {
  const [player, setPlayer] = useState<any | null>(null);
  const [isHitter, setIsHitter] = useState(true);
  const [loading, setLoading] = useState(true);

  const pickRandom = async () => {
    setLoading(true);
    try {
      const isH = Math.random() > 0.5;
      const url = isH
        ? '/api/stats/hitters?sort=woba&limit=20'
        : '/api/stats/pitchers?sort=era&limit=20';
      const res = await api.get(url);
      const list = isH ? res.data.hitters : res.data.pitchers;
      if (list && list.length > 0) {
        const pick = list[Math.floor(Math.random() * list.length)];
        setPlayer(pick);
        setIsHitter(isH);
      }
    } catch {}
    finally { setLoading(false); }
  };

  useEffect(() => { pickRandom(); }, []);

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 mb-6">
        <div className="flex items-center gap-6 flex-wrap">
          <div className="skeleton-box w-16 h-16 rounded-full shrink-0" />
          <div className="flex-1 min-w-[200px]">
            <div className="skeleton-box w-24 h-3 mb-2" />
            <div className="skeleton-box w-40 h-5" />
          </div>
          <div className="flex gap-5">
            {[0,1,2,3].map(i => (
              <div key={i} className="text-center">
                <div className="skeleton-box w-10 h-5 mb-1" />
                <div className="skeleton-box w-8 h-2.5" />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!player) return null;
  const logo = getTeamLogo(player.team_name);

  const hitterStats = [
    { label: 'AVG',  value: Number(player.avg).toFixed(3) },
    { label: 'OBP',  value: Number(player.obp).toFixed(3) },
    { label: 'SLG',  value: Number(player.slg).toFixed(3) },
    { label: 'OPS',  value: Number(player.ops).toFixed(3) },
    { label: 'wOBA', value: Number(player.woba).toFixed(3), highlight: true },
    { label: 'wRC+', value: String(player.wrc_plus) },
    { label: 'HR',   value: String(player.hr) },
    { label: 'RBI',  value: String(player.rbi) },
  ];

  const pitcherStats = [
    { label: 'ERA',  value: Number(player.era).toFixed(2), highlight: true },
    { label: 'W-L',  value: `${player.w}-${player.l}` },
    { label: 'IP',   value: String(player.ip) },
    { label: 'SO',   value: String(player.so) },
    { label: 'WHIP', value: Number(player.whip).toFixed(2) },
    { label: 'SV',   value: String(player.sv) },
  ];

  const displayStats = isHitter ? hitterStats : pitcherStats;

  return (
    <div
      onClick={() => navigate(`/player/${player.player_id}`)}
      className="bg-gradient-to-br from-orange-500/10 to-transparent bg-gray-800 rounded-xl p-6 border border-gray-700 hover:border-orange-400 cursor-pointer transition-all hover:scale-[1.01] mb-6"
    >
      <div className="flex items-center gap-6 flex-wrap">
        <div className="w-16 h-16 rounded-full bg-orange-500 flex items-center justify-center shrink-0 text-white font-black text-xl">
          {player.player_name.charAt(0)}
        </div>
        <div className="flex-1 min-w-[200px]">
          <div className="flex items-center gap-2 mb-1">
            <p className="text-gray-500 text-xs uppercase tracking-widest">⚾ 오늘의 선수</p>
            <button
              onClick={(e) => { e.stopPropagation(); pickRandom(); }}
              className="text-gray-500 hover:text-orange-400 transition-colors text-xs"
              title="다른 선수 보기"
            >
              🔄
            </button>
          </div>
          <div className="flex items-center gap-2">
            <h3 className="text-white font-black text-xl">{player.player_name}</h3>
            {logo && <img src={logo} alt={player.team_name} className="w-5 h-5 object-contain" />}
            <span className="text-gray-400 text-sm">{player.team_name}</span>
          </div>
        </div>
        <div className="flex gap-5 flex-wrap">
          {displayStats.map((s) => (
            <div key={s.label} className="text-center">
              <p className={`font-black text-lg ${s.highlight ? 'text-orange-400' : 'text-white'}`}>{s.value}</p>
              <p className="text-gray-500 text-xs">{s.label}</p>
            </div>
          ))}
        </div>
        <span className="text-gray-600 text-sm shrink-0">프로필 보기 →</span>
      </div>
    </div>
  );
}

function TeamRankPreview({ navigate }: { navigate: (path: string) => void }) {
  const [teams, setTeams] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/api/stats/team-rank')
      .then(res => setTeams((res.data.teams ?? []).slice(0, 5)))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 mb-12">
        <div className="skeleton-box w-48 h-3 mb-4" />
        <div className="space-y-2.5">
          {[0,1,2,3,4].map(i => (
            <div key={i} className="flex items-center gap-3">
              <div className="skeleton-box w-4 h-3" />
              <div className="skeleton-box w-4 h-4 rounded-full" />
              <div className="skeleton-box w-10 h-3" />
              <div className="skeleton-box flex-1 h-5" />
              <div className="skeleton-box w-12 h-3" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (teams.length === 0) return null;
  const maxRate = Math.max(...teams.map(t => Number(t.win_rate)));

  return (
    <div
      onClick={() => navigate('/stats')}
      className="bg-gray-800 rounded-xl p-6 border border-gray-700 hover:border-orange-400 cursor-pointer transition-all hover:scale-[1.01] mb-12"
    >
      <div className="flex items-center justify-between mb-4">
        <p className="text-gray-500 text-xs uppercase tracking-widest">📊 실시간 팀 순위 TOP 5</p>
        <span className="text-gray-600 text-xs">기록실 전체보기 →</span>
      </div>
      <div className="space-y-2.5">
        {teams.map((t, i) => {
          const logo = getTeamLogo(t.team_name);
          const widthPct = (Number(t.win_rate) / maxRate) * 100;
          return (
            <div key={t.team_name} className="flex items-center gap-3">
              <span className={`text-xs font-black w-4 shrink-0 ${i === 0 ? 'text-orange-400' : 'text-gray-500'}`}>{i + 1}</span>
              {logo && <img src={logo} alt={t.team_name} className="w-4 h-4 object-contain shrink-0" />}
              <span className="text-white text-xs font-bold w-10 shrink-0">{t.team_name}</span>
              <div className="flex-1 h-5 bg-gray-900 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${i === 0 ? 'bg-orange-500' : 'bg-gray-600'}`}
                  style={{ width: `${widthPct}%` }}
                />
              </div>
              <span className={`text-xs font-black w-12 text-right shrink-0 ${i === 0 ? 'text-orange-400' : 'text-gray-400'}`}>
                {Number(t.win_rate).toFixed(3)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function HomePage() {
  const navigate = useNavigate();
  const now = new Date();

  const [typingIdx,    setTypingIdx]   = useState(0);
  const [typingText,   setTypingText]  = useState('');
  const [isDeleting,   setIsDeleting]  = useState(false);
  const [selectedDate, setSelectedDate] = useState<Date>(now);
  const [monthCache,   setMonthCache]  = useState<Record<string, Game[]>>({});
  const [loadingGames, setLoadingGames] = useState(false);
  const [lastUpdated,  setLastUpdated] = useState<Date | null>(null);
  const [cardsVisible, setCardsVisible] = useState(false);

  useEffect(() => {
    const current = TYPING_TEXTS[typingIdx];
    const speed   = isDeleting ? 60 : 100;
    const timer = setTimeout(() => {
      if (!isDeleting && typingText === current) {
        setTimeout(() => setIsDeleting(true), 1200);
        return;
      }
      if (isDeleting && typingText === '') {
        setIsDeleting(false);
        setTypingIdx((prev) => (prev + 1) % TYPING_TEXTS.length);
        return;
      }
      setTypingText((prev) =>
        isDeleting ? prev.slice(0, -1) : current.slice(0, prev.length + 1)
      );
    }, speed);
    return () => clearTimeout(timer);
  }, [typingText, isDeleting, typingIdx]);

  useEffect(() => {
    const t = setTimeout(() => setCardsVisible(true), 300);
    return () => clearTimeout(t);
  }, []);

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

  const tickerGames = allGames
    .filter(g => g.score_a !== null && g.score_b !== null)
    .slice(-10);

  const moveDay = (delta: number) => {
    setSelectedDate(prev => {
      const next = new Date(prev);
      next.setDate(next.getDate() + delta);
      return next;
    });
  };

  const isToday   = getDateKey(selectedDate) === getDateKey(now);
  const dateLabel = selectedDate.toLocaleDateString('ko-KR', {
    month: 'long', day: 'numeric', weekday: 'short',
  });

  return (
    <div className="min-h-screen bg-gray-900">
      <style>{`
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(24px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes tickerScroll {
          from { transform: translateX(0); }
          to   { transform: translateX(-50%); }
        }
        .ticker-track {
          animation: tickerScroll 40s linear infinite;
          display: flex;
          width: max-content;
        }
        .ticker-wrap:hover .ticker-track {
          animation-play-state: paused;
        }
        @keyframes bounceDown {
          0%, 100% { transform: translateY(0); opacity: 0.6; }
          50%      { transform: translateY(8px); opacity: 1; }
        }
        @keyframes diamondPulse {
          0%, 100% { opacity: 0.05; }
          50%      { opacity: 0.09; }
        }
        @keyframes floatBall {
          0%   { transform: translateY(0) rotate(0deg); }
          50%  { transform: translateY(-16px) rotate(180deg); }
          100% { transform: translateY(0) rotate(360deg); }
        }
        .scroll-hint { animation: bounceDown 1.6s ease-in-out infinite; }
        .diamond-bg  { animation: diamondPulse 4s ease-in-out infinite; }
        .float-ball  { animation: floatBall 6s ease-in-out infinite; }
        .scroll-hint { animation: bounceDown 1.6s ease-in-out infinite; }
        .diamond-bg  { animation: diamondPulse 4s ease-in-out infinite; }
        .float-ball  { animation: floatBall 6s ease-in-out infinite; }
        @keyframes skeletonPulse {
          0%, 100% { opacity: 0.4; }
          50%      { opacity: 0.7; }
        }
        .skeleton-box { animation: skeletonPulse 1.4s ease-in-out infinite; background: #374151; border-radius: 6px; }
      `}</style>
      

      {/* 라이브 티커 */}
      {tickerGames.length > 0 && (
        <div className="ticker-wrap bg-black border-b border-gray-800 overflow-hidden py-2">
          <div className="ticker-track">
            {[...tickerGames, ...tickerGames].map((g, i) => (
              <TickerItem key={i} game={g} />
            ))}
          </div>
        </div>
      )}

      <div className="px-10 pt-8">
        <SpotlightCard navigate={navigate} />
        <TeamRankPreview navigate={navigate} />
      </div>

      {/* 히어로 */}
      <div className="relative overflow-hidden bg-gradient-to-br from-gray-800 via-gray-900 to-gray-950 border-b border-gray-700">
        <span className="float-ball absolute text-3xl opacity-10" style={{ top: '15%', left: '8%' }}>⚾</span>
        <span className="float-ball absolute text-2xl opacity-10" style={{ top: '65%', left: '85%', animationDelay: '2s' }}>⚾</span>
        <span className="float-ball absolute text-xl opacity-10" style={{ top: '40%', left: '75%', animationDelay: '4s' }}>⚾</span>
        <svg className="diamond-bg absolute inset-0 w-full h-full" viewBox="0 0 800 400" preserveAspectRatio="xMidYMid slice">
          <polygon points="400,50 550,200 400,350 250,200" fill="none" stroke="white" strokeWidth="1"/>
          <line x1="250" y1="200" x2="400" y2="350" stroke="white" strokeWidth="1"/>
          <line x1="550" y1="200" x2="400" y2="350" stroke="white" strokeWidth="1"/>
          <line x1="250" y1="200" x2="400" y2="50"  stroke="white" strokeWidth="1"/>
          <line x1="550" y1="200" x2="400" y2="50"  stroke="white" strokeWidth="1"/>
          <circle cx="400" cy="50"  r="6" fill="white"/>
          <circle cx="550" cy="200" r="6" fill="white"/>
          <circle cx="400" cy="350" r="6" fill="white"/>
          <circle cx="250" cy="200" r="6" fill="white"/>
          <circle cx="400" cy="200" r="4" fill="white" opacity="0.5"/>
          <path d="M 150,370 Q 400,30 650,370" fill="none" stroke="white" strokeWidth="1" opacity="0.4"/>
        </svg>

        <div className="relative px-10 py-20 text-center">
          <div className="mb-4 text-6xl">⚾</div>
          <h1 className="text-white text-5xl font-black mb-4 tracking-tight">
            BallPark Intelligence
          </h1>
          <p className="text-gray-300 text-lg mb-2 h-7">
            KBO 데이터 기반{' '}
            <span className="text-orange-400 font-black">
              {typingText}
              <span className="animate-pulse">|</span>
            </span>
            {' '}플랫폼
          </p>
          <p className="text-gray-500 text-sm mb-10">
            마르코프 체인 · 몬테카를로 · K-Means 클러스터링
          </p>
          <div className="flex justify-center gap-4 mb-14">
            <button
              onClick={() => navigate('/simulator')}
              className="bg-orange-500 hover:bg-orange-400 text-white font-black px-8 py-3 rounded-xl transition-all hover:scale-105 shadow-lg shadow-orange-500/20"
            >
              ▶ 경기 시뮬레이션
            </button>
            <button
              onClick={() => navigate('/player')}
              className="bg-gray-700 hover:bg-gray-600 text-white font-bold px-8 py-3 rounded-xl transition-all hover:scale-105 border border-gray-600"
            >
              선수 프로필 보기
            </button>
          </div>
          <div className="grid grid-cols-4 gap-4 max-w-3xl mx-auto">
            {stats.map((s) => (
              <div key={s.label} className="bg-gray-800/60 backdrop-blur rounded-xl px-4 py-3 border border-gray-700/50">
                <p className="text-orange-400 text-xl font-black">{s.value}</p>
                <p className="text-white text-xs font-bold mt-0.5">{s.label}</p>
                <p className="text-gray-500 text-xs mt-0.5">{s.sub}</p>
              </div>
            ))}
          </div>
          <div className="scroll-hint flex justify-center mt-12">
            <svg viewBox="0 0 24 24" fill="none" className="w-6 h-6 text-gray-500" stroke="currentColor" strokeWidth={2}>
              <path d="M12 5v14M19 12l-7 7-7-7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
        </div>
      </div>

      <div className="px-10 py-12">
        <h2 className="text-white text-2xl font-black mb-6">주요 기능</h2>
        <div className="grid grid-cols-3 gap-4 mb-12">
          {features.map((f, i) => (
            <div
              key={f.title}
              onClick={() => navigate(f.path)}
              style={cardsVisible ? {
                animation: `fadeSlideUp 0.5s ease forwards`,
                animationDelay: `${i * 0.15}s`,
                opacity: 0,
              } : { opacity: 0 }}
              className={`bg-gradient-to-br ${f.color} bg-gray-800 rounded-xl p-6 cursor-pointer transition-all border border-gray-700 ${f.border} hover:scale-[1.02] hover:shadow-lg`}
            >
              <div className={`${f.iconColor} mb-4`}>{f.icon}</div>
              <h3 className="text-white font-bold text-lg mb-2">{f.title}</h3>
              <p className="text-gray-400 text-sm leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>

        {/* 경기 일정 */}
        <div className="flex items-center gap-4 mb-6 flex-wrap">
          <h2 className="text-white text-2xl font-black">KBO 경기 일정</h2>
          <div className="flex items-center gap-2 ml-2">
            <button onClick={() => moveDay(-1)}
              className="w-8 h-8 flex items-center justify-center bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors text-sm">
              ←
            </button>
            <div className="flex items-center gap-2 px-4 py-1.5 bg-gray-800 rounded-lg border border-gray-700">
              <span className={`text-sm font-bold ${isToday ? 'text-orange-400' : 'text-white'}`}>
                {dateLabel}
              </span>
              {isToday && <span className="text-orange-400 text-xs font-black">TODAY</span>}
            </div>
            <button onClick={() => moveDay(1)}
              className="w-8 h-8 flex items-center justify-center bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors text-sm">
              →
            </button>
            {!isToday && (
              <button onClick={() => setSelectedDate(now)}
                className="text-xs text-orange-400 hover:text-orange-300 font-bold transition-colors ml-1">
                오늘로
              </button>
            )}
          </div>
          {lastUpdated && (
            <span className="ml-auto text-gray-600 text-xs">
              🔄 {lastUpdated.toLocaleTimeString('ko-KR', {
                hour: '2-digit', minute: '2-digit', second: '2-digit'
              })} 업데이트
            </span>
          )}
        </div>

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
            const isLive   = !finished && !canceled && game.time !== '' && (() => {
              const [h, m] = game.time.split(':').map(Number);
              const gameMin = h * 60 + m;
              const nowMin  = now.getHours() * 60 + now.getMinutes();
              return isToday && nowMin >= gameMin && nowMin <= gameMin + 210;
            })();

            return (
              <div key={i} className={`bg-gray-800 rounded-xl px-6 py-4 flex items-center gap-6 border transition-colors ${isLive ? 'border-red-500/50 hover:border-red-400' : 'border-gray-700/50 hover:border-gray-600'}`}>
                <div className="flex flex-col items-center w-14 shrink-0 gap-0.5">
                  <span className="text-orange-400 font-bold text-sm">{game.time}</span>
                  {isLive && (
                    <span className="flex items-center gap-1 text-red-400 text-xs font-black">
                      <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse inline-block"/>
                      LIVE
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3 flex-1">
                  <TeamLabel name={game.team_a} bold={aWin} />
                  {finished && !canceled ? (
                    <span className="text-white font-black text-lg">{game.score_a} : {game.score_b}</span>
                  ) : canceled ? (
                    <span className="text-yellow-500 text-xs font-bold">{game.status}</span>
                  ) : (
                    <span className="text-gray-600 text-sm">vs</span>
                  )}
                  <TeamLabel name={game.team_b} bold={bWin} />
                </div>
                <span className="text-gray-500 text-xs shrink-0">{game.stadium}</span>
                {finished ? (
                  <span className="text-orange-400 text-xs font-bold shrink-0 w-20 text-right">{game.result}</span>
                ) : (
                  <button
                    onClick={() => navigate(`/simulator?team_a=${encodeURIComponent(toDbTeamName(game.team_a))}&team_b=${encodeURIComponent(toDbTeamName(game.team_b))}`)}
                    className="bg-gray-700 hover:bg-orange-500 text-gray-300 hover:text-white text-xs font-bold px-4 py-2 rounded-lg transition-colors shrink-0">
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