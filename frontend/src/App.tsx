import { BrowserRouter, Routes, Route, NavLink, Link, useNavigate } from 'react-router-dom';
import { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import HomePage from './pages/HomePage';
import PlayerPage from './pages/PlayerPage';
import SimulatorPage from './pages/SimulatorPage';
import LineupPage from './pages/LineupPage';
import NotFoundPage from './pages/NotFoundPage';
import MyTeamPage from './pages/MyTeamPage';
import StatsPage from './pages/StatsPage';
import SchedulePage from './pages/SchedulePage';
import { useSearchHistory } from './hooks/useSearchHistory';

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL });

interface SearchPlayer {
  player_id: string;
  player_name: string;
  team_name: string;
  position: string;
}

function NavBar() {
  const [query, setQuery]           = useState('');
  const [focused, setFocused]       = useState(false);
  const [results, setResults]       = useState<SearchPlayer[]>([]);
  const [searching, setSearching]   = useState(false);
  const navigate                    = useNavigate();
  const { history, addHistory, removeHistory, clearHistory } = useSearchHistory();
  const inputRef    = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const timerRef    = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 외부 클릭 시 드롭다운 닫기
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (
        dropdownRef.current && !dropdownRef.current.contains(e.target as Node) &&
        !inputRef.current?.contains(e.target as Node)
      ) {
        setFocused(false);
        setResults([]);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  // 입력 시 실시간 검색
  useEffect(() => {
    if (!query.trim()) { setResults([]); return; }
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setSearching(true);
      api.get(`/api/players?search=${encodeURIComponent(query.trim())}`)
        .then(res => setResults(res.data.players.slice(0, 8)))
        .catch(() => setResults([]))
        .finally(() => setSearching(false));
    }, 300);
  }, [query]);

  // 선수 클릭 시 바로 프로필로 이동
  function handleSelectPlayer(p: SearchPlayer) {
    addHistory(p.player_name);
    navigate(`/player/${p.player_id}`);
    setQuery('');
    setFocused(false);
    setResults([]);
  }

  // 히스토리 검색어 클릭
  function handleHistorySearch(q: string) {
    setQuery(q);
    inputRef.current?.focus();
  }

  // 엔터 시 첫 번째 결과로 이동
  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      if (results.length > 0) {
        handleSelectPlayer(results[0]);
      } else if (query.trim()) {
        addHistory(query.trim());
        navigate(`/player?search=${encodeURIComponent(query.trim())}`);
        setQuery('');
        setFocused(false);
      }
    }
    if (e.key === 'Escape') {
      setFocused(false);
      setResults([]);
    }
  }

  const showDropdown = focused && (results.length > 0 || history.length > 0 || searching);
  const showResults  = query.trim().length > 0;

  return (
    <nav className="bg-gray-900 border-b border-gray-700 px-10 py-4 flex items-center gap-6 relative z-50">
      <Link to="/home" className="text-orange-400 font-black text-lg mr-4 shrink-0">
        ⚾ BallPark
      </Link>

      {[
        { to: '/player',    label: '선수 프로필' },
        { to: '/simulator', label: '경기 시뮬레이터' },
        { to: '/lineup',    label: '타순 배치' },
        { to: '/my-team',   label: '나만의 팀' },
        { to: '/stats',     label: '기록실' },
        { to: '/schedule',  label: '경기 일정' },
      ].map(({ to, label }) => (
        <NavLink
          key={to} to={to}
          className={({ isActive }) =>
            `text-sm transition-colors shrink-0 pb-1 ${
              isActive ? 'text-white font-bold border-b-2 border-orange-400' : 'text-gray-400 hover:text-white'
            }`
          }
        >
          {label}
        </NavLink>
      ))}

      {/* 검색바 */}
      <div className="ml-auto relative w-72">
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm z-10">🔍</span>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setFocused(true)}
          placeholder="선수 이름 검색..."
          className="w-full bg-gray-800 text-white placeholder-gray-500 rounded-lg pl-9 pr-4 py-2 text-sm border border-gray-700 focus:outline-none focus:border-orange-400 transition-colors"
        />
        {query && (
          <button
            onClick={() => { setQuery(''); setResults([]); }}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-400 text-xs"
          >✕</button>
        )}

        {/* 드롭다운 */}
        {showDropdown && (
          <div ref={dropdownRef} className="absolute top-full mt-1 w-full bg-gray-800 border border-gray-700 rounded-xl shadow-xl overflow-hidden">

            {/* 실시간 검색 결과 */}
            {showResults && (
              <>
                {searching && (
                  <div className="px-4 py-3 text-gray-500 text-xs animate-pulse">검색 중...</div>
                )}
                {!searching && results.length === 0 && query.trim() && (
                  <div className="px-4 py-3 text-gray-500 text-xs">검색 결과가 없습니다</div>
                )}
                {results.map((p) => (
                  <button
                    key={p.player_id}
                    onClick={() => handleSelectPlayer(p)}
                    className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-gray-700 transition-colors text-left"
                  >
                    <div className={`w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-black shrink-0 ${
                      p.position === '투수' ? 'bg-blue-600' : 'bg-orange-500'
                    }`}>
                      {p.position === '투수' ? '투' : p.position?.[0] ?? '?'}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-white text-sm font-bold">{p.player_name}</p>
                      <p className="text-gray-500 text-xs">{p.team_name} · {p.position ?? '-'}</p>
                    </div>
                  </button>
                ))}
              </>
            )}

            {/* 검색어 없을 때 히스토리 */}
            {!showResults && history.length > 0 && (
              <>
                <div className="flex items-center justify-between px-4 py-2 border-b border-gray-700">
                  <span className="text-gray-500 text-xs">최근 검색</span>
                  <button onClick={clearHistory} className="text-gray-600 hover:text-red-400 text-xs transition-colors">
                    전체 삭제
                  </button>
                </div>
                {history.map((h) => (
                  <div key={h} className="flex items-center justify-between px-4 py-2 hover:bg-gray-700 transition-colors">
                    <button onClick={() => handleHistorySearch(h)} className="text-gray-300 text-sm text-left flex-1">
                      🕐 {h}
                    </button>
                    <button onClick={() => removeHistory(h)} className="text-gray-600 hover:text-red-400 text-xs ml-2 transition-colors">
                      ✕
                    </button>
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </div>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <NavBar />
      <Routes>
        <Route path="/"             element={<HomePage />} />
        <Route path="/home"         element={<HomePage />} />
        <Route path="/player"       element={<PlayerPage />} />
        <Route path="/player/:playerId" element={<PlayerPage />} />
        <Route path="/simulator"    element={<SimulatorPage />} />
        <Route path="/lineup"       element={<LineupPage />} />
        <Route path="/my-team"      element={<MyTeamPage />} />
        <Route path="/stats"        element={<StatsPage />} />
        <Route path="/schedule"     element={<SchedulePage />} />
        <Route path="*"             element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  );
}