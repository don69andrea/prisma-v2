'use client';

import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { Bell, Trash2, Plus, Mail, Webhook } from 'lucide-react';

import {
  listAlerts,
  createAlert,
  deleteAlert,
  type TriggerType,
  type ChannelType,
} from '@/lib/api/alerts';
import { usePrismaMode } from '@/hooks/usePrismaMode';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

const LS_ALERT_FORM_KEY = 'prisma_alert_form_config';

function loadStoredAlertForm() {
  try {
    const raw = localStorage.getItem(LS_ALERT_FORM_KEY);
    if (raw) return JSON.parse(raw) as { triggerType: TriggerType; threshold: string; channel: ChannelType; target: string };
  } catch {}
  return null;
}

const TRIGGER_LABELS: Record<TriggerType, string> = {
  PRICE_CHANGE: 'Kursänderung',
  SIGNAL_CHANGE: 'Signal-Wechsel',
};

const CHANNEL_ICONS: Record<ChannelType, React.ReactNode> = {
  EMAIL: <Mail className="h-3 w-3" />,
  WEBHOOK: <Webhook className="h-3 w-3" />,
};

function InfoBtn({ text }: { text: string }) {
  const [show, setShow] = useState(false);
  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => setShow(!show)}
        className="inline-flex items-center justify-center w-4 h-4 rounded-full text-[10px] font-bold bg-muted text-muted-foreground hover:bg-accent hover:text-foreground transition-colors ml-1"
        aria-label="Mehr Info"
      >
        i
      </button>
      {show && (
        <span className="absolute z-50 left-6 -top-1 w-52 text-xs bg-popover border border-border rounded-md px-2 py-1.5 text-popover-foreground shadow-lg">
          {text}
        </span>
      )}
    </span>
  );
}

function CreateAlertForm({ onCreated, initialTicker = '' }: { onCreated: () => void; initialTicker?: string }) {
  const [ticker, setTicker] = useState(initialTicker);
  const [triggerType, setTriggerType] = useState<TriggerType>('PRICE_CHANGE');
  const [threshold, setThreshold] = useState('5');
  const [channel, setChannel] = useState<ChannelType>('EMAIL');
  const [target, setTarget] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    const s = loadStoredAlertForm();
    if (!s) return;
    if (s.triggerType) setTriggerType(s.triggerType);
    if (s.threshold) setThreshold(s.threshold);
    if (s.channel) setChannel(s.channel);
    if (s.target) setTarget(s.target);
  }, []);

  const mutation = useMutation({
    mutationFn: createAlert,
    onSuccess: () => {
      localStorage.setItem(LS_ALERT_FORM_KEY, JSON.stringify({ triggerType, threshold, channel, target }));
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
          <label className="text-xs text-muted-foreground">
            Ticker
            <InfoBtn text="Das Kürzel der Aktie an der Börse. z.B. NESN für Nestlé oder UBSG für UBS" />
          </label>
          <input
            className="w-full rounded border bg-background px-2 py-1.5 text-sm uppercase placeholder:normal-case placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            placeholder="NESN"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            maxLength={20}
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">
            Trigger
            <InfoBtn text="Preis-Alarm = wenn ein bestimmter Kurs erreicht wird. Signal-Alarm = wenn sich das BUY/HOLD/SELL Signal ändert." />
          </label>
          <select
            className="w-full rounded border bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            value={triggerType}
            onChange={(e) => setTriggerType(e.target.value as TriggerType)}
          >
            <option value="PRICE_CHANGE">Kursänderung</option>
            <option value="SIGNAL_CHANGE">Signal-Wechsel</option>
          </select>
        </div>

        <div className="space-y-1">
          <label htmlFor="alert-threshold" className="text-xs text-muted-foreground">
            Threshold (%)
            <InfoBtn text="Der Schwellenwert in Prozent bei dem der Alarm ausgelöst wird. z.B. 5 = Alarm wenn der Kurs um 5% steigt oder fällt." />
          </label>
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

// ---------------------------------------------------------------------------
// Simple Mode — minimal Signal-Wechsel-only view
// ---------------------------------------------------------------------------

function SimpleCreateForm({ onCreated, initialTicker = '' }: { onCreated: () => void; initialTicker?: string }) {
  const [ticker, setTicker] = useState(initialTicker);
  const [error, setError] = useState('');

  const mutation = useMutation({
    mutationFn: createAlert,
    onSuccess: () => {
      setTicker('');
      setError('');
      onCreated();
    },
    onError: () => setError('Alert konnte nicht erstellt werden.'),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!ticker.trim()) {
      setError('Bitte einen Ticker eingeben.');
      return;
    }
    mutation.mutate({
      ticker: ticker.toUpperCase(),
      trigger_type: 'SIGNAL_CHANGE',
      threshold: 0,
      channel: 'EMAIL',
      target: '',
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-end gap-3 mt-4">
      <div className="space-y-1 flex-1 max-w-xs">
        <label className="text-xs text-muted-foreground">Ticker</label>
        <input
          className="w-full rounded border bg-background px-2 py-1.5 text-sm uppercase placeholder:normal-case placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          placeholder="NESN"
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          maxLength={20}
        />
      </div>
      <Button type="submit" size="sm" disabled={mutation.isPending}>
        {mutation.isPending ? 'Wird erstellt…' : 'Alert anlegen'}
      </Button>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </form>
  );
}

function SimpleAlertsView({ initialTicker }: { initialTicker: string }) {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(!!initialTicker);

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
    setShowForm(false);
  }

  const signalAlerts = useMemo(
    () => data?.alerts.filter((a) => a.trigger_type === 'SIGNAL_CHANGE') ?? [],
    [data],
  );

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">
        PRISMA benachrichtigt dich wenn sich ein Signal in deiner Watchlist ändert.
      </p>

      <div className="space-y-2">
        {isLoading && (
          <>
            <Skeleton className="h-11 w-full rounded-lg" />
            <Skeleton className="h-11 w-full rounded-lg" />
          </>
        )}

        {isError && (
          <p className="text-sm text-destructive text-center py-8">
            Alerts konnten nicht geladen werden.
          </p>
        )}

        {data && signalAlerts.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
            <Bell className="h-10 w-10 text-muted-foreground/40" />
            <p className="text-sm font-medium">Kein Alert gesetzt</p>
            <p className="text-xs text-muted-foreground max-w-xs">
              Füge einen Alert hinzu wenn sich ein Signal ändert
            </p>
          </div>
        )}

        {signalAlerts.map((alert) => (
          <div
            key={alert.id}
            className="flex items-center justify-between gap-4 rounded-lg border bg-card px-4 py-2.5"
          >
            <div className="flex items-center gap-3 min-w-0">
              <span className="text-emerald-400 text-xs font-medium shrink-0">&#10003;</span>
              <Link
                href={`/stocks/${alert.ticker}`}
                className="font-mono font-bold hover:underline truncate"
              >
                {alert.ticker}
              </Link>
              <span className="text-xs text-muted-foreground">Signal-Wechsel</span>
              <span className="text-xs text-muted-foreground">Aktiv</span>
            </div>
            <button
              onClick={() => deleteMutation.mutate(alert.id)}
              className="text-slate-500 hover:text-red-400 shrink-0 transition-colors"
              aria-label="Alert löschen"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>

      {showForm ? (
        <SimpleCreateForm onCreated={handleCreated} initialTicker={initialTicker} />
      ) : (
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <Plus className="h-4 w-4" />
          Alert hinzufügen
        </button>
      )}

      <p className="text-xs text-muted-foreground border-t pt-3">
        Alerts sind Hinweise — keine Anlageberatung. Tägliche Prüfung um 08:00 Uhr Schweizer Zeit.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pro Mode — full table layout with history
// ---------------------------------------------------------------------------

function ProAlertsView({ initialTicker }: { initialTicker: string }) {
  const queryClient = useQueryClient();
  const [triggerFilter, setTriggerFilter] = useState<'all' | TriggerType>('all');
  const [showForm, setShowForm] = useState(!!initialTicker);

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
    setShowForm(false);
  }

  const triggerCounts = useMemo(() => ({
    PRICE_CHANGE:  data?.alerts.filter((a) => a.trigger_type === 'PRICE_CHANGE').length  ?? 0,
    SIGNAL_CHANGE: data?.alerts.filter((a) => a.trigger_type === 'SIGNAL_CHANGE').length ?? 0,
  }), [data]);

  const visibleAlerts = useMemo(() => {
    if (!data) return [];
    if (triggerFilter === 'all') return data.alerts;
    return data.alerts.filter((a) => a.trigger_type === triggerFilter);
  }, [data, triggerFilter]);

  const triggeredAlerts = useMemo(
    () =>
      (data?.alerts ?? [])
        .filter((a) => !!a.last_triggered_at)
        .sort(
          (a, b) =>
            new Date(b.last_triggered_at!).getTime() - new Date(a.last_triggered_at!).getTime(),
        ),
    [data],
  );

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div />
        <Button size="sm" onClick={() => setShowForm((v) => !v)}>
          <Plus className="h-4 w-4 mr-1.5" />
          Alert erstellen
        </Button>
      </div>

      {showForm && (
        <CreateAlertForm onCreated={handleCreated} initialTicker={initialTicker} />
      )}

      {data && data.alerts.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          {([
            { key: 'all',           label: 'Alle',          count: data.alerts.length },
            { key: 'PRICE_CHANGE',  label: 'Kursänderung',  count: triggerCounts.PRICE_CHANGE },
            { key: 'SIGNAL_CHANGE', label: 'Signal-Wechsel', count: triggerCounts.SIGNAL_CHANGE },
          ] as const).map(({ key, label, count }) => (
            <button
              key={key}
              onClick={() => setTriggerFilter(key)}
              className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                triggerFilter === key
                  ? 'border-transparent bg-foreground text-background'
                  : 'bg-background hover:bg-muted'
              }`}
              data-testid={key === 'all' ? 'alerts-filter-all' : key === 'PRICE_CHANGE' ? 'alerts-filter-price' : 'alerts-filter-signal'}
            >
              {label}
              <span className="tabular-nums">{count}</span>
            </button>
          ))}
        </div>
      )}

      <div>
        {isLoading && (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full rounded" />
            <Skeleton className="h-10 w-full rounded" />
          </div>
        )}

        {isError && (
          <p className="text-sm text-destructive text-center py-8">
            Alerts konnten nicht geladen werden.
          </p>
        )}

        {data && data.alerts.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
            <Bell className="h-10 w-10 text-muted-foreground/40" />
            <p className="text-sm font-medium">Keine Kursalarme gesetzt</p>
            <p className="text-xs text-muted-foreground max-w-xs">
              Erstelle Alarme die dich benachrichtigen wenn ein Kurs ein bestimmtes Niveau erreicht
            </p>
          </div>
        )}

        {data && data.alerts.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-xs text-muted-foreground">
                <th className="text-left py-2 pr-4 font-medium">TICKER</th>
                <th className="text-left py-2 pr-4 font-medium">BEDINGUNG</th>
                <th className="text-left py-2 pr-4 font-medium">SCHWELLWERT</th>
                <th className="text-left py-2 pr-4 font-medium">KANAL</th>
                <th className="text-left py-2 pr-4 font-medium">STATUS</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {visibleAlerts.map((alert) => (
                <tr key={alert.id} className="border-b border-border/50">
                  <td className="py-3 pr-4 font-mono font-bold">
                    <Link href={`/stocks/${alert.ticker}`} className="hover:underline">
                      {alert.ticker}
                    </Link>
                  </td>
                  <td className="py-3 pr-4">{TRIGGER_LABELS[alert.trigger_type as TriggerType]}</td>
                  <td className="py-3 pr-4 text-muted-foreground">
                    {alert.trigger_type === 'PRICE_CHANGE' && alert.threshold
                      ? `${alert.threshold}%`
                      : '—'}
                  </td>
                  <td className="py-3 pr-4">
                    <span className="flex items-center gap-1 text-xs text-muted-foreground">
                      {CHANNEL_ICONS[alert.channel as ChannelType]}
                      <span className="truncate max-w-[120px]">{alert.target}</span>
                    </span>
                  </td>
                  <td className="py-3 pr-4">
                    <span className="text-emerald-400 text-xs font-medium">&#10003; Aktiv</span>
                  </td>
                  <td className="py-3">
                    <button
                      onClick={() => deleteMutation.mutate(alert.id)}
                      className="text-slate-500 hover:text-red-400 transition-colors"
                      aria-label="Alert löschen"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {data && data.alerts.length > 0 && visibleAlerts.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-4">
            Keine Alerts für diesen Trigger-Typ.
          </p>
        )}
      </div>

      {triggeredAlerts.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Alert-Historie
          </h2>
          <div className="space-y-1.5">
            {triggeredAlerts.map((alert) => (
              <div key={alert.id} className="flex items-center justify-between gap-4 text-sm">
                <div className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {new Date(alert.last_triggered_at!).toLocaleDateString('de-CH', { dateStyle: 'short' })}
                  </span>
                  <span className="font-mono font-bold">{alert.ticker}</span>
                  <span className="text-muted-foreground">
                    {TRIGGER_LABELS[alert.trigger_type as TriggerType]}
                  </span>
                </div>
                <Link
                  href={`/stocks/${alert.ticker}`}
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  Factsheet
                </Link>
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="text-xs text-muted-foreground border-t pt-3">
        Alerts sind Hinweise — keine Anlageberatung. Tägliche Prüfung um 08:00 Uhr Schweizer Zeit.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Root export — mode-switches between Simple and Pro
// ---------------------------------------------------------------------------

export function AlertsClient() {
  const searchParams = useSearchParams();
  const initialTicker = searchParams.get('ticker')?.toUpperCase() ?? '';
  const { isSimple } = usePrismaMode();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {isSimple ? 'Meine Alerts.' : 'Alerts.'}
        </h1>
      </div>
      {isSimple
        ? <SimpleAlertsView initialTicker={initialTicker} />
        : <ProAlertsView initialTicker={initialTicker} />}
    </div>
  );
}
