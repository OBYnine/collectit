import { useState, useRef, useEffect, useCallback } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { logout, getNotifications, getUnreadCount, markAllRead, isAuthenticated, getChatUnreadCount, getChats, getOrCreateChat, getMessages, sendMessage, agreeChatSale, payChatFromBalance, shipChat, confirmReceipt, rateChat, acknowledgeRating, hideChat } from '../api/client';
import { useUser } from '../context/UserContext';
import { mediaUrl } from '../utils/config';
import { useChatSocket } from '../hooks/useChatSocket';
import { useUserEventsSocket } from '../hooks/useUserEventsSocket';

const tabs = [
  { path: '/profile', label: 'Профиль' },
  { path: '/news',    label: 'Новости' },
  { path: '/search',  label: 'Поиск' },
  { path: '/admin/tickets', label: 'Обращения', adminOnly: true },
];

const MIN_W = 260, MIN_H = 200;

function ChatWindow({ pos, size, setPos, setSize, onClose, activeChat, setActiveChat, onMessagesRead }) {

  const { user }  = useUser();
  const navigate   = useNavigate();
  const action     = useRef(null);
  const startMouse = useRef({ x: 0, y: 0 });
  const startState = useRef({});
  const messagesEndRef = useRef(null);
  const markReadRef = useRef(null);

  // Чат-список
  const [chats, setChats]             = useState([]);
  const [chatsLoading, setChatsLoading] = useState(false);

  // Активный чат
  const [chatId, setChatId]       = useState(null);
  const [chatData, setChatData]   = useState(null); // { status, price, viewer_role, seller_id }
  const [messages, setMessages]   = useState([]);
  const [msgText, setMsgText]     = useState('');
  const [sending, setSending]     = useState(false);
  const [agreeing, setAgreeing]   = useState(false);
  const [hoverStar, setHoverStar] = useState(0);

  // Загрузка списка чатов (когда activeChat = null)
  useEffect(() => {
    if (activeChat) return;
    setChatsLoading(true);
    getChats().then(data => setChats(Array.isArray(data) ? data : [])).finally(() => setChatsLoading(false));
  }, [activeChat]);

  // Открытие конкретного чата: resolve chatId через API
  useEffect(() => {
    if (!activeChat) { setChatId(null); setChatData(null); setMessages([]); return; }
    setChatId(null);
    setChatData(null);
    setMessages([]);
    getOrCreateChat(
      activeChat.username,
      activeChat.itemName || '',
      activeChat.itemImage || '',
      activeChat.itemPrice || null,
      activeChat.sellerIsOther || false,
      activeChat.itemId || null,
    ).then(data => {
      if (data?.id) {
        setChatId(data.id);
        setChatData(data);
      }
    }).catch(() => {});
  }, [
    activeChat?.username,
    activeChat?.itemName,
    activeChat?.itemPrice,
    activeChat?.itemId,
    activeChat?.sellerIsOther,
  ]);

  // Первичная загрузка сообщений (HTTP) + подписка на WebSocket для пушей.
  // WebSocket дешевле и быстрее polling-а 3с; если ws оборвался — useChatSocket
  // сам реконнектится с экспоненциальным backoff.
  useEffect(() => {
    if (!chatId) return undefined;
    let cancelled = false;
    getMessages(chatId).then(data => {
      if (cancelled) return;
      const list = Array.isArray(data) ? data : (data?.messages ?? []);
      setMessages(list);
      if (data?.chat) setChatData(data.chat);
      onMessagesRead();
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [chatId]);

  // WebSocket: новые сообщения и обновления статуса сделки прилетают сюда.
  const handleSocketEvent = useCallback((event) => {
    if (!event?.type) return;
    if (event.type === 'message.created' && event.message) {
      setMessages(prev => {
        // Дедупликация — на случай race c HTTP-ответом в handleSend.
        if (prev.some(m => m.id === event.message.id)) return prev;
        // is_mine считаем по sender_id — у нас нет user-id-а в ChatWindow,
        // но handleSend локально добавит msg с is_mine=true до прихода ws-event,
        // так что фильтр выше не пустит дубль.
        return [...prev, { ...event.message, is_mine: event.message.sender_id === user?.id }];
      });
      onMessagesRead();
      markReadRef.current?.();
    } else if (event.type === 'chat.updated' && event.chat) {
      setChatData(event.chat);
    } else if (event.type === 'chat.price_updated' && event.chat_id) {
      setChatData(prev => (
        prev?.id === event.chat_id
          ? {
              ...prev,
              price: event.price,
              seller_price: event.seller_price ?? event.price,
              buyer_price: event.buyer_price,
              service_fee_amount: event.service_fee_amount,
            }
          : prev
      ));
      setChats(prev => prev.map(chat => (
        chat.id === event.chat_id
          ? {
              ...chat,
              price: event.price,
              seller_price: event.seller_price ?? event.price,
              buyer_price: event.buyer_price,
              service_fee_amount: event.service_fee_amount,
            }
          : chat
      )));
    }
  }, [onMessagesRead, user?.id]);

  const { socketReady, sendMessage: wsSend, markRead } = useChatSocket(chatId, handleSocketEvent);
  useEffect(() => { markReadRef.current = markRead; }, [markRead]);

  // Автоскролл вниз
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function handleSend() {
    const text = msgText.trim();
    if (!text || !chatId || sending) return;
    setSending(true);
    setMsgText('');
    // Сначала пытаемся через WebSocket — мгновенно и без HTTP-роунда.
    // Серверный consumer сам пошлёт нам обратно message.created (его и положим).
    if (socketReady && wsSend(text)) {
      setSending(false);
      return;
    }
    // HTTP fallback (ws ещё коннектится / сервер без channels).
    try {
      const msg = await sendMessage(chatId, text);
      if (msg?.id) setMessages(prev => [...prev, msg]);
    } catch {}
    setSending(false);
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  }

  function handleHeaderMouseDown(e) {
    action.current = 'drag';
    startMouse.current = { x: e.clientX, y: e.clientY };
    startState.current = { ...pos };
    e.preventDefault();
  }

  function handleResizeMouseDown(e) {
    action.current = 'resize';
    startMouse.current = { x: e.clientX, y: e.clientY };
    startState.current = { ...size };
    e.preventDefault();
    e.stopPropagation();
  }

  useEffect(() => {
    function onMove(e) {
      if (!action.current) return;
      const dx = e.clientX - startMouse.current.x;
      const dy = e.clientY - startMouse.current.y;
      if (action.current === 'drag') {
        setPos({
          x: Math.max(0, Math.min(startState.current.x + dx, window.innerWidth  - size.w)),
          y: Math.max(0, Math.min(startState.current.y + dy, window.innerHeight - 60)),
        });
      } else {
        setSize({
          w: Math.max(MIN_W, startState.current.w + dx),
          h: Math.max(MIN_H, startState.current.h + dy),
        });
      }
    }
    function onUp() { action.current = null; }
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup',   onUp);
    return () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup',   onUp);
    };
  }, [size.w]);

  const supportCode = chatData?.support_code || (chatId ? `CHAT-${chatId}` : '');
  const sellerPrice = chatData?.seller_price ?? chatData?.price;
  const buyerPrice = chatData?.buyer_price ?? chatData?.price;
  const serviceFee = chatData?.service_fee_amount ?? null;

  return (
    <div
      className="fixed z-[100] bg-[#151c2c] border border-white/[.08] rounded-2xl shadow-2xl flex flex-col overflow-hidden"
      style={{ left: pos.x, top: pos.y, width: size.w, height: size.h }}
    >
      {/* Заголовок — drag handle */}
      <div
        onMouseDown={handleHeaderMouseDown}
        className="flex items-center justify-between px-4 py-3 border-b border-white/[.06] cursor-grab active:cursor-grabbing select-none shrink-0"
      >
        <div className="flex items-center gap-2 min-w-0">
          {activeChat ? (
            <>
              <button
                onMouseDown={e => e.stopPropagation()}
                onClick={() => setActiveChat(null)}
                className="text-[#4a5568] hover:text-[#8892a4] transition-colors shrink-0"
              >
                <svg viewBox="0 0 16 16" fill="none" className="w-3.5 h-3.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M10 3L5 8l5 5"/>
                </svg>
              </button>
              {activeChat.itemImage ? (
                <div className="w-10 h-10 shrink-0 relative overflow-hidden rounded-lg">
                  <img src={mediaUrl(activeChat.itemImage)} alt="" className="w-full h-full object-cover" />
                  <div className="absolute inset-0" style={{ background: 'linear-gradient(to right, transparent 40%, #151c2c 100%)' }} />
                </div>
              ) : (
                <div className="w-6 h-6 rounded-full bg-[#e8a635] flex items-center justify-center text-[10px] font-bold text-[#0a0e17] shrink-0 overflow-hidden">
                  {activeChat.avatar
                    ? <img src={mediaUrl(activeChat.avatar)} alt="" className="w-full h-full object-cover" />
                    : activeChat.username?.[0]?.toUpperCase()
                  }
                </div>
              )}
              <div
                className="min-w-0 cursor-pointer group"
                onMouseDown={e => e.stopPropagation()}
                onClick={() => { onClose(); navigate(`/users/${activeChat.username}`); }}
              >
                {activeChat.itemName && (
                  <div className="text-sm font-semibold text-[#e8eaf0] truncate group-hover:text-[#e8a635] transition-colors">{activeChat.itemName}</div>
                )}
                <div className={`truncate group-hover:text-[#e8a635] transition-colors ${activeChat.itemName ? 'text-[10px] text-[#4a5568]' : 'text-sm font-semibold text-[#e8eaf0]'}`}>{activeChat.username}</div>
              </div>
            </>
          ) : (
            <>
              <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4 text-[#8892a4] shrink-0" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
              <span className="text-sm font-semibold text-[#e8eaf0]">Сообщения</span>
            </>
          )}
        </div>
        <button
          onMouseDown={e => e.stopPropagation()}
          onClick={onClose}
          className="text-[#4a5568] hover:text-[#8892a4] text-lg leading-none transition-colors shrink-0 ml-2"
        >✕</button>
      </div>

      {/* Контент */}
      {activeChat ? (
        <>
          {supportCode && (
            <div className="px-3 py-2 border-b border-white/[.06] bg-white/[.025] shrink-0">
              <button
                type="button"
                onClick={() => navigator.clipboard?.writeText(supportCode)}
                title="Скопировать код для поддержки"
                className="w-full flex items-center justify-between gap-3 text-left"
              >
                <span className="text-[10px] uppercase tracking-widest text-[#4a5568]">Код для поддержки</span>
                <span className="font-['JetBrains_Mono'] text-[11px] text-[#e8a635]">{supportCode}</span>
              </button>
            </div>
          )}
          {/* Область сообщений */}
          <div className="flex-1 overflow-y-auto px-3 py-3 flex flex-col gap-1.5">
            {!chatId ? (
              <div className="flex-1 flex items-center justify-center">
                <span className="text-xs text-[#4a5568]">Загрузка...</span>
              </div>
            ) : messages.length === 0 ? (
              <div className="flex-1 flex items-center justify-center">
                <span className="text-xs text-[#4a5568]">Начните переписку</span>
              </div>
            ) : (
              messages.map(msg => (
                <div key={msg.id} className={`flex ${msg.is_mine ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-[75%] px-3 py-1.5 rounded-2xl text-sm leading-snug break-words ${
                      msg.is_mine
                        ? 'bg-[#e8a635] text-[#0a0e17] rounded-br-sm'
                        : 'bg-white/[.07] text-[#e8eaf0] rounded-bl-sm'
                    }`}
                  >
                    {msg.text}
                  </div>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Блок сделки */}
          {chatData?.price && chatData?.viewer_role && (
            <div className="px-3 pb-2 shrink-0 flex flex-col gap-1.5">

              {/* Продавец: согласиться */}
              {chatData.viewer_role === 'seller' && chatData.status === 'pending' && (
                <button disabled={agreeing} onClick={async () => {
                  setAgreeing(true);
                  try {
                    const u = await agreeChatSale(chatId);
                    if (u?.status) setChatData(u);
                    else if (u?.detail) alert(u.detail);
                  } catch {}
                  setAgreeing(false);
                }} className="w-full py-2 rounded-xl bg-[#e8a635] text-[#0a0e17] text-sm font-semibold disabled:opacity-50">
                  Согласен продать за {Number(sellerPrice).toLocaleString('ru-RU')} ₽
                </button>
              )}

              {/* Покупатель: оплатить */}
              {chatData.viewer_role === 'buyer' && chatData.status === 'seller_agreed' && (
                <div className="flex flex-col gap-1">
                  <button disabled={agreeing} onClick={async () => {
                    setAgreeing(true);
                    try {
                      const res = await payChatFromBalance(chatId);
                      if (res?.status) { setChatData(res); window.dispatchEvent(new CustomEvent('balance-updated')); }
                      else if (res?.detail) alert(res.detail);
                    } catch {}
                    setAgreeing(false);
                  }} className="w-full py-2 rounded-xl bg-[#e8a635] text-[#0a0e17] text-sm font-semibold disabled:opacity-50">
                    Оплатить {Number(buyerPrice).toLocaleString('ru-RU')} ₽
                  </button>
                  <div className="text-[10px] text-[#4a5568] text-center">
                    Цена продавца {Number(sellerPrice).toLocaleString('ru-RU')} ₽ · сервисный сбор {Number(serviceFee || 0).toLocaleString('ru-RU')} ₽
                  </div>
                </div>
              )}

              {/* Покупатель ожидает отправки */}
              {chatData.viewer_role === 'buyer' && chatData.status === 'paid' && (
                <div className="w-full py-2 rounded-xl bg-white/[.04] text-[#8892a4] text-xs text-center">
                  Деньги удержаны · ожидаем, когда продавец сдаст посылку в СДЭК
                </div>
              )}

              {/* Продавец: заказ СДЭК создан — сдать посылку */}
              {chatData.viewer_role === 'seller' && chatData.status === 'paid' && (
                <div className="flex flex-col gap-2">
                  {chatData.track_number && (
                    <div className="bg-white/[.04] rounded-xl px-3 py-2 text-xs text-[#8892a4]">
                      Заказ СДЭК <span className="font-['JetBrains_Mono'] text-[#e8eaf0]">№ {chatData.track_number}</span> создан.
                      Сдайте посылку в ваш ПВЗ и нажмите кнопку ниже.
                    </div>
                  )}
                  <button disabled={agreeing} onClick={async () => {
                    setAgreeing(true);
                    try { const u = await shipChat(chatId); if (u?.status) setChatData(u); } catch {}
                    setAgreeing(false);
                  }} className="w-full py-2 rounded-xl bg-[#e8a635] text-[#0a0e17] text-sm font-semibold disabled:opacity-50">
                    Я сдал посылку в СДЭК
                  </button>
                </div>
              )}

              {/* Номер заказа СДЭК — оба видят после отправки */}
              {chatData.track_number && ['shipped','arrived'].includes(chatData.status) && (
                <div className="flex items-center gap-2 bg-white/[.04] rounded-xl px-3 py-2">
                  <span className="text-xs text-[#4a5568] shrink-0">СДЭК №</span>
                  <span className="font-['JetBrains_Mono'] text-xs text-[#e8eaf0] flex-1">{chatData.track_number}</span>
                  <a
                    href={`https://www.cdek.ru/ru/tracking/?order_id=${chatData.track_number}`}
                    target="_blank" rel="noreferrer"
                    className="text-[10px] text-[#e8a635] hover:text-white transition-colors shrink-0"
                  >
                    отследить
                  </a>
                </div>
              )}

              {/* Посылка прибыла — покупатель подтверждает получение (выпуск эскроу) */}
              {chatData.status === 'arrived' && chatData.viewer_role === 'buyer' && (
                <div className="flex flex-col gap-2">
                  <p className="text-xs text-[#8892a4] text-center">
                    Посылка прибыла в ваш ПВЗ · заберите и подтвердите получение
                  </p>
                  <button disabled={agreeing} onClick={async () => {
                    setAgreeing(true);
                    try {
                      const u = await confirmReceipt(chatId);
                      if (u?.status) setChatData(u);
                    } catch {}
                    setAgreeing(false);
                  }} className="w-full py-2 rounded-xl bg-[#e8a635] text-[#0a0e17] text-sm font-semibold disabled:opacity-50">
                    Я получил товар · перевести {Number(sellerPrice).toLocaleString('ru-RU')} ₽ продавцу
                  </button>
                  <p className="text-[10px] text-[#4a5568] text-center leading-relaxed">
                    Деньги в эскроу до подтверждения. Если посылка не пришла — обратитесь в поддержку.
                  </p>
                </div>
              )}

              {/* Покупатель оценивает продавца (после подтверждения) */}
              {chatData.status === 'completed' && chatData.viewer_role === 'buyer' && !chatData.buyer_confirmed && (
                <div className="flex flex-col gap-2">
                  <p className="text-xs text-[#8892a4] text-center">Оцените продавца</p>
                  <div className="flex justify-center gap-1" onMouseLeave={() => setHoverStar(0)}>
                    {[1,2,3,4,5].map(star => (
                      <button key={star}
                        onMouseEnter={() => setHoverStar(star)}
                        onClick={async () => {
                          setAgreeing(true);
                          try {
                            const u = await rateChat(chatId, star);
                            if (u?.id) {
                              setChatData(u);
                              setChats(prev => prev.filter(c => c.id !== chatId));
                            }
                          } catch {}
                          setAgreeing(false);
                        }} disabled={agreeing}
                        className="text-2xl leading-none transition-transform hover:scale-110 disabled:opacity-50"
                        style={{ color: star <= hoverStar ? '#e8a635' : '#4a5568' }}
                      >
                        ★
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Продавец — посылка прибыла, ждём подтверждения покупателя */}
              {chatData.status === 'arrived' && chatData.viewer_role === 'seller' && (
                <div className="bg-white/[.04] rounded-xl px-3 py-2 text-xs text-[#8892a4] text-center leading-relaxed">
                  Посылка прибыла в ПВЗ покупателя.<br/>
                  <span className="text-[#4a5568]">Деньги поступят на ваш счёт после подтверждения получения.</span>
                </div>
              )}

              {/* Продавец — после получения, ждём оценки или подтверждает */}
              {chatData.status === 'completed' && chatData.viewer_role === 'seller' && (
                chatData.buyer_confirmed ? (
                  <div className="flex flex-col gap-2">
                    <div className="text-xs text-[#8892a4] text-center">
                      Покупатель оценил сделку:&nbsp;
                      <span className="text-[#e8a635]">{'★'.repeat(chatData.rating)}{'☆'.repeat(5 - chatData.rating)}</span>
                    </div>
                    {!chatData.seller_confirmed && (
                      <button disabled={agreeing} onClick={async () => {
                        setAgreeing(true);
                        try {
                          const u = await acknowledgeRating(chatId);
                          if (u?.id) {
                            setChatData(u);
                            setChats(prev => prev.filter(c => c.id !== chatId));
                          }
                        } catch {}
                        setAgreeing(false);
                      }} className="w-full py-2 rounded-xl bg-white/[.06] text-[#e8eaf0] text-sm font-semibold disabled:opacity-50">
                        Подтвердить и закрыть чат
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="text-xs text-[#4a5568] text-center py-1">
                    Деньги зачислены · ожидаем оценку от покупателя…
                  </div>
                )
              )}
            </div>
          )}

          {/* Поле ввода */}
          <div className="px-3 pb-3 shrink-0 border-t border-white/[.06] pt-3">
            <div className="flex items-center gap-2 bg-white/[.04] rounded-xl px-3 py-2">
              <input
                type="text"
                value={msgText}
                onChange={e => setMsgText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Сообщение..."
                className="flex-1 bg-transparent text-sm text-[#e8eaf0] placeholder-[#4a5568] outline-none"
                disabled={!chatId || sending}
              />
              <button
                onClick={handleSend}
                disabled={!msgText.trim() || !chatId || sending}
                className="text-[#e8a635] disabled:text-[#4a5568] transition-colors"
              >
                <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 2L11 13M22 2L15 22l-4-9-9-4 20-7z"/>
                </svg>
              </button>
            </div>
          </div>
        </>
      ) : (
        /* Список чатов */
        <div className="flex-1 overflow-y-auto">
          {chatsLoading ? (
            <div className="flex items-center justify-center h-full">
              <span className="text-xs text-[#4a5568]">Загрузка...</span>
            </div>
          ) : chats.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full px-6 text-center">
              <svg viewBox="0 0 24 24" fill="none" className="w-10 h-10 text-[#4a5568] mb-3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
              <p className="text-sm text-[#4a5568]">У вас нет чатов</p>
            </div>
          ) : (
            chats.map(chat => {
              const other = chat.other_participant;
              if (!other) return null;
              const avatarSrc = mediaUrl(other.avatar);
              const itemImageSrc = mediaUrl(chat.item_image);
              return (
                <button
                  key={chat.id}
                  onClick={() => setActiveChat({ username: other.username, avatar: avatarSrc, itemName: chat.subject || null, itemImage: itemImageSrc })}
                  className="w-full flex items-center gap-3 px-4 py-3 border-b border-white/[.04] last:border-0 hover:bg-white/[.03] transition-colors text-left"
                >
                  {itemImageSrc ? (
                    <div className="w-9 h-9 shrink-0 relative overflow-hidden rounded-lg">
                      <img src={itemImageSrc} alt="" className="w-full h-full object-cover" />
                      <div className="absolute inset-0" style={{ background: 'linear-gradient(to right, transparent 40%, #151c2c 100%)' }} />
                    </div>
                  ) : (
                    <div className="w-9 h-9 rounded-full bg-[#e8a635] flex items-center justify-center text-xs font-bold text-[#0a0e17] shrink-0 overflow-hidden">
                      {avatarSrc
                        ? <img src={avatarSrc} alt="" className="w-full h-full object-cover" />
                        : other.username?.[0]?.toUpperCase()
                      }
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    {chat.subject
                      ? <>
                          <div className="text-sm font-medium text-[#e8eaf0] truncate">{chat.subject}</div>
                          <div className="text-xs text-[#8892a4] truncate mt-0.5">{other.username}</div>
                        </>
                      : <div className="text-sm font-medium text-[#e8eaf0] truncate">{other.username}</div>
                    }
                    {chat.last_message && (
                      <div className="text-xs text-[#4a5568] truncate mt-0.5">{chat.last_message.text}</div>
                    )}
                  </div>
                  {chat.unread_count > 0 && (
                    <div className="min-w-[18px] h-[18px] px-1 rounded-full bg-[#e8a635] text-[#0a0e17] text-[10px] font-bold flex items-center justify-center shrink-0">
                      {chat.unread_count}
                    </div>
                  )}
                </button>
              );
            })
          )}
        </div>
      )}

      {/* Resize handle */}
      <div
        onMouseDown={handleResizeMouseDown}
        className="absolute bottom-0 right-0 w-5 h-5 cursor-nwse-resize flex items-end justify-end pb-1 pr-1"
      >
        <svg viewBox="0 0 10 10" className="w-3 h-3 text-[#4a5568]" fill="currentColor">
          <path d="M9 3L9 9L3 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none"/>
          <path d="M9 6L9 9L6 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none"/>
        </svg>
      </div>
    </div>
  );
}

function timeAgo(dateStr) {
  const diff = Math.floor((Date.now() - new Date(dateStr)) / 1000);
  if (diff < 60) return 'только что';
  if (diff < 3600) return `${Math.floor(diff / 60)} мин. назад`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} ч. назад`;
  return new Date(dateStr).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
}

function NotificationsDropdown({ notifs, newIds, loading, onClose }) {

  return (
    <div className="absolute right-0 top-[calc(100%+10px)] w-80 bg-[#151c2c] border border-white/[.07] rounded-xl shadow-xl overflow-hidden z-50">
      <div className="px-4 py-3 border-b border-white/[.06] flex items-center justify-between">
        <span className="text-sm font-semibold text-[#e8eaf0]">Уведомления</span>
        <button onClick={onClose} className="text-[#4a5568] hover:text-[#8892a4] text-lg leading-none transition-colors">✕</button>
      </div>

      <div className="max-h-80 overflow-y-auto">
        {loading ? (
          <div className="py-8 text-center text-sm text-[#4a5568]">Загрузка...</div>
        ) : notifs.length === 0 ? (
          <div className="py-8 text-center text-sm text-[#4a5568]">Нет уведомлений</div>
        ) : (
          notifs.map(n => (
            <div
              key={n.id}
              className={`px-4 py-3 border-b border-white/[.04] last:border-0 ${newIds.has(n.id) ? 'bg-[#e8a635]/[.07]' : ''}`}
            >
              <div className="flex items-start gap-2.5">
                {newIds.has(n.id) && (
                  <div className="w-1.5 h-1.5 rounded-full bg-[#e8a635] mt-1.5 shrink-0" />
                )}
                <div className={newIds.has(n.id) ? '' : 'pl-4'}>
                  <div className="text-sm font-medium text-[#e8eaf0] leading-snug">{n.title}</div>
                  <div className="text-xs text-[#8892a4] mt-0.5 leading-relaxed">{n.body}</div>
                  <div className="text-[11px] text-[#4a5568] mt-1">{timeAgo(n.created_at)}</div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default function TopNav() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [bellOpen, setBellOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatPos,  setChatPos]  = useState({ x: window.innerWidth - 380, y: 72 });
  const [chatSize, setChatSize] = useState({ w: 320, h: 400 });
  const [activeChat, setActiveChat] = useState(null);
  const [chatUnreadCount, setChatUnreadCount] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  // Данные уведомлений живут в TopNav — сохраняются между открытиями дропдауна
  const [notifs, setNotifs] = useState([]);
  const [newIds, setNewIds] = useState(new Set());
  const [notifsLoading, setNotifsLoading] = useState(false);
  const { user, setUser } = useUser();
  const menuRef = useRef(null);
  const bellRef = useRef(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const authed = isAuthenticated();

  const handleUserEvent = useCallback((event) => {
    if (event?.type === 'notification.created' && event.notification) {
      setUnreadCount(count => count + 1);
      setNewIds(prev => new Set(prev).add(event.notification.id));
      setNotifs(prev => [event.notification, ...prev.filter(n => n.id !== event.notification.id)].slice(0, 50));
      queryClient.setQueryData(['notif-unread'], (count = 0) => Number(count || 0) + 1);
      if (event.kind === 'chat.message') {
        const count = Number(event.chat_unread_count ?? 0);
        setChatUnreadCount(count);
        queryClient.setQueryData(['chat-unread'], count);
        queryClient.invalidateQueries({ queryKey: ['chat-unread'] });
      }
      return;
    }

    if (event?.type === 'chat.unread_count') {
      const count = Number(event.count || 0);
      setChatUnreadCount(count);
      queryClient.setQueryData(['chat-unread'], count);
      return;
    }

    if (event?.type === 'chat.message.created') {
      const count = Number(event.unread_count ?? 0);
      setChatUnreadCount(count);
      queryClient.setQueryData(['chat-unread'], count);
      queryClient.invalidateQueries({ queryKey: ['chat-unread'] });
      return;
    }

    if (event?.type === 'support.ticket.updated' && event.ticket) {
      const sortUserTickets = (items) => {
        const order = { open: 0, answered: 1, closed: 2 };
        return [...items].sort((a, b) => {
          const statusDiff = (order[a.status] ?? 3) - (order[b.status] ?? 3);
          if (statusDiff !== 0) return statusDiff;
          return new Date(b.updated_at || b.created_at) - new Date(a.updated_at || a.created_at);
        });
      };
      const sortAdminTickets = (items) => {
        const order = { open: 0, answered: 1 };
        return [...items].sort((a, b) => {
          const statusDiff = (order[a.status] ?? 2) - (order[b.status] ?? 2);
          if (statusDiff !== 0) return statusDiff;
          return new Date(b.updated_at || b.created_at) - new Date(a.updated_at || a.created_at);
        });
      };
      const upsertTicket = (prev = []) => {
        if (!Array.isArray(prev)) return prev;
        const exists = prev.some(ticket => ticket.id === event.ticket.id);
        return exists
          ? prev.map(ticket => ticket.id === event.ticket.id ? event.ticket : ticket)
          : [event.ticket, ...prev];
      };
      queryClient.setQueryData(['support-tickets'], (prev = []) => {
        if (prev === undefined) return prev;
        return sortUserTickets(upsertTicket(prev));
      });
      queryClient.setQueryData(['admin-support-tickets'], (prev = []) => {
        if (prev === undefined) return prev;
        if (event.ticket.status === 'closed') {
          return prev.filter(ticket => ticket.id !== event.ticket.id);
        }
        return sortAdminTickets(upsertTicket(prev));
      });
      queryClient.invalidateQueries({ queryKey: ['support-tickets'] });
      queryClient.invalidateQueries({ queryKey: ['admin-support-tickets'] });
    }
  }, [queryClient]);

  const { socketReady: userEventsReady } = useUserEventsSocket(authed, handleUserEvent);

  useEffect(() => {
    if (!authed || !userEventsReady) return;
    getChatUnreadCount()
      .then(d => {
        const count = Number(d?.count || 0);
        setChatUnreadCount(count);
        queryClient.setQueryData(['chat-unread'], count);
      })
      .catch(() => {});
  }, [authed, userEventsReady, queryClient]);

  // Открытие чата через кастомное событие (из ItemModal / WishlistItemModal)
  useEffect(() => {
    function onOpenChat(e) {
      const { username, avatar, itemName, itemImage, itemPrice, itemId, sellerIsOther } = e.detail || {};
      setActiveChat({ username, avatar, itemName, itemImage, itemPrice, itemId, sellerIsOther });
      setChatOpen(true);
    }
    window.addEventListener('open-chat', onOpenChat);
    return () => window.removeEventListener('open-chat', onOpenChat);
  }, []);

  // Счётчики уведомлений и непрочитанных сообщений — через React Query.
  // refetchInterval = 60с (как было), плюс кэшируется между маунтами TopNav.
  const notifQ = useQuery({
    queryKey: ['notif-unread'],
    queryFn:  () => getUnreadCount().then(d => d?.count || 0),
    enabled:  authed,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
  const chatQ = useQuery({
    queryKey: ['chat-unread'],
    queryFn:  () => getChatUnreadCount().then(d => d?.count || 0),
    enabled:  authed,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
  useEffect(() => { if (notifQ.data !== undefined) setUnreadCount(notifQ.data); }, [notifQ.data]);
  useEffect(() => { if (chatQ.data  !== undefined) setChatUnreadCount(chatQ.data);  }, [chatQ.data]);

  const closeNotifications = useCallback(() => {
    setBellOpen(false);
    if (!bellOpen) return;

    setUnreadCount(0);
    queryClient.setQueryData(['notif-unread'], 0);
    markAllRead().then(() => setNewIds(new Set())).catch(() => {});
  }, [bellOpen, queryClient]);

  // Закрытие меню по клику вне
  const handleOutsideClick = useCallback((e) => {
    if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false);
    if (bellRef.current && !bellRef.current.contains(e.target)) closeNotifications();
  }, [closeNotifications]);

  useEffect(() => {
    if (menuOpen || bellOpen) document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [menuOpen, bellOpen, handleOutsideClick]);

  async function handleLogout() {
    await logout();
    setUser(null);
    navigate('/login');
  }

  function handleBellOpen() {
    const opening = !bellOpen;
    if (!opening) {
      closeNotifications();
      return;
    }

    setBellOpen(true);
    setMenuOpen(false);

    if (opening) {
      setNotifsLoading(true);
      getNotifications().then(data => {
        const list = data.results || [];
        setNotifs(list);
        // Фиксируем непрочитанные один раз — Set хранится в TopNav до перезагрузки страницы
        const unread = new Set(list.filter(n => !n.is_read).map(n => n.id));
        setNewIds(unread);
      }).finally(() => setNotifsLoading(false));
    }
  }

  const initials = user?.username?.[0]?.toUpperCase() || 'U';
  const avatarSrc = mediaUrl(user?.avatar);
  const visibleTabs = tabs.filter(t => !t.adminOnly || user?.is_staff);

  return (
    <>
    <nav className="flex items-center justify-between px-8 h-14 bg-[#111827]/80 backdrop-blur-xl border-b border-white/[.06] sticky top-0 z-50">
      <NavLink to="/" className="font-bold text-[22px] tracking-tight no-underline">
        <span className="text-[#e8eaf0] mr-[2px]">◆ Collect</span><span className="text-[#e8a635]">IT</span>
      </NavLink>

      <div className="flex gap-1">
        {visibleTabs.map((t) => (
          <NavLink
            key={t.path}
            to={t.path}
            className={({ isActive }) =>
              `px-5 py-2 text-sm font-medium transition-colors duration-200 no-underline relative ${
                isActive ? 'tab-active' : 'text-[#8892a4] hover:text-[#e8eaf0]'
              }`
            }
          >
            {t.label}
          </NavLink>
        ))}
      </div>

      <div className="flex items-center gap-3">
        {/* Баланс */}
        {isAuthenticated() && user?.balance !== undefined && (
          <button
            onClick={() => navigate('/balance')}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-white/[.04] border border-white/[.06] hover:border-[#e8a635]/40 transition-colors"
          >
            <span className="font-['JetBrains_Mono'] text-sm font-semibold text-[#e8a635]">
              {Number(user.balance).toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}
            </span>
            <span className="text-xs text-[#4a5568]">₽</span>
          </button>
        )}

        {/* Чат */}
        {isAuthenticated() && (
          <button
            onClick={() => setChatOpen(v => !v)}
            className={`w-8 h-8 flex items-center justify-center rounded-lg transition-colors relative ${chatOpen ? 'text-[#e8a635]' : 'text-[#8892a4] hover:text-[#e8eaf0]'}`}
          >
            <svg viewBox="0 0 24 24" fill="none" className="w-5 h-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
            {chatUnreadCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-[#e8a635] text-[#0a0e17] text-[10px] font-bold flex items-center justify-center leading-none">
                {chatUnreadCount > 99 ? '99+' : chatUnreadCount}
              </span>
            )}
          </button>
        )}

        {/* Колокольчик */}
        {isAuthenticated() && (
          <div className="relative" ref={bellRef}>
            <button
              onClick={handleBellOpen}
              className="w-8 h-8 flex items-center justify-center rounded-lg text-[#8892a4] hover:text-[#e8eaf0] transition-colors relative"
            >
              <svg viewBox="0 0 24 24" fill="none" className="w-5 h-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
              </svg>
              {unreadCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-[#e8a635] text-[#0a0e17] text-[10px] font-bold flex items-center justify-center leading-none">
                  {unreadCount > 99 ? '99+' : unreadCount}
                </span>
              )}
            </button>

            {bellOpen && (
              <NotificationsDropdown
                notifs={notifs}
                newIds={newIds}
                loading={notifsLoading}
                onClose={closeNotifications}
              />
            )}
          </div>
        )}

        {/* Аватар + дропдаун */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => { setMenuOpen(v => !v); closeNotifications(); }}
            className="flex items-center gap-1.5 cursor-pointer select-none bg-transparent border-none p-0"
          >
            <div className="w-[34px] h-[34px] rounded-full overflow-hidden bg-[#e8a635] flex items-center justify-center font-bold text-sm text-[#0a0e17] flex-shrink-0">
              {avatarSrc
                ? <img src={avatarSrc} alt="avatar" className="w-full h-full object-cover" />
                : initials
              }
            </div>
            <svg
              className={`w-3 h-3 text-[#8892a4] transition-transform duration-200 ${menuOpen ? 'rotate-180' : ''}`}
              viewBox="0 0 12 12" fill="none"
            >
              <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>

          {menuOpen && (
            <div className="absolute right-0 top-[calc(100%+10px)] w-48 bg-[#151c2c] border border-white/[.07] rounded-xl shadow-xl overflow-hidden z-50">
              {user && (
                <div className="px-4 py-3 border-b border-white/[.06]">
                  <p className="text-[#e8eaf0] text-sm font-medium truncate">{user.username}</p>
                  <p className="text-[#8892a4] text-xs truncate">{user.email}</p>
                </div>
              )}
              <div className="py-1">
                <button
                  onClick={() => { setMenuOpen(false); navigate('/settings'); }}
                  className="w-full text-left px-4 py-2.5 text-sm text-[#8892a4] hover:text-[#e8eaf0] transition-colors duration-150"
                >
                  Настройки
                </button>
                <button
                  onClick={() => { setMenuOpen(false); navigate('/support'); }}
                  className="w-full text-left px-4 py-2.5 text-sm text-[#8892a4] hover:text-[#e8eaf0] transition-colors duration-150"
                >
                  Поддержка
                </button>
              </div>
              <div className="border-t border-white/[.06] py-1">
                <button
                  onClick={handleLogout}
                  className="w-full text-left px-4 py-2.5 text-sm text-[#f87171] hover:bg-[#f87171]/10 transition-colors duration-150"
                >
                  Выйти
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </nav>
    {chatOpen && <ChatWindow pos={chatPos} size={chatSize} setPos={setChatPos} setSize={setChatSize} onClose={() => setChatOpen(false)} activeChat={activeChat} setActiveChat={setActiveChat} onMessagesRead={() => getChatUnreadCount().then(d => setChatUnreadCount(d.count || 0)).catch(() => {})} />}
    </>
  );
}
