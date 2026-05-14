import Link from 'next/link';

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import type { UniverseRead } from '@/lib/api/universes';

export function UniverseList({ universes }: { universes: UniverseRead[] }) {
  if (universes.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-8 text-center">
        Noch keine Universen angelegt.{' '}
        <Link href="/universes/new" className="underline">
          Erstes Universum erstellen
        </Link>
      </p>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Region</TableHead>
          <TableHead>Anzahl Ticker</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {universes.map((u) => (
          <TableRow key={u.id}>
            <TableCell className="font-medium">{u.name}</TableCell>
            <TableCell>{u.region}</TableCell>
            <TableCell>{u.tickers.length}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
