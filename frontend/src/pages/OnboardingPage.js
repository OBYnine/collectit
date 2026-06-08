import { Link, useNavigate } from 'react-router-dom';
import { useUser } from '../context/UserContext';
import { getOnboardingProgress, ONBOARDING_TOTAL_XP } from '../utils/onboarding';

function ProgressBar({ percent }) {
  return (
    <div className="h-2 rounded-full bg-white/[.06] overflow-hidden">
      <div
        className="h-full rounded-full bg-[#e8a635] transition-all duration-500"
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}

function StepIcon({ step }) {
  if (step.done) {
    return (
      <svg viewBox="0 0 24 24" fill="none" className="w-5 h-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 6L9 17l-5-5" />
      </svg>
    );
  }

  if (step.locked) {
    return (
      <svg viewBox="0 0 24 24" fill="none" className="w-5 h-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="5" y="11" width="14" height="10" rx="2" />
        <path d="M8 11V8a4 4 0 0 1 8 0v3" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" fill="none" className="w-5 h-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2l2.4 6.7H21l-5.3 4 2 6.8-5.7-4-5.7 4 2-6.8L3 8.7h6.6L12 2z" />
    </svg>
  );
}

function MissionCard({ step }) {
  const navigate = useNavigate();

  return (
    <div className={`rounded-2xl border p-5 transition-colors ${
      step.done
        ? 'bg-emerald-500/[.06] border-emerald-400/20'
        : step.locked
          ? 'bg-white/[.025] border-white/[.05]'
          : 'bg-[#151c2c] border-[#e8a635]/25'
    }`}>
      <div className="flex items-start gap-4">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
          step.done
            ? 'bg-emerald-400/15 text-emerald-300'
            : step.locked
              ? 'bg-white/[.05] text-[#4a5568]'
              : 'bg-[#e8a635] text-[#0a0e17]'
        }`}>
          <StepIcon step={step} />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-[11px] uppercase tracking-widest text-[#4a5568] mb-1">
                Миссия {step.number}
              </div>
              <h2 className="text-[#e8eaf0] text-base font-bold leading-snug">{step.title}</h2>
            </div>
            <span className={`font-['JetBrains_Mono'] text-xs shrink-0 ${
              step.done ? 'text-emerald-300' : 'text-[#e8a635]'
            }`}>
              +{step.reward} XP
            </span>
          </div>

          <p className="text-sm text-[#8892a4] leading-relaxed mt-3">{step.description}</p>

          {step.locked && (
            <p className="text-xs text-[#4a5568] mt-3">{step.lockedLabel}</p>
          )}

          <button
            type="button"
            onClick={() => navigate(step.to)}
            className={`mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-colors ${
              step.done
                ? 'bg-white/[.04] text-emerald-300 border border-emerald-400/20'
                : 'bg-[#e8a635] text-[#0a0e17] hover:bg-[#f0b84a]'
            }`}
          >
            {step.done ? 'Выполнено' : step.actionLabel}
            {!step.done && (
              <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12h14" />
                <path d="M13 5l7 7-7 7" />
              </svg>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function OnboardingPage() {
  const { user } = useUser();
  const progress = getOnboardingProgress(user);

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center pt-32 text-[#4a5568]">
        <div className="text-sm">Загрузка обучения...</div>
      </div>
    );
  }

  return (
    <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-10 py-10">
      <section className="grid lg:grid-cols-[1.4fr_.8fr] gap-6 items-stretch mb-8">
        <div className="rounded-2xl border border-white/[.07] bg-[#151c2c] p-6 sm:p-8 overflow-hidden relative">
          <div className="absolute right-0 top-0 w-64 h-64 bg-[#e8a635]/[.06] blur-3xl pointer-events-none" />
          <div className="relative">
            <div className="text-[11px] uppercase tracking-[0.28em] text-[#e8a635] mb-4">
              Обучение коллекционера
            </div>
            <h1 className="text-[#e8eaf0] text-2xl sm:text-3xl font-bold tracking-tight leading-tight max-w-2xl">
              Пройдите стартовый маршрут и подготовьте аккаунт к первой сделке
            </h1>
            <p className="text-[#8892a4] text-sm sm:text-base leading-relaxed mt-4 max-w-2xl">
              Каждая миссия открывает часть платформы: доставка, витрина коллекции и первый предмет.
            </p>

            <div className="mt-8 max-w-xl">
              <div className="flex items-center justify-between gap-4 mb-2">
                <span className="text-sm text-[#8892a4]">{progress.rank}</span>
                <span className="font-['JetBrains_Mono'] text-sm text-[#e8a635]">
                  {progress.xp}/{ONBOARDING_TOTAL_XP} XP
                </span>
              </div>
              <ProgressBar percent={progress.percent} />
              <div className="text-xs text-[#4a5568] mt-2">
                Выполнено {progress.doneCount} из {progress.totalCount} миссий
              </div>
            </div>
          </div>
        </div>

        <aside className="rounded-2xl border border-white/[.07] bg-[#0d1321] p-6">
          <div className="text-[11px] uppercase tracking-widest text-[#4a5568] mb-4">
            Награды маршрута
          </div>
          <div className="space-y-4">
            {[
              ['Готовность к СДЭК', progress.steps[0].done && progress.steps[1].done],
              ['Первая витрина', progress.steps[2].done],
              ['Предмет в коллекции', progress.steps[3].done],
            ].map(([label, done]) => (
              <div key={label} className="flex items-center gap-3">
                <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${
                  done ? 'bg-emerald-400/15 text-emerald-300' : 'bg-white/[.04] text-[#4a5568]'
                }`}>
                  <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 6L9 17l-5-5" />
                  </svg>
                </div>
                <span className={done ? 'text-[#e8eaf0] text-sm' : 'text-[#4a5568] text-sm'}>{label}</span>
              </div>
            ))}
          </div>

          {progress.complete ? (
            <div className="mt-6 rounded-xl border border-emerald-400/20 bg-emerald-400/[.07] px-4 py-3 text-sm text-emerald-200">
              Стартовый маршрут закрыт. Аккаунт готов к полноценным сделкам.
            </div>
          ) : (
            <Link
              to={progress.nextStep?.to || '/profile'}
              className="mt-6 w-full inline-flex items-center justify-center px-4 py-2.5 rounded-xl bg-[#e8a635] text-[#0a0e17] text-sm font-bold no-underline hover:bg-[#f0b84a] transition-colors"
            >
              Следующая миссия
            </Link>
          )}
        </aside>
      </section>

      <section className="grid md:grid-cols-2 gap-4">
        {progress.steps.map(step => (
          <MissionCard key={step.key} step={step} />
        ))}
      </section>
    </main>
  );
}
