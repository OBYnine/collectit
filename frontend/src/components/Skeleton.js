import React from 'react';

// Базовый shimmer-прямоугольник. Класс animate-pulse нативно есть в Tailwind.
export function LineSkeleton({ className = 'h-4 w-full' }) {
  return <div className={`bg-white/[.05] rounded animate-pulse ${className}`} />;
}

export function CardSkeleton() {
  return (
    <div className="bg-[#151c2c] border border-white/[.06] rounded-xl overflow-hidden">
      <div className="h-36 bg-white/[.03] animate-pulse" />
      <div className="p-4 space-y-3">
        <LineSkeleton className="h-3 w-2/3" />
        <div className="flex justify-between items-center pt-1">
          <LineSkeleton className="h-4 w-20" />
          <LineSkeleton className="h-3 w-14" />
        </div>
      </div>
    </div>
  );
}

export function GridSkeleton({ count = 8 }) {
  return (
    <div
      className="grid gap-4"
      style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))' }}
    >
      {Array.from({ length: count }).map((_, i) => (
        <CardSkeleton key={i} />
      ))}
    </div>
  );
}

export function PageFallback() {
  return (
    <div className="max-w-5xl mx-auto px-10 py-9">
      <LineSkeleton className="h-6 w-48 mb-6" />
      <GridSkeleton count={8} />
    </div>
  );
}
