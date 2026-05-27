import { useEffect, useState } from 'react';

const KEY = 'collectit_accessibility_mode';

export default function AccessibilityToggle() {
  const [enabled, setEnabled] = useState(() => localStorage.getItem(KEY) === '1');

  useEffect(() => {
    document.body.classList.toggle('accessibility-mode', enabled);
    localStorage.setItem(KEY, enabled ? '1' : '0');
  }, [enabled]);

  return (
    <button
      type="button"
      onClick={() => setEnabled(v => !v)}
      className={`fixed right-4 bottom-4 z-[90] w-12 h-12 rounded-full border flex items-center justify-center font-bold shadow-lg ${
        enabled
          ? 'bg-white text-black border-white'
          : 'bg-[#151c2c] text-[#e8eaf0] border-white/[.12]'
      }`}
      aria-pressed={enabled}
      aria-label="Версия для слабовидящих"
      title="Версия для слабовидящих"
    >
      Aa
    </button>
  );
}
