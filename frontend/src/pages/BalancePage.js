import { useState, useEffect } from 'react';
import { getTransactions, createPayment, verifyPayment } from '../api/client';
import { useUser } from '../context/UserContext';

const PRESETS = [100, 500, 1000, 2500, 5000];

function formatMoney(val) {
  return Number(val).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatDate(dateStr) {
  return new Date(dateStr).toLocaleString('ru-RU', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function DepositModal({ onClose }) {
  const [amount, setAmount] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    const num = parseFloat(amount);
    if (!num || num <= 0) { setError('Введите сумму больше нуля'); return; }
    setLoading(true);
    setError('');
    try {
      const data = await createPayment(num);
      if (data?.confirmation_url) {
        localStorage.setItem('yookassa_payment_id', data.payment_id);
        window.location.href = data.confirmation_url;
      } else {
        setError(data?.detail || 'Ошибка при создании платежа');
      }
    } catch {
      setError('Ошибка при создании платежа');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      style={{ background: 'rgba(10,14,23,0.88)', backdropFilter: 'blur(6px)' }}
      onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-sm bg-[#151c2c] border border-white/[.08] rounded-2xl p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold text-[#e8eaf0]">Пополнение через ЮKassa</h2>
          <button onClick={onClose} className="text-[#4a5568] hover:text-[#8892a4] text-lg leading-none transition-colors">✕</button>
        </div>

        {/* Тестовая карта */}
        <div className="mb-4 p-3 rounded-xl bg-white/[.03] border border-white/[.06] text-xs text-[#8892a4] space-y-1">
          <div className="text-[#4a5568] uppercase tracking-wider text-[10px] mb-2">Тестовая карта</div>
          <div className="font-['JetBrains_Mono'] text-[#e8eaf0]">5555 5555 5555 4444</div>
          <div className="flex gap-4">
            <span>Срок: <span className="text-[#e8eaf0] font-['JetBrains_Mono']">12/25</span></span>
            <span>CVV: <span className="text-[#e8eaf0] font-['JetBrains_Mono']">000</span></span>
          </div>
        </div>

        {/* Быстрые суммы */}
        <div className="flex flex-wrap gap-2 mb-4">
          {PRESETS.map(p => (
            <button
              key={p}
              onClick={() => setAmount(String(p))}
              className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                amount === String(p)
                  ? 'border-[#e8a635] text-[#e8a635] bg-[#e8a635]/[.08]'
                  : 'border-white/[.08] text-[#8892a4] hover:border-white/[.2]'
              }`}
            >
              {p.toLocaleString('ru-RU')} ₽
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit}>
          <div className="relative mb-4">
            <input
              type="number"
              min="1"
              step="any"
              value={amount}
              onChange={e => { setAmount(e.target.value); setError(''); }}
              placeholder="Своя сумма"
              className="w-full bg-white/[.04] border border-white/[.08] rounded-xl px-4 py-3 text-sm text-[#e8eaf0] placeholder-[#4a5568] outline-none focus:border-[#e8a635]/50 transition-colors pr-10"
            />
            <span className="absolute right-4 top-1/2 -translate-y-1/2 text-sm text-[#4a5568]">₽</span>
          </div>

          {error && <p className="text-xs text-[#f87171] mb-3">{error}</p>}

          <button
            type="submit"
            disabled={loading || !amount}
            className="w-full py-2.5 rounded-xl bg-[#e8a635] text-[#0a0e17] text-sm font-semibold hover:bg-[#d4952e] transition-colors disabled:opacity-50"
          >
            {loading ? 'Создание платежа...' : 'Перейти к оплате →'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default function BalancePage() {
  const { user, setUser } = useUser();
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDeposit, setShowDeposit] = useState(false);
  const [paymentBanner, setPaymentBanner] = useState(null); // 'success' | 'pending' | 'failed'

  // Автоверификация после возврата с ЮKassa
  useEffect(() => {
    const pendingId = localStorage.getItem('yookassa_payment_id');
    if (!pendingId) return;
    localStorage.removeItem('yookassa_payment_id');
    verifyPayment(pendingId).then(data => {
      if (data?.status === 'succeeded' || data?.status === 'already_credited') {
        if (data.balance !== undefined) setUser(prev => ({ ...prev, balance: data.balance }));
        setPaymentBanner('success');
        getTransactions().then(d => setTransactions(Array.isArray(d) ? d : []));
      } else if (data?.status === 'pending' || data?.status === 'waiting_for_capture') {
        setPaymentBanner('pending');
      } else {
        setPaymentBanner('failed');
      }
    }).catch(() => setPaymentBanner('failed'));
  }, [setUser]);

  useEffect(() => {
    getTransactions()
      .then(data => setTransactions(Array.isArray(data) ? data : []))
      .finally(() => setLoading(false));
  }, []);

  const balance = user?.balance ?? 0;
  const deposits = transactions.filter(t => t.kind === 'deposit');
  const expenses = transactions.filter(t => t.kind === 'expense');
  const totalDeposited = deposits.reduce((s, t) => s + parseFloat(t.amount), 0);
  const totalSpent = expenses.reduce((s, t) => s + parseFloat(t.amount), 0);

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">

      {/* Баннер результата платежа */}
      {paymentBanner && (
        <div className={`flex items-center justify-between gap-3 mb-6 px-4 py-3 rounded-xl border text-sm ${
          paymentBanner === 'success' ? 'bg-emerald-500/[.08] border-emerald-500/30 text-emerald-400' :
          paymentBanner === 'pending' ? 'bg-[#e8a635]/[.08] border-[#e8a635]/30 text-[#e8a635]' :
          'bg-[#f87171]/[.08] border-[#f87171]/30 text-[#f87171]'
        }`}>
          <span>
            {paymentBanner === 'success' && '✓ Оплата прошла успешно — баланс пополнен'}
            {paymentBanner === 'pending' && '⏳ Платёж обрабатывается, подождите немного'}
            {paymentBanner === 'failed' && '✕ Платёж не прошёл или был отменён'}
          </span>
          <button onClick={() => setPaymentBanner(null)} className="opacity-50 hover:opacity-100 transition-opacity shrink-0">✕</button>
        </div>
      )}

      {/* Баланс */}
      <div className="text-center mb-10">
        <div className="text-[11px] text-[#4a5568] uppercase tracking-widest mb-3">Баланс</div>
        <div className="font-['JetBrains_Mono'] text-6xl font-bold text-[#e8a635] mb-1">
          {formatMoney(balance)}
        </div>
        <div className="text-lg text-[#8892a4]">₽</div>
      </div>

      {/* Кнопка пополнить */}
      <div className="flex justify-center mb-10">
        <button
          onClick={() => setShowDeposit(true)}
          className="flex items-center gap-2 px-8 py-3 rounded-2xl bg-[#e8a635] text-[#0a0e17] font-semibold text-sm hover:bg-[#d4952e] transition-colors"
        >
          <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M10 4v12M4 10h12"/>
          </svg>
          Пополнить
        </button>
      </div>

      {/* Статистика */}
      <div className="flex gap-4 mb-8">
        <div className="flex-1 bg-[#151c2c] rounded-2xl px-5 py-4 border border-white/[.06]">
          <div className="text-[10px] text-[#4a5568] uppercase tracking-wider mb-1">Пополнено</div>
          <div className="font-['JetBrains_Mono'] text-lg font-semibold text-[#e8eaf0]">
            +{formatMoney(totalDeposited)} <span className="text-sm text-[#4a5568]">₽</span>
          </div>
        </div>
        <div className="flex-1 bg-[#151c2c] rounded-2xl px-5 py-4 border border-white/[.06]">
          <div className="text-[10px] text-[#4a5568] uppercase tracking-wider mb-1">Потрачено</div>
          <div className="font-['JetBrains_Mono'] text-lg font-semibold text-[#e8eaf0]">
            -{formatMoney(totalSpent)} <span className="text-sm text-[#4a5568]">₽</span>
          </div>
        </div>
      </div>

      {/* История */}
      <div className="bg-[#151c2c] rounded-2xl border border-white/[.06] overflow-hidden">
        <div className="px-5 py-4 border-b border-white/[.06]">
          <span className="text-sm font-semibold text-[#e8eaf0]">История операций</span>
        </div>

        {loading ? (
          <div className="py-12 text-center text-sm text-[#4a5568]">Загрузка...</div>
        ) : transactions.length === 0 ? (
          <div className="py-12 text-center text-sm text-[#4a5568]">Операций пока нет</div>
        ) : (
          <div>
            {transactions.map(tx => (
              <div key={tx.id} className="flex items-center gap-4 px-5 py-3.5 border-b border-white/[.04] last:border-0">
                {/* Иконка */}
                <div className={`w-9 h-9 rounded-full flex items-center justify-center shrink-0 ${
                  tx.kind === 'deposit' ? 'bg-emerald-500/[.12]' : 'bg-[#f87171]/[.12]'
                }`}>
                  {tx.kind === 'deposit' ? (
                    <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4 text-emerald-400" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                      <path d="M10 16V4M4 10l6-6 6 6"/>
                    </svg>
                  ) : (
                    <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4 text-[#f87171]" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                      <path d="M10 4v12M4 10l6 6 6-6"/>
                    </svg>
                  )}
                </div>

                {/* Описание */}
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-[#e8eaf0] truncate">{tx.description || (tx.kind === 'deposit' ? 'Пополнение' : 'Списание')}</div>
                  <div className="text-xs text-[#4a5568] mt-0.5">{formatDate(tx.created_at)}</div>
                </div>

                {/* Сумма */}
                <div className={`font-['JetBrains_Mono'] text-sm font-semibold shrink-0 ${
                  tx.kind === 'deposit' ? 'text-emerald-400' : 'text-[#f87171]'
                }`}>
                  {tx.kind === 'deposit' ? '+' : '−'}{formatMoney(tx.amount)} ₽
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {showDeposit && (
        <DepositModal onClose={() => setShowDeposit(false)} />
      )}
    </div>
  );
}
