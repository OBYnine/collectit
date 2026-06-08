import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useUser } from '../context/UserContext';
import { getOnboardingProgress } from '../utils/onboarding';

const COLLAPSED_KEY = 'collectit_onboarding_collapsed';

export default function OnboardingQuestWidget() {
  const { user } = useUser();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(COLLAPSED_KEY) === '1');

  useEffect(() => {
    localStorage.setItem(COLLAPSED_KEY, collapsed ? '1' : '0');
  }, [collapsed]);

  if (!user || location.pathname === '/onboarding') return null;

  const progress = getOnboardingProgress(user);
  if (progress.complete) return null;

  const nextStep = progress.nextStep;

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={() => setCollapsed(false)}
        className="fixed left-4 bottom-4 z-[80] flex items-center gap-2 rounded-full border border-[#e8a635]/30 bg-[#151c2c]/95 px-4 py-2 text-sm text-[#e8eaf0] shadow-xl backdrop-blur"
      >
        <span className="font-['JetBrains_Mono'] text-[#e8a635]">{progress.percent}%</span>
        <span>Квест</span>
      </button>
    );
  }

  return (
    <div className="fixed left-4 bottom-4 z-[80] w-[min(360px,calc(100vw-32px))] rounded-2xl border border-white/[.08] bg-[#151c2c]/95 p-4 shadow-2xl backdrop-blur">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-widest text-[#4a5568] mb-1">
            Стартовый квест
          </div>
          <div className="text-sm font-bold text-[#e8eaf0]">{progress.rank}</div>
        </div>
        <button
          type="button"
          onClick={() => setCollapsed(true)}
          className="w-7 h-7 rounded-lg flex items-center justify-center text-[#4a5568] hover:text-[#8892a4] hover:bg-white/[.04] transition-colors"
          aria-label="Свернуть обучение"
        >
          <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M6 12h12" />
          </svg>
        </button>
      </div>

      <div className="mt-3 h-2 rounded-full bg-white/[.06] overflow-hidden">
        <div
          className="h-full rounded-full bg-[#e8a635] transition-all duration-500"
          style={{ width: `${progress.percent}%` }}
        />
      </div>

      <div className="flex items-center justify-between mt-2 text-xs">
        <span className="text-[#8892a4]">{progress.doneCount}/{progress.totalCount} миссий</span>
        <span className="font-['JetBrains_Mono'] text-[#e8a635]">{progress.xp} XP</span>
      </div>

      {nextStep && (
        <div className="mt-4 rounded-xl bg-[#0a0e17] border border-white/[.06] p-3">
          <div className="text-[10px] uppercase tracking-widest text-[#4a5568] mb-1">
            Следующий шаг
          </div>
          <div className="text-sm text-[#e8eaf0] font-semibold">{nextStep.title}</div>
          <button
            type="button"
            onClick={() => navigate(nextStep.to)}
            className="mt-3 w-full flex items-center justify-center gap-2 rounded-xl bg-[#e8a635] px-3 py-2 text-sm font-bold text-[#0a0e17] hover:bg-[#f0b84a] transition-colors"
          >
            {nextStep.actionLabel}
            <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14" />
              <path d="M13 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}
