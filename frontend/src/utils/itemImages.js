import { mediaUrl } from './config';

export function itemImageUrls(item) {
  const urls = [];
  if (item?.image) urls.push(mediaUrl(item.image));
  for (const entry of item?.images || []) {
    const url = mediaUrl(entry.image);
    if (url && !urls.includes(url)) urls.push(url);
  }
  return urls.filter(Boolean);
}

export function itemCoverUrl(item) {
  return itemImageUrls(item)[0] || '';
}
