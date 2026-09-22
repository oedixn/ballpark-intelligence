import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';

export default function LoginPage() {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? '/home';

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      if (mode === 'register') await register(email, password, displayName);
      else await login(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      if (axios.isAxiosError(err)) setError(err.response?.data?.detail ?? '요청 처리 중 오류가 발생했습니다.');
      else setError('요청 처리 중 오류가 발생했습니다.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-[calc(100vh-73px)] bg-gray-900 flex items-center justify-center px-4">
      <section className="w-full max-w-md bg-gray-800 border border-gray-700 rounded-2xl p-8 shadow-2xl">
        <h1 className="text-white text-2xl font-black">{mode === 'login' ? '로그인' : '회원가입'}</h1>
        <p className="text-gray-400 text-sm mt-2">내 전적은 로그인한 계정에만 안전하게 저장됩니다.</p>

        <form onSubmit={handleSubmit} className="mt-7 space-y-4">
          {mode === 'register' && (
            <label className="block text-gray-300 text-sm">
              닉네임
              <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} minLength={2} maxLength={30} required
                className="mt-1.5 w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2.5 text-white focus:outline-none focus:border-orange-400" />
            </label>
          )}
          <label className="block text-gray-300 text-sm">
            이메일
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email"
              className="mt-1.5 w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2.5 text-white focus:outline-none focus:border-orange-400" />
          </label>
          <label className="block text-gray-300 text-sm">
            비밀번호
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} maxLength={128} required
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              className="mt-1.5 w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2.5 text-white focus:outline-none focus:border-orange-400" />
          </label>
          {error && <p className="text-red-400 text-sm bg-red-400/10 rounded-lg px-3 py-2">{error}</p>}
          <button disabled={submitting} className="w-full bg-orange-500 hover:bg-orange-600 disabled:bg-gray-600 text-white font-bold rounded-lg py-3 transition-colors">
            {submitting ? '처리 중...' : mode === 'login' ? '로그인' : '회원가입'}
          </button>
        </form>

        <button onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}
          className="w-full mt-5 text-gray-400 hover:text-orange-400 text-sm transition-colors">
          {mode === 'login' ? '계정이 없나요? 회원가입' : '이미 계정이 있나요? 로그인'}
        </button>
      </section>
    </main>
  );
}
