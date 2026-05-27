/**
 * API client for CollectIt backend.
 *
 * Авторизация — через httpOnly cookie (access_token / refresh_token).
 * Старый localStorage-механизм оставлен ТОЛЬКО для миграции существующих сессий
 * (если пользователь уже залогинен старым способом, токен ещё работает),
 * новые логины кладут токен в cookie.
 */

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000/api";

// --- Auth state (флаг "залогинен", не сам токен) ---
const AUTH_FLAG = "collecta_authed";

// Старые ключи (пробуем мигрировать наружу).
const LEGACY_ACCESS = "access_token";
const LEGACY_REFRESH = "refresh_token";

let accessToken = localStorage.getItem(LEGACY_ACCESS); // legacy, скоро убираем
let refreshToken = localStorage.getItem(LEGACY_REFRESH);

export function setTokens(access, refresh) {
  // Legacy совместимость: токены в localStorage. Новый login() их не использует,
  // но если кто-то ещё дёргает старое API — пусть работает.
  accessToken = access;
  refreshToken = refresh;
  if (access)  localStorage.setItem(LEGACY_ACCESS, access);
  if (refresh) localStorage.setItem(LEGACY_REFRESH, refresh);
  localStorage.setItem(AUTH_FLAG, "1");
}

export function clearTokens() {
  accessToken = null;
  refreshToken = null;
  localStorage.removeItem(LEGACY_ACCESS);
  localStorage.removeItem(LEGACY_REFRESH);
  localStorage.removeItem(AUTH_FLAG);
}

export function isAuthenticated() {
  // Куку прочитать из JS нельзя (httpOnly), поэтому держим отдельный публичный флаг.
  return !!accessToken || localStorage.getItem(AUTH_FLAG) === "1";
}

export async function logout() {
  // Серверу — очистить cookies; локально — снять флаг и legacy-токены.
  try {
    await fetch(`${API_BASE}/accounts/cookie-logout/`, {
      method: "POST",
      credentials: "include",
    });
  } catch {}
  clearTokens();
}

// --- Fetch wrapper ---
async function apiFetch(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const isFormData = options.body instanceof FormData;
  const headers = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...options.headers,
  };

  // Legacy-режим: если у пользователя ещё лежит токен в localStorage — отправим его.
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;

  // credentials: 'include' — чтобы браузер посылал httpOnly-cookies.
  let response = await fetch(url, { ...options, headers, credentials: "include" });

  // Auto-refresh on 401: сначала пробуем cookie-refresh (новый), затем legacy.
  if (response.status === 401) {
    let refreshed = false;
    try {
      const r = await fetch(`${API_BASE}/accounts/cookie-refresh/`, {
        method: "POST", credentials: "include",
      });
      if (r.ok) refreshed = true;
    } catch {}

    if (!refreshed && refreshToken) {
      // Legacy fallback
      try {
        const refreshRes = await fetch(`${API_BASE}/auth/token/refresh/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh: refreshToken }),
        });
        if (refreshRes.ok) {
          const data = await refreshRes.json();
          setTokens(data.access, refreshToken);
          headers["Authorization"] = `Bearer ${data.access}`;
          refreshed = true;
        }
      } catch {}
    }

    if (refreshed) {
      response = await fetch(url, { ...options, headers, credentials: "include" });
    } else {
      clearTokens();
      window.location.href = "/login";
      return null;
    }
  }

  return response;
}

// --- Auth ---
export async function login(email, password) {
  let res;
  try {
    res = await fetch(`${API_BASE}/accounts/cookie-login/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email, password }),
    });
  } catch {
    throw new Error("Нет связи с сервером. Убедитесь, что бэкенд запущен.");
  }
  if (!res.ok) throw new Error("Неверный email или пароль");
  const data = await res.json();
  // Токены теперь в httpOnly cookie. Локально только ставим публичный флаг.
  localStorage.setItem(AUTH_FLAG, "1");
  // Чистим legacy-токены — теперь не нужны.
  localStorage.removeItem(LEGACY_ACCESS);
  localStorage.removeItem(LEGACY_REFRESH);
  accessToken = null;
  refreshToken = null;
  return data;
}

export async function register(username, email, password, passwordConfirm) {
  const res = await fetch(`${API_BASE}/accounts/register/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username,
      email,
      password,
      password_confirm: passwordConfirm,
    }),
  });
  if (!res.ok) {
    const errors = await res.json();
    throw new Error(JSON.stringify(errors));
  }
  return res.json();
}

export async function verifyEmail(token) {
  const res = await fetch(`${API_BASE}/accounts/verify-email/${encodeURIComponent(token)}/`, {
    method: "GET",
    credentials: "include",
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Не удалось подтвердить email");
  }
  return data;
}

// --- Profile ---
export async function getMe() {
  const res = await apiFetch("/accounts/me/");
  return res.json();
}

export async function updateMe(data) {
  const res = await apiFetch("/accounts/me/", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function updateMeForm(formData) {
  const res = await apiFetch("/accounts/me/", {
    method: "PATCH",
    body: formData,
  });
  return res.json();
}

export async function changePassword(data) {
  const res = await apiFetch("/accounts/change-password/", {
    method: "POST",
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(JSON.stringify(err));
  }
  return res.json();
}

export async function getUserProfile(username) {
  const res = await apiFetch(`/accounts/users/${username}/`);
  return res.json();
}

export async function getPublicCollections(userId) {
  const res = await apiFetch(`/collections/collections/?owner=${userId}`);
  return res.json();
}

export async function getForSalePrivateItems(userId) {
  const res = await apiFetch(`/collections/items/?owner=${userId}&private_for_sale=1`);
  return res.json();
}

// --- Collections ---
export async function getMyCollections() {
  const res = await apiFetch("/collections/collections/?owner=me");
  return res.json();
}

export async function getCollection(id) {
  const res = await apiFetch(`/collections/collections/${id}/`);
  return res.json();
}

export async function createCollection(data) {
  const res = await apiFetch("/collections/collections/", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function updateCollection(id, data) {
  const res = await apiFetch(`/collections/collections/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function deleteCollection(id) {
  return apiFetch(`/collections/collections/${id}/`, { method: "DELETE" });
}

// --- Items ---
export async function getMyItems() {
  const res = await apiFetch("/collections/items/?owner=me");
  return res.json();
}

export async function createItem(formData) {
  const res = await apiFetch("/collections/items/", {
    method: "POST",
    body: formData,
  });
  return res.json();
}

export async function updateItem(id, formData) {
  const res = await apiFetch(`/collections/items/${id}/`, {
    method: "PATCH",
    body: formData,
  });
  return res.json();
}

export async function deleteItem(id) {
  return apiFetch(`/collections/items/${id}/`, { method: "DELETE" });
}

// --- CDEK ---
export async function getCdekPoints(city) {
  const query = city ? `?city=${encodeURIComponent(city)}` : '';
  const res = await apiFetch(`/accounts/cdek-points/${query}`);
  return res.json();
}

// --- Wishlist ---
export async function toggleWishlist(itemId) {
  const res = await apiFetch(`/collections/wishlist/${itemId}/`, { method: "POST" });
  return res.json();
}

export async function getWishlist() {
  const res = await apiFetch("/collections/wishlist/");
  return res.json();
}

// --- News ---
export async function getNews(page = 1) {
  const res = await apiFetch(`/news/articles/?page=${page}`);
  return res.json();
}

export async function createArticle(formData) {
  const res = await apiFetch('/news/articles/', { method: 'POST', body: formData });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function updateArticle(id, formData) {
  const res = await apiFetch(`/news/articles/${id}/`, { method: 'PATCH', body: formData });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function deleteArticle(id) {
  const res = await apiFetch(`/news/articles/${id}/`, { method: 'DELETE' });
  if (!res.ok) throw new Error(await res.text());
}

export async function getArticle(id) {
  const res = await apiFetch(`/news/articles/${id}/`);
  return res.json();
}

// --- Support ---
export async function getTickets() {
  const res = await apiFetch('/support/tickets/');
  return res.json();
}

export async function createTicket(topic, message) {
  const res = await apiFetch('/support/tickets/', {
    method: 'POST',
    body: JSON.stringify({ topic, message }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function sendTicketMessage(id, message) {
  const res = await apiFetch(`/support/tickets/${id}/messages/`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function confirmTicketResolved(id) {
  const res = await apiFetch(`/support/tickets/${id}/resolve/`, { method: 'POST' });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getAdminTickets(params = {}) {
  const query = new URLSearchParams(params).toString();
  const res = await apiFetch(`/support/admin/tickets/${query ? `?${query}` : ''}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function updateAdminTicket(id, data) {
  const res = await apiFetch(`/support/admin/tickets/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// --- Search ---
export async function searchItems(params = {}) {
  const query = new URLSearchParams(params).toString();
  const res = await apiFetch(`/search/?${query}`);
  return res.json();
}

// --- Notifications ---
export async function getNotifications() {
  const res = await apiFetch("/notifications/");
  return res.json();
}

export async function getUnreadCount() {
  const res = await apiFetch("/notifications/unread-count/");
  return res.json();
}

export async function markAllRead() {
  return apiFetch("/notifications/mark-read/", { method: "POST" });
}

// --- Chats ---
// --- Balance ---
export async function getTransactions() {
  const res = await apiFetch("/accounts/transactions/");
  return res.json();
}

export async function depositBalance(amount) {
  const res = await apiFetch("/accounts/deposit/", {
    method: "POST",
    body: JSON.stringify({ amount }),
  });
  return res.json();
}

export async function createPayment(amount) {
  const res = await apiFetch("/accounts/create-payment/", {
    method: "POST",
    body: JSON.stringify({ amount }),
  });
  return res.json();
}

export async function verifyPayment(paymentId) {
  const res = await apiFetch("/accounts/verify-payment/", {
    method: "POST",
    body: JSON.stringify({ payment_id: paymentId }),
  });
  return res.json();
}

export async function getChatUnreadCount() {
  const res = await apiFetch("/chats/unread-count/");
  return res.json();
}

export async function getChats() {
  const res = await apiFetch("/chats/");
  return res.json();
}

export async function getOrCreateChat(username, itemName = "", itemImage = "", itemPrice = null, sellerIsOther = false, itemId = null) {
  const res = await apiFetch("/chats/", {
    method: "POST",
    body: JSON.stringify({
      username,
      item_name: itemName,
      item_image: itemImage,
      item_price: itemPrice,
      seller_is_other: sellerIsOther,
      item_id: itemId,
    }),
  });
  return res.json();
}

export async function agreeChatSale(chatId) {
  const res = await apiFetch(`/chats/${chatId}/agree/`, { method: "POST" });
  return res.json();
}

export async function payChatFromBalance(chatId) {
  const res = await apiFetch(`/chats/${chatId}/pay/`, { method: "POST" });
  return res.json();
}

export async function shipChat(chatId) {
  const res = await apiFetch(`/chats/${chatId}/ship/`, { method: "POST" });
  return res.json();
}

export async function confirmReceipt(chatId) {
  const res = await apiFetch(`/chats/${chatId}/confirm-receipt/`, { method: "POST" });
  return res.json();
}

export async function rateChat(chatId, rating) {
  const res = await apiFetch(`/chats/${chatId}/rate/`, {
    method: "POST",
    body: JSON.stringify({ rating }),
  });
  return res.json();
}

export async function acknowledgeRating(chatId) {
  const res = await apiFetch(`/chats/${chatId}/acknowledge/`, { method: "POST" });
  return res.json();
}

export async function hideChat(chatId) {
  const res = await apiFetch(`/chats/${chatId}/hide/`, { method: "DELETE" });
  return res.json();
}

export async function getDeals() {
  const res = await apiFetch("/chats/deals/");
  return res.json();
}

export async function getMessages(chatId) {
  const res = await apiFetch(`/chats/${chatId}/messages/`);
  return res.json();
}

export async function sendMessage(chatId, text) {
  const res = await apiFetch(`/chats/${chatId}/messages/`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
  return res.json();
}

