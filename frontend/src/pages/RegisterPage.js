import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { register, login } from '../api/client';

export default function RegisterPage() {
  const [form, setForm] = useState({ username: '', email: '', password: '', password_confirm: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  function set(field) {
    return e => setForm(f => ({ ...f, [field]: e.target.value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    if (form.password !== form.password_confirm) {
      setError('Пароли не совпадают');
      return;
    }
    setLoading(true);
    try {
      await register(form.username, form.email, form.password, form.password_confirm);
      await login(form.email, form.password);
      navigate('/profile');
    } catch (err) {
      try {
        const parsed = JSON.parse(err.message);
        const first = Object.values(parsed)[0];
        setError(Array.isArray(first) ? first[0] : first);
      } catch {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }

  const fields = [
    { key: 'username',         label: 'Имя пользователя', type: 'text',     placeholder: 'collector42' },
    { key: 'email',            label: 'Email',             type: 'email',    placeholder: 'your@email.com' },
    { key: 'password',         label: 'Пароль',            type: 'password', placeholder: '••••••••' },
    { key: 'password_confirm', label: 'Повторите пароль',  type: 'password', placeholder: '••••••••' },
  ];

  return (
    <div className="min-h-screen app-bg flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="font-bold text-2xl tracking-tight mb-2">
            <span className="text-[#e8a635]">◆ CollectIT</span>
          </div>
          <div className="text-sm text-[#4a5568]">Создайте аккаунт</div>
        </div>

        <form onSubmit={handleSubmit} className="bg-[#151c2c] border border-white/[.06] rounded-2xl p-7 flex flex-col gap-4">
          {error && (
            <div className="text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-4 py-2.5">
              {error}
            </div>
          )}

          {fields.map(f => (
            <div key={f.key}>
              <label className="text-[11px] text-[#4a5568] uppercase tracking-widest mb-2 block">{f.label}</label>
              <input
                type={f.type}
                value={form[f.key]}
                onChange={set(f.key)}
                className="w-full bg-[#0a0e17] border border-white/[.06] rounded-xl px-4 py-3 text-sm text-[#e8eaf0] outline-none transition-all focus:border-[#e8a635] focus:shadow-[0_0_0_3px_rgba(232,166,53,0.1)] placeholder-[#4a5568]"
                placeholder={f.placeholder}
                required
              />
            </div>
          ))}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-[#e8a635] text-[#0a0e17] font-bold py-3 rounded-xl text-sm transition-all hover:bg-[#f0b84a] disabled:opacity-50 disabled:cursor-not-allowed mt-1"
          >
            {loading ? 'Создание...' : 'Зарегистрироваться'}
          </button>

          <div className="text-center text-xs text-[#4a5568]">
            Уже есть аккаунт?{' '}
            <Link to="/login" className="text-[#e8a635] hover:underline">Войти</Link>
          </div>
        </form>
      </div>
    </div>
  );
}
