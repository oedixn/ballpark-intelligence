import { useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import axios from 'axios';
import { getTeamLogo } from '../utils/teamLogo';

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL });

interface Game {
  date: string; time: string; team_a: string; team_b: string;
  score_a: string | null; score_b: string | null; result: string | null;
  stadium: string; status: string | null;
}

const KBO_TEAM_MAP: Record<string, string> = {
  'KIA 타이거즈': 'KIA', 'SSG 랜더스': 'SSG', 'LG 트윈스': 'LG', 'KT 위즈': 'KT', 'NC 다이노스': 'NC',
  '두산 베어스': '두산', '삼성 라이온즈': '삼성', '한화 이글스': '한화', '롯데 자이언츠': '롯데', '키움 히어로즈': '키움',
};
const toDbTeamName = (name: string) => KBO_TEAM_MAP[name] ?? name;

const features = [
  { title: '선수 프로필', desc: '리그 백분위, 능력치 레이더, 유사 선수, 다음 시즌 예측까지 한 화면에서 확인합니다.', path: '/player' },
  { title: '경기 시뮬레이터', desc: '마르코프 체인으로 경기를 타석 단위로 재현하고 1,000경기 통계를 냅니다.', path: '/simulator' },
  { title: '타순 배치', desc: '드래그로 타순을 구성하고 득점 기대값 변화를 확인합니다.', path: '/lineup' },
];

const heroStats = [
  { label: '시즌 데이터', value: '9개', sub: '2018 ~ 2026' },
  { label: '등록 선수', value: '800+', sub: 'KBO 전체' },
  { label: '시뮬레이션', value: '1,000회', sub: '몬테카를로' },
  { label: '알고리즘', value: '4종', sub: 'Markov · ML · LSTM · 유사도' },
];

const TYPING_TEXTS = ['경기 예측', '선수 분석', '시뮬레이션'];

const FLOATERS = [
  { team: 'LG',   top: '10%', left: '4%',  size: 44, delay: 0,   dur: 7 },
  { team: '한화', top: '55%', left: '9%',  size: 40, delay: 1.2, dur: 8 },
  { team: 'SSG',  top: '25%', left: '16%', size: 36, delay: 2.4, dur: 6.5 },
  { team: '삼성', top: '68%', left: '20%', size: 42, delay: 3.1, dur: 7.5 },
  { team: 'NC',   top: '40%', left: '2%',  size: 34, delay: 4,   dur: 9 },
  { team: 'KT',   top: '12%', left: '92%', size: 44, delay: 0.6, dur: 7.2 },
  { team: '롯데', top: '58%', left: '88%', size: 40, delay: 1.8, dur: 8.2 },
  { team: 'KIA',  top: '30%', left: '82%', size: 36, delay: 2.9, dur: 6.8 },
  { team: '두산', top: '70%', left: '94%', size: 42, delay: 3.5, dur: 7.8 },
  { team: '키움', top: '8%',  left: '76%', size: 34, delay: 4.4, dur: 8.6 },
];

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
  const a = Number(game.score_a ?? 0), b = Number(game.score_b ?? 0);
  const la = getTeamLogo(game.team_a), lb = getTeamLogo(game.team_b);
  return (
    <span className="inline-flex items-center gap-2 px-4 shrink-0">
      {la && <img src={la} alt={game.team_a} className="w-4 h-4 object-contain" />}
      <span className={`text-xs font-bold ${a > b ? 'text-white' : 'text-gray-500'}`}>{game.team_a} {game.score_a}</span>
      <span className="text-gray-600 text-xs">:</span>
      <span className={`text-xs font-bold ${b > a ? 'text-white' : 'text-gray-500'}`}>{game.score_b} {game.team_b}</span>
      {lb && <img src={lb} alt={game.team_b} className="w-4 h-4 object-contain" />}
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
      const res = await api.get(isH ? '/api/stats/hitters?sort=woba&limit=20' : '/api/stats/pitchers?sort=era&limit=20');
      const list = isH ? res.data.hitters : res.data.pitchers;
      if (list?.length) { setPlayer(list[Math.floor(Math.random() * list.length)]); setIsHitter(isH); }
    } catch {} finally { setLoading(false); }
  };
  useEffect(() => { pickRandom(); }, []);

  if (loading) return (
    <div className="border border-gray-800 rounded-lg p-5 flex items-center gap-5">
      <div className="skeleton-box w-12 h-12 rounded-full shrink-0" />
      <div className="flex-1"><div className="skeleton-box w-20 h-3 mb-2" /><div className="skeleton-box w-40 h-5" /></div>
      <div className="flex gap-5">{[0, 1, 2, 3].map(i => <div key={i}><div className="skeleton-box w-10 h-5 mb-1" /><div className="skeleton-box w-8 h-3" /></div>)}</div>
    </div>
  );
  if (!player) return null;

  const logo = getTeamLogo(player.team_name);
  const shown = isHitter ? [
    { label: 'AVG', value: Number(player.avg).toFixed(3) }, { label: 'OBP', value: Number(player.obp).toFixed(3) },
    { label: 'SLG', value: Number(player.slg).toFixed(3) }, { label: 'OPS', value: Number(player.ops).toFixed(3) },
    { label: 'wOBA', value: Number(player.woba).toFixed(3), hi: true }, { label: 'wRC+', value: String(player.wrc_plus) },
    { label: 'HR', value: String(player.hr) }, { label: 'RBI', value: String(player.rbi) },
  ] : [
    { label: 'ERA', value: Number(player.era).toFixed(2), hi: true }, { label: 'W-L', value: `${player.w}-${player.l}` },
    { label: 'IP', value: String(player.ip) }, { label: 'SO', value: String(player.so) },
    { label: 'WHIP', value: Number(player.whip).toFixed(2) }, { label: 'SV', value: String(player.sv) },
  ];

  return (
    <div onClick={() => navigate(`/player/${player.player_id}`)}
      className="border border-gray-800 hover:border-gray-600 rounded-lg p-5 cursor-pointer transition-colors">
      <div className="flex items-center gap-5 flex-wrap">
        <div className="w-12 h-12 rounded-full bg-gray-700 flex items-center justify-center text-white font-bold shrink-0">
          {player.player_name.charAt(0)}
        </div>
        <div className="flex-1 min-w-[200px]">
          <p className="text-gray-500 text-sm">
            오늘의 선수
            <button onClick={(e) => { e.stopPropagation(); pickRandom(); }}
              className="ml-3 text-xs underline hover:text-orange-400 transition-colors">다른 선수 보기</button>
          </p>
          <div className="flex items-center gap-2 mt-1">
            <h3 className="text-white font-bold text-xl">{player.player_name}</h3>
            {logo && <img src={logo} alt={player.team_name} className="w-5 h-5 object-contain" />}
            <span className="text-gray-400 text-sm">{player.team_name}</span>
          </div>
        </div>
        <div className="flex gap-5 flex-wrap">
          {shown.map(s => (
            <div key={s.label} className="text-center">
              <p className={`font-semibold text-lg ${s.hi ? 'text-orange-400' : 'text-white'}`}>{s.value}</p>
              <p className="text-gray-500 text-xs">{s.label}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function TeamRankPreview({ navigate }: { navigate: (path: string) => void }) {
  const [teams, setTeams] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/api/stats/team-rank').then(r => setTeams((r.data.teams ?? []).slice(0, 5))).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="border border-gray-800 bg-gray-900 rounded-lg p-4">
      <div className="skeleton-box w-24 h-3 mb-3" />
      <div className="space-y-2.5">{[0, 1, 2, 3, 4].map(i => <div key={i} className="skeleton-box w-full h-4" />)}</div>
    </div>
  );
  if (!teams.length) return null;

  const max = Math.max(...teams.map(t => Number(t.win_rate)));
  return (
    <div className="border border-gray-700 bg-gray-900 rounded-lg p-4 shadow-lg shadow-black/30">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-white text-sm font-semibold">팀 순위 TOP 5</h2>
        <button onClick={() => navigate('/stats')} className="text-gray-500 hover:text-orange-400 text-xs transition-colors">전체 →</button>
      </div>
      <div className="space-y-2">
        {teams.map((t, i) => {
          const logo = getTeamLogo(t.team_name);
          return (
            <div key={t.team_name} className="flex items-center gap-2">
              <span className={`text-xs font-semibold w-3 ${i === 0 ? 'text-orange-400' : 'text-gray-500'}`}>{i + 1}</span>
              {logo && <img src={logo} alt={t.team_name} className="w-3.5 h-3.5 object-contain" />}
              <span className="text-white text-xs w-10">{t.team_name}</span>
              <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${i === 0 ? 'bg-orange-500' : 'bg-gray-600'}`} style={{ width: `${(Number(t.win_rate) / max) * 100}%` }} />
              </div>
              <span className={`text-xs w-10 text-right ${i === 0 ? 'text-orange-400' : 'text-gray-400'}`}>{Number(t.win_rate).toFixed(3)}</span>
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
  const [typingIdx, setTypingIdx] = useState(0);
  const [typingText, setTypingText] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);
  const [selectedDate, setSelectedDate] = useState<Date>(now);
  const [monthCache, setMonthCache] = useState<Record<string, Game[]>>({});
  const [loadingGames, setLoadingGames] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    const current = TYPING_TEXTS[typingIdx];
    const timer = setTimeout(() => {
      if (!isDeleting && typingText === current) { setTimeout(() => setIsDeleting(true), 1200); return; }
      if (isDeleting && typingText === '') { setIsDeleting(false); setTypingIdx(p => (p + 1) % TYPING_TEXTS.length); return; }
      setTypingText(prev => isDeleting ? prev.slice(0, -1) : current.slice(0, prev.length + 1));
    }, isDeleting ? 60 : 100);
    return () => clearTimeout(timer);
  }, [typingText, isDeleting, typingIdx]);

  const getMonth = (d: Date) => String(d.getMonth() + 1).padStart(2, '0');
  const getDateKey = (d: Date) => `${getMonth(d)}.${String(d.getDate()).padStart(2, '0')}`;
  const selectedMonth = getMonth(selectedDate);
  const selectedKey = getDateKey(selectedDate);

  useEffect(() => {
    const fetchMonth = () => {
      api.get(`/api/schedule?month=${selectedMonth}`)
        .then(res => { setMonthCache(prev => ({ ...prev, [selectedMonth]: res.data.games })); setLastUpdated(new Date()); })
        .catch(() => {}).finally(() => setLoadingGames(false));
    };
    setLoadingGames(true);
    fetchMonth();
    const interval = setInterval(fetchMonth, 60000);
    return () => clearInterval(interval);
  }, [selectedMonth]);

  const allGames = monthCache[selectedMonth] ?? [];
  const dayGames = allGames.filter(g => g.date.startsWith(selectedKey));
  const tickerGames = allGames.filter(g => g.score_a !== null && g.score_b !== null).slice(-10);
  const isToday = selectedKey === getDateKey(now);
  const dateLabel = selectedDate.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric', weekday: 'short' });
  const moveDay = (delta: number) => setSelectedDate(prev => { const n = new Date(prev); n.setDate(n.getDate() + delta); return n; });

  return (
    <div className="min-h-screen bg-gray-900">
      <style>{`
        @keyframes tickerScroll { from { transform: translateX(0); } to { transform: translateX(-50%); } }
        .ticker-track { animation: tickerScroll 40s linear infinite; display: flex; width: max-content; }
        .ticker-wrap:hover .ticker-track { animation-play-state: paused; }
        @keyframes skeletonPulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 0.7; } }
        .skeleton-box { animation: skeletonPulse 1.4s ease-in-out infinite; background: #374151; border-radius: 6px; }
        @keyframes bounceDown { 0%, 100% { transform: translateY(0); opacity: 0.6; } 50% { transform: translateY(6px); opacity: 1; } }
        @keyframes diamondPulse { 0%, 100% { opacity: 0.05; } 50% { opacity: 0.09; } }
        @keyframes floatLogo { 0%, 100% { transform: translateY(0) rotate(0deg); } 50% { transform: translateY(-14px) rotate(8deg); } }
        .scroll-hint { animation: bounceDown 1.6s ease-in-out infinite; }
        .diamond-bg { animation: diamondPulse 4s ease-in-out infinite; }
        .float-logo { opacity: 0.2; animation: floatLogo 7s ease-in-out infinite; }
      `}</style>

      {tickerGames.length > 0 && (
        <div className="ticker-wrap bg-black border-b border-gray-800 overflow-hidden py-2">
          <div className="ticker-track">{[...tickerGames, ...tickerGames].map((g, i) => <TickerItem key={i} game={g} />)}</div>
        </div>
      )}

      {/* 히어로 */}
      <div className="relative overflow-hidden bg-gradient-to-br from-gray-800 via-gray-900 to-gray-950">
        {FLOATERS.map(f => {
          const logo = getTeamLogo(f.team);
          return logo ? (
            <img key={f.team} src={logo} alt="" aria-hidden
              className="float-logo absolute pointer-events-none select-none object-contain"
              style={{ top: f.top, left: f.left, width: f.size, height: f.size, animationDuration: `${f.dur}s`, animationDelay: `${f.delay}s` }} />
          ) : null;
        })}
        <svg className="diamond-bg absolute inset-0 w-full h-full" viewBox="0 0 800 400" preserveAspectRatio="xMidYMid slice">
          <polygon points="400,50 550,200 400,350 250,200" fill="none" stroke="white" strokeWidth="1" />
          <line x1="250" y1="200" x2="400" y2="350" stroke="white" strokeWidth="1" />
          <line x1="550" y1="200" x2="400" y2="350" stroke="white" strokeWidth="1" />
          <line x1="250" y1="200" x2="400" y2="50" stroke="white" strokeWidth="1" />
          <line x1="550" y1="200" x2="400" y2="50" stroke="white" strokeWidth="1" />
          <circle cx="400" cy="50" r="6" fill="white" />
          <circle cx="550" cy="200" r="6" fill="white" />
          <circle cx="400" cy="350" r="6" fill="white" />
          <circle cx="250" cy="200" r="6" fill="white" />
          <circle cx="400" cy="200" r="4" fill="white" opacity="0.5" />
          <path d="M 150,370 Q 400,30 650,370" fill="none" stroke="white" strokeWidth="1" opacity="0.4" />
        </svg>

        <div className="relative px-10 py-9 text-center">
          <div className="mb-2 text-4xl">⚾</div>
          <h1 className="text-white text-4xl font-black mb-2 tracking-tight">BallPark Intelligence</h1>
          <p className="text-gray-300 text-base mb-1 h-6">
            KBO 데이터 기반{' '}
            <span className="text-orange-400 font-black">{typingText}<span className="animate-pulse">|</span></span>
            {' '}플랫폼
          </p>
          <p className="text-gray-500 text-xs mb-5">마르코프 체인 · 몬테카를로 · K-Means 클러스터링</p>
          <div className="flex justify-center gap-3 mb-6">
            <button onClick={() => navigate('/simulator')}
              className="bg-orange-500 hover:bg-orange-400 text-white font-black text-sm px-6 py-2 rounded-xl transition-all hover:scale-105 shadow-lg shadow-orange-500/20">
              ▶ 경기 시뮬레이션
            </button>
            <button onClick={() => navigate('/player')}
              className="bg-gray-700 hover:bg-gray-600 text-white font-bold text-sm px-6 py-2 rounded-xl transition-all hover:scale-105 border border-gray-600">
              선수 프로필 보기
            </button>
          </div>
          <div className="grid grid-cols-4 gap-3 max-w-2xl mx-auto">
            {heroStats.map(s => (
              <div key={s.label} className="bg-gray-800/60 backdrop-blur rounded-xl px-3 py-2 border border-gray-700/50">
                <p className="text-orange-400 text-lg font-black">{s.value}</p>
                <p className="text-white text-xs font-bold">{s.label}</p>
                <p className="text-gray-500 text-[11px]">{s.sub}</p>
              </div>
            ))}
          </div>
          <div className="scroll-hint flex justify-center mt-3">
            <svg viewBox="0 0 24 24" fill="none" className="w-5 h-5 text-gray-500" stroke="currentColor" strokeWidth={2}>
              <path d="M12 5v14M19 12l-7 7-7-7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
        </div>
      </div>

      {/* 기능 버튼 */}
      <div className="px-10 py-4 bg-gray-800/50 border-y border-gray-700 grid grid-cols-3 gap-4">
        {features.map(f => (
          <button key={f.title} onClick={() => navigate(f.path)}
            className="text-left border border-gray-700 hover:border-orange-400 rounded-lg px-4 py-3 transition-colors">
            <h3 className="text-white font-semibold text-sm">{f.title}</h3>
            <p className="text-gray-400 text-xs mt-0.5 leading-relaxed">{f.desc}</p>
          </button>
        ))}
      </div>

      <div className="px-10 py-8 grid grid-cols-[1fr_260px] gap-8 items-start">
        <div className="space-y-10 min-w-0">
          <SpotlightCard navigate={navigate} />

          <section>
            <div className="flex items-center gap-3 mb-4 flex-wrap">
              <h2 className="text-white text-xl font-semibold">경기 일정</h2>
              <div className="flex items-center gap-2">
                <button onClick={() => moveDay(-1)} className="w-8 h-8 border border-gray-700 hover:border-gray-500 text-white rounded-lg transition-colors">←</button>
                <span className={`text-sm px-3 ${isToday ? 'text-orange-400 font-semibold' : 'text-white'}`}>{dateLabel}{isToday && ' · 오늘'}</span>
                <button onClick={() => moveDay(1)} className="w-8 h-8 border border-gray-700 hover:border-gray-500 text-white rounded-lg transition-colors">→</button>
                {lastUpdated && <span className="text-gray-600 text-xs ml-2">{lastUpdated.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })} 업데이트</span>}
                {!isToday && <button onClick={() => setSelectedDate(now)} className="text-xs text-orange-400 hover:text-orange-300 ml-1">오늘로</button>}
              </div>
            </div>

            {loadingGames && <p className="text-gray-500 text-sm animate-pulse">경기 일정을 불러오는 중입니다.</p>}
            {!loadingGames && dayGames.length === 0 && <p className="text-gray-500 text-sm">이 날 예정된 경기가 없습니다.</p>}

            <div className="space-y-2">
              {dayGames.map((game, i) => {
                const finished = game.score_a !== null && game.score_b !== null;
                const a = Number(game.score_a ?? 0), b = Number(game.score_b ?? 0);
                const canceled = game.status && (game.status.includes('우천') || game.status.includes('취소'));
                const live = !finished && !canceled && game.time !== '' && (() => {
                  const [h, m] = game.time.split(':').map(Number);
                  const start = h * 60 + m, cur = now.getHours() * 60 + now.getMinutes();
                  return isToday && cur >= start && cur <= start + 210;
                })();
                return (
                  <div key={i} className={`flex items-center gap-4 px-4 py-3 border rounded-lg ${live ? 'border-red-500/50' : 'border-gray-800'}`}>
                    <div className="w-16 shrink-0">
                      <p className="text-orange-400 font-semibold text-sm">{game.time}</p>
                      <p className="text-gray-500 text-xs">{game.stadium}</p>
                      {live && <p className="text-red-400 text-xs font-bold flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />LIVE</p>}
                    </div>
                    <div className="flex items-center gap-3 flex-1">
                      <TeamLabel name={game.team_a} bold={finished && a > b} />
                      {finished && !canceled ? <span className="text-white font-bold text-lg">{game.score_a} : {game.score_b}</span>
                        : canceled ? <span className="text-yellow-500 text-xs font-bold">{game.status}</span>
                        : <span className="text-gray-600 text-sm">vs</span>}
                      <TeamLabel name={game.team_b} bold={finished && b > a} />
                    </div>
                    {finished ? <span className="text-orange-400 text-xs font-semibold shrink-0">{game.result}</span> : (
                      <button onClick={() => navigate(`/simulator?team_a=${encodeURIComponent(toDbTeamName(game.team_a))}&team_b=${encodeURIComponent(toDbTeamName(game.team_b))}`)}
                        className="border border-gray-700 hover:border-orange-500 hover:text-orange-400 text-gray-300 text-xs px-3 py-1.5 rounded-lg transition-colors shrink-0">시뮬레이션</button>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        </div>

        <aside className="self-start sticky top-20"><TeamRankPreview navigate={navigate} /></aside>
      </div>
    </div>
  );
}