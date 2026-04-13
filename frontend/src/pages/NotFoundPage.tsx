import { useNavigate } from 'react-router-dom';

export default function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-900 flex flex-col items-center justify-center text-center px-10">
      <div className="text-8xl mb-6">⚾</div>
      <h1 className="text-orange-400 text-8xl font-black mb-4">404</h1>
      <p className="text-white text-2xl font-bold mb-2">페이지를 찾을 수 없어요</p>
      <p className="text-gray-400 text-sm mb-10">
        요청하신 페이지가 존재하지 않거나 이동되었습니다
      </p>
      <div className="flex gap-4">
        <button
          onClick={() => navigate('/home')}
          className="bg-orange-500 hover:bg-orange-600 text-white font-black px-8 py-3 rounded-xl transition-colors"
        >
          🏠 메인으로
        </button>
        <button
          onClick={() => navigate(-1)}
          className="bg-gray-700 hover:bg-gray-600 text-white font-bold px-8 py-3 rounded-xl transition-colors"
        >
          ← 이전 페이지
        </button>
      </div>
    </div>
  );
}