import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { register } from '../api/client';

const LEGAL_DOCUMENTS = {
  terms: {
    title: 'Пользовательское соглашение CollectIT',
    intro: 'Редакция от 08.06.2026. Настоящий текст определяет базовые правила использования сервиса CollectIT.',
    sections: [
      {
        heading: '1. Назначение сервиса',
        text: 'CollectIT предоставляет пользователям инструменты для ведения коллекций, публикации предметов, общения, оформления сделок, доставки, оплаты и обращения в поддержку.',
      },
      {
        heading: '2. Аккаунт пользователя',
        text: 'Пользователь обязуется указывать достоверные данные, сохранять доступ к аккаунту и не передавать учетные данные третьим лицам. Администрация может ограничить доступ при нарушении правил сервиса.',
      },
      {
        heading: '3. Предметы и сделки',
        text: 'Пользователь отвечает за достоверность описаний, фотографий, цены и законность размещаемых предметов. Запрещено размещать товары, оборот которых запрещен или ограничен законодательством.',
      },
      {
        heading: '4. Платежи, сбор и вывод средств',
        text: 'При сделках сервис может учитывать оплату, сервисный сбор, удержание средств до завершения сделки и заявки на вывод. Подробные условия определяются правилами сделок и платежными документами сервиса.',
      },
      {
        heading: '5. Доставка и споры',
        text: 'Для оформления доставки пользователь предоставляет контактные данные и выбранный пункт выдачи. При спорных ситуациях администрация может запросить дополнительные сведения и документы.',
      },
      {
        heading: '6. Ответственность',
        text: 'Пользователь несет ответственность за свои действия, опубликованный контент и соблюдение законодательства. Сервис вправе удалять запрещенные материалы и ограничивать подозрительные операции.',
      },
    ],
  },
  personalData: {
    title: 'Согласие на обработку персональных данных',
    intro: 'Редакция от 08.06.2026. Согласие нужно для регистрации и работы с функциями CollectIT.',
    sections: [
      {
        heading: '1. Какие данные обрабатываются',
        text: 'Сервис может обрабатывать имя пользователя, email, телефон, аватар, адрес пункта выдачи, данные сделок, сообщения в чатах, обращения в поддержку, IP-адрес, user-agent и технические cookies.',
      },
      {
        heading: '2. Цели обработки',
        text: 'Данные используются для создания аккаунта, подтверждения почты, безопасности, связи между участниками сделки, доставки, платежей, вывода средств, поддержки, уведомлений и исполнения правил сервиса.',
      },
      {
        heading: '3. Передача третьим лицам',
        text: 'Данные могут передаваться подключенным сервисам только в объеме, необходимом для работы функций: платежному провайдеру, службе доставки, email-провайдеру, Telegram-боту для уведомлений администратора и технической инфраструктуре.',
      },
      {
        heading: '4. Срок действия',
        text: 'Согласие действует до его отзыва или до достижения целей обработки. Отзыв согласия может ограничить доступ к функциям, для которых персональные данные обязательны.',
      },
      {
        heading: '5. Права пользователя',
        text: 'Пользователь может запросить уточнение, блокирование или удаление персональных данных, если это не противоречит требованиям законодательства и обязательствам по уже совершенным сделкам.',
      },
    ],
  },
};

export default function RegisterPage() {
  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    password_confirm: '',
    terms_accepted: false,
    personal_data_accepted: false,
  });
  const [error, setError] = useState('');
  const [submittedEmail, setSubmittedEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [openDocument, setOpenDocument] = useState(null);

  function set(field) {
    return e => setForm(f => ({ ...f, [field]: e.target.value }));
  }

  function setChecked(field) {
    return e => setForm(f => ({ ...f, [field]: e.target.checked }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    if (form.password !== form.password_confirm) {
      setError('Пароли не совпадают');
      return;
    }
    if (!form.terms_accepted) {
      setError('Необходимо принять пользовательское соглашение');
      return;
    }
    if (!form.personal_data_accepted) {
      setError('Необходимо дать согласие на обработку персональных данных');
      return;
    }
    setLoading(true);
    try {
      const data = await register(
        form.username,
        form.email,
        form.password,
        form.password_confirm,
        {
          termsAccepted: form.terms_accepted,
          personalDataAccepted: form.personal_data_accepted,
        },
      );
      setSubmittedEmail(data.email || form.email);
    } catch (err) {
      try {
        const parsed = JSON.parse(err.message);
        const first = Object.values(parsed)[0];
        setError(Array.isArray(first) ? first[0] : first);
      } catch {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }

  const fields = [
    { key: 'username',         label: 'Имя пользователя', type: 'text',     placeholder: 'collector42' },
    { key: 'email',            label: 'Email',             type: 'email',    placeholder: 'your@email.com' },
    { key: 'password',         label: 'Пароль',            type: 'password', placeholder: '••••••••' },
    { key: 'password_confirm', label: 'Повторите пароль',  type: 'password', placeholder: '••••••••' },
  ];

  return (
    <div className="min-h-screen app-bg flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="font-bold text-2xl tracking-tight mb-2">
            <span className="text-[#e8a635]">◆ CollectIT</span>
          </div>
          <div className="text-sm text-[#4a5568]">Создайте аккаунт</div>
        </div>

        {submittedEmail ? (
          <div className="bg-[#151c2c] border border-white/[.06] rounded-2xl p-7 flex flex-col gap-4">
            <div className="text-sm text-[#e8eaf0] leading-relaxed">
              Мы отправили письмо для подтверждения на{' '}
              <span className="text-[#e8a635] font-semibold">{submittedEmail}</span>.
            </div>
            <div className="text-sm text-[#8892a4] leading-relaxed">
              Перейдите по ссылке из письма, чтобы завершить создание аккаунта.
            </div>
            <Link
              to="/login"
              className="w-full text-center bg-[#e8a635] text-[#0a0e17] font-bold py-3 rounded-xl text-sm transition-all hover:bg-[#f0b84a]"
            >
              Перейти ко входу
            </Link>
          </div>
        ) : (
        <form onSubmit={handleSubmit} className="bg-[#151c2c] border border-white/[.06] rounded-2xl p-7 flex flex-col gap-4">
          {error && (
            <div className="text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-4 py-2.5">
              {error}
            </div>
          )}

          {fields.map(f => (
            <div key={f.key}>
              <label className="text-[11px] text-[#4a5568] uppercase tracking-widest mb-2 block">{f.label}</label>
              <input
                type={f.type}
                value={form[f.key]}
                onChange={set(f.key)}
                className="w-full bg-[#0a0e17] border border-white/[.06] rounded-xl px-4 py-3 text-sm text-[#e8eaf0] outline-none transition-all focus:border-[#e8a635] focus:shadow-[0_0_0_3px_rgba(232,166,53,0.1)] placeholder-[#4a5568]"
                placeholder={f.placeholder}
                required
              />
            </div>
          ))}

          <div className="space-y-3">
            <div className="flex items-start gap-3 rounded-xl border border-white/[.06] bg-[#0a0e17]/60 px-3 py-3">
              <input
                id="terms_accepted"
                type="checkbox"
                checked={form.terms_accepted}
                onChange={setChecked('terms_accepted')}
                className="mt-1 h-4 w-4 accent-[#e8a635]"
                required
              />
              <button
                type="button"
                onClick={() => setOpenDocument('terms')}
                className="text-left text-xs text-[#8892a4] leading-relaxed hover:text-[#e8eaf0]"
              >
                Я принимаю <span className="text-[#e8a635] hover:underline">пользовательское соглашение и правила сервиса</span>
              </button>
            </div>

            <div className="flex items-start gap-3 rounded-xl border border-white/[.06] bg-[#0a0e17]/60 px-3 py-3">
              <input
                id="personal_data_accepted"
                type="checkbox"
                checked={form.personal_data_accepted}
                onChange={setChecked('personal_data_accepted')}
                className="mt-1 h-4 w-4 accent-[#e8a635]"
                required
              />
              <button
                type="button"
                onClick={() => setOpenDocument('personalData')}
                className="text-left text-xs text-[#8892a4] leading-relaxed hover:text-[#e8eaf0]"
              >
                Даю <span className="text-[#e8a635] hover:underline">согласие на обработку персональных данных</span>
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-[#e8a635] text-[#0a0e17] font-bold py-3 rounded-xl text-sm transition-all hover:bg-[#f0b84a] disabled:opacity-50 disabled:cursor-not-allowed mt-1"
          >
            {loading ? 'Создание...' : 'Зарегистрироваться'}
          </button>

          <div className="text-center text-xs text-[#4a5568]">
            Уже есть аккаунт?{' '}
            <Link to="/login" className="text-[#e8a635] hover:underline">Войти</Link>
          </div>
        </form>
        )}
      </div>

      {openDocument && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-6">
          <div className="w-full max-w-2xl max-h-[88vh] overflow-hidden rounded-2xl border border-white/[.08] bg-[#151c2c] shadow-2xl">
            <div className="flex items-start justify-between gap-4 border-b border-white/[.06] px-5 py-4">
              <div>
                <h2 className="text-lg font-bold text-[#e8eaf0]">{LEGAL_DOCUMENTS[openDocument].title}</h2>
                <p className="mt-1 text-xs text-[#8892a4] leading-relaxed">{LEGAL_DOCUMENTS[openDocument].intro}</p>
              </div>
              <button
                type="button"
                onClick={() => setOpenDocument(null)}
                className="shrink-0 rounded-lg border border-white/[.08] px-3 py-1.5 text-xs text-[#8892a4] hover:text-[#e8eaf0] hover:border-white/[.18]"
              >
                Закрыть
              </button>
            </div>
            <div className="max-h-[68vh] overflow-y-auto px-5 py-4">
              <div className="space-y-4">
                {LEGAL_DOCUMENTS[openDocument].sections.map(section => (
                  <section key={section.heading}>
                    <h3 className="text-sm font-semibold text-[#e8a635]">{section.heading}</h3>
                    <p className="mt-1 text-sm leading-relaxed text-[#c8ceda]">{section.text}</p>
                  </section>
                ))}
              </div>
              <div className="mt-5 rounded-xl border border-[#e8a635]/20 bg-[#e8a635]/10 px-4 py-3 text-xs leading-relaxed text-[#d5b975]">
                Полные юридические документы перед коммерческим запуском нужно утвердить с профильным юристом.
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
