'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Play } from 'lucide-react';

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { StartRankingDialog } from '@/components/universes/StartRankingDialog';
import type { UniverseRead } from '@/lib/api/universes';

export function UniverseList({ universes }: { universes: UniverseRead[] }) {
  const [selectedUniverse, setSelectedUniverse] = useState<{ id: string; name: string } | null>(null);

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
          {universes.map((u) => (
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
