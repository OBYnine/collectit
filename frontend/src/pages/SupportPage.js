import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getTickets, createTicket } from '../api/client';

const STATUS_LABEL = {
  open:     { text: 'Открыт',  cls: 'text-[#e8a635] border-[#e8a635]/40' },
  answered: { text: 'Отвечен', cls: 'text-emerald-400 border-emerald-400/40' },
  closed:   { text: 'Закрыт',  cls: 'text-[#4a5568] border-white/[.1]' },
};

function formatDate(d) {
  return new Date(d).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
}

export default function SupportPage() {
  const [showForm, setShowForm] = useState(false);
  const [openId, setOpenId]     = useState(null);

  const [topic, setTopic]       = useState('');
  const [message, setMessage]   = useState('');
  const [error, setError]       = useState('');

  const TOPICS = [
    { value: 'site',    label: 'Проблема с сайтом' },
    { value: 'seller',  label: 'Проблема с продавцом' },
    { value: 'buyer',   label: 'Проблема с покупателем' },
    { value: 'payment', label: 'Проблема с оплатой' },
    { value: 'no_money',label: 'Не пришли деньги' },
    { value: 'cdek',    label: 'Проблема со СДЭК' },
    { value: 'deposit', label: 'Проблема с пополнением счёта' },
    { value: 'other',   label: 'Другое' },
  ];

  const qc = useQueryClient();
  const ticketsQ = useQuery({
    queryKey: ['support-tickets'],
    queryFn:  () => getTickets().then(d => Array.isArray(d) ? d : []),
    staleTime: 60_000,
  });
  const tickets = ticketsQ.data || [];
  const loading = ticketsQ.isLoading;

  const createMut = useMutation({
    mutationFn: ({ topic, message }) => createTicket(topic, message),
    onSuccess: (t) => {
      // Добавляем тикет наверх кэша без повторного запроса.
      qc.setQueryData(['support-tickets'], (prev = []) => [t, ...(prev || [])]);
      setTopic('');
      setMessage('');
      setShowForm(false);
      setOpenId(t.id);
    },
    onError: () => setError('Ошибка при отправке.'),
  });

  function handleSubmit(e) {
    e.preventDefault();
    if (!topic || !message.trim()) { setError('Выберите тему и заполните сообщение.'); return; }
    setError('');
    createMut.mutate({ topic, message: message.trim() });
  }
  const sending = createMut.isPending;

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-[22px] font-bold tracking-tight mb-1">Поддержка</h1>
          <p className="text-sm text-[#4a5568]">Мы ответим на ваш вопрос как можно скорее</p>
        </div>
        {!showForm && (
          <button
            onClick={() => setShowForm(true)}
            className="flex items-center gap-2 px-4 py-2 bg-[#e8a635] text-[#0a0e17] text-sm font-semibold rounded-xl hover:bg-[#f0b84a] transition-colors flex-shrink-0"
          >
            + Новое обращение
          </button>
        )}
      </div>

      {/* Форма нового обращения */}
      {showForm && (
        <form onSubmit={handleSubmit} className="bg-[#151c2c] rounded-2xl p-6 mb-6 border border-white/[.06]">
          <p className="text-[#8892a4] text-xs font-medium uppercase tracking-wider mb-4">Новое обращение</p>
          <div className="flex flex-col gap-4">
            <div>
              <label className="text-[#8892a4] text-xs mb-1.5 block">Тема обращения</label>
              <select
                value={topic}
                onChange={e => setTopic(e.target.value)}
                className="w-full bg-[#0a0e17] text-[#e8eaf0] text-sm px-4 py-2.5 rounded-lg border border-white/[.08] outline-none focus:border-[#e8a635]/50 transition-colors appearance-none cursor-pointer"
              >
                <option value="" disabled>Выберите тему...</option>
                {TOPICS.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[#8892a4] text-xs mb-1.5 block">Сообщение</label>
              <textarea
                value={message}
                onChange={e => setMessage(e.target.value)}
                rows={5}
                placeholder="Опишите проблему подробнее..."
                className="w-full bg-[#0a0e17] text-[#e8eaf0] text-sm px-4 py-2.5 rounded-lg border border-white/[.08] outline-none focus:border-[#e8a635]/50 transition-colors resize-none"
              />
            </div>
            {error && <p className="text-red-400 text-sm">{error}</p>}
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => { setShowForm(false); setError(''); }}
                className="px-4 py-2.5 text-sm rounded-xl border border-white/[.1] text-[#8892a4] hover:text-[#e8eaf0] transition-colors"
              >
                Отмена
              </button>
              <button
                type="submit"
                disabled={sending}
                className="flex-1 py-2.5 bg-[#e8a635] text-[#0a0e17] text-sm font-semibold rounded-xl disabled:opacity-50"
              >
                {sending ? 'Отправка...' : 'Отправить'}
              </button>
            </div>
          </div>
        </form>
      )}

      {/* Список обращений */}
      {loading ? (
        <div className="text-center py-16 text-[#4a5568] text-sm">Загрузка...</div>
      ) : tickets.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-[#4a5568]">
          <div className="text-4xl mb-3">💬</div>
          <div className="text-sm">У вас пока нет обращений</div>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {tickets.map(t => {
            const s = STATUS_LABEL[t.status] || STATUS_LABEL.open;
            const isOpen = openId === t.id;
            return (
              <div
                key={t.id}
                className="bg-[#151c2c] border border-white/[.06] rounded-xl overflow-hidden"
              >
                {/* Шапка тикета */}
                <button
                  onClick={() => setOpenId(isOpen ? null : t.id)}
                  className="w-full flex items-center gap-3 px-6 py-4 text-left"
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-semibold text-[#e8eaf0] truncate">{t.topic_label}</div>
                    <div className="text-xs text-[#4a5568] mt-0.5">{formatDate(t.created_at)}</div>
                  </div>
                  <span className={`text-[10px] font-semibold uppercase tracking-wider px-2.5 py-0.5 rounded border flex-shrink-0 ${s.cls}`}>
                    {s.text}
                  </span>
                  <svg width="14" height="14" viewBox="0 0 12 12" fill="none" className={`text-[#4a5568] transition-transform flex-shrink-0 ${isOpen ? 'rotate-180' : ''}`}>
                    <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </button>

                {/* Раскрытое содержимое */}
                {isOpen && (
                  <div className="px-6 pb-5 border-t border-white/[.06] pt-4 flex flex-col gap-4">
                    {/* Сообщение пользователя */}
                    <div>
                      <p className="text-[10px] text-[#4a5568] uppercase tracking-wider mb-2">Ваше сообщение</p>
                      <p className="text-sm text-[#8892a4] leading-relaxed whitespace-pre-wrap">{t.message}</p>
                    </div>

                    {/* Ответ поддержки */}
                    {t.admin_reply ? (
                      <div className="bg-[#0a0e17] rounded-xl p-4 border border-[#e8a635]/20">
                        <p className="text-[10px] text-[#e8a635] uppercase tracking-wider mb-2">Ответ поддержки</p>
                        <p className="text-sm text-[#e8eaf0] leading-relaxed whitespace-pre-wrap">{t.admin_reply}</p>
                      </div>
                    ) : (
                      <p className="text-xs text-[#4a5568] italic">Ожидаем ответа от поддержки...</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
