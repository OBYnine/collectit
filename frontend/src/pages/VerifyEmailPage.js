import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { verifyEmail } from '../api/client';

export default function VerifyEmailPage() {
  const { token } = useParams();
  const [state, setState] = useState({ status: 'loading', message: 'Подтверждаем почту...' });

  useEffect(() => {
    let cancelled = false;

    async function confirm() {
      try {
        const data = await verifyEmail(token);
        if (!cancelled) {
          setState({
            status: 'success',
            message: data.detail || 'Email подтверждён. Аккаунт создан.',
          });
        }
      } catch (err) {
        if (!cancelled) {
          setState({
            status: 'error',
            message: err.message || 'Ссылка подтверждения недействительна.',
          });
        }
      }
    }

    confirm();
    return () => { cancelled = true; };
  }, [token]);

  const isSuccess = state.status === 'success';

  return (
    <div className="min-h-screen app-bg flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="font-bold text-2xl tracking-tight mb-2">
            <span className="text-[#e8a635]">◆ CollectIT</span>
          </div>
          <div className="text-sm text-[#4a5568]">Подтверждение почты</div>
        </div>

        <div className="bg-[#151c2c] border border-white/[.06] rounded-2xl p-7 flex flex-col gap-4">
          <div className={isSuccess ? 'text-sm text-emerald-300' : state.status === 'error' ? 'text-sm text-red-300' : 'text-sm text-[#e8eaf0]'}>
            {state.message}
          </div>

          {state.status !== 'loading' && (
            <Link
              to={isSuccess ? '/login' : '/register'}
              className="w-full text-center bg-[#e8a635] text-[#0a0e17] font-bold py-3 rounded-xl text-sm transition-all hover:bg-[#f0b84a]"
            >
              {isSuccess ? 'Войти' : 'Зарегистрироваться заново'}
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
