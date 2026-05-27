import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { getMyCollections, createCollection, updateCollection, deleteCollection, getCollection, createItem, updateItem, deleteItem, getWishlist, toggleWishlist, getDeals, getMessages, hideChat } from '../api/client';
import { useUser } from '../context/UserContext';
import { mediaUrl } from '../utils/config';
import { itemCoverUrl } from '../utils/itemImages';
import ItemGallery from '../components/ItemGallery';

function relativeDate(dateStr) {
  const days = Math.floor((Date.now() - new Date(dateStr)) / 86400000);
  if (days === 0) return 'Сегодня';
  if (days === 1) return '1 день назад';
  if (days < 5) return `${days} дня назад`;
  if (days < 21) return `${days} дней назад`;
  return new Date(dateStr).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
}

const EMOJI_PRESETS = ['📦', '🪙', '📮', '🎵', '🏺', '🃏', '🔮', '⚙️', '🎨', '🌿'];
const COLOR_PRESETS = ['#e8a635', '#3b82f6', '#22c55e', '#ef4444', '#a855f7', '#ec4899', '#14b8a6', '#f97316'];

function editableItemImages(item) {
  const entries = [];
  const primary = mediaUrl(item?.image);
  for (const image of item?.images || []) {
    const src = mediaUrl(image.image);
    if (!src) continue;
    entries.push({ id: image.id, src, isPrimary: primary && src === primary });
  }
  if (primary && !entries.some(entry => entry.src === primary)) {
    entries.unshift({ id: null, src: primary, isPrimary: true });
  }
  return entries;
}

function CreateCollectionModal({ onClose, onCreated }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [color, setColor] = useState('#e8a635');
  const [isPublic, setIsPublic] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape') onClose();
  }, [onClose]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError('');
    try {
      const created = await createCollection({ name: name.trim(), description: description.trim(), color, is_public: isPublic });
      onCreated(created);
      onClose();
    } catch {
      setError('Не удалось создать коллекцию');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      style={{ background: 'rgba(10,14,23,0.85)', backdropFilter: 'blur(6px)' }}
      onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="w-full max-w-md bg-[#151c2c] border border-white/[.08] rounded-2xl p-7 flex flex-col gap-5"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold tracking-tight">Новая коллекция</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-[#4a5568] hover:text-[#8892a4] hover:bg-white/[.05] transition-colors text-lg leading-none"
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-4 py-2.5">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* Color */}
          <div>
            <label className="text-[11px] text-[#4a5568] uppercase tracking-widest mb-2 block">Цвет</label>
            <div className="flex gap-2 flex-wrap">
              {COLOR_PRESETS.map(c => (
                <button
                  key={c} type="button"
                  onClick={() => setColor(c)}
                  className="w-6 h-6 rounded-full transition-all"
                  style={{
                    background: c,
                    outline: color === c ? `2px solid ${c}` : 'none',
                    outlineOffset: '2px',
                    transform: color === c ? 'scale(1.2)' : 'scale(1)',
                  }}
                />
              ))}
            </div>
          </div>

          {/* Name */}
          <div>
            <label className="text-[11px] text-[#4a5568] uppercase tracking-widest mb-2 block">Название *</label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              maxLength={200}
              placeholder="Например: Советские монеты"
              className="w-full bg-[#0a0e17] border border-white/[.06] rounded-xl px-4 py-3 text-sm text-[#e8eaf0] outline-none transition-all focus:border-[#e8a635] focus:shadow-[0_0_0_3px_rgba(232,166,53,0.1)] placeholder-[#4a5568]"
              autoFocus
              required
            />
          </div>

          {/* Description */}
          <div>
            <label className="text-[11px] text-[#4a5568] uppercase tracking-widest mb-2 block">Описание</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              maxLength={500}
              rows={3}
              placeholder="Коротко о коллекции (необязательно)"
              className="w-full bg-[#0a0e17] border border-white/[.06] rounded-xl px-4 py-3 text-sm text-[#e8eaf0] outline-none transition-all focus:border-[#e8a635] focus:shadow-[0_0_0_3px_rgba(232,166,53,0.1)] placeholder-[#4a5568] resize-none"
            />
          </div>

          {/* Visibility */}
          <label className="flex items-center justify-between cursor-pointer select-none">
            <div>
              <div className="text-sm text-[#e8eaf0]">Видна всем</div>
              <div className="text-xs text-[#4a5568] mt-0.5">Отключите, чтобы скрыть от других пользователей</div>
            </div>
            <div
              onClick={() => setIsPublic(v => !v)}
              className={`w-10 h-5 rounded-full relative transition-colors duration-200 shrink-0 ml-4 ${isPublic ? 'bg-[#e8a635]' : 'bg-white/[.08]'}`}
            >
              <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200 ${isPublic ? 'translate-x-5' : 'translate-x-0.5'}`} />
            </div>
          </label>

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 rounded-xl text-sm text-[#8892a4] border border-white/[.06] hover:bg-white/[.04] transition-colors"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={loading || !name.trim()}
              className="flex-1 py-2.5 rounded-xl text-sm font-bold bg-[#e8a635] text-[#0a0e17] hover:bg-[#f0b84a] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? 'Создание...' : 'Создать'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function AddItemModal({ collectionId, onClose, onAdded }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [price, setPrice] = useState('');
  const [isForSale, setIsForSale] = useState(false);
  const [imageFiles, setImageFiles] = useState([]);
  const [imagePreviews, setImagePreviews] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  function handleImageChange(e) {
    const files = Array.from(e.target.files || []).slice(0, 8);
    setImageFiles(files);
    setImagePreviews(files.map(file => URL.createObjectURL(file)));
  }

  function handleRemoveNew(index) {
    setImageFiles(prev => prev.filter((_, i) => i !== index));
    setImagePreviews(prev => prev.filter((_, i) => i !== index));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError('');
    try {
      const fd = new FormData();
      fd.append('name', name.trim());
      fd.append('description', description.trim());
      fd.append('collection', collectionId);
      fd.append('is_for_sale', isForSale);
      if (price) fd.append('price', price);
      imageFiles.forEach((file, index) => {
        fd.append('images', file);
        if (index === 0) fd.append('image', file);
      });
      const item = await createItem(fd);
      onAdded(item);
      onClose();
    } catch {
      setError('Не удалось добавить предмет');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center px-4"
      style={{ background: 'rgba(10,14,23,0.9)', backdropFilter: 'blur(6px)' }}
      onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-sm bg-[#151c2c] border border-white/[.08] rounded-2xl p-6 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold tracking-tight">Новый предмет</h2>
          <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-lg text-[#4a5568] hover:text-[#8892a4] transition-colors text-lg leading-none">✕</button>
        </div>

        {error && (
          <div className="text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-4 py-2.5">{error}</div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          {/* Photo */}
          <div>
            <label className="text-[11px] text-[#4a5568] uppercase tracking-widest mb-2 block">Фото</label>
            {imagePreviews.length > 0 && (
              <div className="grid grid-cols-3 gap-2 mb-2">
                {imagePreviews.map((src, i) => (
                  <div key={`${src}-${i}`} className="relative h-20 rounded-lg overflow-hidden border border-[#e8a635]/40 bg-[#0a0e17]">
                    <img src={src} alt="" className="w-full h-full object-cover" />
                    <button
                      type="button"
                      onClick={() => handleRemoveNew(i)}
                      className="absolute top-1 right-1 w-6 h-6 rounded-full bg-black/65 text-white text-sm flex items-center justify-center"
                      aria-label="Убрать новое фото"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}
            <label className="cursor-pointer block">
              <div className="w-full h-24 bg-[#0a0e17] border border-dashed border-white/[.08] rounded-xl flex items-center justify-center overflow-hidden transition-colors hover:border-white/[.14]">
                <div className="text-center text-[#4a5568]">
                  <div className="text-2xl mb-1">+</div>
                  <div className="text-xs">Добавить фото</div>
                </div>
              </div>
              <input type="file" accept="image/*" multiple onChange={handleImageChange} className="hidden" />
            </label>
          </div>

          {/* Name */}
          <div>
            <label className="text-[11px] text-[#4a5568] uppercase tracking-widest mb-1.5 block">Название *</label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              maxLength={300}
              autoFocus
              required
              className="w-full bg-[#0a0e17] border border-white/[.06] rounded-xl px-4 py-2.5 text-sm text-[#e8eaf0] outline-none transition-all focus:border-[#e8a635] focus:shadow-[0_0_0_3px_rgba(232,166,53,0.1)] placeholder-[#4a5568]"
            />
          </div>

          {/* Description */}
          <div>
            <label className="text-[11px] text-[#4a5568] uppercase tracking-widest mb-1.5 block">Описание</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              maxLength={500}
              rows={2}
              className="w-full bg-[#0a0e17] border border-white/[.06] rounded-xl px-4 py-2.5 text-sm text-[#e8eaf0] outline-none transition-all focus:border-[#e8a635] focus:shadow-[0_0_0_3px_rgba(232,166,53,0.1)] placeholder-[#4a5568] resize-none"
            />
          </div>

          {/* Price */}
          <div>
            <label className="text-[11px] text-[#4a5568] uppercase tracking-widest mb-1.5 block">Стоимость</label>
            <div className="flex gap-2">
              <input
                type="number"
                value={price}
                onChange={e => setPrice(e.target.value)}
                min="0"
                step="0.01"
                placeholder="0"
                className="flex-1 bg-[#0a0e17] border border-white/[.06] rounded-xl px-4 py-2.5 text-sm text-[#e8eaf0] outline-none transition-all focus:border-[#e8a635] focus:shadow-[0_0_0_3px_rgba(232,166,53,0.1)] placeholder-[#4a5568] font-['JetBrains_Mono']"
              />
              <div className="px-4 py-2.5 text-sm text-[#4a5568] bg-[#0a0e17] border border-white/[.06] rounded-xl select-none">₽</div>
            </div>
          </div>

          {/* For sale */}
          <label className="flex items-center gap-3 cursor-pointer select-none">
            <div
              onClick={() => setIsForSale(v => !v)}
              className={`w-10 h-5 rounded-full relative transition-colors duration-200 ${isForSale ? 'bg-[#e8a635]' : 'bg-white/[.08]'}`}
            >
              <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200 ${isForSale ? 'translate-x-5' : 'translate-x-0.5'}`} />
            </div>
            <span className="text-sm text-[#8892a4]">Выставить на продажу</span>
          </label>

          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-xl text-sm text-[#8892a4] border border-white/[.06] transition-colors">Отмена</button>
            <button type="submit" disabled={loading || !name.trim()} className="flex-1 py-2.5 rounded-xl text-sm font-bold bg-[#e8a635] text-[#0a0e17] disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
              {loading ? 'Добавление...' : 'Добавить'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function EditItemModal({ item, onClose, onUpdated, onDeleted }) {
  const [name, setName] = useState(item.name);
  const [description, setDescription] = useState(item.description || '');
  const [price, setPrice] = useState(item.price || '');
  const [isForSale, setIsForSale] = useState(item.is_for_sale || false);
  const [existingImages, setExistingImages] = useState(() => editableItemImages(item));
  const [deleteImageIds, setDeleteImageIds] = useState([]);
  const [clearPrimaryImage, setClearPrimaryImage] = useState(false);
  const [imageFiles, setImageFiles] = useState([]);
  const [imagePreviews, setImagePreviews] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);

  function handleImageChange(e) {
    const files = Array.from(e.target.files || []).slice(0, 8);
    setImageFiles(prev => [...prev, ...files].slice(0, 8));
    setImagePreviews(prev => [...prev, ...files.map(file => URL.createObjectURL(file))].slice(0, 8));
    e.target.value = '';
  }

  function handleRemoveExisting(entry) {
    setExistingImages(prev => prev.filter(image => image.src !== entry.src));
    if (entry.id) setDeleteImageIds(prev => [...prev, entry.id]);
    if (entry.isPrimary && !entry.id) setClearPrimaryImage(true);
  }

  function handleRemoveNew(index) {
    setImageFiles(prev => prev.filter((_, i) => i !== index));
    setImagePreviews(prev => prev.filter((_, i) => i !== index));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError('');
    try {
      const fd = new FormData();
      fd.append('name', name.trim());
      fd.append('description', description.trim());
      fd.append('is_for_sale', isForSale);
      if (price) fd.append('price', price);
      else fd.append('price', '');
      deleteImageIds.forEach(id => fd.append('delete_image_ids', id));
      if (clearPrimaryImage) fd.append('clear_image', 'true');
      imageFiles.forEach((file, index) => {
        fd.append('images', file);
        if (index === 0 && existingImages.length === 0) {
          fd.append('image', file);
        }
      });
      const updated = await updateItem(item.id, fd);
      onUpdated(updated);
      onClose();
    } catch {
      setError('Не удалось сохранить изменения');
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    setLoading(true);
    setError('');
    try {
      await deleteItem(item.id);
      onDeleted(item.id);
      onClose();
    } catch {
      setError('Не удалось удалить предмет');
      setConfirmDelete(false);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center px-4"
      style={{ background: 'rgba(10,14,23,0.9)', backdropFilter: 'blur(6px)' }}
      onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-sm bg-[#151c2c] border border-white/[.08] rounded-2xl p-6 flex flex-col gap-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold tracking-tight">Редактировать предмет</h2>
          <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-lg text-[#4a5568] hover:text-[#8892a4] transition-colors text-lg leading-none">✕</button>
        </div>

        {error && (
          <div className="text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-4 py-2.5">{error}</div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          {/* Photo */}
          <div>
            <label className="text-[11px] text-[#4a5568] uppercase tracking-widest mb-2 block">Фото</label>
            {existingImages.length > 0 && (
              <div className="grid grid-cols-3 gap-2 mb-2">
                {existingImages.map(entry => (
                  <div key={entry.src} className="relative h-20 rounded-lg overflow-hidden border border-white/[.08] bg-[#0a0e17]">
                    <img src={entry.src} alt="" className="w-full h-full object-cover" />
                    <button
                      type="button"
                      onClick={() => handleRemoveExisting(entry)}
                      className="absolute top-1 right-1 w-6 h-6 rounded-full bg-black/65 text-white text-sm flex items-center justify-center"
                      aria-label="Удалить фото"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}
            {imagePreviews.length > 0 && (
              <div className="grid grid-cols-3 gap-2 mb-2">
                {imagePreviews.map((src, i) => (
                  <div key={`${src}-${i}`} className="relative h-20 rounded-lg overflow-hidden border border-[#e8a635]/40 bg-[#0a0e17]">
                    <img src={src} alt="" className="w-full h-full object-cover" />
                    <button
                      type="button"
                      onClick={() => handleRemoveNew(i)}
                      className="absolute top-1 right-1 w-6 h-6 rounded-full bg-black/65 text-white text-sm flex items-center justify-center"
                      aria-label="Убрать новое фото"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}
            <label className="cursor-pointer block">
              <div className="w-full h-24 bg-[#0a0e17] border border-dashed border-white/[.08] rounded-xl flex items-center justify-center overflow-hidden transition-colors hover:border-white/[.14]">
                <div className="text-center text-[#4a5568]">
                  <div className="text-2xl mb-1">+</div>
                  <div className="text-xs">Добавить фото</div>
                </div>
              </div>
              <input type="file" accept="image/*" multiple onChange={handleImageChange} className="hidden" />
            </label>
          </div>

          {/* Name */}
          <div>
            <label className="text-[11px] text-[#4a5568] uppercase tracking-widest mb-1.5 block">Название *</label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              maxLength={300}
              autoFocus
              required
              className="w-full bg-[#0a0e17] border border-white/[.06] rounded-xl px-4 py-2.5 text-sm text-[#e8eaf0] outline-none transition-all focus:border-[#e8a635] focus:shadow-[0_0_0_3px_rgba(232,166,53,0.1)] placeholder-[#4a5568]"
            />
          </div>

          {/* Description */}
          <div>
            <label className="text-[11px] text-[#4a5568] uppercase tracking-widest mb-1.5 block">Описание</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              maxLength={500}
              rows={2}
              className="w-full bg-[#0a0e17] border border-white/[.06] rounded-xl px-4 py-2.5 text-sm text-[#e8eaf0] outline-none transition-all focus:border-[#e8a635] focus:shadow-[0_0_0_3px_rgba(232,166,53,0.1)] placeholder-[#4a5568] resize-none"
            />
          </div>

          {/* Price */}
          <div>
            <label className="text-[11px] text-[#4a5568] uppercase tracking-widest mb-1.5 block">Стоимость</label>
            <div className="flex gap-2">
              <input
                type="number"
                value={price}
                onChange={e => setPrice(e.target.value)}
                min="0"
                step="0.01"
                placeholder="0"
                className="flex-1 bg-[#0a0e17] border border-white/[.06] rounded-xl px-4 py-2.5 text-sm text-[#e8eaf0] outline-none transition-all focus:border-[#e8a635] focus:shadow-[0_0_0_3px_rgba(232,166,53,0.1)] placeholder-[#4a5568] font-['JetBrains_Mono']"
              />
              <div className="px-4 py-2.5 text-sm text-[#4a5568] bg-[#0a0e17] border border-white/[.06] rounded-xl select-none">₽</div>
            </div>
          </div>

          {/* For sale */}
          <label className="flex items-center gap-3 cursor-pointer select-none">
            <div
              onClick={() => setIsForSale(v => !v)}
              className={`w-10 h-5 rounded-full relative transition-colors duration-200 ${isForSale ? 'bg-[#e8a635]' : 'bg-white/[.08]'}`}
            >
              <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200 ${isForSale ? 'translate-x-5' : 'translate-x-0.5'}`} />
            </div>
            <span className="text-sm text-[#8892a4]">Выставить на продажу</span>
          </label>

          {confirmDelete ? (
            <div className="bg-red-500/[.08] border border-red-500/20 rounded-xl p-4 flex flex-col gap-3">
              <p className="text-sm text-[#e8eaf0]">
                Удалить <span className="font-semibold">«{item.name}»</span>? Это действие необратимо.
              </p>
              <div className="flex gap-2">
                <button type="button" onClick={() => setConfirmDelete(false)} className="flex-1 py-2 rounded-lg text-sm text-[#8892a4] border border-white/[.06] transition-colors">Отмена</button>
                <button type="button" onClick={handleDelete} disabled={loading} className="flex-1 py-2 rounded-lg text-sm font-bold bg-red-500 text-white disabled:opacity-50 transition-colors">
                  {loading ? 'Удаление...' : 'Да, удалить'}
                </button>
              </div>
            </div>
          ) : (
            <div className="flex gap-3 pt-1">
              <button type="button" onClick={() => setConfirmDelete(true)} className="py-2.5 px-4 rounded-xl text-sm text-red-400/70 border border-red-500/20 hover:text-red-400 transition-colors">Удалить</button>
              <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-xl text-sm text-[#8892a4] border border-white/[.06] transition-colors">Отмена</button>
              <button type="submit" disabled={loading || !name.trim()} className="flex-1 py-2.5 rounded-xl text-sm font-bold bg-[#e8a635] text-[#0a0e17] disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                {loading ? 'Сохранение...' : 'Сохранить'}
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}

function EditCollectionModal({ collection, onClose, onUpdated, onDeleted }) {
  const [name, setName] = useState(collection.name);
  const [description, setDescription] = useState(collection.description || '');
  const [color, setColor] = useState(collection.color || '#e8a635');
  const [isPublic, setIsPublic] = useState(collection.is_public !== false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [items, setItems] = useState([]);
  const [itemsLoading, setItemsLoading] = useState(true);
  const [showAddItem, setShowAddItem] = useState(false);
  const [editingItem, setEditingItem] = useState(null);

  useEffect(() => {
    getCollection(collection.id).then(data => {
      setItems(data.items || []);
      setItemsLoading(false);
    }).catch(() => setItemsLoading(false));
  }, [collection.id]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape') onClose();
  }, [onClose]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError('');
    try {
      const updated = await updateCollection(collection.id, {
        name: name.trim(),
        description: description.trim(),
        color,
        is_public: isPublic,
      });
      onUpdated(updated);
      onClose();
    } catch {
      setError('Не удалось сохранить изменения');
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    setLoading(true);
    setError('');
    try {
      await deleteCollection(collection.id);
      onDeleted(collection.id);
      onClose();
    } catch {
      setError('Не удалось удалить коллекцию');
      setConfirmDelete(false);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      style={{ background: 'rgba(10,14,23,0.85)', backdropFilter: 'blur(6px)' }}
      onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="w-full max-w-md bg-[#151c2c] border border-white/[.08] rounded-2xl p-7 flex flex-col gap-5 max-h-[90vh] overflow-y-auto"
      >
        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold tracking-tight">Редактировать коллекцию</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-[#4a5568] hover:text-[#8892a4] hover:bg-white/[.05] transition-colors text-lg leading-none"
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-4 py-2.5">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* Color */}
          <div>
            <label className="text-[11px] text-[#4a5568] uppercase tracking-widest mb-2 block">Цвет</label>
            <div className="flex gap-2 flex-wrap">
              {COLOR_PRESETS.map(c => (
                <button
                  key={c} type="button"
                  onClick={() => setColor(c)}
                  className="w-6 h-6 rounded-full transition-all"
                  style={{
                    background: c,
                    outline: color === c ? `2px solid ${c}` : 'none',
                    outlineOffset: '2px',
                    transform: color === c ? 'scale(1.2)' : 'scale(1)',
                  }}
                />
              ))}
            </div>
          </div>

          {/* Name */}
          <div>
            <label className="text-[11px] text-[#4a5568] uppercase tracking-widest mb-2 block">Название *</label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              maxLength={200}
              className="w-full bg-[#0a0e17] border border-white/[.06] rounded-xl px-4 py-3 text-sm text-[#e8eaf0] outline-none transition-all focus:border-[#e8a635] focus:shadow-[0_0_0_3px_rgba(232,166,53,0.1)] placeholder-[#4a5568]"
              autoFocus
              required
            />
          </div>

          {/* Description */}
          <div>
            <label className="text-[11px] text-[#4a5568] uppercase tracking-widest mb-2 block">Описание</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              maxLength={500}
              rows={3}
              className="w-full bg-[#0a0e17] border border-white/[.06] rounded-xl px-4 py-3 text-sm text-[#e8eaf0] outline-none transition-all focus:border-[#e8a635] focus:shadow-[0_0_0_3px_rgba(232,166,53,0.1)] placeholder-[#4a5568] resize-none"
            />
          </div>

          {/* Visibility */}
          <label className="flex items-center justify-between cursor-pointer select-none">
            <div>
              <div className="text-sm text-[#e8eaf0]">Видна всем</div>
              <div className="text-xs text-[#4a5568] mt-0.5">Отключите, чтобы скрыть от других пользователей</div>
            </div>
            <div
              onClick={() => setIsPublic(v => !v)}
              className={`w-10 h-5 rounded-full relative transition-colors duration-200 shrink-0 ml-4 ${isPublic ? 'bg-[#e8a635]' : 'bg-white/[.08]'}`}
            >
              <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200 ${isPublic ? 'translate-x-5' : 'translate-x-0.5'}`} />
            </div>
          </label>

          {/* Items */}
          <div>
            <label className="text-[11px] text-[#4a5568] uppercase tracking-widest mb-2 block">
              Предметы{items.length > 0 && <span className="font-['JetBrains_Mono'] ml-1.5 normal-case text-[#8892a4]">{items.length}</span>}
            </label>
            {itemsLoading ? (
              <div className="text-center py-5 text-[#4a5568] text-sm">...</div>
            ) : (
              <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))' }}>
                {items.map(item => (
                  <div key={item.id} onClick={() => setEditingItem(item)} className="bg-[#0a0e17] border border-white/[.06] rounded-lg overflow-hidden cursor-pointer transition-colors hover:border-white/[.12]">
                    {itemCoverUrl(item)
                      ? <img src={itemCoverUrl(item)} alt="" className="w-full h-16 object-cover" />
                      : <div className="w-full h-16 flex items-center justify-center text-2xl bg-[#0d1220]">📦</div>
                    }
                    <div className="p-2">
                      <div className="text-xs font-medium text-[#e8eaf0] truncate">{item.name}</div>
                      {item.price && (
                        <div className="text-[11px] text-[#8892a4] font-['JetBrains_Mono'] mt-0.5">{item.price} ₽</div>
                      )}
                    </div>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => setShowAddItem(true)}
                  className="border border-dashed border-white/[.07] rounded-lg flex flex-col items-center justify-center gap-1 min-h-[96px] text-[#4a5568] transition-colors hover:border-[#e8a635]/30 hover:text-[#e8a635]/80"
                >
                  <span className="text-xl font-light leading-none">+</span>
                  <span className="text-[11px]">Добавить</span>
                </button>
              </div>
            )}
          </div>

          {confirmDelete ? (
            <div className="bg-red-500/[.08] border border-red-500/20 rounded-xl p-4 flex flex-col gap-3">
              <p className="text-sm text-[#e8eaf0]">
                Удалить коллекцию <span className="font-semibold">«{collection.name}»</span>? Это действие необратимо.
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setConfirmDelete(false)}
                  className="flex-1 py-2 rounded-lg text-sm text-[#8892a4] border border-white/[.06] hover:bg-white/[.04] transition-colors"
                >
                  Отмена
                </button>
                <button
                  type="button"
                  onClick={handleDelete}
                  disabled={loading}
                  className="flex-1 py-2 rounded-lg text-sm font-bold bg-red-500 text-white hover:bg-red-400 disabled:opacity-50 transition-colors"
                >
                  {loading ? 'Удаление...' : 'Да, удалить'}
                </button>
              </div>
            </div>
          ) : (
            <div className="flex gap-3 pt-1">
              <button
                type="button"
                onClick={() => setConfirmDelete(true)}
                className="py-2.5 px-4 rounded-xl text-sm text-red-400/70 border border-red-500/20 hover:bg-red-500/[.06] hover:text-red-400 transition-colors"
              >
                Удалить
              </button>
              <button
                type="button"
                onClick={onClose}
                className="flex-1 py-2.5 rounded-xl text-sm text-[#8892a4] border border-white/[.06] hover:bg-white/[.04] transition-colors"
              >
                Отмена
              </button>
              <button
                type="submit"
                disabled={loading || !name.trim()}
                className="flex-1 py-2.5 rounded-xl text-sm font-bold bg-[#e8a635] text-[#0a0e17] hover:bg-[#f0b84a] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? 'Сохранение...' : 'Сохранить'}
              </button>
            </div>
          )}
        </form>
      </div>
      {showAddItem && (
        <AddItemModal
          collectionId={collection.id}
          onClose={() => setShowAddItem(false)}
          onAdded={item => setItems(prev => [...prev, item])}
        />
      )}
      {editingItem && (
        <EditItemModal
          item={editingItem}
          onClose={() => setEditingItem(null)}
          onUpdated={updated => setItems(prev => prev.map(i => i.id === updated.id ? updated : i))}
          onDeleted={id => setItems(prev => prev.filter(i => i.id !== id))}
        />
      )}
    </div>
  );
}

function WishlistItemModal({ item, onClose, onUnliked }) {
  const navigate = useNavigate();

  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') onClose(); }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const avatarSrc = mediaUrl(item.owner_avatar);
  const avatarInitial = item.owner_username?.[0]?.toUpperCase() || 'U';

  async function handleUnlike(e) {
    e.stopPropagation();
    try {
      await toggleWishlist(item.id);
      onUnliked(item.id);
      onClose();
    } catch {}
  }

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
          {/* Название + сердечко */}
          <div className="flex items-start justify-between gap-3 mb-4">
            <h2 className="text-lg font-bold leading-snug flex-1">{item.name}</h2>
            <button
              onClick={handleUnlike}
              className="w-7 h-7 flex items-center justify-center transition-colors duration-150 shrink-0"
              title="Убрать из вишлиста"
            >
              <svg viewBox="0 0 20 18" fill="#e8a635" className="w-5 h-5" stroke="#e8a635" strokeWidth="1.6">
                <path d="M10 16.5S1.5 11 1.5 5.5A4.5 4.5 0 0 1 10 3.34 4.5 4.5 0 0 1 18.5 5.5C18.5 11 10 16.5 10 16.5z"/>
              </svg>
            </button>
          </div>

          {/* Описание */}
          {item.description && (
            <p className="text-sm text-[#8892a4] leading-relaxed mb-5">{item.description}</p>
          )}

          {/* Детали */}
          {item.price && (
            <div className="mb-6">
              <div className="text-[10px] text-[#4a5568] uppercase tracking-wider mb-0.5">Цена</div>
              <div className="font-['JetBrains_Mono'] text-[#e8a635] font-bold text-base">{Number(item.price).toLocaleString('ru-RU')} ₽</div>
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
                  : <span>{avatarInitial}</span>
                }
              </div>
              <div>
                <div className="text-sm font-semibold group-hover:text-[#e8a635] transition-colors">{item.owner_username}</div>
                {item.owner_bio && <div className="text-xs text-[#4a5568] mt-0.5 line-clamp-1">{item.owner_bio}</div>}
              </div>
              <svg className="w-4 h-4 text-[#4a5568] group-hover:text-[#e8a635] ml-auto transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </div>
            <button
              onClick={() => {
                onClose();
                window.dispatchEvent(new CustomEvent('open-chat', { detail: { username: item.owner_username, avatar: avatarSrc, itemName: item.name, itemImage: itemCoverUrl(item), itemPrice: item.price, itemId: item.id, sellerIsOther: true } }));
              }}
              className="mt-3 w-full flex items-center justify-center gap-2 py-2 rounded-xl bg-white/[.04] hover:bg-white/[.07] text-sm text-[#8892a4] hover:text-[#e8eaf0] transition-colors"
            >
              <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
              Написать продавцу
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ProfileHeader({ user }) {
  const avatarSrc = mediaUrl(user?.avatar);
  const initials = user?.username?.[0]?.toUpperCase() || 'U';

  return (
    <div className="max-w-5xl mx-auto px-10 pt-10 pb-0 anim-in">
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
            <div className="text-sm text-[#8892a4] mb-3">{user.email}</div>
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
    </div>
  );
}

function StatsRow({ user }) {
  const ratingVal = user.rating && parseFloat(user.rating) > 0
    ? parseFloat(user.rating).toFixed(1)
    : '—';
  const stats = [
    { value: user.total_collections, label: 'коллекций', gold: true },
    { value: user.total_items,       label: 'предметов' },
    { value: user.total_trades,      label: 'сделок' },
    { value: ratingVal,              label: 'рейтинг' },
  ];
  return (
    <div className="max-w-5xl mx-auto px-10 mb-8 anim-in anim-d1">
      <div className="grid grid-cols-4">
        {stats.map((s, i) => (
          <div key={i} className={`py-5 px-4 text-center ${i < stats.length - 1 ? 'border-r border-white/[.06]' : ''}`}>
            <div className={`font-['JetBrains_Mono'] text-2xl font-bold tracking-tight mb-1 ${s.gold ? 'text-[#e8a635]' : s.green ? 'text-[#22c55e]' : 'text-[#e8eaf0]'}`}>
              {s.value}
            </div>
            <div className="text-[11px] text-[#4a5568] uppercase tracking-widest">{s.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function CollectionsCanvas({ collections, wishlistItems, onNewCollection, onEditCollection, onWishlistItemUnliked }) {
  const [subTab, setSubTab] = useState('collections');
  const [selectedWishlistItem, setSelectedWishlistItem] = useState(null);
  const subTabs = [
    { key: 'collections', label: 'Коллекции' },
    { key: 'wishlist',    label: 'Вишлист'   },
    { key: 'trades',      label: 'Сделки'    },
  ];

  return (
    <>
      <div className="max-w-5xl mx-auto px-10 border-b border-white/[.06] flex anim-in anim-d2">
        {subTabs.map(t => (
          <button
            key={t.key}
            onClick={() => setSubTab(t.key)}
            className={`px-6 py-2.5 text-[13px] font-medium uppercase tracking-widest border-0 bg-transparent cursor-pointer relative transition-colors duration-200 ${
              subTab === t.key ? 'subtab-active' : 'text-[#4a5568] hover:text-[#8892a4]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="max-w-5xl mx-auto px-10 py-7">
        {subTab === 'collections' && (
          <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))' }}>
            {collections.map((c, i) => (
              <div
                key={c.id}
                onClick={() => onEditCollection(c)}
                className={`bg-[#151c2c] border border-white/[.06] rounded-xl cursor-pointer relative overflow-hidden transition-colors duration-200 hover:border-white/[.14] anim-in anim-d${Math.min(i + 1, 6)}`}
                style={{ minHeight: '160px' }}
              >
                {/* Цветной градиент сверху */}
                <div
                  className="absolute top-0 left-0 right-0 h-24 pointer-events-none"
                  style={{ background: `linear-gradient(to bottom, ${c.color || '#e8a635'}55 0%, transparent 100%)` }}
                />
                {/* Контент */}
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
                  <div className="flex justify-between items-center text-xs text-[#4a5568] mt-4">
                    <span className="font-['JetBrains_Mono'] text-[#8892a4] font-semibold">{c.items_count} шт.</span>
                    <span>{relativeDate(c.updated_at)}</span>
                  </div>
                </div>
              </div>
            ))}
            <button
              onClick={onNewCollection}
              className="border-2 border-dashed border-white/[.07] rounded-xl p-5 cursor-pointer flex flex-col items-center justify-center gap-2.5 min-h-[140px] text-[#4a5568] transition-all duration-200 hover:border-[#e8a635]/30 hover:text-[#e8a635] hover:bg-[#e8a635]/[.04] anim-in anim-d6"
            >
              <span className="text-3xl font-light">+</span>
              <span className="text-[13px] font-medium">Новая коллекция</span>
            </button>
          </div>
        )}
        {subTab === 'wishlist' && (
          wishlistItems.length === 0 ? (
            <div className="text-center py-16 text-[#4a5568]">
              <div className="text-4xl mb-3">🤍</div>
              <div className="text-sm">Вишлист пока пуст</div>
            </div>
          ) : (
            <>
              <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))' }}>
                {wishlistItems.map((item, i) => {
                  const imgSrc = itemCoverUrl(item);
                  return (
                    <div
                      key={item.id}
                      onClick={() => setSelectedWishlistItem(item)}
                      className={`bg-[#151c2c] border border-white/[.06] rounded-xl overflow-hidden cursor-pointer transition-colors hover:border-white/[.14] anim-in anim-d${Math.min(i + 1, 6)}`}
                    >
                      <div className="h-32 bg-[#0d1321] flex items-center justify-center overflow-hidden">
                        {imgSrc
                          ? <img src={imgSrc} alt={item.name} className="w-full h-full object-cover" />
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
                          <span className="text-xs text-[#4a5568]">{item.owner_username}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
              {selectedWishlistItem && (
                <WishlistItemModal
                  item={selectedWishlistItem}
                  onClose={() => setSelectedWishlistItem(null)}
                  onUnliked={id => { onWishlistItemUnliked(id); setSelectedWishlistItem(null); }}
                />
              )}
            </>
          )
        )}
        {subTab === 'trades' && (
          <DealsTab />
        )}
      </div>
    </>
  );
}

function ArchiveChatModal({ deal, onClose, onDelete }) {
  const [messages, setMessages] = useState([]);
  const [deleting, setDeleting] = useState(false);
  const supportCode = deal.support_code || `CHAT-${deal.id}`;

  useEffect(() => {
    getMessages(deal.id).then(data => {
      const list = Array.isArray(data) ? data : (data?.messages ?? []);
      setMessages(list);
    }).catch(() => {});
  }, [deal.id]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-[#151c2c] rounded-2xl w-full max-w-lg mx-4 flex flex-col max-h-[80vh]">
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/[.06] shrink-0">
          <div>
            <p className="text-sm font-semibold text-[#e8eaf0]">{deal.subject || 'Предмет'}</p>
            <p className="text-xs text-[#8892a4]">
              {deal.other_participant?.username} · {Number(deal.price).toLocaleString('ru-RU')} ₽
            </p>
            <button
              type="button"
              onClick={() => navigator.clipboard?.writeText(supportCode)}
              title="Скопировать код для поддержки"
              className="mt-1 font-['JetBrains_Mono'] text-[11px] text-[#e8a635] hover:text-white transition-colors"
            >
              {supportCode}
            </button>
          </div>
          <div className="flex items-center gap-3">
            {deal.rating != null && deal.viewer_role === 'seller' && (
              <span className="text-[#e8a635] text-sm">
                {'★'.repeat(deal.rating)}<span className="text-[#4a5568]">{'★'.repeat(5 - deal.rating)}</span>
              </span>
            )}
            <button onClick={onClose} className="text-[#4a5568] hover:text-[#e8eaf0] text-xl leading-none">×</button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-2">
          {messages.length === 0 && (
            <p className="text-xs text-[#4a5568] text-center mt-4">Нет сообщений</p>
          )}
          {messages.map(msg => (
            <div key={msg.id} className={`flex ${msg.is_mine ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[75%] px-3 py-2 rounded-xl text-sm ${
                msg.is_mine ? 'bg-[#e8a635]/20 text-[#e8eaf0]' : 'bg-white/[.06] text-[#e8eaf0]'
              }`}>
                {msg.text}
              </div>
            </div>
          ))}
        </div>
        <div className="px-5 py-3 border-t border-white/[.06] shrink-0 flex items-center justify-between gap-3">
          <span className="text-xs text-[#4a5568]">Архивный чат · только для просмотра</span>
          <button
            disabled={deleting}
            onClick={async () => {
              if (!window.confirm('Удалить этот архивный чат только у вас?')) return;
              setDeleting(true);
              try {
                await hideChat(deal.id);
                onDelete?.(deal.id);
                onClose();
              } catch {
                setDeleting(false);
              }
            }}
            className="px-3 py-1.5 rounded-lg border border-red-500/20 text-xs text-red-400 hover:bg-red-500/[.08] disabled:opacity-50 transition-colors shrink-0"
          >
            {deleting ? '...' : 'Удалить у меня'}
          </button>
        </div>
      </div>
    </div>
  );
}

function DealsTab() {
  const [deals, setDeals]       = useState([]);
  const [loading, setLoading]   = useState(true);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    getDeals().then(data => {
      setDeals(Array.isArray(data) ? data : []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-sm text-[#4a5568] py-8 text-center">Загрузка…</p>;

  if (deals.length === 0) return (
    <div className="text-center py-16 text-[#4a5568]">
      <div className="text-4xl mb-3">🤝</div>
      <div className="text-sm">Завершённых сделок пока нет</div>
    </div>
  );

  return (
    <>
      <div className="flex flex-col gap-3 py-2">
        {deals.map(deal => {
          const img = mediaUrl(deal.item_image);
          const isSeller = deal.viewer_role === 'seller';
          const date = new Date(deal.created_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' });

          return (
            <button
              key={deal.id}
              onClick={() => setSelected(deal)}
              className="flex items-center gap-4 bg-white/[.03] rounded-2xl px-4 py-3 text-left hover:bg-white/[.06] transition-colors"
            >
              <div className="w-11 h-11 rounded-xl bg-white/[.06] shrink-0 overflow-hidden">
                {img
                  ? <img src={img} alt="" className="w-full h-full object-cover" />
                  : <div className="w-full h-full flex items-center justify-center text-[#4a5568]">◆</div>
                }
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[#e8eaf0] truncate">{deal.subject || 'Предмет'}</p>
                <p className="text-xs text-[#8892a4]">
                  {isSeller ? 'Покупатель' : 'Продавец'}: {deal.other_participant?.username}
                </p>
                <p className="text-xs text-[#4a5568]">{date}</p>
              </div>
              <div className="shrink-0 text-right">
                <p className="text-sm font-semibold text-[#e8eaf0]">
                  {isSeller ? '+' : '−'}{Number(deal.price).toLocaleString('ru-RU')} ₽
                </p>
                {isSeller && deal.rating != null && (
                  <span className="text-[#e8a635] text-sm">
                    {'★'.repeat(deal.rating)}<span className="text-[#4a5568]">{'★'.repeat(5 - deal.rating)}</span>
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {selected && (
        <ArchiveChatModal
          deal={selected}
          onClose={() => setSelected(null)}
          onDelete={id => setDeals(prev => prev.filter(deal => deal.id !== id))}
        />
      )}
    </>
  );
}

export default function ProfilePage() {
  const { user } = useUser();
  const [collections, setCollections] = useState([]);
  const [wishlistItems, setWishlistItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editingCollection, setEditingCollection] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const [colData, wlData] = await Promise.all([getMyCollections(), getWishlist()]);
        setCollections(colData.results || []);
        setWishlistItems(wlData.results || []);
      } catch {
        setError('Не удалось загрузить коллекции');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  function handleCreated(newCollection) {
    setCollections(prev => [newCollection, ...prev]);
  }

  function handleUpdated(updated) {
    setCollections(prev => prev.map(c => c.id === updated.id ? updated : c));
  }

  function handleDeleted(id) {
    setCollections(prev => prev.filter(c => c.id !== id));
  }

  if (loading || !user) {
    return (
      <div className="flex flex-col items-center justify-center pt-32 text-[#4a5568]">
        <div className="text-4xl mb-3">⏳</div>
        <div className="text-sm">Загрузка...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center pt-32 text-[#4a5568]">
        <div className="text-4xl mb-3">⚠️</div>
        <div className="text-sm">{error}</div>
      </div>
    );
  }

  return (
    <>
      <ProfileHeader user={user} />
      <StatsRow user={user} />
      <CollectionsCanvas
        collections={collections}
        wishlistItems={wishlistItems}
        onNewCollection={() => setShowModal(true)}
        onEditCollection={setEditingCollection}
        onWishlistItemUnliked={id => setWishlistItems(prev => prev.filter(i => i.id !== id))}
      />
      {showModal && (
        <CreateCollectionModal
          onClose={() => setShowModal(false)}
          onCreated={handleCreated}
        />
      )}
      {editingCollection && (
        <EditCollectionModal
          collection={editingCollection}
          onClose={() => setEditingCollection(null)}
          onUpdated={handleUpdated}
          onDeleted={handleDeleted}
        />
      )}
    </>
  );
}
