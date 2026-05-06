import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getAdminTickets, updateAdminTicket } from '../api/client';
import { useUser } from '../context/UserContext';

const TOPICS = [
  { value: 'site', label: 'Проблема с сайтом' },
  { value: 'seller', label: 'Проблема с продавцом' },
  { value: 'buyer', label: 'Проблема с покупателем' },
  { value: 'payment', label: 'Проблема с оплатой' },
  { value: 'no_money', label: 'Не пришли деньги' },
  { value: 'cdek', label: 'Проблема со СДЭК' },
  { value: 'deposit', label: 'Проблема с пополнением счета' },
  { value: 'other', label: 'Другое' },
];

const STATUS_LABELS = {
  open: { text: 'Открыт', cls: 'text-[#e8a635] border-[#e8a635]/40 bg-[#e8a635]/10' },
  answered: { text: 'Отвечен', cls: 'text-emerald-400 border-emerald-400/40 bg-emerald-400/10' },
  closed: { text: 'Закрыт', cls: 'text-[#8892a4] border-white/[.1] bg-white/[.03]' },
};

function formatDate(date) {
  return new Date(date).toLocaleString('ru-RU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getTicketMessages(ticket) {
  if (Array.isArray(ticket.messages) && ticket.messages.length > 0) return ticket.messages;
  const messages = [];
  if (ticket.message) {
    messages.push({
      id: `${ticket.id}-legacy-user`,
      is_admin: false,
      text: ticket.message,
      created_at: ticket.created_at,
      sender: ticket.user,
    });
  }
  if (ticket.admin_reply) {
    messages.push({
      id: `${ticket.id}-legacy-admin`,
      is_admin: true,
      text: ticket.admin_reply,
      created_at: ticket.updated_at || ticket.created_at,
      sender: null,
    });
  }
  return messages;
}

function TicketCard({ ticket, onSave, saving }) {
  const [reply, setReply] = useState('');
  const [status, setStatus] = useState(ticket.status || 'open');
  const [error, setError] = useState('');
  const messages = getTicketMessages(ticket);
  const hasAdminAnswer = messages.some((message) => message.is_admin);

  useEffect(() => {
    setReply('');
    setStatus(ticket.status || 'open');
    setError('');
  }, [ticket.id, ticket.status, ticket.updated_at]);

  const dirty = Boolean(reply.trim()) || status !== ticket.status;
  const label = STATUS_LABELS[ticket.status] || STATUS_LABELS.open;

  async function handleSave() {
    if (!reply.trim() && status === 'answered' && !hasAdminAnswer) {
      setError('Для статуса “Отвечен” нужен текст ответа.');
      return;
    }
    setError('');
    try {
      await onSave(ticket.id, {
        ...(reply.trim() ? { admin_reply: reply.trim() } : {}),
        status: status === 'open' && reply.trim() ? 'answered' : status,
      });
      setReply('');
    } catch {
      setError('Не удалось сохранить изменения.');
    }
  }

  return (
    <article className="bg-[#151c2c] border border-white/[.06] rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-white/[.06] flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-[#e8eaf0]">{ticket.user?.username || 'Пользователь'}</h3>
            <span className="text-xs text-[#4a5568]">{ticket.user?.email}</span>
          </div>
          <div className="text-xs text-[#4a5568] mt-1">
            #{ticket.id} · {formatDate(ticket.created_at)}
          </div>
        </div>
        <span className={`text-[10px] font-semibold uppercase tracking-wider px-2.5 py-1 rounded border shrink-0 ${label.cls}`}>
          {label.text}
        </span>
      </div>

      <div className="px-5 py-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]">
        <div>
          <p className="text-[10px] text-[#4a5568] uppercase tracking-wider mb-3">История обращения</p>
          <div className="flex flex-col gap-3">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`rounded-xl p-3 border ${
                  message.is_admin
                    ? 'bg-[#0a0e17] border-[#e8a635]/20'
                    : 'bg-white/[.03] border-white/[.06]'
                }`}
              >
                <div className="flex items-center justify-between gap-3 mb-2">
                  <p className={`text-[10px] uppercase tracking-wider ${message.is_admin ? 'text-[#e8a635]' : 'text-[#4a5568]'}`}>
                    {message.is_admin ? 'Администратор' : message.sender?.username || ticket.user?.username || 'Пользователь'}
                  </p>
                  <span className="text-[10px] text-[#4a5568] shrink-0">{formatDate(message.created_at)}</span>
                </div>
                <p className="text-sm text-[#cbd3df] leading-relaxed whitespace-pre-wrap break-words">
                  {message.text}
                </p>
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <label className="text-xs text-[#8892a4] shrink-0">Статус</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="w-full bg-[#0a0e17] text-[#e8eaf0] text-sm px-3 py-2 rounded-lg border border-white/[.08] outline-none focus:border-[#e8a635]/50"
            >
              <option value="open">Открыт</option>
              <option value="answered">Отвечен</option>
              <option value="closed">Закрыт</option>
            </select>
          </div>

          <textarea
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            rows={6}
            placeholder="Новый ответ администратора..."
            className="w-full bg-[#0a0e17] text-[#e8eaf0] text-sm px-3 py-2.5 rounded-lg border border-white/[.08] outline-none focus:border-[#e8a635]/50 resize-none"
          />

          {error && <p className="text-sm text-red-400">{error}</p>}

          <button
            onClick={handleSave}
            disabled={!dirty || saving}
            className="self-end px-4 py-2 bg-[#e8a635] text-[#0a0e17] text-sm font-semibold rounded-xl disabled:opacity-45 disabled:cursor-not-allowed hover:bg-[#f0b84a] transition-colors"
          >
            {saving ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>
      </div>
    </article>
  );
}

export default function AdminTicketsPage() {
  const { user } = useUser();
  const [savingId, setSavingId] = useState(null);
  const [expandedTopics, setExpandedTopics] = useState({});
  const queryClient = useQueryClient();

  const ticketsQ = useQuery({
    queryKey: ['admin-support-tickets'],
    queryFn: () => getAdminTickets().then((data) => (Array.isArray(data) ? data : [])),
    enabled: Boolean(user?.is_staff),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => updateAdminTicket(id, data),
    onMutate: ({ id }) => setSavingId(id),
    onSuccess: (updated) => {
      queryClient.setQueryData(['admin-support-tickets'], (prev = []) =>
        prev.map((ticket) => (ticket.id === updated.id ? updated : ticket)),
      );
    },
    onSettled: () => setSavingId(null),
  });

  const tickets = ticketsQ.data || [];

  const grouped = useMemo(() => {
    const byTopic = new Map(TOPICS.map((topic) => [topic.value, []]));
    tickets.forEach((ticket) => {
      const key = byTopic.has(ticket.topic) ? ticket.topic : 'other';
      byTopic.get(key).push(ticket);
    });
    return TOPICS
      .map((topic) => {
        const topicTickets = byTopic.get(topic.value) || [];
        return {
          ...topic,
          tickets: topicTickets,
          openCount: topicTickets.filter((ticket) => ticket.status === 'open').length,
        };
      });
  }, [tickets]);

  if (!user) {
    return <div className="max-w-5xl mx-auto px-4 py-16 text-sm text-[#4a5568]">Загрузка...</div>;
  }

  if (!user.is_staff) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-16">
        <h1 className="text-[22px] font-bold tracking-tight mb-2">Обращения</h1>
        <p className="text-sm text-[#8892a4]">Этот раздел доступен только администраторам.</p>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-[22px] font-bold tracking-tight mb-1">Обращения</h1>
          <p className="text-sm text-[#4a5568]">Тикеты пользователей сгруппированы по темам</p>
        </div>
        <div className="bg-white/[.04] border border-white/[.06] rounded-xl px-4 py-2 text-xs text-[#8892a4]">
          Открытых: <span className="text-[#e8a635] font-semibold">{tickets.filter((ticket) => ticket.status === 'open').length}</span>
        </div>
      </div>

      {ticketsQ.isLoading ? (
        <div className="py-16 text-center text-sm text-[#4a5568]">Загрузка обращений...</div>
      ) : ticketsQ.isError ? (
        <div className="bg-[#151c2c] border border-red-400/20 rounded-xl px-5 py-4 text-sm text-red-300">
          Не удалось загрузить обращения.
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {grouped.map((group) => (
            <section key={group.value} className="border-b border-white/[.06] last:border-b-0">
              <button
                onClick={() => setExpandedTopics(prev => ({ ...prev, [group.value]: !prev[group.value] }))}
                className="w-full flex items-center gap-3 px-2 py-4 text-left hover:bg-white/[.02] transition-colors"
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 12 12"
                  fill="none"
                  className={`text-[#8892a4] transition-transform shrink-0 ${expandedTopics[group.value] ? 'rotate-180' : ''}`}
                >
                  <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                <h2 className="text-sm font-semibold text-[#e8eaf0] flex-1">{group.label}</h2>
                <span className="text-xs text-[#4a5568]">{group.tickets.length} всего</span>
                <span className={`text-[10px] font-semibold uppercase tracking-wider px-2.5 py-1 rounded border ${
                  group.openCount > 0
                    ? 'text-[#e8a635] border-[#e8a635]/40 bg-[#e8a635]/10'
                    : 'text-[#4a5568] border-white/[.08] bg-white/[.03]'
                }`}>
                  {group.openCount} открытых
                </span>
              </button>

              {expandedTopics[group.value] && (
                <div className="pt-1 pb-5 flex flex-col gap-3">
                  {group.tickets.length === 0 ? (
                    <div className="px-4 py-8 text-center text-sm text-[#4a5568]">
                      Обращений по этой теме нет.
                    </div>
                  ) : (
                    group.tickets.map((ticket) => (
                      <TicketCard
                        key={ticket.id}
                        ticket={ticket}
                        saving={savingId === ticket.id}
                        onSave={(id, data) => updateMut.mutateAsync({ id, data })}
                      />
                    ))
                  )}
                </div>
              )}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
