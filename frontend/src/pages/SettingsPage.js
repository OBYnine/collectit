import { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { getMe, updateMe, updateMeForm, changePassword, getCdekPoints } from '../api/client';
import { useUser } from '../context/UserContext';
import { mediaUrl } from '../utils/config';

// Цветные круглые маркеры — обходит проблему с путями к PNG в webpack
function makeMarkerIcon(active) {
  return L.divIcon({
    html: `<div style="
      width:14px;height:14px;
      background:${active ? '#e8a635' : '#4a5568'};
      border:2px solid ${active ? '#fff' : 'rgba(255,255,255,0.3)'};
      border-radius:50%;
      box-shadow:${active ? '0 0 0 4px rgba(232,166,53,0.25)' : 'none'};
    "></div>`,
    className: '',
    iconSize: [14, 14],
    iconAnchor: [7, 7],
    popupAnchor: [0, -10],
  });
}

function RecenterMap({ center }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, 12);
    setTimeout(() => map.invalidateSize(), 0);
  }, [center, map]);
  return null;
}

function DeliverySection({ user, onSaved }) {
  const [city, setCity]           = useState(user?.delivery_city || '');
  const [points, setPoints]       = useState([]);
  const [mapCenter, setMapCenter] = useState([55.75, 37.62]);
  const [selected, setSelected]   = useState(
    user?.delivery_point_code
      ? { code: user.delivery_point_code, address: user.delivery_point_address, name: '' }
      : null
  );
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState('');
  const [saveMsg, setSaveMsg]     = useState(null);

  // Загружаем все точки при монтировании
  useEffect(() => {
    getCdekPoints('').then(data => {
      if (data.points) {
        setPoints(data.points);
        const current = data.points.find(p => p.code === user?.delivery_point_code) || data.points[0];
        if (current?.lat && current?.lng) setMapCenter([current.lat, current.lng]);
      }
    }).catch(() => {});
  }, [user?.delivery_point_code]);

  async function handleSearch() {
    if (!city.trim()) return;
    setLoading(true);
    setError('');
    try {
      const data = await getCdekPoints(city.trim());
      if (data.error) { setError(data.error); return; }
      // Обновляем все точки и зумим на город
      if (data.points) setPoints(data.points);
      if (data.city?.lat) setMapCenter([data.city.lat, data.city.lng]);
      else if (data.points?.[0]?.lat && data.points?.[0]?.lng) setMapCenter([data.points[0].lat, data.points[0].lng]);
    } catch {
      setError('Не удалось получить данные СДЭК');
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    setSaveMsg(null);
    try {
      await updateMe({
        delivery_city: city,
        delivery_point_code: selected?.code || '',
        delivery_point_address: selected?.address || '',
      });
      setSaveMsg({ type: 'ok', text: 'Точка сохранена.' });
      onSaved();
    } catch {
      setSaveMsg({ type: 'err', text: 'Ошибка сохранения.' });
    }
  }

  return (
    <div className="bg-[#151c2c] rounded-2xl p-6 mt-6">
      <p className="text-[#8892a4] text-xs font-medium uppercase tracking-wider mb-5">
        Точка самовывоза СДЭК
      </p>

      {user?.delivery_point_code && (
        <div className="mb-5 p-3 bg-[#0d1321] rounded-xl border border-[#e8a635]/20">
          <div className="text-[10px] text-[#4a5568] uppercase tracking-wider mb-1">Сохранённая точка</div>
          <div className="text-sm text-[#e8eaf0] font-semibold">{user.delivery_city} — {user.delivery_point_code}</div>
          <div className="text-xs text-[#8892a4] mt-0.5">{user.delivery_point_address}</div>
        </div>
      )}

      <div className="flex gap-3 mb-4">
        <input
          value={city}
          onChange={e => setCity(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          placeholder="Введите город (напр. Москва)"
          className="flex-1 bg-[#0a0e17] text-[#e8eaf0] text-sm px-4 py-2.5 rounded-lg border border-white/[.08] outline-none focus:border-[#e8a635]/50 transition-colors placeholder-[#4a5568]"
        />
        <button
          onClick={handleSearch}
          disabled={loading}
          className="px-5 py-2.5 bg-[#e8a635] text-[#0a0e17] text-sm font-semibold rounded-lg disabled:opacity-50 transition-opacity"
        >
          {loading ? '...' : 'Найти'}
        </button>
      </div>

      {error && <p className="text-red-400 text-sm mb-3">{error}</p>}

      {points.length > 0 && (
        <>
          <p className="text-xs text-[#4a5568] mb-2">
            {points.length} точек — нажмите на маркер для выбора
          </p>
          <div style={{ height: 360, borderRadius: 12, overflow: 'hidden' }} className="mb-4">
            <MapContainer center={mapCenter} zoom={5} style={{ height: '100%', width: '100%' }} attributionControl={false}>
              <TileLayer
                url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              />
              <RecenterMap center={mapCenter} />
              {points.map(p => (
                <Marker
                  key={p.code}
                  position={[p.lat, p.lng]}
                  icon={makeMarkerIcon(selected?.code === p.code)}
                  eventHandlers={{ click: () => setSelected(p) }}
                >
                  <Popup>
                    <div style={{ fontSize: 13, lineHeight: 1.5 }}>
                      <b>{p.name}</b><br />
                      {p.address}<br />
                      {p.work_time && <span style={{ color: '#888' }}>{p.work_time}</span>}
                    </div>
                  </Popup>
                </Marker>
              ))}
            </MapContainer>
          </div>

          {selected && (
            <div className="p-3 bg-[#0d1321] rounded-xl border border-[#e8a635]/30 mb-4">
              <div className="text-[10px] text-[#e8a635] uppercase tracking-wider mb-1">Выбрана</div>
              <div className="text-sm text-[#e8eaf0] font-semibold">{selected.name || selected.code}</div>
              <div className="text-xs text-[#8892a4] mt-0.5">{selected.address}</div>
              {selected.work_time && (
                <div className="text-xs text-[#4a5568] mt-0.5">{selected.work_time}</div>
              )}
            </div>
          )}
        </>
      )}

      {saveMsg && (
        <p className={`text-sm mb-3 ${saveMsg.type === 'ok' ? 'text-emerald-400' : 'text-red-400'}`}>
          {saveMsg.text}
        </p>
      )}

      {selected && (
        <button
          onClick={handleSave}
          className="px-6 py-2.5 bg-[#e8a635] text-[#0a0e17] text-sm font-semibold rounded-lg"
        >
          Сохранить точку
        </button>
      )}
    </div>
  );
}

export default function SettingsPage() {
  const { refreshUser } = useUser();
  const [user, setUser]             = useState(null);
  const [profileMsg, setProfileMsg] = useState(null);
  const [passMsg, setPassMsg]       = useState(null);
  const [avatarPreview, setAvatarPreview] = useState(null);
  const avatarInputRef = useRef();

  const [username, setUsername] = useState('');
  const [email, setEmail]       = useState('');
  const [bio, setBio]           = useState('');
  const [phone, setPhone]       = useState('');
  const [avatarFile, setAvatarFile] = useState(null);

  const [oldPass, setOldPass]         = useState('');
  const [newPass, setNewPass]         = useState('');
  const [confirmPass, setConfirmPass] = useState('');

  useEffect(() => {
    getMe().then(u => {
      setUser(u);
      setUsername(u.username || '');
      setEmail(u.email || '');
      setBio(u.bio || '');
      setPhone(u.phone || '');
    });
  }, []);

  function handleAvatarChange(e) {
    const file = e.target.files[0];
    if (!file) return;
    setAvatarFile(file);
    setAvatarPreview(URL.createObjectURL(file));
  }

  async function handleProfileSave(e) {
    e.preventDefault();
    setProfileMsg(null);
    try {
      if (avatarFile) {
        const fd = new FormData();
        fd.append('username', username);
        fd.append('email', email);
        fd.append('bio', bio);
        fd.append('phone', phone);
        fd.append('avatar', avatarFile);
        const updated = await updateMeForm(fd);
        setUser(updated);
      } else {
        const updated = await updateMe({ username, email, bio, phone });
        setUser(updated);
      }
      await refreshUser();
      setProfileMsg({ type: 'ok', text: 'Данные сохранены.' });
    } catch (err) {
      let text = 'Ошибка сохранения.';
      try { text = Object.values(JSON.parse(err.message)).flat().join(' '); } catch {}
      setProfileMsg({ type: 'err', text });
    }
  }

  async function handlePasswordSave(e) {
    e.preventDefault();
    setPassMsg(null);
    if (newPass !== confirmPass) {
      setPassMsg({ type: 'err', text: 'Новые пароли не совпадают.' });
      return;
    }
    try {
      await changePassword({ old_password: oldPass, new_password: newPass });
      setPassMsg({ type: 'ok', text: 'Пароль изменён.' });
      setOldPass(''); setNewPass(''); setConfirmPass('');
    } catch (err) {
      let text = 'Ошибка.';
      try { text = Object.values(JSON.parse(err.message)).flat().join(' '); } catch {}
      setPassMsg({ type: 'err', text });
    }
  }

  const avatarSrc = avatarPreview
    || mediaUrl(user?.avatar);
  const initials = user?.username?.[0]?.toUpperCase() || 'U';

  return (
    <div className="max-w-xl mx-auto px-4 py-10">
      <h1 className="text-[#e8eaf0] text-xl font-semibold mb-8">Настройки</h1>

      {/* Профиль */}
      <form onSubmit={handleProfileSave} className="bg-[#151c2c] rounded-2xl p-6 mb-6">
        <p className="text-[#8892a4] text-xs font-medium uppercase tracking-wider mb-5">Профиль</p>

        <div className="flex items-center gap-5 mb-6">
          <div
            className="w-[72px] h-[72px] rounded-full overflow-hidden bg-[#e8a635] flex items-center justify-center cursor-pointer flex-shrink-0"
            onClick={() => avatarInputRef.current.click()}
          >
            {avatarSrc
              ? <img src={avatarSrc} alt="avatar" className="w-full h-full object-cover" />
              : <span className="text-[#0a0e17] text-2xl font-bold">{initials}</span>
            }
          </div>
          <div>
            <button type="button" onClick={() => avatarInputRef.current.click()}
              className="text-sm text-[#e8a635] hover:text-[#f0b84a] transition-colors">
              Изменить фото
            </button>
            <p className="text-[#4a5568] text-xs mt-1">JPG, PNG до 5 МБ</p>
          </div>
          <input ref={avatarInputRef} type="file" accept="image/*" className="hidden" onChange={handleAvatarChange} />
        </div>

        <div className="flex flex-col gap-4">
          <div>
            <label className="text-[#8892a4] text-xs mb-1.5 block">Имя пользователя</label>
            <input value={username} onChange={e => setUsername(e.target.value)}
              className="w-full bg-[#0a0e17] text-[#e8eaf0] text-sm px-4 py-2.5 rounded-lg border border-white/[.08] outline-none focus:border-[#e8a635]/50 transition-colors" />
          </div>
          <div>
            <label className="text-[#8892a4] text-xs mb-1.5 block">Email</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)}
              className="w-full bg-[#0a0e17] text-[#e8eaf0] text-sm px-4 py-2.5 rounded-lg border border-white/[.08] outline-none focus:border-[#e8a635]/50 transition-colors" />
          </div>
          <div>
            <label className="text-[#8892a4] text-xs mb-1.5 block">О себе</label>
            <textarea value={bio} onChange={e => setBio(e.target.value)} rows={3}
              className="w-full bg-[#0a0e17] text-[#e8eaf0] text-sm px-4 py-2.5 rounded-lg border border-white/[.08] outline-none focus:border-[#e8a635]/50 transition-colors resize-none" />
          </div>
          <div>
            <label className="text-[#8892a4] text-xs mb-1.5 block">Номер телефона</label>
            <input type="tel" value={phone} onChange={e => setPhone(e.target.value)}
              placeholder="+7 900 000 00 00"
              className="w-full bg-[#0a0e17] text-[#e8eaf0] text-sm px-4 py-2.5 rounded-lg border border-white/[.08] outline-none focus:border-[#e8a635]/50 transition-colors" />
            <p className="text-[#4a5568] text-[11px] mt-1">Используется для оформления доставки СДЭК</p>
          </div>
        </div>

        {profileMsg && (
          <p className={`text-sm mt-4 ${profileMsg.type === 'ok' ? 'text-emerald-400' : 'text-red-400'}`}>
            {profileMsg.text}
          </p>
        )}
        <button type="submit"
          className="mt-5 px-6 py-2.5 bg-[#e8a635] text-[#0a0e17] text-sm font-semibold rounded-lg hover:bg-[#f0b84a] transition-colors">
          Сохранить
        </button>
      </form>

      {/* Доставка СДЭК */}
      {user && (
        <DeliverySection
          user={user}
          onSaved={async () => { const u = await getMe(); setUser(u); }}
        />
      )}

      {/* Пароль */}
      <form onSubmit={handlePasswordSave} className="bg-[#151c2c] rounded-2xl p-6 mt-6">
        <p className="text-[#8892a4] text-xs font-medium uppercase tracking-wider mb-5">Смена пароля</p>

        <div className="flex flex-col gap-4">
          <div>
            <label className="text-[#8892a4] text-xs mb-1.5 block">Текущий пароль</label>
            <input type="password" value={oldPass} onChange={e => setOldPass(e.target.value)}
              className="w-full bg-[#0a0e17] text-[#e8eaf0] text-sm px-4 py-2.5 rounded-lg border border-white/[.08] outline-none focus:border-[#e8a635]/50 transition-colors" />
          </div>
          <div>
            <label className="text-[#8892a4] text-xs mb-1.5 block">Новый пароль</label>
            <input type="password" value={newPass} onChange={e => setNewPass(e.target.value)}
              className="w-full bg-[#0a0e17] text-[#e8eaf0] text-sm px-4 py-2.5 rounded-lg border border-white/[.08] outline-none focus:border-[#e8a635]/50 transition-colors" />
          </div>
          <div>
            <label className="text-[#8892a4] text-xs mb-1.5 block">Повторите новый пароль</label>
            <input type="password" value={confirmPass} onChange={e => setConfirmPass(e.target.value)}
              className="w-full bg-[#0a0e17] text-[#e8eaf0] text-sm px-4 py-2.5 rounded-lg border border-white/[.08] outline-none focus:border-[#e8a635]/50 transition-colors" />
          </div>
        </div>

        {passMsg && (
          <p className={`text-sm mt-4 ${passMsg.type === 'ok' ? 'text-emerald-400' : 'text-red-400'}`}>
            {passMsg.text}
          </p>
        )}
        <button type="submit"
          className="mt-5 px-6 py-2.5 bg-[#1e2a3a] text-[#e8eaf0] text-sm font-semibold rounded-lg border border-white/[.08] hover:border-white/20 transition-colors">
          Изменить пароль
        </button>
      </form>
    </div>
  );
}
