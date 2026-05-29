'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Sparkles, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  createUniverse,
  suggestUniverse,
  type UniverseSuggestion,
} from '@/lib/api/universes';

export default function WizardPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [description, setDescription] = useState('');
  const [suggestion, setSuggestion] = useState<UniverseSuggestion | null>(null);
  const [name, setName] = useState('');
  const [region, setRegion] = useState('');
  const [tickersRaw, setTickersRaw] = useState('');

  const suggestMutation = useMutation({
    mutationFn: () => suggestUniverse(description),
    onSuccess: (data) => {
      setSuggestion(data);
      setName(data.name);
      setRegion(data.region);
      setTickersRaw(data.tickers.join(', '));
    },
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createUniverse({
        name: name.trim(),
        region: region.trim(),
        tickers: tickersRaw
          .split(',')
          .map((t) => t.trim().toUpperCase())
          .filter(Boolean),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['universes'] });
      router.push('/universes');
    },
  });

  function resetSuggestion() {
    setSuggestion(null);
    setName('');
    setRegion('');
    setTickersRaw('');
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <Link
        href="/universes"
        className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="mr-1 h-4 w-4" />
        Zurück zu Universen
      </Link>

      <div>
        <h1 className="text-2xl font-bold tracking-tight">Universe mit KI generieren</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Beschreibe, welches Universe du suchst — Claude wählt passende Tickers aus dem
          verfügbaren Stock-Katalog.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Beschreibung</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Beschreibe dein Universe — z.B. 'Tech-Stocks USA mit Fokus Halbleiter'"
            className="w-full min-h-[100px] rounded-md border bg-background px-3 py-2 text-sm"
            disabled={suggestMutation.isPending}
          />
          <Button
            onClick={() => suggestMutation.mutate()}
            disabled={description.trim().length < 3 || suggestMutation.isPending}
            className="gap-2"
          >
            {suggestMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            Vorschlag generieren
          </Button>
          {suggestMutation.isError && (
            <p className="text-sm text-destructive" role="alert">
              {suggestMutation.error instanceof Error
                ? suggestMutation.error.message
                : 'Vorschlag konnte nicht erstellt werden'}
            </p>
          )}
        </CardContent>
      </Card>

      {suggestion && (
        <>
          <Card className="border-pink-500/40 bg-pink-50/40 dark:bg-pink-950/20">
            <CardContent className="py-4 flex items-start gap-2">
              <Sparkles className="h-4 w-4 text-pink-600 dark:text-pink-400 shrink-0 mt-0.5" />
              <p className="text-sm text-muted-foreground">{suggestion.reasoning}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Vorschlag anpassen</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <label className="text-sm font-medium block mb-1">Name</label>
                <Input value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div>
                <label className="text-sm font-medium block mb-1">Region</label>
                <Input value={region} onChange={(e) => setRegion(e.target.value)} />
              </div>
              <div>
                <label className="text-sm font-medium block mb-1">
                  Tickers (komma-separiert)
                </label>
                <Input
                  value={tickersRaw}
                  onChange={(e) => setTickersRaw(e.target.value)}
                />
              </div>
              <div className="flex gap-2 pt-2">
                <Button
                  onClick={() => createMutation.mutate()}
                  disabled={createMutation.isPending}
                >
                  {createMutation.isPending ? 'Erstellt...' : 'Erstellen'}
                </Button>
                <Button variant="outline" onClick={resetSuggestion}>
                  Vorschlag verwerfen
                </Button>
              </div>
              {createMutation.isError && (
                <p className="text-sm text-destructive" role="alert">
                  {createMutation.error instanceof Error
                    ? createMutation.error.message
                    : 'Erstellung fehlgeschlagen'}
                </p>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
