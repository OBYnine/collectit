import { mediaUrl } from './config';

export function formatPrice(price) {
  if (price === null || price === undefined || price === '') return '';
  const n = Number(price);
  if (Number.isNaN(n)) return '';
  return `${n.toLocaleString('ru-RU')} ₽`;
}

export function buyerPriceWithFee(price) {
  if (price === null || price === undefined || price === '') return null;
  const n = Number(price);
  if (Number.isNaN(n)) return null;
  return Math.round(n * 1.07 * 100) / 100;
}

export function displayBuyerPrice(item) {
  return item?.buyer_price ?? item?.price ?? null;
}

export function displaySellerPrice(item) {
  return item?.seller_price ?? item?.price ?? null;
}

export function formatDate(dateStr, opts = {}) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
    ...opts,
  });
}

// «5 мин назад», «2 ч назад» и т.п.
export function relativeDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return '';
  const diff = Math.floor((Date.now() - d.getTime()) / 1000);

  if (diff < 60) return 'только что';
  if (diff < 3600) return `${Math.floor(diff / 60)} мин назад`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} ч назад`;
  if (diff < 2592000) return `${Math.floor(diff / 86400)} дн назад`;
  return formatDate(dateStr);
}

// Алиас — чтобы заменить все локальные imgSrc на единый util.
export const imgSrc = mediaUrl;
