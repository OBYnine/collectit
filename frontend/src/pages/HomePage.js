import { Link } from 'react-router-dom';
import { isAuthenticated } from '../api/client';

const heroImage =
  '/assets/collectit-hero.png';

const storyImages = [
  {
    src: '/assets/collectit-story-coins.png',
    alt: 'Коллекционные монеты на темном фоне',
  },
  {
    src: '/assets/collectit-story-stamps.png',
    alt: 'Коллекционные почтовые марки на темном фоне',
  },
  {
    src: '/assets/collectit-story-magnifier.png',
    alt: 'Винтажная лупа на темном фоне',
  },
];

const capabilities = [
  {
    number: '01',
    title: 'Предмет как полноценная карточка',
    text: 'Добавляйте несколько фотографий, описание, стоимость и статус продажи. Покупатель видит предмет не по одной случайной картинке, а как аккуратную витрину.',
    accent: 'border-[#e8a635]/45',
  },
  {
    number: '02',
    title: 'Поиск с понятными фильтрами',
    text: 'Можно искать по названию, смотреть только предметы с фото, ограничивать цену и сортировать выдачу. Это помогает быстрее найти нужный экземпляр.',
    accent: 'border-[#38bdf8]/45',
  },
  {
    number: '03',
    title: 'Оплата с удержанием средств',
    text: 'Деньги покупателя фиксируются на время сделки. Администратор видит удержанные суммы и может завершить выплату или вернуть деньги покупателю.',
    accent: 'border-[#22c55e]/45',
  },
  {
    number: '04',
    title: 'Чат, архив и код обращения',
    text: 'Переписка остается доступной после завершения сделки как архив. В чате показывается код, по которому поддержка быстро находит нужную сделку.',
    accent: 'border-[#f472b6]/45',
  },
  {
    number: '05',
    title: 'Доставка через пункт выдачи',
    text: 'Покупатель выбирает пункт СДЭК на карте, а выбранный адрес сохраняется в сценарии сделки. Это снижает путаницу при отправке.',
    accent: 'border-[#a3e635]/45',
  },
  {
    number: '06',
    title: 'Важные события и доступность',
    text: 'Важные события появляются внутри сайта, а часть уведомлений можно дублировать на почту. Для слабовидящих доступен режим повышенной контрастности.',
    accent: 'border-[#fb7185]/45',
  },
];

const workflow = [
  ['Заведите витрину', 'Создайте коллекцию, добавьте предметы и фотографии, отметьте то, что готовы продать.'],
  ['Обсудите детали', 'Покупатель пишет продавцу, стороны уточняют состояние, цену, доставку и спорные моменты.'],
  ['Проведите оплату', 'Сумма удерживается до результата сделки, чтобы у обеих сторон было больше контроля.'],
  ['Сохраните историю', 'Завершенные диалоги остаются архивом, а поддержку можно быстро подключить по коду чата.'],
];

const faq = [
  {
    question: 'Можно ли использовать CollectIT просто как личный каталог?',
    answer:
      'Да. Предметы можно хранить в коллекциях и не выставлять на продажу. Публичность коллекции и статус продажи управляются отдельно.',
  },
  {
    question: 'Что происходит с деньгами во время сделки?',
    answer:
      'Платеж проходит через сценарий удержания. Пока сделка не завершена, сумма видна администратору как удержанная. После проверки деньги можно перечислить продавцу или вернуть покупателю.',
  },
  {
    question: 'Зачем нужен код в чате?',
    answer:
      'Код помогает поддержке быстро найти конкретную переписку или сделку, если пользователь пишет администратору о проблеме.',
  },
  {
    question: 'Можно ли удалить архивную переписку?',
    answer:
      'Архив можно скрыть локально у покупателя или продавца. Это не ломает историю сделки для второй стороны и поддержки.',
  },
  {
    question: 'Нужна ли отдельная установка для мобильной версии?',
    answer:
      'Нет. Интерфейс адаптируется под мобильный экран, а основные действия доступны из браузера.',
  },
];

export default function HomePage() {
  const authed = isAuthenticated();

  return (
    <div className="min-h-screen bg-[#0a0e17] text-[#e8eaf0] overflow-hidden">
      <section className="relative min-h-[78vh] flex flex-col">
        <img
          src={heroImage}
          alt="Стол коллекционера с редкими предметами"
          className="absolute inset-0 w-full h-full object-cover object-center"
        />
        <div className="absolute inset-0 bg-[#0a0e17]/35" />
        <div className="absolute inset-0 bg-gradient-to-r from-[#0a0e17]/35 via-transparent to-[#0a0e17]/35" />
        <div className="absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-[#0a0e17] to-transparent" />

        <header className="relative z-10 max-w-6xl mx-auto w-full px-5 sm:px-8 py-5 flex items-center justify-between gap-4">
          <Link to="/" className="text-xl font-bold text-[#e8a635]">
            CollectIT
          </Link>
          <div className="flex items-center gap-2">
            {authed ? (
              <>
                <Link to="/search" className="px-4 py-2 rounded-lg text-sm text-[#d8dde8] hover:text-white transition-colors">Поиск</Link>
                <Link to="/profile" className="px-4 py-2 rounded-lg bg-[#e8a635] text-[#0a0e17] text-sm font-semibold">Профиль</Link>
              </>
            ) : (
              <>
                <Link to="/login" className="px-4 py-2 rounded-lg text-sm text-[#d8dde8] hover:text-white transition-colors">Войти</Link>
                <Link to="/register" className="px-4 py-2 rounded-lg bg-[#e8a635] text-[#0a0e17] text-sm font-semibold">Зарегистрироваться</Link>
              </>
            )}
          </div>
        </header>

        <div className="relative z-10 max-w-6xl mx-auto w-full px-5 sm:px-8 flex-1 flex items-center justify-center py-12">
          <div className="max-w-3xl mx-auto text-center">
            <p className="text-sm text-[#e8a635] font-semibold mb-5">Платформа для коллекционеров и безопасных сделок</p>
            <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold leading-none">
              CollectIT
            </h1>
            <p className="mt-6 text-base sm:text-xl text-[#d8dde8] leading-relaxed max-w-2xl">
              Ведите коллекции, показывайте предметы с несколькими фотографиями, находите покупателей, общайтесь в чате и проводите сделки с удержанием средств до результата.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Link to={authed ? '/search' : '/register'} className="px-6 py-3 rounded-lg bg-[#e8a635] text-[#0a0e17] font-semibold hover:bg-[#f0b84a] transition-colors">
                {authed ? 'Перейти к поиску' : 'Начать пользоваться'}
              </Link>
              <Link to="/search" className="px-6 py-3 rounded-lg border border-white/[.18] text-white hover:bg-white/[.08] transition-colors">
                Посмотреть предметы
              </Link>
            </div>
          </div>
        </div>
      </section>

      <main>
        <section className="max-w-6xl mx-auto px-5 sm:px-8 py-14">
          <div className="grid lg:grid-cols-[0.82fr_1.18fr] gap-10 items-center">
            <div>
              <p className="text-sm text-[#e8a635] font-semibold mb-3">Зачем нужна платформа</p>
              <h2 className="text-3xl sm:text-4xl font-bold leading-tight">
                Не просто список вещей, а рабочее место коллекционера
              </h2>
              <p className="mt-5 text-[#8892a4] leading-relaxed">
                CollectIT собирает в одном месте каталог предметов, публичную витрину, поиск, переписку, доставку и финансовый контроль сделки. Сервис помогает не терять детали, фотографии, договоренности и историю общения.
              </p>
            </div>
            <div className="grid sm:grid-cols-3 gap-3">
              {storyImages.map((image, index) => (
                <div key={image.src} className={`home-photo-frame h-56 sm:h-72 rounded-lg overflow-hidden border border-white/[.08] bg-[#151c2c] ${index === 1 ? 'sm:mt-8' : ''}`}>
                  <img src={image.src} alt={image.alt} className="w-full h-full object-cover" />
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="border-y border-white/[.06] bg-[#0d121c]">
          <div className="max-w-6xl mx-auto px-5 sm:px-8 py-14">
            <div className="max-w-2xl mb-8">
              <p className="text-sm text-[#e8a635] font-semibold mb-3">Возможности</p>
              <h2 className="text-3xl sm:text-4xl font-bold leading-tight">
                Что уже закрывает CollectIT
              </h2>
            </div>

            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {capabilities.map(feature => (
                <article key={feature.number} className={`relative home-sweep rounded-lg border ${feature.accent} bg-[#151c2c] p-5 min-h-[210px] overflow-hidden`}>
                  <div className="font-['JetBrains_Mono'] text-xs text-[#e8a635] mb-5">{feature.number}</div>
                  <h3 className="text-lg font-semibold leading-snug">{feature.title}</h3>
                  <p className="mt-3 text-sm text-[#8892a4] leading-relaxed">{feature.text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="max-w-6xl mx-auto px-5 sm:px-8 py-14">
          <div className="grid lg:grid-cols-[1fr_0.9fr] gap-10 items-start">
            <div>
              <p className="text-sm text-[#e8a635] font-semibold mb-3">Путь пользователя</p>
              <h2 className="text-3xl sm:text-4xl font-bold leading-tight">
                От добавления предмета до закрытой сделки
              </h2>
            </div>
            <div className="space-y-3">
              {workflow.map(([title, text], index) => (
                <div key={title} className="grid grid-cols-[48px_1fr] gap-4 rounded-lg border border-white/[.08] bg-[#151c2c] p-4">
                  <div className="w-10 h-10 rounded-lg bg-[#e8a635] text-[#0a0e17] font-bold flex items-center justify-center">
                    {index + 1}
                  </div>
                  <div>
                    <h3 className="font-semibold">{title}</h3>
                    <p className="mt-1 text-sm text-[#8892a4] leading-relaxed">{text}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="relative overflow-hidden border-y border-white/[.06] bg-[#101724]">
          <div className="home-moving-line" />
          <div className="max-w-6xl mx-auto px-5 sm:px-8 py-14 grid lg:grid-cols-[0.9fr_1.1fr] gap-10 items-center">
            <div className="relative h-72 sm:h-96 rounded-lg overflow-hidden border border-white/[.08]">
              <img
                src="https://images.unsplash.com/photo-1554224155-6726b3ff858f?auto=format&fit=crop&w=1200&q=80"
                alt="Проверка деталей сделки и оплаты"
                className="w-full h-full object-cover"
              />
              <div className="absolute inset-0 bg-[#0a0e17]/25" />
            </div>
            <div>
              <p className="text-sm text-[#e8a635] font-semibold mb-3">Контроль и доверие</p>
              <h2 className="text-3xl sm:text-4xl font-bold leading-tight">
                Администратор видит спорные места, а пользователи не теряют контекст
              </h2>
              <p className="mt-5 text-[#8892a4] leading-relaxed">
                Сделка хранится с собственным идентификатором, чат получает код обращения, удержанные суммы видны в админке, а архив переписки остается доступным после завершения. Это особенно важно для редких вещей, где состояние, упаковка и доставка решают многое.
              </p>
            </div>
          </div>
        </section>

        <section className="max-w-6xl mx-auto px-5 sm:px-8 py-14">
          <div className="grid lg:grid-cols-[0.8fr_1.2fr] gap-10">
            <div>
              <p className="text-sm text-[#e8a635] font-semibold mb-3">FAQ</p>
              <h2 className="text-3xl sm:text-4xl font-bold leading-tight">
                Частые вопросы
              </h2>
              <p className="mt-4 text-[#8892a4] leading-relaxed">
                Короткие ответы на вопросы, которые возникают перед регистрацией и первой сделкой.
              </p>
            </div>

            <div className="space-y-3">
              {faq.map(item => (
                <details key={item.question} className="group rounded-lg border border-white/[.08] bg-[#151c2c] p-5">
                  <summary className="cursor-pointer list-none flex items-center justify-between gap-4">
                    <span className="font-semibold">{item.question}</span>
                    <span className="text-[#e8a635] group-open:rotate-45 transition-transform text-2xl leading-none">+</span>
                  </summary>
                  <p className="mt-3 text-sm text-[#8892a4] leading-relaxed">{item.answer}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="max-w-6xl mx-auto px-5 sm:px-8 pb-16">
          <div className="rounded-lg border border-white/[.08] bg-[#151c2c] px-5 sm:px-8 py-8 flex flex-col md:flex-row md:items-center md:justify-between gap-5">
            <div>
              <h2 className="text-2xl font-bold">Готовы собрать свою витрину?</h2>
              <p className="mt-2 text-sm text-[#8892a4]">
                Зарегистрируйтесь, добавьте первый предмет и проверьте, как выглядит профиль коллекционера.
              </p>
            </div>
            <Link to={authed ? '/profile' : '/register'} className="inline-flex justify-center px-6 py-3 rounded-lg bg-[#e8a635] text-[#0a0e17] font-semibold hover:bg-[#f0b84a] transition-colors shrink-0">
              {authed ? 'Открыть профиль' : 'Создать аккаунт'}
            </Link>
          </div>
        </section>
      </main>
    </div>
  );
}
