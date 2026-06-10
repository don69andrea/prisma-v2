'use client';

import { useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { Bell, Trash2, Plus, Mail, Webhook } from 'lucide-react';

import {
  listAlerts,
  createAlert,
  deleteAlert,
  type Alert,
  type TriggerType,
  type ChannelType,
} from '@/lib/api/alerts';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

const TRIGGER_LABELS: Record<TriggerType, string> = {
  PRICE_CHANGE: 'Kursänderung',
  SIGNAL_CHANGE: 'Signalwechsel',
};

const CHANNEL_ICONS: Record<ChannelType, React.ReactNode> = {
  EMAIL: <Mail className="h-3 w-3" />,
  WEBHOOK: <Webhook className="h-3 w-3" />,
};

function AlertRow({ alert, onDelete }: { alert: Alert; onDelete: () => void }) {
  const [confirming, setConfirming] = useState(false);

  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border bg-card px-4 py-3 hover:shadow-sm transition-shadow">
      <div className="flex items-center gap-3 min-w-0">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10">
          <Bell className="h-4 w-4 text-primary" />
        </div>
        <div className="min-w-0">
          <Link
            href={`/stocks/${alert.ticker}`}
            className="font-semibold truncate hover:underline"
          >
            {alert.ticker}
          </Link>
          <p className="text-xs text-muted-foreground">
            {TRIGGER_LABELS[alert.trigger_type as TriggerType]} ≥ {alert.threshold}%
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <Badge variant="outline" className="flex items-center gap-1 text-xs">
          {CHANNEL_ICONS[alert.channel as ChannelType]}
          <span className="truncate max-w-[120px]">{alert.target}</span>
        </Badge>
        {alert.last_triggered_at && (
          <span className="text-[10px] text-muted-foreground hidden sm:block">
            {new Date(alert.last_triggered_at).toLocaleDateString('de-CH', { dateStyle: 'short' })}
          </span>
        )}
        {confirming ? (
          <div className="flex gap-1">
            <Button size="sm" variant="destructive" onClick={onDelete}>
              Löschen
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>
              Abbruch
            </Button>
          </div>
        ) : (
          <Button
            size="icon"
            variant="ghost"
            aria-label="Alert löschen"
            className="h-7 w-7 text-muted-foreground hover:text-destructive"
            onClick={() => setConfirming(true)}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>
    </div>
  );
}

function CreateAlertForm({ onCreated, initialTicker = '' }: { onCreated: () => void; initialTicker?: string }) {
  const [ticker, setTicker] = useState(initialTicker);
  const [triggerType, setTriggerType] = useState<TriggerType>('PRICE_CHANGE');
  const [threshold, setThreshold] = useState('5');
  const [channel, setChannel] = useState<ChannelType>('EMAIL');
  const [target, setTarget] = useState('');
  const [error, setError] = useState('');

  const mutation = useMutation({
    mutationFn: createAlert,
    onSuccess: () => {
      setTicker('');
      setThreshold('5');
      setTarget('');
      setError('');
      onCreated();
    },
    onError: () => setError('Alert konnte nicht erstellt werden.'),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const t = parseFloat(threshold);
    if (!ticker || isNaN(t) || t <= 0 || !target) {
      setError('Bitte alle Felder korrekt ausfüllen.');
      return;
    }
    mutation.mutate({ ticker: ticker.toUpperCase(), trigger_type: triggerType, threshold: t, channel, target });
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-lg border bg-card p-4 space-y-3">
      <h3 className="text-sm font-semibold flex items-center gap-2">
        <Plus className="h-4 w-4" /> Neuer Alert
      </h3>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Ticker</label>
          <input
            className="w-full rounded border bg-background px-2 py-1.5 text-sm uppercase placeholder:normal-case placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            placeholder="NESN"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            maxLength={20}
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Trigger</label>
          <select
            className="w-full rounded border bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            value={triggerType}
            onChange={(e) => setTriggerType(e.target.value as TriggerType)}
          >
            <option value="PRICE_CHANGE">Kursänderung</option>
            <option value="SIGNAL_CHANGE">Signalwechsel</option>
          </select>
        </div>

        <div className="space-y-1">
          <label htmlFor="alert-threshold" className="text-xs text-muted-foreground">Threshold (%)</label>
          <input
            id="alert-threshold"
            className="w-full rounded border bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            type="number"
            min="0.1"
            max="100"
            step="0.1"
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Kanal</label>
          <select
            className="w-full rounded border bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            value={channel}
            onChange={(e) => setChannel(e.target.value as ChannelType)}
          >
            <option value="EMAIL">E-Mail</option>
            <option value="WEBHOOK">Webhook</option>
          </select>
        </div>
      </div>

      <div className="space-y-1">
        <label className="text-xs text-muted-foreground">
          {channel === 'EMAIL' ? 'E-Mail-Adresse' : 'Webhook-URL'}
        </label>
        <input
          className="w-full rounded border bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
          type={channel === 'EMAIL' ? 'email' : 'url'}
          placeholder={channel === 'EMAIL' ? 'name@example.com' : 'https://hooks.example.com/...'}
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          maxLength={255}
        />
      </div>

      {error && <p className="text-xs text-destructive">{error}</p>}

      <Button type="submit" size="sm" disabled={mutation.isPending}>
        {mutation.isPending ? 'Wird erstellt…' : 'Alert anlegen'}
      </Button>
    </form>
  );
}

export function AlertsClient() {
  const searchParams = useSearchParams();
  const initialTicker = searchParams.get('ticker')?.toUpperCase() ?? '';
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ['alerts'],
    queryFn: listAlerts,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteAlert,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alerts'] }),
  });

  function handleCreated() {
    queryClient.invalidateQueries({ queryKey: ['alerts'] });
  }

  return (
    <div className="space-y-6">
      <CreateAlertForm onCreated={handleCreated} initialTicker={initialTicker} />

      <div className="space-y-2">
        {isLoading && (
          <>
            <Skeleton className="h-14 w-full rounded-lg" />
            <Skeleton className="h-14 w-full rounded-lg" />
          </>
        )}
        {isError && (
          <p className="text-sm text-destructive text-center py-8">
            Alerts konnten nicht geladen werden.
          </p>
        )}
        {data && data.alerts.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-8">
            Keine Alerts konfiguriert.
          </p>
        )}
        {data?.alerts.map((alert) => (
          <AlertRow
            key={alert.id}
            alert={alert}
            onDelete={() => deleteMutation.mutate(alert.id)}
          />
        ))}
      </div>

      <p className="text-xs text-muted-foreground border-t pt-3">
        Alerts sind Hinweise — keine Anlageberatung. Tägliche Prüfung um 08:00 Uhr Schweizer Zeit.
      </p>
    </div>
  );
}
