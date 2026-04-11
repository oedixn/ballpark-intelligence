import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import PlayerPage from './pages/PlayerPage';
import SimulatorPage from './pages/SimulatorPage';

export default function App() {
  return (
    <BrowserRouter>
      {/* 네비게이션 바 */}
      <nav className="bg-gray-900 border-b border-gray-700 px-10 py-4 flex gap-6">
        <span className="text-orange-400 font-black text-lg mr-6">⚾ BallPark</span>
        <Link to="/" className="text-gray-400 hover:text-white text-sm transition-colors">
          선수 프로필
        </Link>
        <Link to="/simulator" className="text-gray-400 hover:text-white text-sm transition-colors">
          경기 시뮬레이터
        </Link>
      </nav>

      {/* 페이지 라우팅 */}
      <Routes>
        <Route path="/" element={<PlayerPage />} />
        <Route path="/simulator" element={<SimulatorPage />} />
      </Routes>
    </BrowserRouter>
  );
}