import { PrismaBar } from '@/components/ui/PrismaBar';

export default function RankingDetailLoading() {
  return (
    <div className="space-y-6">
      <PrismaBar />
      {/* Back + title */}
      <div className="space-y-2">
        <div className="h-4 w-36 rounded bg-muted animate-pulse" />
        <div className="h-7 w-52 rounded bg-muted animate-pulse" />
      </div>

      {/* Status card */}
      <div className="h-14 rounded-xl bg-muted animate-pulse" />

      {/* Table rows */}
      <div className="space-y-2">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-10 rounded-md bg-muted animate-pulse" />
        ))}
      </div>
    </div>
  );
}
