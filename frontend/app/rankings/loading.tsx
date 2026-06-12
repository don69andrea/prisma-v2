export default function RankingsLoading() {
  return (
    <div className="space-y-6 max-w-3xl">
      <div className="space-y-1">
        <div className="h-7 w-44 rounded bg-muted animate-pulse" />
        <div className="h-4 w-64 rounded bg-muted animate-pulse" />
      </div>
      <div className="h-28 rounded-xl bg-muted animate-pulse" />
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-10 rounded-md bg-muted animate-pulse" />
        ))}
      </div>
    </div>
  );
}
