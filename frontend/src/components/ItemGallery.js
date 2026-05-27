import { useEffect, useMemo, useState } from 'react';
import { itemImageUrls } from '../utils/itemImages';

export default function ItemGallery({ item, className = 'h-56', alt = '' }) {
  const images = useMemo(() => itemImageUrls(item), [item]);
  const [index, setIndex] = useState(0);
  const hasMany = images.length > 1;

  useEffect(() => {
    setIndex(0);
  }, [item?.id]);

  useEffect(() => {
    function onKey(e) {
      if (!hasMany) return;
      if (e.key === 'ArrowLeft') setIndex(prev => (prev - 1 + images.length) % images.length);
      if (e.key === 'ArrowRight') setIndex(prev => (prev + 1) % images.length);
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [hasMany, images.length]);

  return (
    <div className={`${className} bg-[#0d1321] flex items-center justify-center overflow-hidden relative`}>
      {images[index] ? (
        <img src={images[index]} alt={alt || item?.name || ''} className="w-full h-full object-cover" />
      ) : (
        <span className="text-6xl opacity-20">□</span>
      )}

      {hasMany && (
        <>
          <button
            type="button"
            onClick={e => { e.stopPropagation(); setIndex(prev => (prev - 1 + images.length) % images.length); }}
            className="absolute left-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-black/55 text-white/80 hover:text-white flex items-center justify-center"
            aria-label="Предыдущее фото"
          >
            ‹
          </button>
          <button
            type="button"
            onClick={e => { e.stopPropagation(); setIndex(prev => (prev + 1) % images.length); }}
            className="absolute right-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-black/55 text-white/80 hover:text-white flex items-center justify-center"
            aria-label="Следующее фото"
          >
            ›
          </button>
          <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex gap-1.5">
            {images.map((_, i) => (
              <button
                key={i}
                type="button"
                onClick={e => { e.stopPropagation(); setIndex(i); }}
                className={`w-2 h-2 rounded-full ${i === index ? 'bg-[#e8a635]' : 'bg-white/45'}`}
                aria-label={`Фото ${i + 1}`}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
