import { useState, useEffect } from 'react';
import { createPayment, createWithdrawal, getTransactions, getWithdrawals, verifyPayment } from '../api/client';
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

const PAYMENT_REASON_MESSAGES = {
  '3d_secure_failed': 'Не пройдена 3-D Secure проверка. Попробуйте повторить оплату или используйте другую карту.',
  call_issuer: 'Банк отклонил оплату. Обратитесь в банк или используйте другую карту.',
  card_expired: 'Срок действия карты истек. Используйте другую карту.',
  country_forbidden: 'Оплата картой, выпущенной в этой стране, запрещена. Используйте другое платежное средство.',
  fraud_suspected: 'Платеж отклонен из-за подозрения в мошенничестве. Используйте другое платежное средство.',
  general_decline: 'Платеж отклонен без детальной причины. Обратитесь в банк или попробуйте другой способ оплаты.',
  insufficient_funds: 'На платежном средстве недостаточно средств. Пополните баланс или используйте другую карту.',
  invalid_card_number: 'Неверно указан номер карты. Проверьте данные и попробуйте снова.',
  invalid_csc: 'Неверно указан CVV/CVC-код. Проверьте данные и попробуйте снова.',
  issuer_unavailable: 'Банк сейчас недоступен. Повторите оплату позже или используйте другую карту.',
  payment_method_limit_exceeded: 'Превышен лимит платежей для карты или магазина. Используйте другой способ оплаты или повторите позже.',
  payment_method_restricted: 'Операции этим платежным средством запрещены. Обратитесь в банк или используйте другую карту.',
};

function paymentFailureMessage(data) {
  const apiMessage = data?.message || data?.detail || data?.cancellation_details?.message;
  if (apiMessage) return apiMessage;
  const reason = data?.cancellation_details?.reason;
  if (reason && PAYMENT_REASON_MESSAGES[reason]) return PAYMENT_REASON_MESSAGES[reason];
  return 'Платеж не прошел или был отменен. Попробуйте повторить оплату или выбрать другой способ.';
}

function apiErrorText(data, fallback = 'Проверьте данные и попробуйте снова.') {
  if (!data) return fallback;
  if (typeof data === 'string') return data;
  if (data.detail) return data.detail;
  const parts = Object.values(data).flat().filter(Boolean);
  return parts.length ? parts.join(' ') : fallback;
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

function WithdrawModal({ user, onClose, onCreated }) {
  const [method, setMethod] = useState('sbp');
  const [amount, setAmount] = useState('');
  const [fullName, setFullName] = useState('');
  const [phone, setPhone] = useState(user?.phone || '');
  const [bankName, setBankName] = useState('');
  const [cardNumber, setCardNumber] = useState('');
  const [cardHolder, setCardHolder] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    const num = parseFloat(amount);
    if (!num || num <= 0) { setError('Введите сумму больше нуля'); return; }
    setLoading(true);
    setError('');
    try {
      const payload = {
        amount,
        method,
        full_name: fullName,
        ...(method === 'sbp'
          ? { phone, bank_name: bankName }
          : { card_number: cardNumber, card_holder: cardHolder }),
      };
      const data = await createWithdrawal(payload);
      if (data?.withdrawal) {
        onCreated(data);
        onClose();
      } else {
        setError(apiErrorText(data, 'Не удалось создать заявку на вывод.'));
      }
    } catch {
      setError('Не удалось создать заявку на вывод.');
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
      <div className="w-full max-w-md bg-[#151c2c] border border-white/[.08] rounded-2xl p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold text-[#e8eaf0]">Заявка на вывод</h2>
          <button onClick={onClose} className="text-[#4a5568] hover:text-[#8892a4] text-lg leading-none transition-colors">✕</button>
        </div>

        <div className="grid grid-cols-2 gap-2 mb-5">
          {[
            ['sbp', 'СБП'],
            ['card', 'Карта'],
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => { setMethod(value); setError(''); }}
              className={`py-2 rounded-xl text-sm border transition-colors ${
                method === value
                  ? 'border-[#e8a635] text-[#e8a635] bg-[#e8a635]/[.08]'
                  : 'border-white/[.08] text-[#8892a4] hover:border-white/[.2]'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="relative">
            <input
              type="number"
              min="100"
              step="0.01"
              value={amount}
              onChange={e => { setAmount(e.target.value); setError(''); }}
              placeholder="Сумма вывода"
              className="w-full bg-white/[.04] border border-white/[.08] rounded-xl px-4 py-3 text-sm text-[#e8eaf0] placeholder-[#4a5568] outline-none focus:border-[#e8a635]/50 transition-colors pr-10"
            />
            <span className="absolute right-4 top-1/2 -translate-y-1/2 text-sm text-[#4a5568]">₽</span>
          </div>

          <input
            value={fullName}
            onChange={e => { setFullName(e.target.value); setError(''); }}
            placeholder="Фамилия и имя получателя"
            className="w-full bg-white/[.04] border border-white/[.08] rounded-xl px-4 py-3 text-sm text-[#e8eaf0] placeholder-[#4a5568] outline-none focus:border-[#e8a635]/50 transition-colors"
          />

          {method === 'sbp' ? (
            <>
              <input
                type="tel"
                value={phone}
                onChange={e => { setPhone(e.target.value); setError(''); }}
                placeholder="+7 900 000 00 00"
                className="w-full bg-white/[.04] border border-white/[.08] rounded-xl px-4 py-3 text-sm text-[#e8eaf0] placeholder-[#4a5568] outline-none focus:border-[#e8a635]/50 transition-colors"
              />
              <input
                value={bankName}
                onChange={e => { setBankName(e.target.value); setError(''); }}
                placeholder="Банк для СБП"
                className="w-full bg-white/[.04] border border-white/[.08] rounded-xl px-4 py-3 text-sm text-[#e8eaf0] placeholder-[#4a5568] outline-none focus:border-[#e8a635]/50 transition-colors"
              />
            </>
          ) : (
            <>
              <input
                inputMode="numeric"
                value={cardNumber}
                onChange={e => { setCardNumber(e.target.value); setError(''); }}
                placeholder="Номер карты"
                className="w-full bg-white/[.04] border border-white/[.08] rounded-xl px-4 py-3 text-sm text-[#e8eaf0] placeholder-[#4a5568] outline-none focus:border-[#e8a635]/50 transition-colors"
              />
              <input
                value={cardHolder}
                onChange={e => { setCardHolder(e.target.value); setError(''); }}
                placeholder="Держатель карты"
                className="w-full bg-white/[.04] border border-white/[.08] rounded-xl px-4 py-3 text-sm text-[#e8eaf0] placeholder-[#4a5568] outline-none focus:border-[#e8a635]/50 transition-colors"
              />
            </>
          )}

          <div className="p-3 rounded-xl bg-white/[.03] border border-white/[.06] text-[11px] text-[#8892a4] leading-relaxed">
            Деньги резервируются сразу. Администратор проверит заявку и выполнит перевод вручную.
          </div>

          {error && <p className="text-xs text-[#f87171]">{error}</p>}

          <button
            type="submit"
            disabled={loading || !amount}
            className="w-full py-2.5 rounded-xl bg-[#e8a635] text-[#0a0e17] text-sm font-semibold hover:bg-[#d4952e] transition-colors disabled:opacity-50"
          >
            {loading ? 'Создание заявки...' : 'Создать заявку'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default function BalancePage() {
  const { user, setUser } = useUser();
  const [transactions, setTransactions] = useState([]);
  const [withdrawals, setWithdrawals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDeposit, setShowDeposit] = useState(false);
  const [showWithdraw, setShowWithdraw] = useState(false);
  const [paymentBanner, setPaymentBanner] = useState(null);

  // Автоверификация после возврата с ЮKassa
  useEffect(() => {
    const pendingId = localStorage.getItem('yookassa_payment_id');
    if (!pendingId) return;
    localStorage.removeItem('yookassa_payment_id');
    verifyPayment(pendingId).then(data => {
      if (data?.status === 'succeeded' || data?.status === 'already_credited') {
        if (data.balance !== undefined) setUser(prev => ({ ...prev, balance: data.balance }));
        setPaymentBanner({
          type: 'success',
          title: 'Оплата прошла успешно - баланс пополнен',
        });
        getTransactions().then(d => setTransactions(Array.isArray(d) ? d : []));
      } else if (data?.status === 'pending' || data?.status === 'waiting_for_capture') {
        setPaymentBanner({
          type: 'pending',
          title: 'Платеж обрабатывается',
          detail: 'Подождите немного, затем обновите страницу баланса.',
        });
      } else {
        setPaymentBanner({
          type: 'failed',
          title: 'Платеж не прошел',
          detail: paymentFailureMessage(data),
        });
      }
    }).catch(() => setPaymentBanner({
      type: 'failed',
      title: 'Не удалось проверить платеж',
      detail: 'Проверьте подключение и откройте страницу баланса еще раз.',
    }));
  }, [setUser]);

  useEffect(() => {
    Promise.all([getTransactions(), getWithdrawals()])
      .then(([txData, withdrawalData]) => {
        setTransactions(Array.isArray(txData) ? txData : []);
        setWithdrawals(Array.isArray(withdrawalData) ? withdrawalData : []);
      })
      .finally(() => setLoading(false));
  }, []);

  const balance = user?.balance ?? 0;
  const deposits = transactions.filter(t => t.kind === 'deposit');
  const expenses = transactions.filter(t => t.kind === 'expense');
  const totalDeposited = deposits.reduce((s, t) => s + parseFloat(t.amount), 0);
  const totalSpent = expenses.reduce((s, t) => s + parseFloat(t.amount), 0);
  const activeWithdrawals = withdrawals.filter(w => ['pending', 'processing'].includes(w.status));
  const totalReserved = activeWithdrawals.reduce((s, w) => s + parseFloat(w.amount), 0);

  function handleWithdrawalCreated(data) {
    if (data.balance !== undefined) {
      setUser(prev => ({ ...prev, balance: data.balance }));
    }
    if (data.withdrawal) {
      setWithdrawals(prev => [data.withdrawal, ...prev]);
    }
    getTransactions().then(d => setTransactions(Array.isArray(d) ? d : []));
    setPaymentBanner({
      type: 'success',
      title: 'Заявка на вывод создана',
      detail: 'Сумма зарезервирована. Администратор обработает заявку вручную.',
    });
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">

      {/* Баннер результата платежа */}
      {paymentBanner && (
        <div className={`flex items-center justify-between gap-3 mb-6 px-4 py-3 rounded-xl border text-sm ${
          paymentBanner.type === 'success' ? 'bg-emerald-500/[.08] border-emerald-500/30 text-emerald-400' :
          paymentBanner.type === 'pending' ? 'bg-[#e8a635]/[.08] border-[#e8a635]/30 text-[#e8a635]' :
          'bg-[#f87171]/[.08] border-[#f87171]/30 text-[#f87171]'
        }`}>
          <div className="min-w-0">
            <div>{paymentBanner.title}</div>
            {paymentBanner.detail && (
              <div className="mt-1 text-xs leading-snug opacity-85">{paymentBanner.detail}</div>
            )}
          </div>
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

      {/* Кнопки баланса */}
      <div className="flex justify-center gap-3 mb-10">
        <button
          onClick={() => setShowDeposit(true)}
          className="flex items-center gap-2 px-8 py-3 rounded-2xl bg-[#e8a635] text-[#0a0e17] font-semibold text-sm hover:bg-[#d4952e] transition-colors"
        >
          <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M10 4v12M4 10h12"/>
          </svg>
          Пополнить
        </button>
        <button
          onClick={() => setShowWithdraw(true)}
          className="flex items-center gap-2 px-8 py-3 rounded-2xl bg-[#151c2c] border border-white/[.08] text-[#e8eaf0] font-semibold text-sm hover:border-white/[.18] transition-colors"
        >
          <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M10 4v12M4 10l6 6 6-6"/>
          </svg>
          Вывести
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
        <div className="flex-1 bg-[#151c2c] rounded-2xl px-5 py-4 border border-white/[.06]">
          <div className="text-[10px] text-[#4a5568] uppercase tracking-wider mb-1">В выводе</div>
          <div className="font-['JetBrains_Mono'] text-lg font-semibold text-[#e8eaf0]">
            {formatMoney(totalReserved)} <span className="text-sm text-[#4a5568]">₽</span>
          </div>
        </div>
      </div>

      {/* Заявки на вывод */}
      {withdrawals.length > 0 && (
        <div className="bg-[#151c2c] rounded-2xl border border-white/[.06] overflow-hidden mb-8">
          <div className="px-5 py-4 border-b border-white/[.06]">
            <span className="text-sm font-semibold text-[#e8eaf0]">Заявки на вывод</span>
          </div>
          <div>
            {withdrawals.slice(0, 5).map(w => (
              <div key={w.id} className="flex items-center gap-4 px-5 py-3.5 border-b border-white/[.04] last:border-0">
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-[#e8eaf0] truncate">
                    {w.method_label} · {w.status_label}
                  </div>
                  <div className="text-xs text-[#4a5568] mt-0.5">
                    {formatDate(w.created_at)}
                    {w.method === 'sbp' && w.payout_details?.bank_name ? ` · ${w.payout_details.bank_name}` : ''}
                    {w.method === 'card' && w.payout_details?.card_number ? ` · ${w.payout_details.card_number}` : ''}
                  </div>
                </div>
                <div className="font-['JetBrains_Mono'] text-sm font-semibold text-[#e8a635] shrink-0">
                  {formatMoney(w.amount)} ₽
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

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
      {showWithdraw && (
        <WithdrawModal
          user={user}
          onClose={() => setShowWithdraw(false)}
          onCreated={handleWithdrawalCreated}
        />
      )}
    </div>
  );
}
