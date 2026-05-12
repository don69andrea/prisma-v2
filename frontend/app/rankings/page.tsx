import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Rankings',
};

export default function RankingsPage() {
  return (
    <div className="flex flex-col items-center justify-center py-32 text-center">
      <h1 className="text-2xl font-bold">Rankings</h1>
      <p className="mt-2 text-muted-foreground">Kommt bald.</p>
    </div>
  );
}
