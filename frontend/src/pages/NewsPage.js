import React, { useState, useEffect, useRef } from 'react';
import { getNews, getArticle, createArticle, updateArticle, deleteArticle } from '../api/client';
import { useUser } from '../context/UserContext';
import { mediaUrl } from '../utils/config';

function imgSrc(url) {
  return mediaUrl(url);
}

function Lightbox({ images, startIndex, onClose }) {
  const [idx, setIdx] = useState(startIndex);

  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowRight') setIdx(i => (i + 1) % images.length);
      if (e.key === 'ArrowLeft')  setIdx(i => (i - 1 + images.length) % images.length);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [images.length, onClose]);

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/90"
      onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      {/* Закрыть */}
      <button
        onClick={onClose}
        className="absolute top-4 right-4 text-white/60 hover:text-white text-3xl leading-none z-10"
      >
        ✕
      </button>

      {/* Счётчик */}
      {images.length > 1 && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 text-white/50 text-sm font-['JetBrains_Mono']">
          {idx + 1} / {images.length}
        </div>
      )}

      {/* Стрелка влево */}
      {images.length > 1 && (
        <button
          onClick={() => setIdx(i => (i - 1 + images.length) % images.length)}
          className="absolute left-4 text-white/50 hover:text-white text-4xl leading-none px-2 py-4 z-10"
        >
          ‹
        </button>
      )}

      {/* Фото */}
      <img
        src={imgSrc(images[idx].image)}
        alt=""
        className="max-h-[90vh] max-w-[90vw] object-contain rounded-xl select-none"
        draggable={false}
      />

      {/* Стрелка вправо */}
      {images.length > 1 && (
        <button
          onClick={() => setIdx(i => (i + 1) % images.length)}
          className="absolute right-4 text-white/50 hover:text-white text-4xl leading-none px-2 py-4 z-10"
        >
          ›
        </button>
      )}

      {/* Точки */}
      {images.length > 1 && (
        <div className="absolute bottom-5 flex gap-2">
          {images.map((_, i) => (
            <button
              key={i}
              onClick={() => setIdx(i)}
              className={`w-2 h-2 rounded-full transition-colors ${i === idx ? 'bg-[#e8a635]' : 'bg-white/30'}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function formatDate(dateStr) {
  return new Date(dateStr).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
}

function contentBlocks(content) {
  return (content || '')
    .split(/\n{2,}/)
    .map(block => block.trim())
    .filter(Boolean);
}

function renderInlineMarkdown(text) {
  const parts = [];
  const re = /\*\*(.+?)\*\*/g;
  let lastIndex = 0;
  let match;

  while ((match = re.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push(
      <strong key={`${match.index}-${match[1]}`} className="font-semibold text-[#e8eaf0]">
        {match[1]}
      </strong>
    );
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length ? parts : text;
}

function ArticleModal({ article, onClose, onSaved, onDeleted }) {
  const isEdit = !!article;

  const [title, setTitle]     = useState(article?.title || '');
  const [content, setContent] = useState(article?.content || '');

  // Существующие фото (из БД) — [{id, image}], можно помечать на удаление
  const [existingImages, setExistingImages] = useState(
    (article?.images || []).map(img => ({ ...img, marked: false }))
  );
  // Новые файлы выбранные пользователем — [{file, preview}]
  const [newImages, setNewImages] = useState([]);

  const [loading, setLoading]   = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError]       = useState('');
  const fileRef = useRef();

  async function handleDelete() {
    if (!window.confirm('Удалить новость?')) return;
    setDeleting(true);
    try {
      await deleteArticle(article.id);
      onDeleted(article.id);
    } catch {
      setError('Ошибка при удалении.');
      setDeleting(false);
    }
  }

  function handleFiles(e) {
    const files = Array.from(e.target.files);
    const previews = files.map(f => ({ file: f, preview: URL.createObjectURL(f) }));
    setNewImages(prev => [...prev, ...previews]);
    e.target.value = '';
  }

  function removeNew(idx) {
    setNewImages(prev => prev.filter((_, i) => i !== idx));
  }

  function toggleExisting(id) {
    setExistingImages(prev => prev.map(img => img.id === id ? { ...img, marked: !img.marked } : img));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!title.trim() || !content.trim()) { setError('Заполните заголовок и текст.'); return; }
    setLoading(true);
    setError('');
    try {
      const fd = new FormData();
      fd.append('title', title.trim());
      fd.append('content', content.trim());

      newImages.forEach(({ file }) => fd.append('images', file));

      if (isEdit) {
        const removeIds = existingImages.filter(img => img.marked).map(img => img.id);
        fd.append('remove_image_ids', JSON.stringify(removeIds));
      }

      const saved = isEdit ? await updateArticle(article.id, fd) : await createArticle(fd);
      onSaved(saved);
    } catch {
      setError('Ошибка при сохранении.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-[#151c2c] rounded-2xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 pt-6 pb-4 border-b border-white/[.06]">
          <span className="text-[#e8eaf0] font-semibold">{isEdit ? 'Редактировать новость' : 'Новая новость'}</span>
          <button onClick={onClose} className="text-[#4a5568] hover:text-[#8892a4] text-xl leading-none">✕</button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 flex flex-col gap-4">
          <div>
            <label className="text-[#8892a4] text-xs mb-1.5 block">Заголовок</label>
            <input
              value={title}
              onChange={e => setTitle(e.target.value)}
              maxLength={300}
              placeholder="Введите заголовок новости"
              className="w-full bg-[#0a0e17] text-[#e8eaf0] text-sm px-4 py-2.5 rounded-lg border border-white/[.08] outline-none focus:border-[#e8a635]/50 transition-colors"
            />
          </div>

          <div>
            <label className="text-[#8892a4] text-xs mb-1.5 block">Текст новости</label>
            <textarea
              value={content}
              onChange={e => setContent(e.target.value)}
              rows={7}
              placeholder="Напишите текст новости..."
              className="w-full bg-[#0a0e17] text-[#e8eaf0] text-sm px-4 py-2.5 rounded-lg border border-white/[.08] outline-none focus:border-[#e8a635]/50 transition-colors resize-none"
            />
          </div>

          <div>
            <label className="text-[#8892a4] text-xs mb-1.5 block">Фотографии</label>

            {/* Существующие фото (только при редактировании) */}
            {existingImages.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-2">
                {existingImages.map(img => (
                  <div key={img.id} className="relative w-20 h-20 rounded-lg overflow-hidden flex-shrink-0">
                    <img src={imgSrc(img.image)} alt="" className="w-full h-full object-cover" />
                    {img.marked && (
                      <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
                        <span className="text-red-400 text-xs font-semibold">Удалить</span>
                      </div>
                    )}
                    <button
                      type="button"
                      onClick={() => toggleExisting(img.id)}
                      className={`absolute top-1 right-1 w-5 h-5 rounded-full text-[10px] font-bold flex items-center justify-center transition-colors ${
                        img.marked ? 'bg-red-500 text-white' : 'bg-black/60 text-white'
                      }`}
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Новые фото */}
            {newImages.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-2">
                {newImages.map((img, idx) => (
                  <div key={idx} className="relative w-20 h-20 rounded-lg overflow-hidden flex-shrink-0">
                    <img src={img.preview} alt="" className="w-full h-full object-cover" />
                    <button
                      type="button"
                      onClick={() => removeNew(idx)}
                      className="absolute top-1 right-1 w-5 h-5 rounded-full bg-black/60 text-white text-[10px] font-bold flex items-center justify-center"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div
              onClick={() => fileRef.current.click()}
              className="border border-dashed border-white/[.12] rounded-xl h-20 flex items-center justify-center cursor-pointer hover:border-[#e8a635]/40 transition-colors"
            >
              <span className="text-[#4a5568] text-sm">+ Добавить фотографии</span>
            </div>
            <input ref={fileRef} type="file" accept="image/*" multiple className="hidden" onChange={handleFiles} />
          </div>

          {error && <p className="text-red-400 text-sm">{error}</p>}

          <div className="flex gap-3">
            {isEdit && (
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleting}
                className="px-4 py-2.5 text-sm font-semibold rounded-xl border border-red-500/40 text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50"
              >
                {deleting ? 'Удаление...' : 'Удалить'}
              </button>
            )}
            <button
              type="submit"
              disabled={loading}
              className="flex-1 py-2.5 bg-[#e8a635] text-[#0a0e17] text-sm font-semibold rounded-xl disabled:opacity-50"
            >
              {loading ? 'Сохранение...' : (isEdit ? 'Сохранить' : 'Опубликовать')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function NewsPage() {
  const { user } = useUser();
  const [articles, setArticles]       = useState([]);
  const [loading, setLoading]         = useState(true);
  const [showCreate, setShowCreate]   = useState(false);
  const [editArticle, setEditArticle] = useState(null);
  const [lightbox, setLightbox]       = useState(null); // { images, startIndex }

  useEffect(() => {
    getNews()
      .then(data => setArticles(data.results || []))
      .finally(() => setLoading(false));
  }, []);

  const canCreate = user?.is_news_editor || user?.is_staff;

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center pt-32 text-[#4a5568]">
        <div className="text-4xl mb-3">⏳</div>
        <div className="text-sm">Загрузка...</div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-10 py-9">
      <div className="flex items-start justify-between mb-8 anim-in">
        <div>
          <h1 className="text-[22px] font-bold tracking-tight mb-1">Новости</h1>
          <p className="text-sm text-[#4a5568]">События в мире коллекционирования</p>
        </div>
        {canCreate && (
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 bg-[#e8a635] text-[#0a0e17] text-sm font-semibold rounded-xl hover:bg-[#f0b84a] transition-colors flex-shrink-0"
          >
            <span className="text-base leading-none">+</span>
            Создать новость
          </button>
        )}
      </div>

      {articles.length === 0 ? (
        <div className="flex flex-col items-center justify-center pt-20 text-[#4a5568]">
          <div className="text-4xl mb-3">📰</div>
          <div className="text-sm">Новостей пока нет</div>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {articles.map((n, i) => (
            <div
              key={n.id}
              className={`bg-[#151c2c] border border-white/[.06] rounded-xl overflow-hidden transition-all duration-200 hover:border-white/[.1] hover:bg-[#1a2236] anim-in anim-d${i + 1}`}
            >
              <div className="px-5 sm:px-7 py-5 sm:py-6">
                <div className="flex items-start justify-between gap-3 mb-1">
                  <div className="text-[17px] font-semibold leading-snug">{n.title}</div>
                  <div className="flex items-center gap-2 flex-shrink-0 mt-0.5">
                    <span className="font-['JetBrains_Mono'] text-[11px] text-[#4a5568]">
                      {formatDate(n.published_at)}
                    </span>
                    {canCreate && (
                      <button
                        onClick={async () => {
                          const full = await getArticle(n.id);
                          setEditArticle(full);
                        }}
                        className="text-[11px] text-[#8892a4] hover:text-[#e8a635] transition-colors px-2 py-0.5 rounded border border-white/[.06] hover:border-[#e8a635]/40"
                      >
                        Ред.
                      </button>
                    )}
                  </div>
                </div>

                <div className="mt-4 space-y-4 text-[15px] text-[#c9d0dc] leading-7">
                  {contentBlocks(n.content || n.excerpt).map((block, idx) => (
                    <p key={idx}>{renderInlineMarkdown(block)}</p>
                  ))}
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1">
                  {n.source_url && (
                    <a
                      href={n.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex text-[11px] text-[#e8a635] hover:text-[#f0b84a] transition-colors"
                    >
                      Источник: {n.source_site || 'оригинальная публикация'}
                    </a>
                  )}
                </div>

                {/* Фотографии в конце карточки */}
                {n.images?.length > 0 && (
                  <div className={`mt-5 grid gap-2 ${n.images.length === 1 ? 'grid-cols-1' : n.images.length === 2 ? 'grid-cols-2' : 'grid-cols-2 sm:grid-cols-3'}`}>
                    {n.images.map((img, imgIdx) => (
                      <div
                        key={img.id}
                        className="rounded-lg overflow-hidden cursor-zoom-in"
                        style={{ aspectRatio: '4/3' }}
                        onClick={() => setLightbox({ images: n.images, startIndex: imgIdx })}
                      >
                        <img src={imgSrc(img.image)} alt="" className="w-full h-full object-cover hover:scale-105 transition-transform duration-300" />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {lightbox && (
        <Lightbox
          images={lightbox.images}
          startIndex={lightbox.startIndex}
          onClose={() => setLightbox(null)}
        />
      )}

      {showCreate && (
        <ArticleModal
          onClose={() => setShowCreate(false)}
          onSaved={article => {
            setArticles(prev => [article, ...prev]);
            setShowCreate(false);
          }}
        />
      )}

      {editArticle && (
        <ArticleModal
          article={editArticle}
          onClose={() => setEditArticle(null)}
          onSaved={updated => {
            setArticles(prev => prev.map(a => a.id === updated.id ? updated : a));
            setEditArticle(null);
          }}
          onDeleted={id => {
            setArticles(prev => prev.filter(a => a.id !== id));
            setEditArticle(null);
          }}
        />
      )}
    </div>
  );
}
