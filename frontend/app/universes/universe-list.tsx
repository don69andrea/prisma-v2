'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { Play, Search } from 'lucide-react';

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { StartRankingDialog } from '@/components/universes/StartRankingDialog';
import type { UniverseRead } from '@/lib/api/universes';

export function UniverseList({ universes }: { universes: UniverseRead[] }) {
  const [selectedUniverse, setSelectedUniverse] = useState<{ id: string; name: string } | null>(null);
  const [search, setSearch] = useState('');

  const filteredUniverses = useMemo(() => {
    if (!search.trim()) return universes;
    const q = search.trim().toLowerCase();
    return universes.filter(
      (u) => u.name.toLowerCase().includes(q) || (u.region ?? '').toLowerCase().includes(q),
    );
  }, [universes, search]);

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
    <>
      {universes.length >= 3 && (
        <div className="relative mb-3">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Universum suchen…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 max-w-xs"
            data-testid="universe-search-input"
          />
        </div>
      )}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Region</TableHead>
            <TableHead>Anzahl Ticker</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {filteredUniverses.map((u) => (
            <TableRow key={u.id}>
              <TableCell className="font-medium">
                <Link
                  href={`/universes/${u.id}`}
                  className="hover:underline"
                  data-testid={`universe-name-link-${u.id}`}
                >
                  {u.name}
                </Link>
              </TableCell>
              <TableCell>{u.region}</TableCell>
              <TableCell>{u.tickers.length}</TableCell>
              <TableCell className="text-right">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setSelectedUniverse({ id: u.id, name: u.name })}
                >
                  <Play className="h-3 w-3 mr-1" />
                  Ranking starten
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <StartRankingDialog
        universe={selectedUniverse}
        onClose={() => setSelectedUniverse(null)}
      />
    </>
  );
}
