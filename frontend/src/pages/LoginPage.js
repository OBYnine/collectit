import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { login } from '../api/client';
import { useUser } from '../context/UserContext';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { refreshUser, setUser } = useUser();

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = await login(email, password);
      const loggedInUser = data?.user?.id ? data.user : await refreshUser();
      if (!loggedInUser?.id) {
        throw new Error('Не удалось загрузить профиль после входа. Попробуйте ещё раз.');
      }
      setUser(loggedInUser);
      navigate('/profile', { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen app-bg flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="font-bold text-2xl tracking-tight mb-2">
            <span className="text-[#e8a635]">◆ CollectIT</span>
          </div>
          <div className="text-sm text-[#4a5568]">Войдите в аккаунт</div>
        </div>

        <form onSubmit={handleSubmit} className="bg-[#151c2c] border border-white/[.06] rounded-2xl p-7 flex flex-col gap-4">
          {error && (
            <div className="text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-4 py-2.5">
              {error}
            </div>
          )}

          <div>
            <label className="text-[11px] text-[#4a5568] uppercase tracking-widest mb-2 block">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full bg-[#0a0e17] border border-white/[.06] rounded-xl px-4 py-3 text-sm text-[#e8eaf0] outline-none transition-all focus:border-[#e8a635] focus:shadow-[0_0_0_3px_rgba(232,166,53,0.1)] placeholder-[#4a5568]"
              placeholder="your@email.com"
              required
            />
          </div>

          <div>
            <label className="text-[11px] text-[#4a5568] uppercase tracking-widest mb-2 block">Пароль</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full bg-[#0a0e17] border border-white/[.06] rounded-xl px-4 py-3 text-sm text-[#e8eaf0] outline-none transition-all focus:border-[#e8a635] focus:shadow-[0_0_0_3px_rgba(232,166,53,0.1)] placeholder-[#4a5568]"
              placeholder="••••••••"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-[#e8a635] text-[#0a0e17] font-bold py-3 rounded-xl text-sm transition-all hover:bg-[#f0b84a] disabled:opacity-50 disabled:cursor-not-allowed mt-1"
          >
            {loading ? 'Вход...' : 'Войти'}
          </button>

          <div className="text-center text-xs text-[#4a5568]">
            Нет аккаунта?{' '}
            <Link to="/register" className="text-[#e8a635] hover:underline">Зарегистрироваться</Link>
          </div>
        </form>
      </div>
    </div>
  );
}
