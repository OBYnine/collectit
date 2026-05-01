import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { searchItems, toggleWishlist, getWishlist, isAuthenticated } from '../api/client';
import { API_BASE } from '../utils/config';
import { formatPrice } from '../utils/format';
import { useDebounce } from '../hooks/useDebounce';
import { GridSkeleton } from '../components/Skeleton';

function HeartButton({ liked, onClick }) {
  return (
    <button
      onClick={onClick}
      className="w-7 h-7 flex items-center justify-center transition-colors duration-150"
      title={liked ? 'Убрать из вишлиста' : 'Добавить в вишлист'}
    >
      <svg viewBox="0 0 20 18" fill={liked ? '#e8a635' : 'none'} className="w-5 h-5" stroke={liked ? '#e8a635' : '#4a5568'} strokeWidth="1.6">
        <path d="M10 16.5S1.5 11 1.5 5.5A4.5 4.5 0 0 1 10 3.34 4.5 4.5 0 0 1 18.5 5.5C18.5 11 10 16.5 10 16.5z"/>
      </svg>
    </button>
  );
}

function ItemModal({ item, liked, onToggleLike, onClose }) {
  const navigate = useNavigate();

  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') onClose(); }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const imageSrc = item.image
    ? (item.image.startsWith('http') ? item.image : `${API_BASE}${item.image}`)
    : null;
  const avatarSrc = item.owner_avatar
    ? (item.owner_avatar.startsWith('http') ? item.owner_avatar : `${API_BASE}${item.owner_avatar}`)
    : null;
  const avatarInitial = item.owner_username?.[0]?.toUpperCase() || 'U';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      style={{ background: 'rgba(10,14,23,0.88)', backdropFilter: 'blur(6px)' }}
      onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-lg bg-[#151c2c] border border-white/[.08] rounded-2xl overflow-hidden max-h-[90vh] overflow-y-auto">
        {/* Фото */}
        <div className="h-56 bg-[#0d1321] flex items-center justify-center overflow-hidden relative">
          {imageSrc
            ? <img src={imageSrc} alt={item.name} className="w-full h-full object-cover" />
            : <span className="text-6xl opacity-20">📦</span>
          }
          <button
            onClick={onClose}
            className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center rounded-lg bg-black/40 text-white/70 hover:text-white transition-colors text-lg"
          >
            ✕
          </button>
        </div>

        <div className="p-6">
          {/* Название + сердечко */}
          <div className="flex items-start justify-between gap-3 mb-4">
            <h2 className="text-lg font-bold leading-snug flex-1">{item.name}</h2>
            {isAuthenticated() && (
              <HeartButton liked={liked} onClick={e => { e.stopPropagation(); onToggleLike(item.id); }} />
            )}
          </div>

          {/* Описание */}
          {item.description && (
            <p className="text-sm text-[#8892a4] leading-relaxed mb-5">{item.description}</p>
          )}

          {/* Детали */}
          {item.price && (
            <div className="mb-6">
              <div className="text-[10px] text-[#4a5568] uppercase tracking-wider mb-0.5">Цена</div>
              <div className="font-['JetBrains_Mono'] text-[#e8a635] font-bold text-base">{formatPrice(item.price)}</div>
            </div>
          )}

          {/* Продавец */}
          <div className="border-t border-white/[.06] pt-4">
            <div className="text-[10px] text-[#4a5568] uppercase tracking-wider mb-3">Продавец</div>
            <div
              className="flex items-center gap-3 cursor-pointer group"
              onClick={() => { onClose(); navigate(`/users/${item.owner_username}`); }}
            >
              <div className="w-10 h-10 rounded-full bg-[#e8a635] flex items-center justify-center font-bold text-sm text-[#0a0e17] shrink-0 overflow-hidden">
                {avatarSrc
                  ? <img src={avatarSrc} alt="" className="w-full h-full object-cover" />
                  : avatarInitial
                }
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold group-hover:text-[#e8a635] transition-colors">{item.owner_username}</div>
                {item.owner_bio && (
                  <div className="text-xs text-[#4a5568] truncate">{item.owner_bio}</div>
                )}
              </div>
              <svg className="w-4 h-4 text-[#4a5568] group-hover:text-[#e8a635] transition-colors shrink-0" viewBox="0 0 16 16" fill="none">
                <path d="M6 3l5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            {isAuthenticated() && (
              <button
                onClick={() => {
                  onClose();
                  window.dispatchEvent(new CustomEvent('open-chat', { detail: { username: item.owner_username, avatar: avatarSrc, itemName: item.name, itemImage: imageSrc, itemPrice: item.price, itemId: item.id, sellerIsOther: true } }));
                }}
                className="mt-3 w-full flex items-center justify-center gap-2 py-2 rounded-xl bg-white/[.04] hover:bg-white/[.07] text-sm text-[#8892a4] hover:text-[#e8eaf0] transition-colors"
              >
                <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
                Написать продавцу
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function SearchPage() {
  const [query, setQuery]               = useState('');
  const debouncedQuery                  = useDebounce(query, 350);
  const [selectedItem, setSelectedItem] = useState(null);
  const qc = useQueryClient();

  // Вишлист — кэш на 5 мин, перезапрашивается только если invalidateQueries.
  const wishlistQ = useQuery({
    queryKey: ['wishlist'],
    queryFn:  () => getWishlist().then(d => d?.results || []),
    enabled:  isAuthenticated(),
    staleTime: 5 * 60_000,
  });
  const likedIds = React.useMemo(
    () => new Set((wishlistQ.data || []).map(i => i.id)),
    [wishlistQ.data],
  );

  // Поиск — отдельный query на каждый debouncedQuery. React Query кэширует
  // результаты по ключу, поэтому повторный набор того же запроса = мгновенно.
  const itemsQ = useQuery({
    queryKey: ['search', debouncedQuery],
    queryFn:  () => searchItems(debouncedQuery ? { q: debouncedQuery } : {}).then(d => d?.results || []),
    keepPreviousData: true,
    staleTime: 60_000,
  });
  const items   = itemsQ.data || [];
  const loading = itemsQ.isLoading;

  // Mutation: optimistic update — мгновенно меняем likedIds, ждём API.
  const likeMut = useMutation({
    mutationFn: toggleWishlist,
    onSuccess: (data, itemId) => {
      qc.setQueryData(['wishlist'], (prev = []) => {
        const arr = Array.isArray(prev) ? prev : [];
        if (data.liked) {
          return arr.some(i => i.id === itemId) ? arr : [...arr, { id: itemId }];
        }
        return arr.filter(i => i.id !== itemId);
      });
      setSelectedItem(prev => prev?.id === itemId ? { ...prev, is_liked: data.liked } : prev);
    },
  });

  const handleToggleLike = useCallback((itemId) => {
    likeMut.mutate(itemId);
  }, [likeMut]);

  return (
    <div className="max-w-5xl mx-auto px-10 py-9">
      <h1 className="text-[22px] font-bold tracking-tight mb-5 anim-in">Поиск предметов</h1>

      <div className="relative mb-4 anim-in anim-d1">
        <span className="absolute left-4 top-1/2 -translate-y-1/2 text-[#4a5568] text-base pointer-events-none select-none">⌕</span>
        <input
          className="w-full pl-10 pr-4 py-3 bg-[#151c2c] border border-white/[.06] rounded-xl text-sm text-[#e8eaf0] outline-none transition-all duration-200 placeholder-[#4a5568] focus:border-[#e8a635] focus:shadow-[0_0_0_3px_rgba(232,166,53,0.1)]"
          placeholder="Поиск монет, значков, марок..."
          value={query}
          onChange={e => setQuery(e.target.value)}
        />
      </div>

      {loading && items.length === 0 && (
        <div className="mt-7">
          <GridSkeleton count={8} />
        </div>
      )}

      <div className="grid gap-4 mt-7" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))' }}>
        {items.map((item, i) => (
          <div
            key={item.id}
            onClick={() => setSelectedItem(item)}
            className={`bg-[#151c2c] border border-white/[.06] rounded-xl overflow-hidden cursor-pointer transition-colors duration-200 hover:border-white/[.12] anim-in anim-d${(i % 6) + 1} relative`}
          >
            <div className="h-36 bg-[#0d1321] flex items-center justify-center overflow-hidden">
              {item.image
                ? <img src={item.image.startsWith('http') ? item.image : `${API_BASE}${item.image}`} alt={item.name} className="w-full h-full object-cover" />
                : <span className="text-4xl opacity-30">📦</span>
              }
            </div>
            {isAuthenticated() && (
              <div className="absolute top-2 right-2" onClick={e => e.stopPropagation()}>
                <HeartButton liked={likedIds.has(item.id)} onClick={() => handleToggleLike(item.id)} />
              </div>
            )}
            <div className="p-4">
              <div className="text-sm font-semibold mb-3 leading-snug">{item.name}</div>
              <div className="flex justify-between items-center">
                {item.price
                  ? <span className="font-['JetBrains_Mono'] text-base font-bold text-[#e8a635]">{formatPrice(item.price)}</span>
                  : <span className="text-sm text-[#4a5568]">Цена не указана</span>
                }
                <span className="text-xs text-[#4a5568]">{item.owner_username}</span>
              </div>
            </div>
          </div>
        ))}
        {items.length === 0 && !loading && (
          <div className="text-center py-16 text-[#4a5568]" style={{ gridColumn: '1/-1' }}>
            <div className="text-4xl mb-3">🔍</div>
            <div className="text-sm">Ничего не найдено</div>
          </div>
        )}
      </div>

      {selectedItem && (
        <ItemModal
          item={selectedItem}
          liked={likedIds.has(selectedItem.id)}
          onToggleLike={handleToggleLike}
          onClose={() => setSelectedItem(null)}
        />
      )}
    </div>
  );
}
