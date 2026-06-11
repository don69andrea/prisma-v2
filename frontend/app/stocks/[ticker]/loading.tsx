export default function StockDetailLoading() {
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      {/* Back-button placeholder */}
      <div className="h-5 w-32 rounded bg-muted animate-pulse" />

      {/* Header card skeleton */}
      <div className="h-36 rounded-xl bg-muted animate-pulse" />

      {/* Metrics rows */}
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-10 rounded-md bg-muted animate-pulse" />
        ))}
      </div>

      {/* Chart skeleton */}
      <div className="h-64 rounded-xl bg-muted animate-pulse" />
    </div>
  );
}
