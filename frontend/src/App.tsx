import { BrowserRouter, Routes, Route, Link, useNavigate } from 'react-router-dom';
import { useState, useRef, useEffect } from 'react';
import HomePage from './pages/HomePage';
import PlayerPage from './pages/PlayerPage';
import SimulatorPage from './pages/SimulatorPage';
import LineupPage from './pages/LineupPage';
import { useSearchHistory } from './hooks/useSearchHistory';

function NavBar() {
  const [query, setQuery] = useState('');
  const [focused, setFocused] = useState(false);
  const navigate = useNavigate();
  const { history, addHistory, removeHistory, clearHistory } = useSearchHistory();
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // 외부 클릭 시 드롭다운 닫기
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node) &&
        !inputRef.current?.contains(e.target as Node)
      ) {
        setFocused(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleSearch = (q: string) => {
    if (!q.trim()) return;
    addHistory(q.trim());
    navigate(`/player?search=${q.trim()}`);
    setQuery('');
    setFocused(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleSearch(query);
  };

  const showDropdown = focused && history.length > 0;

  return (
    <nav className="bg-gray-900 border-b border-gray-700 px-10 py-4 flex items-center gap-6 relative z-50">
      {/* 로고 */}
      <Link to="/home" className="text-orange-400 font-black text-lg mr-4 shrink-0">
        ⚾ BallPark
      </Link>

      {/* 메뉴 */}
      <Link to="/player" className="text-gray-400 hover:text-white text-sm transition-colors shrink-0">
        선수 프로필
      </Link>
      <Link to="/simulator" className="text-gray-400 hover:text-white text-sm transition-colors shrink-0">
        경기 시뮬레이터
      </Link>
      <Link to="/lineup" className="text-gray-400 hover:text-white text-sm transition-colors shrink-0">
        타순 배치
      </Link>

      {/* 검색바 + 히스토리 드롭다운 */}
      <div className="ml-auto relative w-64">
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

        {/* 히스토리 드롭다운 */}
        {showDropdown && (
          <div
            ref={dropdownRef}
            className="absolute top-full mt-1 w-full bg-gray-800 border border-gray-700 rounded-xl shadow-xl overflow-hidden"
          >
            {/* 헤더 */}
            <div className="flex items-center justify-between px-4 py-2 border-b border-gray-700">
              <span className="text-gray-500 text-xs">최근 검색</span>
              <button
                onClick={clearHistory}
                className="text-gray-600 hover:text-red-400 text-xs transition-colors"
              >
                전체 삭제
              </button>
            </div>

            {/* 히스토리 목록 */}
            {history.map((h) => (
              <div
                key={h}
                className="flex items-center justify-between px-4 py-2 hover:bg-gray-700 transition-colors"
              >
                <button
                  onClick={() => handleSearch(h)}
                  className="text-gray-300 text-sm text-left flex-1"
                >
                  🕐 {h}
                </button>
                <button
                  onClick={() => removeHistory(h)}
                  className="text-gray-600 hover:text-red-400 text-xs ml-2 transition-colors"
                >
                  ✕
                </button>
              </div>
            ))}
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
        <Route path="/" element={<HomePage />} />
        <Route path="/home" element={<HomePage />} />
        <Route path="/player" element={<PlayerPage />} />
        <Route path="/simulator" element={<SimulatorPage />} />
        <Route path="/lineup" element={<LineupPage />} />
      </Routes>
    </BrowserRouter>
  );
}