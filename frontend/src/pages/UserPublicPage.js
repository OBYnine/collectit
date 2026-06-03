import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getUserProfile, getPublicCollections, getCollection, getForSalePrivateItems, toggleWishlist, getWishlist, isAuthenticated } from '../api/client';
import { mediaUrl } from '../utils/config';
import { itemCoverUrl } from '../utils/itemImages';
import ItemGallery from '../components/ItemGallery';

function imgSrc(url) {
  return mediaUrl(url);
}

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
  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') onClose(); }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      style={{ background: 'rgba(10,14,23,0.88)', backdropFilter: 'blur(6px)' }}
      onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-lg bg-[#151c2c] border border-white/[.08] rounded-2xl overflow-hidden max-h-[90vh] overflow-y-auto">
        {/* Фото */}
        <div className="relative">
          <ItemGallery item={item} alt={item.name} />
          <button
            onClick={onClose}
            className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center rounded-lg bg-black/40 text-white/70 hover:text-white transition-colors text-lg"
          >✕</button>
        </div>

        <div className="p-6">
          <div className="flex items-start justify-between gap-3 mb-4">
            <h2 className="text-lg font-bold leading-snug flex-1">{item.name}</h2>
            {isAuthenticated() && (
              <HeartButton liked={liked} onClick={e => { e.stopPropagation(); onToggleLike(item.id); }} />
            )}
          </div>

          {item.description && (
            <p className="text-sm text-[#8892a4] leading-relaxed mb-5">{item.description}</p>
          )}

          {item.price && (
            <div className="mb-6">
              <div className="text-[10px] text-[#4a5568] uppercase tracking-wider mb-0.5">Цена</div>
              <div className="font-['JetBrains_Mono'] text-[#e8a635] font-bold text-base">{Number(item.price).toLocaleString('ru-RU')} ₽</div>
              <div className="mt-1 text-[11px] text-[#4a5568]">Сервисный сбор 7% включён.</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function CollectionModal({ collection, onClose }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') onClose(); }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  useEffect(() => {
    getCollection(collection.id)
      .then(data => setItems(data.items || []))
      .finally(() => setLoading(false));
  }, [collection.id]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      style={{ background: 'rgba(10,14,23,0.88)', backdropFilter: 'blur(6px)' }}
      onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-lg bg-[#151c2c] border border-white/[.08] rounded-2xl max-h-[85vh] overflow-y-auto">
        <div
          className="h-20 relative flex items-end px-6 pb-4"
          style={{ background: `linear-gradient(to bottom, ${collection.color || '#e8a635'}55, transparent)` }}
        >
          <h2 className="text-base font-bold uppercase tracking-wide flex-1">{collection.name}</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-[#4a5568] hover:text-[#8892a4] transition-colors text-lg"
          >✕</button>
        </div>

        {collection.description && (
          <p className="px-6 pb-4 text-sm text-[#4a5568]">{collection.description}</p>
        )}

        <div className="px-6 pb-6">
          {loading ? (
            <div className="text-center py-8 text-[#4a5568] text-sm">Загрузка...</div>
          ) : items.length === 0 ? (
            <div className="text-center py-8 text-[#4a5568] text-sm">Коллекция пуста</div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              {items.map(item => (
                <div key={item.id} className="bg-[#0d1321] rounded-xl overflow-hidden border border-white/[.05]">
                  <div className="h-24 w-full flex items-center justify-center overflow-hidden">
                    {itemCoverUrl(item)
                      ? <img src={itemCoverUrl(item)} alt={item.name} className="w-full h-full object-cover" />
                      : <span className="text-3xl opacity-20">📦</span>
                    }
                  </div>
                  <div className="p-3">
                    <div className="text-xs font-semibold leading-snug truncate">{item.name}</div>
                    {item.price && (
                      <div className="text-xs font-['JetBrains_Mono'] text-[#e8a635] mt-1">
                        {Number(item.price).toLocaleString('ru-RU')} ₽
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function UserPublicPage() {
  const { username } = useParams();
  const [user, setUser] = useState(null);
  const [collections, setCollections] = useState([]);
  const [saleItems, setSaleItems] = useState([]);
  const [likedIds, setLikedIds] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [openCollection, setOpenCollection] = useState(null);
  const [openItem, setOpenItem] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const userData = await getUserProfile(username);
        setUser(userData);
        const [colData, saleData] = await Promise.all([
          getPublicCollections(userData.id),
          getForSalePrivateItems(userData.id),
        ]);
        setCollections(colData.results || []);
        setSaleItems(saleData.results || saleData || []);
      } finally {
        setLoading(false);
      }
    }
    load();
    if (isAuthenticated()) {
      getWishlist().then(data => {
        const ids = (data.results || []).map(i => i.id);
        setLikedIds(new Set(ids));
      }).catch(() => {});
    }
  }, [username]);

  async function handleToggleLike(itemId) {
    try {
      const res = await toggleWishlist(itemId);
      setLikedIds(prev => {
        const next = new Set(prev);
        res.liked ? next.add(itemId) : next.delete(itemId);
        return next;
      });
    } catch {}
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center pt-32 text-[#4a5568]">
        <div className="text-sm">Загрузка...</div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center pt-32 text-[#4a5568]">
        <div className="text-4xl mb-3">👤</div>
        <div className="text-sm">Пользователь не найден</div>
      </div>
    );
  }

  const avatarSrc = user.avatar ? imgSrc(user.avatar) : null;
  const initials = user.username?.[0]?.toUpperCase() || 'U';

  return (
    <>
      {/* Шапка профиля */}
      <div className="max-w-5xl mx-auto px-10 pt-10 pb-0">
        <div className="flex items-start gap-7 pb-8">
          <div className="w-[88px] h-[88px] rounded-2xl bg-[#e8a635] flex items-center justify-center shrink-0 overflow-hidden">
            {avatarSrc
              ? <img src={avatarSrc} alt="avatar" className="w-full h-full object-cover" />
              : <span className="text-[#0a0e17] text-4xl font-bold">{initials}</span>
            }
          </div>
          <div className="pt-1 flex-1 flex gap-10">
            <div>
              <div className="text-[26px] font-bold tracking-tight leading-tight mb-1">{user.username}</div>
              <div className="text-xs text-[#4a5568]">
                Коллекционер с {new Date(user.member_since).toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })}
              </div>
            </div>
            {user.bio && (
              <div className="pt-1 border-l border-white/[.06] pl-10 max-w-xs">
                <div className="text-xs text-[#4a5568] uppercase tracking-wider mb-2">О себе</div>
                <p className="text-sm text-[#8892a4] leading-relaxed">{user.bio}</p>
              </div>
            )}
          </div>
        </div>

        {/* Статистика */}
        <div className="grid grid-cols-4 border-b border-white/[.06]">
          {[
            { value: user.total_collections, label: 'коллекций', gold: true },
            { value: user.total_items,       label: 'предметов' },
            { value: user.total_trades,      label: 'обменов' },
            { value: Number(user.rating) > 0 ? user.rating : '—', label: 'рейтинг' },
          ].map((s, i, arr) => (
            <div key={i} className={`py-5 px-4 text-center ${i < arr.length - 1 ? 'border-r border-white/[.06]' : ''}`}>
              <div className={`font-['JetBrains_Mono'] text-2xl font-bold tracking-tight mb-1 ${s.gold ? 'text-[#e8a635]' : 'text-[#e8eaf0]'}`}>
                {s.value}
              </div>
              <div className="text-[11px] text-[#4a5568] uppercase tracking-widest">{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Коллекции */}
      <div className="max-w-5xl mx-auto px-10 py-7">
        <div className="text-xs text-[#4a5568] uppercase tracking-wider mb-5">Коллекции</div>
        {collections.length === 0 ? (
          <div className="text-center py-12 text-[#4a5568]">
            <div className="text-4xl mb-3">📦</div>
            <div className="text-sm">Публичных коллекций нет</div>
          </div>
        ) : (
          <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))' }}>
            {collections.map(c => (
              <div
                key={c.id}
                onClick={() => setOpenCollection(c)}
                className="bg-[#151c2c] border border-white/[.06] rounded-xl cursor-pointer relative overflow-hidden transition-colors duration-200 hover:border-white/[.14]"
                style={{ minHeight: '160px' }}
              >
                <div
                  className="absolute top-0 left-0 right-0 h-24 pointer-events-none"
                  style={{ background: `linear-gradient(to bottom, ${c.color || '#e8a635'}55 0%, transparent 100%)` }}
                />
                <div className="relative flex flex-col justify-between p-5" style={{ minHeight: '160px' }}>
                  <div>
                    <div className="text-[15px] font-bold leading-snug mb-1.5 uppercase tracking-wide">{c.name}</div>
                    {c.description && (
                      <div
                        className="text-xs text-[#4a5568] leading-relaxed"
                        style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
                      >
                        {c.description}
                      </div>
                    )}
                  </div>
                  <div className="text-xs text-[#4a5568] mt-4">
                    <span className="font-['JetBrains_Mono'] text-[#8892a4] font-semibold">{c.items_count} шт.</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Предметы на продажу из скрытых коллекций */}
        {saleItems.length > 0 && (
          <div className="mt-8">
            <div className="text-xs text-[#4a5568] uppercase tracking-wider mb-5">На продажу из скрытых коллекций</div>
            <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))' }}>
              {saleItems.map(item => (
                <div
                  key={item.id}
                  onClick={() => setOpenItem(item)}
                  className="bg-[#151c2c] border border-white/[.06] rounded-xl overflow-hidden cursor-pointer transition-colors hover:border-white/[.14]"
                >
                  <div className="h-32 bg-[#0d1321] flex items-center justify-center overflow-hidden">
                    {itemCoverUrl(item)
                      ? <img src={itemCoverUrl(item)} alt={item.name} className="w-full h-full object-cover" />
                      : <span className="text-4xl opacity-20">📦</span>
                    }
                  </div>
                  <div className="p-4">
                    <div className="text-sm font-semibold mb-2 leading-snug truncate">{item.name}</div>
                    <div className="flex justify-between items-center">
                      {item.price
                        ? <span className="font-['JetBrains_Mono'] text-sm font-bold text-[#e8a635]">{Number(item.price).toLocaleString('ru-RU')} ₽</span>
                        : <span className="text-xs text-[#4a5568]">Цена не указана</span>
                      }
                      {isAuthenticated() && (
                        <div onClick={e => { e.stopPropagation(); handleToggleLike(item.id); }}>
                          <HeartButton liked={likedIds.has(item.id)} onClick={() => {}} />
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {openCollection && (
        <CollectionModal collection={openCollection} onClose={() => setOpenCollection(null)} />
      )}
      {openItem && (
        <ItemModal
          item={openItem}
          liked={likedIds.has(openItem.id)}
          onToggleLike={handleToggleLike}
          onClose={() => setOpenItem(null)}
        />
      )}
    </>
  );
}
