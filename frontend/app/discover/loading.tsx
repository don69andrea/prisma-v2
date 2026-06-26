import { PrismaBar } from '@/components/ui/PrismaBar';

export default function DiscoverLoading() {
  return (
    <div className="space-y-6">
      <PrismaBar />
      <div className="space-y-1">
        <div className="h-7 w-40 rounded bg-muted animate-pulse" />
        <div className="h-4 w-56 rounded bg-muted animate-pulse" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="h-28 rounded-xl animate-pulse bg-muted border border-border"
          />
        ))}
      </div>
    </div>
  );
}
