/**
 * Globaler, minimaler Store für den "Cold Start"-Hinweis.
 *
 * Render-Free-Tier-Instanzen brauchen nach Inaktivität teils >50s, um wieder
 * aufzuwachen. Ohne Hinweis wirkt das für Endnutzer wie ein Hänger/Absturz.
 *
 * apiFetch() (siehe ./client.ts) startet pro Request einen Timer; läuft dieser
 * ab (Request dauert länger als COLD_START_THRESHOLD_MS), wird hier der
 * Hinweis als "sichtbar" markiert. Abonnenten (z.B. ein Banner im Layout)
 * werden per Subscribe-Callback benachrichtigt — bewusst ohne zusätzliche
 * Abhängigkeit (kein Context/State-Library nötig), damit der Eingriff klein
 * und an einer zentralen Stelle bleibt (DRY statt Pro-Seite-Logik).
 */

export const COLD_START_THRESHOLD_MS = 5_000;

type Listener = (visible: boolean) => void;

let pendingCount = 0;
let visible = false;
const listeners = new Set<Listener>();

function setVisible(next: boolean): void {
  if (visible === next) return;
  visible = next;
  for (const listener of listeners) listener(visible);
}

export function subscribeColdStart(listener: Listener): () => void {
  listeners.add(listener);
  listener(visible);
  return () => listeners.delete(listener);
}

export function isColdStartVisible(): boolean {
  return visible;
}

/**
 * Markiert den Start eines Requests. Gibt eine `done()`-Funktion zurück, die
 * nach Abschluss (Erfolg oder Fehler) aufgerufen werden muss, um den Timer zu
 * stoppen und den Hinweis ggf. wieder auszublenden.
 */
export function trackRequestStart(thresholdMs: number = COLD_START_THRESHOLD_MS): () => void {
  pendingCount += 1;

  const timer = setTimeout(() => {
    setVisible(true);
  }, thresholdMs);

  let finished = false;
  return function done() {
    if (finished) return;
    finished = true;
    clearTimeout(timer);
    pendingCount = Math.max(0, pendingCount - 1);
    if (pendingCount === 0) {
      setVisible(false);
    }
  };
}

/** Nur für Tests: setzt den Modul-internen Zustand zurück. */
export function __resetColdStartStateForTests(): void {
  pendingCount = 0;
  visible = false;
  listeners.clear();
}
