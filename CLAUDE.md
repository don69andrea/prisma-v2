# PRISMA V2 — CLAUDE.md
## Persistenter Kontext für alle Agenten & Teammitglieder

> **Dieses Dokument ist die einzige Wahrheit.**
> Jeder Claude Code Agent, jedes Teammitglied, jede neue Session beginnt hier.
> Lies es vollständig bevor du eine einzige Zeile schreibst.

---

## 🚦 LIVE STATUS — WER MACHT WAS (bei jedem Start prüfen & updaten)

> **Pflicht:** Jeder Agent updated diesen Block sobald er eine Aufgabe startet (`🔄`) oder abschliesst (`✅`).
> So weiss jeder sofort was blockiert ist, was frei ist, und wo man aufhören kann.

### Aktuelle Aufgaben

| # | Aufgabe | Person | Branch | Status | Blockiert durch |
|---|---|---|---|---|---|
| R2.3-1 | Datenpipeline: SMI seeden + XGBoost trainieren | Andrea | `develop` (direkt) | ✅ DONE 2026-06-11 | — |
| R2.3-2 | /decision: echte BUY/HOLD/WATCH Signale + Audit-Trail | Andrea | `feature/andrea-datenpipeline` | ✅ DONE 2026-06-11 | — |
| R2.3-3 | Frontend: SignalBadge + PrismaScore + ExplainButton | Helin | `feature/helin-ux-components` | 🔄 IN PROGRESS | — |
| R2.3-4 | Frontend: Glassmorphism Cards + Loading-States | Helin | `feature/helin-ux-components` | ⬜ NEXT | — |
| R2.3-5 | Backend: InvestorProfile Model + DB Migration | Aurelius | `feature/aurelius-investorprofile` | 🔄 IN PROGRESS | — |
| R2.3-6 | Backend: DiscoveryService + API Endpoints | Aurelius | `feature/aurelius-investorprofile` | ⬜ NEXT | R2.3-5 |
| R2.4-1 | /start: Conversational Discovery Engine — 5 Turns (Sektion 4b) | Andrea | `develop` (direkt, Frontend-Shell ✅) | ✅ DONE 2026-06-11 | Backend-Integration wartet auf R2.3-5/6 |
| R2.4-2 | /start: Brand Logo Grid (24 Logos) + Risk-Feeling-Test + ProfileReveal | Helin | `feature/helin-discovery-ui` | ⬜ BLOCKED | R2.4-1 Backend |
| R2.4-3 | Haiku-Klassifikation + Session-State (Redis) + Konfidenz-Score | Aurelius | `feature/aurelius-discovery-agent` | ⬜ BLOCKED | R2.3-5 |
| R2.4-4 | Navigation: 5 Bereiche umstrukturieren | Helin | `feature/helin-navigation` | ⬜ NEXT | — |
| R2.4-5 | AuditTrail Komponente + Profil-Reveal Animation | Helin | `feature/helin-discovery-ui` | ⬜ BLOCKED | R2.4-2 |
| R2.4-6 | Makro-Agent + RAG verifizieren | Aurelius | `feature/aurelius-discovery-agent` | ⬜ NEXT | ~~R2.3-1~~ unblocked |
| R2.5-1 | Demo-Flow + Präsentation | Alle | `feature/presentation` | ⬜ BLOCKED | Alle R2.4 |

### Branch-Übersicht

```
develop (Hauptbranch — nie direkt pushen)
│
├── feature/andrea-datenpipeline          ← Andrea, aktiv
├── feature/andrea-discovery-engine       ← Andrea, startet nach R2.3
│
├── feature/helin-ux-components           ← Helin, aktiv
├── feature/helin-discovery-ui            ← Helin, startet nach R2.4-1
├── feature/helin-navigation              ← Helin, kann jetzt starten
│
├── feature/aurelius-investorprofile       ← Aurelius, aktiv
├── feature/aurelius-discovery-agent      ← Aurelius, startet nach R2.3-5
│
└── feature/presentation                  ← Alle gemeinsam, zuletzt
```

### Merge-Reihenfolge (kritisch einhalten)

```
1. feature/aurelius-investorprofile   → develop   (Backend-Fundament zuerst)
2. feature/andrea-datenpipeline       → develop   (Daten + Signale)
3. feature/helin-ux-components        → develop   (Komponenten)
4. feature/helin-navigation           → develop   (kann unabhängig)
5. feature/aurelius-discovery-agent   → develop   (Agent-Logik)
6. feature/andrea-discovery-engine    → develop   (Frontend braucht 5)
7. feature/helin-discovery-ui         → develop   (UI braucht 6)
8. feature/presentation               → develop   (alles zusammen)
```

### Wie du den Status updatest

```bash
# Am Anfang deiner Session:
git pull origin develop
# Status-Block oben in CLAUDE.md updaten: deine Aufgabe auf 🔄 setzen
git add CLAUDE.md && git commit -m "chore: update status — [dein name] startet [aufgabe]"

# Wenn du fertig bist:
# Status-Block: deine Aufgabe auf ✅ setzen
git add CLAUDE.md && git commit -m "chore: update status — [aufgabe] abgeschlossen"
# Pull Request erstellen: feature/[dein-branch] → develop
```

---

## 0 · KRITISCHE RAHMENBEDINGUNGEN — LIES ZUERST

```
MODUL:        Business Intelligence (BI) — NICHT das WPM-Capstone
DOZENT:       Prof. Dr. Manuel Renold, FHNW
STUDENT:      Andrea Petretta
REPO:         github.com/don69andrea/prisma-v2
DEPLOYMENT:   prisma-v2-frontend.onrender.com
ZIEL NOTE:    6 (Maximum)
EMPLOYER:     VIAC (Fintech, Schweiz) — Projekt als Pitch-Material
```

### Was dieses Projekt NICHT ist
- ❌ Kein WPM-Capstone-Workflow (kein Spec-First, kein AI-USAGE.md als Pflicht, keine AGENTS.md-Konventionen)
- ❌ Kein Bloomberg-Terminal für Profis
- ❌ Kein Robo-Advisor der autonom entscheidet
- ❌ Kein US-Fokus (Schweizer Markt ist primär)

### Was dieses Projekt IST
- ✅ BI-Modul-Projekt mit Bewertungskriterien: Agentic AI, ML, RAG, Dashboard, Decision Intelligence
- ✅ Ein Tool für **unsichere Privatanleger** ohne Finanzwissen
- ✅ Ein Schweizer Marktprodukt (SMI, SMIM, SPI)
- ✅ Ein VIAC-Pitch für freie Mittel (NICHT primär 3a)
- ✅ Premium, futuristisches UX — "durchleuchten" als Kernmetapher

---

## 1 · DIE VISION — NIEMALS VERGESSEN

### Der Nutzer — "Der verunsicherte Investor"

```
Er hat Kapital (z.B. CHF 20'000–100'000).
Er braucht das Geld nicht — es liegt auf dem Konto und verliert durch Inflation an Wert.
Er will investieren, aber er hat ANGST.
Er will investieren, aber ihm fehlt das KNOWHOW.
Er fragt Kollegen — aber deren Wissen kann er nicht greifen.
Er weiss noch nicht einmal was er will.
Er sucht zuerst INSPIRATION.
Er braucht TRANSPARENZ — er will verstehen, nicht blind vertrauen.
Er will seine Entscheidung DURCHLEUCHTEN.
Er braucht ein gutes GEFÜHL — Vertrauen, keine Angst.
Er will die Entscheidung SELBST treffen — PRISMA gibt ihm die Basis.
```

### Der Produktsatz (immer im Kopf)

> **"PRISMA ist der erste Investment-Companion der dir nicht sagt was du tun sollst — sondern dir hilft herauszufinden was du willst."**

### Warum "PRISMA"?
Ein optisches Prisma zerlegt weisses Licht in seine Komponenten — macht das Unsichtbare sichtbar. PRISMA macht dasselbe mit Aktien: es zerlegt sie in verständliche Dimensionen damit der Nutzer **durchleuchten** kann was er kauft.

---

## 2 · DIE USER JOURNEY — ROTER FADEN

```
UNSICHERHEIT → INSPIRATION → VERSTEHEN → EINSCHÄTZEN → ENTSCHEIDEN
```

### Schritt 1 · /start — Ankommen & Orientieren (NEU)
**Was passiert:** Geführter Onboarding-Flow. Keine Fachbegriffe.
- "Wie lange willst du anlegen?" (1–3 Jahre / 3–10 Jahre / 10+ Jahre)
- "Was ist dir wichtiger?" (Stabilität vs. Wachstum — Slider)
- "Was interessiert dich?" (Schweizer Firmen / Technologie / Nachhaltigkeit / egal)
- Ergebnis: Investorprofil wird gespeichert, personalisiertes Dashboard öffnet sich
- **BI-Kriterium:** Agentic AI — Guided Discovery Agent orchestriert den Flow

### Schritt 2 · /discover — Inspiration & Entdecken
**Was passiert:** Personalisierte Titelliste basierend auf Profil.
- Nicht "alle 200 SPI-Titel" — sondern: "Diese 8 Titel passen zu deinem Profil"
- Jeder Titel mit kurzem Teaser: Branche, Score-Zusammenfassung, 1 Satz Kontext
- Filter: Schweizer Markt / International, Sektor, Score-Typ
- **BI-Kriterium:** Dashboard — personalisierte Decision Intelligence

### Schritt 3 · /stocks/[ticker] — Verstehen & Durchleuchten
**Was passiert:** Die Firma wird "durchleuchtet" — alle Dimensionen sichtbar.
- Quant-Score aufgeschlüsselt: Quality, Trend, Value, Diversification
- Jede Zahl hat ein "?" → Claude erklärt in 2 Sätzen auf Deutsch was das bedeutet
- RAG-Deep-Dive: "Laut Jahresbericht 2023 hat Nestlé..."  (mit Quelle)
- ML-Prediction: Wahrscheinlichkeit positiver Rendite + Top-3 Einflussfaktoren
- Makro-Kontext: "Der SNB-Leitzins beeinflusst diese Aktie so..."
- **BI-Kriterium:** RAG + ML + Erklärbarkeit

### Schritt 4 · /decision — Einschätzen & Signal
**Was passiert:** BUY / HOLD / WATCH mit vollständiger Begründung.
- Signal-Herleitung: Quant 45% + ML 35% + Makro 20%
- Audit-Trail: welche Daten, welcher Agent, welches Modell hat wie gewichtet
- Konfidenz sichtbar (z.B. "Mittlere Konfidenz — Makro-Unsicherheit hoch")
- Vergleich: 2 Titel nebeneinander
- **BI-Kriterium:** Decision Intelligence — transparent + auditierbar

### Schritt 5 · /portfolio — Entscheiden & Verfolgen
**Was passiert:** Was ich halte, wie es sich entwickelt.
- Gekaufte Positionen eintragen
- Portfolio-Performance vs. SMI-Benchmark
- Rebalancing-Empfehlung vom Portfolio-Agent
- **BI-Kriterium:** Agentic AI — Portfolio Intelligence Agent

---

## 3 · NAVIGATION — 5 BEREICHE (nicht 13 Links)

```
ENTDECKEN     →  /start, /discover, /universe, /rankings
VERSTEHEN     →  /stocks/[ticker], /research, /news
VERGLEICHEN   →  /backtest, /fonds
ENTSCHEIDEN   →  /decision, /signale, /alerts
MEIN PORTFOLIO →  /portfolio, /3a-sim
```

Alle bestehenden Seiten bleiben. Nur die Navigation wird in 5 Gruppen strukturiert.
Die Seite `/start` ist neu — das ist der einzige net-neue Build in der Navigation.

---

## 4 · UX & DESIGN LANGUAGE — "PREMIUM FUTURISTIC"

### Kernprinzipien
1. **Vertrauen über Komplexität** — Jede UI-Entscheidung fragt: "Macht das dem Nutzer Angst oder gibt es ihm Vertrauen?"
2. **Erklären, nicht dumpen** — Kein Datenpunkt ohne Kontext. Immer "?" verfügbar.
3. **Fortschritt sichtbar machen** — Der Nutzer sieht wie weit er auf der Journey ist.
4. **Niemals überfordern** — Max 3 Handlungsoptionen pro Schritt.
5. **Schweizer Qualität** — Präzision, Klarheit, kein Bullshit.

### Visual Identity

```css
/* FARBEN */
--background:      #0d1117;   /* Fast Schwarz — seriös, premium */
--surface:         #161b22;   /* Card-Hintergrund */
--border:          #21262d;   /* Subtile Trenner */
--text-primary:    #e6edf3;   /* Weiss — Haupttext */
--text-secondary:  #8b949e;   /* Grau — Subtext, Labels */
--accent-blue:     #58a6ff;   /* Aktionen, Links, Highlights */
--accent-green:    #7ee787;   /* BUY, positiv, Erfolg */
--accent-orange:   #ffa657;   /* WATCH, neutral, Warnung */
--accent-red:      #f85149;   /* SELL, negativ, Alarm */
--accent-purple:   #bc8cff;   /* AI-Features, Agents */
--gradient-hero:   linear-gradient(135deg, #58a6ff 0%, #7ee787 100%);

/* TYPOGRAFIE */
--font-display:    -apple-system, BlinkMacSystemFont, 'SF Pro Display', system-ui;
--font-mono:       'SF Mono', 'Fira Code', 'JetBrains Mono', monospace;

/* SPACING-SYSTEM (8px-Grid) */
--space-1: 4px;   --space-2: 8px;   --space-3: 12px;  --space-4: 16px;
--space-5: 20px;  --space-6: 24px;  --space-8: 32px;  --space-10: 40px;
--space-12: 48px; --space-16: 64px;

/* BORDER-RADIUS */
--radius-sm: 6px;  --radius-md: 10px;  --radius-lg: 16px;  --radius-xl: 24px;
```

### Futurismus-Elemente (konkret einzubauen)

#### 1. Glassmorphism für Premium-Cards
```css
.glass-card {
  background: rgba(22, 27, 34, 0.8);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(88, 166, 255, 0.15);
  border-radius: var(--radius-lg);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4),
              inset 0 1px 0 rgba(255, 255, 255, 0.05);
}
```

#### 2. Score-Visualisierung — Prisma-Style
Scores werden nicht als Zahlen gezeigt, sondern als **prismatische Spektrum-Bars**:
```
Quality:    ████████░░  82%   (grün → gelb gradient)
Trend:      ██████░░░░  61%   
Value:      ███░░░░░░░  34%
Makro:      ███████░░░  72%
─────────────────────────────
SIGNAL:     [ BUY  ↑ ]       (leuchtend, animiert)
```

#### 3. BUY/HOLD/WATCH Badges
```
BUY   → grüner Glow-Effekt  + Pfeil nach oben, subtle pulse animation
HOLD  → oranger Ring        + horizontaler Strich
WATCH → blauer Ring         + Fernglas-Icon, "Beobachten"
```

#### 4. AI-Erklärungen — Streaming, nicht statisch
Wenn Claude eine Erklärung gibt: Text streamt buchstabenweise rein (typewriter effect).
Nutzer sieht das AI denkt — kein "loading..." Spinner.

#### 5. Onboarding-Animationen
- Fragen erscheinen mit sanftem Fade-In
- Slider-Auswahl gibt haptisches Feedback (CSS transform + colour-shift)
- Nach letzter Antwort: Prisma-Lichtbrechungs-Animation bevor Dashboard erscheint

#### 6. Dashboard-Karten
```
┌─────────────────────────────────────┐
│  NESTLÉ AG               NESN.SW    │
│  ─────────────────────────────────  │
│  Quality ████████░░  82             │
│  Trend   ██████░░░░  61             │
│  ─────────────────────────────────  │
│  [ BUY ↑ ]    Konfidenz: Hoch       │
│                                     │
│  "Starke Qualität, solider Trend.   │
│   SNB-neutral."          [→ Mehr]   │
└─────────────────────────────────────┘
```

#### 7. Loading-States — nie "Loading..."
```
Statt:  "Loading data..."
→       "PRISMA analysiert Nestlé..."
→       "ML-Modell berechnet Rendite-Wahrscheinlichkeit..."
→       "Agent liest Jahresbericht 2023..."
```

### Was wir NICHT tun
- ❌ Kein helles Theme (zu wenig futuristisch)
- ❌ Keine überfüllten Tabellen mit 20 Spalten
- ❌ Kein Fachjargon ohne sofortige Erklärung (immer "?" daneben)
- ❌ Keine roten Alarme für normale Kurschwankungen (macht Angst)
- ❌ Kein "Wir empfehlen dir X zu kaufen" (wir geben Entscheidungshilfe, nicht Anlageberatung)
- ❌ Kein englisches UI (alles auf Deutsch — Schweizer Nutzer)

### Referenz-Inspirationen
- **Linear.app** — Typografie, Spacing, Dark Mode Qualität
- **Vercel Dashboard** — Daten-Dichte ohne Überladung
- **Stripe Dashboard** — Trust durch Design, nicht durch Worte
- **Raycast** — Command-Interface, Futurismus mit Nutzbarkeit

---

## 4b · DIE DISCOVERY ENGINE — DAS HERZSTÜCK VON PRISMA

> Das ist die Funktion die Prof. Renold vom Hocker haut und die VIAC sofort kauft.
> Kein anderer Robo-Advisor, kein anderes BI-Projekt macht das so.

### Das Kernproblem mit klassischem Onboarding

Jeder Robo-Advisor fragt dasselbe:
```
"Risikotoleranz: 1 / 2 / 3 / 4 / 5"
"Anlagehorizont: kurz / mittel / lang"
"Ziel: Sparen / Altersvorsorge / Vermögensaufbau"
```

Das ist das **falsche Framing**. Der verunsicherte Investor denkt nicht in Finanzkonzepten.
Er denkt in seinem Leben. In seinen Ängsten. In Marken die er kennt. In Gefühlen.

PRISMA fragt aus **seiner Welt** — und übersetzt dann selbst in Finanzkonzepte.
Das ist der Unterschied. Das ist der revolutionäre Ansatz.

---

### DIE ZWEI USER-TYPEN — BEIDE BEDIENT

```
                    ┌─────────────────────────────────────┐
                    │           /start                    │
                    │                                     │
                    │  Wie möchtest du beginnen?          │
                    │                                     │
                    │  ┌──────────────────────────────┐   │
                    │  │  🧭 Ich weiss noch nicht     │   │
                    │  │     wo ich anfangen soll.    │   │ ← DER ENTDECKER
                    │  │  Zeig mir den Weg.           │   │   (Kernzielgruppe)
                    │  └──────────────────────────────┘   │
                    │                                     │
                    │  ┌──────────────────────────────┐   │
                    │  │  🎯 Ich weiss was ich suche. │   │ ← DER KENNER
                    │  │     Direkt zu den Titeln.    │   │   (Fast Lane)
                    │  └──────────────────────────────┘   │
                    └─────────────────────────────────────┘
```

Wer auf **"Ich weiss was ich suche"** klickt, bekommt sofort:
- Autocomplete-Suche: Firmenname / Ticker / ISIN / Sektor
- Quick-Filter-Chips: `SMI-Titel` `Dividenden` `Schweizer Tech` `Pharma` `Industrie`
- Keine Onboarding-Fragen, keine Umwege — direkt zu `/stocks/[ticker]`

**Der Kenner wird nie gebremst.** Das ist Respekt für den Nutzer.

---

### DER ENTDECKER — CONVERSATIONAL DISCOVERY ENGINE

#### Philosophie: Fragen aus seiner Welt, nicht aus der Finanzwelt

```
FALSCH:  "Was ist Ihre Risikotoleranz auf einer Skala von 1–5?"
RICHTIG: "Stell dir vor, du schaust auf dein Konto und siehst –20%.
          Was ist dein erster Impuls?"
```

Der Guided Discovery Agent führt ein echtes Gespräch — kein Formular.
3–5 Fragen, dynamisch, kontextsensitiv. Jede Antwort beeinflusst die nächste Frage.

---

#### GESPRÄCHS-FLOW IM DETAIL

##### Turn 1 — Das Leben des Nutzers verstehen
```
PRISMA:  "Hallo. Ich bin PRISMA.
          Bevor ich dir zeige wo du investieren könntest —
          eine persönliche Frage: Was machst du beruflich?"

          [Freitext-Eingabe — kein Dropdown]
```

**Agent-Logik im Hintergrund (Haiku-Klassifikation):**
```python
# Antwort wird klassifiziert in:
sector_familiarity = classify_sector(answer)
# "Softwareentwickler bei einer Bank" →
#   tech_affinity: HIGH
#   finance_knowledge: MEDIUM
#   conservative_lean: LOW (Banken-Kontext → Zahlen gewohnt)

# "Kindergärtnerin" →
#   finance_knowledge: LOW
#   needs_simplification: HIGH
#   stable_income_likely: TRUE
```

Die Sprache von PRISMA passt sich **sofort** an das Profil an:
- Softwareentwickler → technischere Erklärungen okay
- Kindergärtnerin → noch einfachere Sprache, mehr Analogien

---

##### Turn 2 — Das Ziel hinter dem Geld
```
PRISMA:  "Danke. Und was schwebt dir vor —
          wofür ist das Geld irgendwann gedacht?
          (Kein falsches oder richtiges Ziel — ich will nur verstehen.)"

          [ Neue Wohnung ]  [ Altersvorsorge ]
          [ Freiheit       ]  [ Einfach besser als Konto ]
          [ Etwas anderes... ]
```

**Agent-Logik:**
```
"Neue Wohnung in 3 Jahren"  → horizon: SHORT  / risk: LOW   / needs_liquidity: TRUE
"Altersvorsorge"             → horizon: LONG   / risk: MED   / can_be_illiquid: TRUE
"Freiheit"                   → horizon: MEDIUM / risk: HIGH  / growth_focus: TRUE
"Besser als Konto"           → horizon: ANY    / risk: LOW   / stability_first: TRUE
```

---

##### Turn 3 — Der Risk-Feeling-Test (die futuristische Frage)
```
PRISMA:  "Eine letzte Frage — und das ist wichtig.
          Stell dir vor: Du hast CHF 10'000 investiert.
          Nach 3 Monaten öffnest du die App und siehst das:"

          [CHART: –25% in 3 Monaten — animiert, realistisch]

          "Was denkst du zuerst?"

          😱  "Fehler gemacht. Alles raus."
          😐  "Das ist normal. Ich warte."
          😎  "Jetzt kaufe ich mehr."
```

**Warum das revolutionär ist:**
- Kein Finanz-Jargon — jeder versteht einen Chart der fällt
- Emotional ehrlich — die Antwort kommt aus dem Bauch, nicht aus dem Kopf
- Psychologisch akkurat — tatsächliches Verhalten korreliert stärker mit emotionaler Reaktion als mit deklarierten Präferenzen

**Agent-Logik:**
```
😱 "Alles raus"   → risk_profile: CONSERVATIVE  → Dividenden-Titel, Quality-Fokus
😐 "Ich warte"    → risk_profile: MODERATE      → Quality + Trend Mix
😎 "Mehr kaufen"  → risk_profile: AGGRESSIVE    → Momentum, Growth-Titel
```

---

##### Turn 4 — Brand Affinity Mapping (der Aha-Moment)
```
PRISMA:  "Fast fertig. Eine spielerische Frage:
          Welche dieser Schweizer Firmen kennst du — aus dem Alltag,
          der Arbeit, den Nachrichten? Einfach anklicken."

          [BRAND LOGO GRID — 24 Logos]
```

**Die Logos (sorgfältig ausgewählt — alle börsenkotiert oder bekannt):**
```
Alltag/Konsum:    [Nestlé]  [Lindt]  [Barry Callebaut]  [Givaudan]
Pharma/Health:    [Roche]   [Novartis] [Lonza]          [Straumann]
Finanzen:         [UBS]     [Partners Group] [Zurich]   [Swiss Life]
Industrie:        [ABB]     [Georg Fischer]  [Schindler] [Kühne+Nagel]
Tech/Precision:   [Logitech] [u-blox]        [VAT Group] [Inficon]
Luxus/Lifestyle:  [Swatch]  [Richemont]     [Swiss]     [Flughafen ZH]
```

**Was passiert beim Klicken:**
```
Nutzer klickt [Nestlé]
→ Logo leuchtet auf
→ Tooltip erscheint: "Das ist Nestlé S.A. — NESN.SW · SMI"
→ Kleiner Fact: "Nespresso, KitKat, Maggi — alles Nestlé."

Nutzer klickt [Roche]
→ "Roche Holding — ROG.SW · SMI · Pharma-Weltkonzern aus Basel"

Nutzer klickt [Logitech]
→ "Logitech International — LOGN.SW · SMIM · Maus, Tastatur, Webcam"
```

**Nach 3+ Klicks:**
```
PRISMA:  "Du kennst bereits [5] investierbare Schweizer Firmen.
          Das ist dein Ausgangspunkt. Weiter?"

          [Profil fertigstellen →]
```

**Agent-Logik (Cluster-Analyse):**
```python
# Nestlé + Lindt + Barry Callebaut → Konsumgüter-Affinität
# Roche + Novartis + Straumann     → Healthcare-Affinität
# ABB + Georg Fischer + Schindler  → Industrie-Affinität
# Logitech + u-blox + VAT          → Tech-Affinität

# Gemischte Klicks → Diversification-Affinität
# Alle Pharma      → Sektor-Konzentration → Agent warnt später

sector_affinity = cluster_brands(clicked_logos)
# → beeinflusst welche Titel auf /discover priorisiert werden
```

---

##### Turn 5 — Das Profil-Reveal (die magische UX-Moment)

Nach dem letzten Turn passiert folgendes:

```
[SCREEN: Animierter Prisma-Kristall — weisses Licht bricht sich in Farben]

"PRISMA hat dein Investorprofil erstellt."

┌─────────────────────────────────────────────────────┐
│  DEIN INVESTORPROFIL                                │
│                                                     │
│  Typ:         Stabiler Wachstumsinvestor            │
│  Horizont:    5–10 Jahre                            │
│  Risiko:      Moderat (du wartest bei –20%)         │
│  Affinität:   Schweizer Konsum + Industrie          │
│                                                     │
│  Du kennst bereits: Nestlé · ABB · Logitech         │
│                                                     │
│  ──────────────────────────────────────────────     │
│  PRISMA hat 8 Titel für dich ausgewählt.            │
│  [Zeig mir mein personalisiertes Dashboard →]       │
└─────────────────────────────────────────────────────┘
```

**Der psychologische Effekt:**
- Nutzer sieht sich im Spiegel — PRISMA hat ihn verstanden
- Er fühlt sich nicht mehr allein mit seiner Unsicherheit
- Er hat schon 5 Firmen die er kennt — die Angst ist kleiner geworden
- Die 8 Titel die folgen sind SEINE Titel, nicht generische Empfehlungen

---

### TECHNISCHE ARCHITEKTUR — DISCOVERY ENGINE

```
┌─────────────────────────────────────────────────────────────┐
│                  DISCOVERY AGENT                            │
│                  (claude-sonnet-4-6)                        │
│                                                             │
│  Session State:                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  conversation_history: List[Message]                │   │
│  │  partial_profile: InvestorProfile                   │   │
│  │  confidence_score: float  (0.0 – 1.0)              │   │
│  │  next_question_strategy: QuestionStrategy           │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Nach jeder Nutzer-Antwort:                                 │
│  1. Haiku klassifiziert Antwort → profile dimensions       │
│  2. Sonnet entscheidet: nächste Frage oder fertig?         │
│  3. Profile-Update in Redis (sessionbased)                 │
│  4. Konfidenz steigt: < 0.6 = weitere Frage, ≥ 0.8 = done │
└─────────────────────────────────────────────────────────────┘
                          │
                          │  Profile abgeschlossen
                          ▼
┌─────────────────────────────────────────────────────────────┐
│               PERSONALIZATION SERVICE                       │
│                                                             │
│  Input:   InvestorProfile (horizon, risk, sectors, brands)  │
│  Output:  Ranked List<Stock> — max 8–10 Titel              │
│                                                             │
│  Logik:                                                     │
│  1. Universe Filter: SMI/SMIM/SPI nach Sektor-Affinität    │
│  2. Quality-Filter: nur Titel mit Quant-Score > 50         │
│  3. Risk-Filter: risk_profile bestimmt Volatilitäts-Cap    │
│  4. Brand-Boost: geklickte Marken bekommen +10 Relevanz    │
│  5. ML-Filter: nur Titel mit neutraler/positiver Prediction │
└─────────────────────────────────────────────────────────────┘
```

**Pydantic Model für das Investorprofil:**
```python
class InvestorProfile(BaseModel):
    # Aus dem Gespräch extrahiert
    profession: str | None
    financial_knowledge: Literal["low", "medium", "high"]
    investment_goal: Literal["housing", "retirement", "freedom", "beat_savings", "other"]
    time_horizon: Literal["short", "medium", "long"]  # <3J / 3-10J / 10J+
    risk_profile: Literal["conservative", "moderate", "aggressive"]
    
    # Aus dem Brand-Mapping
    sector_affinity: List[str]  # ["consumer", "pharma", "industrial", "tech"]
    known_brands: List[str]     # ["NESN.SW", "ROG.SW", "LOGN.SW"]
    
    # Meta
    confidence_score: float     # 0.0 – 1.0
    onboarding_complete: bool
    created_at: datetime
    session_id: str

    class Config:
        # Immer strukturiert, niemals freier LLM-Text für Profile-Felder
        # LLM interpretiert → Haiku klassifiziert → Pydantic validiert
        use_enum_values = True
```

---

### WARUM DAS DEN DOZENTEN ÜBERZEUGT

```
Standard BI-Projekt:   Nutzer wählt Aktien aus einer Liste → Dashboard zeigt Daten
PRISMA Discovery:      Agent führt Gespräch → versteht Nutzer → kuratiert Universe
                       → Nutzer versteht warum diese Titel → Entscheidung mit Klarheit
```

**Das ist Decision Intelligence in Reinform:**
Nicht Daten anzeigen. Einen Entscheidungsprozess begleiten.
Der Agent ist nicht ein Tool das Befehle ausführt — er ist ein Gesprächspartner der denkt.

**Für das BI-Modul demonstrierbar in 2 Minuten:**
- Agent-Kette sichtbar machen (Discovery Agent → Haiku Classifier → Personalization Service)
- Zeigen dass dieselbe App für zwei verschiedene Profile zwei komplett verschiedene Titel empfiehlt
- Audit-Trail: "Warum wurde Nestlé empfohlen?" → weil Konsumgüter-Affinität + Moderate Risk + Long Horizon

---

### DER FAST-LANE USER (KENNER) — VOLLSTÄNDIG AUSGEARBEITET

```
/start → "Ich weiss was ich suche" → /search

SEARCH-PAGE:
┌─────────────────────────────────────────────────────┐
│  🔍  Suche nach Firma, Ticker oder Sektor...         │
│      [Nestlé                               ] [→]    │
│                                                     │
│  VORSCHLÄGE WÄHREND DU TIPPST:                      │
│  ├── NESN.SW   Nestlé S.A.          SMI  Konsum     │
│  ├── LOGN.SW   Logitech Int.        SMIM Tech       │
│  └── NESN.US   Nestlé ADR           NYSE (US)       │
│                                                     │
│  SCHNELLFILTER:                                     │
│  [SMI-20] [Dividenden Top 10] [Swiss Tech]          │
│  [Pharma & Life Sciences] [Industrie] [Alle SPI]    │
└─────────────────────────────────────────────────────┘
```

**Was der Kenner NICHT bekommt:**
- Keine 3-Fragen-Onboarding
- Kein "Bitte fülle dein Profil aus"
- Kein Popup das ihn auffordert etwas zu tun

**Was der Kenner BEKOMMT:**
- Direkte `/stocks/[ticker]` Seite mit allen Analysen
- Option am Ende der Analyse: "Willst du ein persönliches Universe aufbauen?" → optional zum Onboarding
- Sein Suchverlauf wird anonym gespeichert → nach 3 Suchen schlägt PRISMA vor: "Du schaust dir oft Tech-Titel an. Soll ich dir mehr zeigen?"

---

## 5 · TECHNISCHE ARCHITEKTUR

### Stack
```
Backend       Python 3.12 · FastAPI · SQLAlchemy 2.0 · Alembic
Database      PostgreSQL 16 · pgvector (Embeddings) · Redis (Cache)
AI/LLM        Claude API: Opus (Architektur) / Sonnet (Agents) / Haiku (Erklärungen)
ML            XGBoost · LightGBM · scikit-learn · pandas · Walk-Forward-Validation
RAG           Voyage AI Embeddings · pgvector · SIX Exchange Filings
Frontend      Next.js 14 · TypeScript · Tailwind CSS · Recharts · Framer Motion
DevOps        Docker · GitHub Actions · Render · GHCR
Data          yfinance (.SW suffix) · SIX Exchange · SNB API · ESTV
```

### Clean Architecture — 4 Layer
```
Domain          → Entities, Value Objects, Business Rules (kein Framework-Import)
Application     → Use Cases, Services (orchestriert Domain)
Interfaces      → REST Controllers, MCP Tools, Pydantic Schemas
Infrastructure  → DB, External APIs, ML Models, Vector Store
```

### Claude Model Routing
| Aufgabe | Modell | Warum |
|---|---|---|
| Architektur-Entscheide, Trade-offs | claude-opus-4-6 | Urteilskraft |
| Agents, RAG, Feature-Analyse | claude-sonnet-4-6 | Balance |
| Score-Erklärungen, Quick-Answers | claude-haiku-4-5-20251001 | Schnell + günstig |
| Return-Prediction, Scoring | XGBoost / LightGBM | Deterministisch, auditierbar |

### Signal-Formel (Decision Intelligence)
```
SIGNAL = Quant 45% + ML 35% + Makro 20%

Quant-Score:  Quality + Trend + Value + Diversification (regelbasiert)
ML-Score:     XGBoost Return Predictor (3 Klassen: Top/Mid/Bottom Quartil)
Makro-Score:  SNB-Leitzins + CHF/EUR + Inflation CH (via Macro Agent)
```

### Datenpipeline (muss laufen bevor Demo!)
```bash
# 1. Swiss Universe seeden
python scripts/seed_smi_universe.py      # SMI-20
python scripts/seed_smim_universe.py     # SMIM-30
python scripts/seed_spi_top50.py         # SPI Top 50

# 2. Historische Preisdaten laden
python scripts/fetch_price_history.py    # yfinance, .SW suffix

# 3. ML-Modell trainieren
python scripts/train_return_predictor.py --universe smi --validate walk_forward

# 4. RAG-Corpus aufbauen
python scripts/ingest_swiss_filings.py   # SIX Exchange Filings
python scripts/seed_estv_corpus.py       # ESTV für Steuer-Agent

# 5. Embeddings generieren
python scripts/generate_embeddings.py    # Voyage AI → pgvector
```

---

## 6 · BI-MODUL BEWERTUNGSKRITERIEN — SO WERDEN WIR BEWERTET

### Kriterium 1: Agentic AI
**Was wir zeigen:** Guided Discovery Agent auf `/start`
- Agent stellt 3 Fragen, baut Investorprofil
- Orchestriert basierend auf Antworten: welche Titel zeigen, welche RAG-Queries stellen
- Zeigt echte Agenten-Kette: Discovery Agent → Fundamentals Agent → Synthesizer Agent
- **Demo-Moment:** Nutzer beantwortet Fragen, Agent gibt personalisierte Titelliste zurück

### Kriterium 2: ML-basiert
**Was wir zeigen:** XGBoost Return Predictor auf `/stocks/[ticker]`
- 3-Klassen-Prediction: Top / Mid / Bottom Quartil (Walk-Forward validiert)
- Feature Importances sichtbar: "Nestlé hat diesen Score weil Quality (40%), Trend (35%)..."
- Nicht als Blackbox — als erklärbares Modell
- **Demo-Moment:** Ticker eingeben → ML-Prediction mit Top-3 Einflussfaktoren erscheint

### Kriterium 3: RAG-basiert
**Was wir zeigen:** Swiss Filings Deep-Dive auf `/stocks/[ticker]`
- Frage: "Was macht Nestlé genau?" → Antwort aus echtem SIX-Jahresbericht, mit Seitenangabe
- Embeddings: Voyage AI multilingual (Deutsch/Französisch/Englisch)
- Quellen werden immer angezeigt: Dokument, Datum, Abschnitt
- **Demo-Moment:** Frage auf Deutsch → Antwort aus deutschem Jahresbericht, Quelle sichtbar

### Kriterium 4: Dashboard / Decision Intelligence
**Was wir zeigen:** Personalisiertes Dashboard + BUY/HOLD/WATCH auf `/decision`
- Dashboard zeigt NUR Titel die zum Nutzerprofil passen (nicht alle 200 SPI)
- Jedes Signal hat vollständigen Audit-Trail
- Konfidenz sichtbar, Makro-Kontext sichtbar
- **Demo-Moment:** Live BUY-Signal für NESN.SW mit Begründung und Audit-Trail

### Originality Bonus
- User Journey (unsicherer Investor) ist nicht das was andere BI-Projekte machen
- Swiss Market Fokus + deutsch-sprachiges RAG ist einzigartig
- "PRISMA durchleuchtet" als Metapher konsequent umgesetzt

---

## 7 · AKTUELLER STAND (IST-ZUSTAND)

### Was funktioniert (live auf Render)
- ✅ Frontend: 13 Seiten vorhanden
- ✅ Backend: FastAPI läuft
- ✅ Clean Architecture implementiert
- ✅ Alle Scripts vorhanden (seed, train, ingest)
- ✅ CI/CD via GitHub Actions
- ✅ PostgreSQL + pgvector konfiguriert

### Was NICHT funktioniert (kritische Gaps)
- ❌ **Datenpipeline wurde nie ausgeführt** → DB ist leer
- ❌ **XGBoost Modell wurde nie trainiert** → ML liefert Fallback
- ❌ **RAG-Corpus ist leer** → keine Filings indexiert
- ❌ **Signale zeigen NEUTRAL** → weil keine echten Daten
- ❌ **/start Seite existiert nicht** → kein Onboarding
- ❌ **Navigation ist 13 unstrukturierte Links** → kein roter Faden

---

## 8 · ROADMAP — PRIORISIERT

### 🔥 RELEASE 2.3 — "The Foundation" (Jetzt, diese Woche)
**Ziel:** 4 BI-Proofs live & demonstrierbar

| # | Task | Wer | Status |
|---|---|---|---|
| 1 | Datenpipeline ausführen (seed SMI + train XGBoost) | Backend | ⬜ TODO |
| 2 | RAG-Corpus aufbauen (ingest_swiss_filings + generate_embeddings) | Backend | ⬜ TODO |
| 3 | /decision zeigt echte BUY/HOLD/WATCH Signale | Backend | ⬜ TODO |
| 4 | /start Seite bauen — CONVERSATIONAL DISCOVERY ENGINE (siehe Sektion 4b) | Frontend + AI | ⬜ TODO |
| 5 | Navigation umstrukturieren (5 Bereiche) | Frontend | ⬜ TODO |
| 6 | Score-Erklärungen via Haiku (? Icon überall) | Frontend + AI | ⬜ TODO |
| 7 | UX-Refresh: Glassmorphism Cards, Signal-Badges, Streaming Text | Frontend | ⬜ TODO |

### 🎯 RELEASE 2.4 — "The Experience" (Nächste Woche)
**Ziel:** UX polieren, Demo-Flow perfektionieren

| # | Task |
|---|---|
| 1 | Onboarding-Animationen (Framer Motion) |
| 2 | Prisma-Spektrum Score-Visualisierung |
| 3 | BUY/HOLD/WATCH Badges mit Glow-Effekten |
| 4 | Streaming AI-Antworten (typewriter effect) |
| 5 | Personalisertes Dashboard (Nutzerprofil-basiert) |
| 6 | Mobile-Responsive |

### 📊 RELEASE 2.5 — "The Pitch" (Präsentation)
**Ziel:** Präsentation + VIAC-Demo

| # | Task |
|---|---|
| 1 | 10-Minuten Demo-Flow dokumentieren |
| 2 | VIAC Pitch-Narrative fertigstellen |
| 3 | Präsentation für Prof. Dr. Renold |
| 4 | README aktualisieren |

---

## 9 · DEMO-FLOW (10 Minuten, für Präsentation)

```
00:00 — Problem: "Ich hab CHF 20k. Ich weiss nicht wo anlegen. Ich hab Angst."
        → Zeige leere Bank-App. Inflation frisst Rendite.

01:00 — /start: Onboarding
        → 3 Fragen beantworten (Horizont: 5+ Jahre, Stabilität, Schweizer Firmen)
        → Guided Discovery Agent im Hintergrund sichtbar (Agent-Kette zeigen)

02:30 — /discover: Personalisiertes Dashboard
        → "Basierend auf deinem Profil: Diese 6 Schweizer Titel"
        → Nestlé herausgepickt

03:30 — /stocks/NESN.SW: Durchleuchten
        → Quant-Scores aufklappen, "?" klicken → Haiku erklärt Quality-Score
        → RAG: "Laut Jahresbericht 2023..." mit Quellenangabe
        → ML-Prediction: "72% Wahrscheinlichkeit Top-Quartil, weil Quality (40%)..."

06:00 — /decision: Signal
        → BUY Signal für NESN.SW
        → Audit-Trail aufklappen: wie wurde das Signal berechnet?
        → Makro-Kontext: "SNB-Entscheid vom März 2025 beeinflusst..."

08:00 — /portfolio: Was jetzt?
        → Nestlé zum Portfolio hinzufügen
        → Portfolio-Agent: "Mit Nestlé fehlt noch Diversifikation in Tech..."

09:30 — Fazit für Prof. Renold:
        "Wir haben Agentic AI, ML, RAG und Decision Intelligence in einer
         kohärenten User Journey gebaut. Für den Nutzer der nie investiert hat."

09:45 — VIAC Pitch:
        "Das ist euer Onboarding für VIAC Stocks. Fertig."
```

---

## 10 · AGENT-VERHALTEN — REGELN FÜR CLAUDE CODE

### Allgemein
- Schreibe IMMER auf Deutsch kommentierte Commits und PR-Beschreibungen
- Nutze Pydantic für alle LLM-Outputs (strukturiert, validiert)
- Keine LLM-Entscheide für regelbasierte Dinge (3a Eligibility = FINMA-Regel, nicht LLM)
- Jede AI-Antwort im Frontend zeigt Quelle/Modell/Konfidenz

### Datenpipeline
- Immer `.SW` Suffix für Schweizer Ticker in yfinance
- SMI-20 > SMIM-30 > SPI Top 50 in dieser Priorität
- Walk-Forward Validation ist Pflicht für ML-Modell (kein einfacher Train/Test-Split)
- Embeddings: Voyage AI `voyage-multilingual-2` für Deutsch/Französisch Support

### Frontend
- Dark Mode only, kein Theme-Toggle (Design-Entscheid)
- Alle Texte auf Deutsch (UI-Labels, Fehlermeldungen, AI-Antworten)
- Score-Erklärungen via Claude Haiku (günstig, schnell)
- Kein "Loading..." — immer spezifische Nachricht was PRISMA gerade tut
- Streaming für alle AI-Antworten (nicht Batch)

### Was NICHT gebaut werden soll (Scope-Schutz)
- ❌ Komplexe 3a-Vergleichs-Features (bleibt einfach, nicht Fokus)
- ❌ Steuer-Optimierungs-Rechner (zu komplex, nicht BI-Kriterium)
- ❌ Echtzeit-Kurs-Feed (yfinance täglich reicht)
- ❌ Social Features / Community
- ❌ Payment / Premium-Tier
- ❌ Mobile App (PWA reicht wenn Zeit bleibt)

---

## 11 · NEXT RELEASE — ANALYSE BENÖTIGTER TOOLS & PROZESSE

### Backend — Was fehlt / angepasst werden muss
```python
# NEU: Investor-Profil Modell
class InvestorProfile(Base):
    id: UUID
    horizon: Literal["short", "medium", "long"]  # 1-3 / 3-10 / 10+ Jahre
    risk_tolerance: float  # 0.0 (Stabilität) bis 1.0 (Wachstum)
    interests: List[str]  # ["swiss", "tech", "sustainability", "any"]
    created_at: datetime

# NEU: Personalisierter Titel-Filter
class DiscoveryService:
    def get_personalized_universe(profile: InvestorProfile) -> List[Stock]:
        # Filtert SMI/SMIM/SPI basierend auf Profil
        ...

# ANPASSEN: DecisionService muss echte Signale liefern
# Heute: liefert NEUTRAL wenn keine ML-Prediction
# Neu: liefert Quant-Only-Signal wenn ML nicht verfügbar, mit Hinweis
```

### Frontend — Was neu gebaut werden muss
```
/start                    → NEU: Onboarding-Flow (3 Fragen + Animation)
/discover                 → NEU: Personalisiertes Dashboard (nutzt InvestorProfile)
/stocks/[ticker]/explain  → NEU: AI-Erklärung via Haiku (Streaming)
components/SignalBadge    → NEU: BUY/HOLD/WATCH mit Glow-Effekt
components/PrismaScore    → NEU: Spektrum-Visualisierung der Scores
components/ExplainButton  → NEU: "?" überall, öffnet Haiku-Erklärung
components/AuditTrail     → NEU: Decision-Herleitung aufklappbar
```

### Neue Dependencies
```bash
# Frontend
npm install framer-motion          # Animationen
npm install @radix-ui/react-*      # Accessible UI Primitives

# Backend (bereits installiert, nur aktivieren)
voyageai                           # Embeddings (bereits in requirements.txt)
xgboost lightgbm                   # ML (bereits in requirements.txt)
```

### Prozesse die einmalig ausgeführt werden müssen
```bash
# SCHRITT 1: Daten laden (einmalig, dann täglich per Cronjob)
python scripts/seed_smi_universe.py
python scripts/fetch_price_history.py --years 5

# SCHRITT 2: ML trainieren (einmalig, dann monatlich neu trainieren)
python scripts/train_return_predictor.py \
  --universe smi_smim \
  --validate walk_forward \
  --output models/return_predictor_v1.pkl

# SCHRITT 3: RAG aufbauen (einmalig, dann wöchentlich updaten)
python scripts/ingest_swiss_filings.py --limit 50  # Top-50 Titel
python scripts/generate_embeddings.py --model voyage-multilingual-2

# SCHRITT 4: Verify
curl https://prisma-v2-backend.onrender.com/api/v1/stocks/NESN.SW/signal
# Muss echtes Signal zurückgeben, nicht NEUTRAL
```

---

## 12 · VIAC PITCH — NARRATIVE

**Kontext:** Andrea arbeitet bei VIAC. VIAC hat eine Stocks-Funktion (freie Mittel, nicht 3a).
**Das Problem für VIAC:** Nutzer kommen in die App, sehen den "Stocks" Tab, wissen nicht was tun, verlassen ihn.
**Die Lösung:** PRISMA als Onboarding-Layer.

**Pitch-Satz:**
> "PRISMA ist nicht ein weiteres Analyse-Tool. Es ist der geführte Einstieg den euer Stocks-Tab heute vermisst. Nutzer die nicht wissen wo anfangen, kommen zu PRISMA, finden ihre ersten 3 Titel, verstehen warum — und kaufen dann in VIAC Stocks. Wir machen Angst zu Vertrauen."

**Was VIAC interessiert:**
- Conversion: Mehr Nutzer die wirklich Stocks kaufen (nicht nur schauen)
- Trust: Nutzer die verstehen was sie kaufen, churnieren weniger
- Differenzierung: Kein anderer Schweizer Broker hat das
- Compliance: PRISMA ist Entscheidungshilfe, keine Anlageberatung (wichtig für FINMA)

---

## 13 · GLOSSAR

| Begriff | Bedeutung in PRISMA |
|---|---|
| Durchleuchten | Eine Aktie in ihre Dimensionen zerlegen (Kernmetapher) |
| Signal | BUY / HOLD / WATCH — immer mit Begründung |
| Discovery | Erste Inspiration — Titel die zum Profil passen |
| Investorprofil | Horizont + Risikotoleranz + Interessen (via Onboarding) |
| Quant-Score | Regelbasierter Faktor-Score (Quality, Trend, Value, Diversification) |
| ML-Prediction | XGBoost Return-Klasse (Top/Mid/Bottom Quartil) |
| Audit-Trail | Vollständige Herleitung wie ein Signal zustande kam |
| Walk-Forward | ML-Validierungsmethode: rollierende Train/Test-Fenster |
| RAG | Retrieval Augmented Generation — Antworten aus echten Dokumenten |

---

---

---

## 14 · DETAILLIERTE AUFGABENPLÄNE PRO PERSON

> Jede Aufgabe ist so beschrieben, dass der Claude Code Agent **ohne Rückfragen** beginnen kann.
> Dateipfade, Modelle, API-Signaturen — alles ist hier. Kein Raten, kein Erfinden.

---

### 👤 ANDREA — Release 2.3 & 2.4

#### Branch: `feature/andrea-datenpipeline`

##### Aufgabe R2.3-1: Datenpipeline ausführen

**Ziel:** Echte Schweizer Aktien in der DB, XGBoost-Modell trainiert und gespeichert.

**Schritt-für-Schritt:**
```bash
# 1. Backend-Umgebung aktivieren
cd /Users/andreapetretta/prisma-v2/backend
source .venv/bin/activate  # oder: conda activate prisma

# 2. DB-Verbindung prüfen
python -c "from app.infrastructure.database import engine; print('DB OK')"

# 3. SMI-20 seeden
python scripts/seed_smi_universe.py
# Erwartete Ausgabe: "Seeded 20 SMI stocks successfully"

# 4. SMIM-30 seeden
python scripts/seed_smim_universe.py
# Erwartete Ausgabe: "Seeded 30 SMIM stocks successfully"

# 5. Historische Preisdaten laden (yfinance, .SW Suffix)
python scripts/fetch_price_history.py --years 5
# Ticker Format: NESN.SW, ROG.SW, NOVN.SW etc.
# Erwartete Ausgabe: "Fetched price history for [N] stocks"

# 6. XGBoost trainieren
python scripts/train_return_predictor.py \
  --universe smi_smim \
  --validate walk_forward \
  --output models/return_predictor_v1.pkl
# Walk-Forward Validation ist PFLICHT — kein einfacher Train/Test-Split
# Erwartete Ausgabe: Accuracy > 45%, F1-Score pro Klasse, Model saved to models/

# 7. Verify
python -c "
import pickle
model = pickle.load(open('models/return_predictor_v1.pkl', 'rb'))
print('Model loaded OK, features:', model.feature_names_in_)
"
```

**Was wenn ein Script fehlt oder crashed:**
- Fehlende Abhängigkeiten: `pip install yfinance xgboost lightgbm scikit-learn --break-system-packages`
- DB-Fehler: `.env` prüfen, `DATABASE_URL` korrekt gesetzt?
- yfinance Timeout: `--limit 10` Flag für kleineres Batch zuerst testen

---

##### Aufgabe R2.3-2: /decision echte Signale (nach R2.3-1)

**Ziel:** `GET /api/v1/stocks/{ticker}/signal` gibt echtes BUY/HOLD/WATCH zurück, nicht NEUTRAL.

**Dateien die angepasst werden müssen:**
```
backend/app/application/services/decision_service.py
backend/app/infrastructure/ml/return_predictor.py
```

**Gewünschte API-Response:**
```json
{
  "ticker": "NESN.SW",
  "signal": "BUY",
  "confidence": 0.74,
  "components": {
    "quant_score": 82,
    "quant_weight": 0.45,
    "ml_prediction": "top_quartile",
    "ml_probability": 0.71,
    "ml_weight": 0.35,
    "macro_score": 68,
    "macro_weight": 0.20
  },
  "reasoning": "Starke Qualität (82/100), ML sieht Top-Quartil-Rendite (71%), SNB-neutral.",
  "top_factors": ["quality_score", "trend_momentum", "price_to_book"],
  "audit_trail": {
    "model_version": "v1",
    "data_as_of": "2026-06-11",
    "quant_calculated_at": "...",
    "ml_predicted_at": "..."
  }
}
```

**Fallback-Logik (wenn ML nicht verfügbar):**
```python
# NICHT: return Signal.NEUTRAL
# SONDERN:
if ml_prediction is None:
    signal = quant_only_signal(quant_score)
    confidence = 0.45  # niedrigere Konfidenz signalisieren
    reasoning += " (ML nicht verfügbar — Quant-Only)"
```

---

#### Branch: `feature/andrea-discovery-engine` (startet nach R2.3)

##### Aufgabe R2.4-1: /start Conversational Discovery Engine

**Ziel:** Neue Next.js Seite `/start` mit vollständigem 5-Turn Gesprächsflow.
Vollständige Spezifikation in **Sektion 4b** dieses Dokuments.

**Neue Dateien erstellen:**
```
frontend/app/start/page.tsx                    ← Haupt-Seite
frontend/app/start/components/
  ├── ConversationFlow.tsx                     ← Gesprächs-Container
  ├── TurnProfession.tsx                       ← Turn 1: Beruf (Freitext)
  ├── TurnGoal.tsx                             ← Turn 2: Ziel (4 Optionen)
  ├── TurnRiskFeeling.tsx                      ← Turn 3: Chart –25% + 3 Emojis
  ├── TurnBrandMapping.tsx                     ← Turn 4: 24 Logo-Grid
  ├── ProfileReveal.tsx                        ← Turn 5: Prisma-Animation + Summary
  └── FastLane.tsx                             ← Direkteinstieg für Kenner
```

**API-Calls die die Seite braucht (Aurelius baut das Backend):**
```typescript
// Session starten
POST /api/v1/discovery/session
→ { session_id: string }

// Antwort senden, nächste Frage erhalten
POST /api/v1/discovery/answer
Body: { session_id, turn: number, answer: string | string[] }
→ { next_turn: number | null, partial_profile: InvestorProfile, confidence: float }

// Profil abschliessen + personalisierte Titel holen
POST /api/v1/discovery/complete
Body: { session_id }
→ { profile: InvestorProfile, recommended_stocks: Stock[] }
```

**UX-Regeln für diese Seite (aus Sektion 4):**
- Jede Frage erscheint mit Fade-In Animation (Framer Motion)
- Fortschrittsbalken oben: Schritt 1/5 → 2/5 etc.
- "Überspringen" Link bei jeder Frage (klein, grau — nie aufdringlich)
- Nach letzter Antwort: Prisma-Kristall-Animation bevor Dashboard erscheint
- Alle Texte auf Deutsch

---

### 👤 HELIN — Release 2.3 & 2.4

#### Branch: `feature/helin-ux-components`

##### Aufgabe R2.3-3: Neue Frontend-Komponenten

**Neue Dateien:**
```
frontend/components/ui/
  ├── SignalBadge.tsx
  ├── PrismaScore.tsx
  └── ExplainButton.tsx
```

**SignalBadge.tsx — exakte Spezifikation:**
```tsx
// Props
interface SignalBadgeProps {
  signal: 'BUY' | 'HOLD' | 'WATCH' | 'SELL'
  confidence?: number  // 0.0 – 1.0, optional
  size?: 'sm' | 'md' | 'lg'
  animated?: boolean   // Puls-Animation bei BUY
}

// Visuell:
// BUY  → grüner Hintergrund (#0d2d1a), grüner Text (#7ee787),
//         grüner Box-Shadow-Glow, ↑ Pfeil-Icon, optional pulse animation
// HOLD → oranger Hintergrund (#2d1a0d), oranger Text (#ffa657),
//         horizontaler Strich-Icon
// WATCH → blauer Hintergrund (#0d1f3c), blauer Text (#58a6ff),
//          Fernglas-Icon (oder Auge-Icon)
// SELL → roter Hintergrund (#2d0d0d), roter Text (#f85149)

// BUY Glow-Effekt:
// box-shadow: 0 0 20px rgba(126, 231, 135, 0.4),
//             0 0 40px rgba(126, 231, 135, 0.15)
```

**PrismaScore.tsx — exakte Spezifikation:**
```tsx
// Props
interface PrismaScoreProps {
  label: string           // "Quality", "Trend", "Value", "Makro"
  score: number           // 0 – 100
  color?: 'green' | 'blue' | 'purple' | 'orange'
  showExplain?: boolean   // zeigt "?" Button
  onExplain?: () => void  // Callback für ExplainButton
}

// Visuell: Gradient-Bar von links nach rechts
// Score 0–40:   rot/orange Gradient
// Score 40–70:  gelb/orange Gradient
// Score 70–100: grün Gradient
//
// Beispiel (Score 82, Quality):
// [████████░░] 82   (?)
// Label links, Score rechts, Gradient-Fill, "?" am Ende
```

**ExplainButton.tsx — exakte Spezifikation:**
```tsx
// Props
interface ExplainButtonProps {
  context: string         // Was erklärt werden soll: "quality_score" | "trend_score" | etc.
  ticker?: string         // Optional: für ticker-spezifische Erklärung
  label?: string          // Default: "?"
}

// Verhalten:
// 1. Klick → Modal/Popover öffnet sich
// 2. API-Call: POST /api/v1/explain { context, ticker }
// 3. Response streamt rein (Server-Sent Events oder fetch streaming)
// 4. Text erscheint buchstabenweise (typewriter effect, CSS animation)
// 5. Quelle wird am Ende angezeigt: "Erklärt von Claude Haiku"
//
// Immer auf Deutsch antworten.
// Max 3 Sätze — keine Essays.
```

---

##### Aufgabe R2.3-4: Glassmorphism Cards + Loading-States

**Dateien anpassen:**
```
frontend/app/stocks/[ticker]/page.tsx    ← Glassmorphism Cards einbauen
frontend/components/ui/LoadingState.tsx  ← NEU: smarte Loading-Messages
frontend/styles/globals.css             ← CSS-Variablen + .glass-card Klasse
```

**globals.css — CSS-Variablen und Glassmorphism:**
```css
:root {
  --background: #0d1117;
  --surface: #161b22;
  --border: #21262d;
  --text-primary: #e6edf3;
  --text-secondary: #8b949e;
  --accent-blue: #58a6ff;
  --accent-green: #7ee787;
  --accent-orange: #ffa657;
  --accent-red: #f85149;
  --accent-purple: #bc8cff;
}

.glass-card {
  background: rgba(22, 27, 34, 0.8);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(88, 166, 255, 0.15);
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4),
              inset 0 1px 0 rgba(255, 255, 255, 0.05);
}
```

**LoadingState.tsx — smarte Nachrichten:**
```tsx
const LOADING_MESSAGES: Record<string, string[]> = {
  stock:    ["PRISMA analysiert {ticker}...", "Quant-Scores werden berechnet...", "ML-Modell läuft..."],
  rag:      ["PRISMA liest den Jahresbericht...", "Relevante Abschnitte werden gesucht..."],
  signal:   ["Signal wird berechnet...", "Makro-Kontext wird einbezogen..."],
  discover: ["PRISMA kuratiert dein Universe...", "Titel werden nach deinem Profil gefiltert..."],
  explain:  ["PRISMA erklärt..."]
}
// Nie: "Loading..." oder "Please wait..."
```

---

#### Branch: `feature/helin-navigation`

##### Aufgabe R2.4-4: Navigation umstrukturieren

**Datei:**
```
frontend/components/layout/Navigation.tsx  (oder wo die Nav aktuell ist)
```

**Neue Struktur (5 Gruppen, nicht 13 Links):**
```
ENTDECKEN
  ├── /start          "Mein Einstieg"
  ├── /discover       "Mein Universe"
  └── /rankings       "Rankings"

VERSTEHEN
  ├── /stocks/[ticker] "Titel analysieren"  ← Suchfeld in der Nav
  ├── /research        "Research"
  └── /news            "News"

VERGLEICHEN
  ├── /backtest        "Backtest"
  └── /fonds           "Fonds vs. Aktien"

ENTSCHEIDEN
  ├── /decision        "Signale"
  ├── /signale         "Alle Signale"
  └── /alerts          "Alerts"

MEIN PORTFOLIO
  ├── /portfolio       "Portfolio"
  └── /3a-sim          "3a Simulator"
```

**Visuell:**
- Gruppenname in Kleinbuchstaben, grau (#8b949e), 11px, Letter-Spacing
- Active State: blauer linker Border + heller Text
- Collapsed auf Mobile: Hamburger → Bottom-Sheet

---

#### Branch: `feature/helin-discovery-ui` (startet nach R2.4-1)

##### Aufgabe R2.4-2: Brand Logo Grid + Risk-Feeling-Test

**TurnBrandMapping.tsx:**
```tsx
// 24 Firmen mit Logos (SVG oder PNG aus /public/brands/)
const SWISS_BRANDS = [
  // Alltag/Konsum
  { name: "Nestlé",          ticker: "NESN.SW", sector: "consumer",   fact: "Nespresso, KitKat, Maggi" },
  { name: "Lindt",           ticker: "LISP.SW", sector: "consumer",   fact: "Schweizer Schokolade seit 1845" },
  { name: "Barry Callebaut", ticker: "BARN.SW", sector: "consumer",   fact: "Grösster Kakaoverarbeiter der Welt" },
  { name: "Givaudan",        ticker: "GIVN.SW", sector: "consumer",   fact: "Duftstoffe in jedem zweiten Parfüm" },
  // Pharma
  { name: "Roche",      ticker: "ROG.SW",  sector: "pharma",    fact: "Basel. Weltführend in Onkologie" },
  { name: "Novartis",   ticker: "NOVN.SW", sector: "pharma",    fact: "Basel. Voltaren, Ritalin, Entresto" },
  { name: "Lonza",      ticker: "LONN.SW", sector: "pharma",    fact: "Produziert mRNA für Pfizer/BioNTech" },
  { name: "Straumann",  ticker: "STMN.SW", sector: "pharma",    fact: "Weltmarktführer Dentalimplantate" },
  // Finanzen
  { name: "UBS",            ticker: "UBSG.SW", sector: "finance",   fact: "Grösste Schweizer Bank" },
  { name: "Partners Group", ticker: "PGHN.SW", sector: "finance",   fact: "Private Equity aus Baar" },
  { name: "Zurich Insurance",ticker: "ZURN.SW", sector: "finance",  fact: "Globaler Versicherungskonzern" },
  { name: "Swiss Life",     ticker: "SLHN.SW", sector: "finance",   fact: "Lebensversicherung Nr. 1 CH" },
  // Industrie
  { name: "ABB",           ticker: "ABBN.SW", sector: "industrial", fact: "Robotik und Elektrifizierung" },
  { name: "Georg Fischer", ticker: "GF.SW",   sector: "industrial", fact: "Rohrsysteme + Leichtmetallguss" },
  { name: "Schindler",     ticker: "SCHP.SW", sector: "industrial", fact: "Jeder 4. Aufzug weltweit" },
  { name: "Kühne+Nagel",   ticker: "KNIN.SW", sector: "industrial", fact: "Grösster Seefrachtspediteur" },
  // Tech/Precision
  { name: "Logitech", ticker: "LOGN.SW", sector: "tech", fact: "Maus, Tastatur, Webcam — Apples Zubehör" },
  { name: "u-blox",   ticker: "UBXN.SW", sector: "tech", fact: "GPS-Chips in Millionen Autos" },
  { name: "VAT Group",ticker: "VACN.SW", sector: "tech", fact: "Vakuumventile für Chipfabriken" },
  { name: "Inficon",  ticker: "IFCN.SW", sector: "tech", fact: "Sensoren für Halbleitertechnik" },
  // Luxus/Lifestyle
  { name: "Swatch",         ticker: "UHR.SW",  sector: "luxury", fact: "Omega, Longines, Tissot — alles Swatch" },
  { name: "Richemont",      ticker: "CFR.SW",  sector: "luxury", fact: "Cartier, IWC, Jaeger-LeCoultre" },
  { name: "Flughafen ZH",   ticker: "FHZN.SW", sector: "luxury", fact: "Zürich Airport — der pünktlichste" },
  { name: "Givaudan",       ticker: "GIVN.SW", sector: "luxury", fact: "Duftstoffe in Chanel No. 5" },
]

// Verhalten beim Klicken:
// 1. Logo leuchtet auf (border-color: var(--accent-green), box-shadow glow)
// 2. Tooltip erscheint unter dem Logo:
//    "Nestlé S.A. · NESN.SW · SMI"
//    "Nespresso, KitKat, Maggi — alles Nestlé."
// 3. Counter oben rechts: "3 Firmen ausgewählt"
// 4. Ab 3 Klicks: "Du kennst bereits [N] investierbare Firmen." erscheint
```

**TurnRiskFeeling.tsx — Risk-Feeling-Test:**
```tsx
// Ein animierter Chart (Recharts LineChart) der von +5% auf -25% fällt
// Animation: 2 Sekunden, dann Freeze
// Darunter drei grosse Buttons:

const RISK_OPTIONS = [
  {
    emoji: "😱",
    label: "Fehler gemacht. Alles raus.",
    sublabel: "Ich will das Risiko minimieren.",
    value: "conservative",
    color: "#f85149"
  },
  {
    emoji: "😐",
    label: "Das ist normal. Ich warte.",
    sublabel: "Kurzfristige Schwankungen gehören dazu.",
    value: "moderate",
    color: "#ffa657"
  },
  {
    emoji: "😎",
    label: "Jetzt kaufe ich mehr.",
    sublabel: "Günstige Gelegenheit.",
    value: "aggressive",
    color: "#7ee787"
  }
]

// Text darunter (klein, grau):
// "Es gibt keine falsche Antwort. Deine ehrliche Reaktion hilft PRISMA
//  dir die richtigen Titel zu zeigen."
```

**ProfileReveal.tsx — Das Profil-Reveal:**
```tsx
// Animationssequenz (Framer Motion):
// 1. Screen wird dunkel (0.5s)
// 2. Prisma-Kristall erscheint in der Mitte, rotiert langsam (1s)
// 3. Kristall "bricht" — Licht strahlt in 5 Farben aus (0.8s)
// 4. Profil-Card fährt von unten ein (0.5s)

// Profil-Card:
// ┌─────────────────────────────────────────────────────┐
// │  DEIN INVESTORPROFIL                                │
// │                                                     │
// │  Typ:      [Dynamisch generiert von Agent]          │
// │  Horizont: [aus Turn 2]                             │
// │  Risiko:   [aus Turn 3]                             │
// │  Affinität:[aus Turn 4 — Sektoren]                  │
// │                                                     │
// │  Du kennst bereits:                                 │
// │  [Brand 1] · [Brand 2] · [Brand 3]                 │
// │                                                     │
// │  ─────────────────────────────────────────────────  │
// │  PRISMA hat [N] Titel für dich ausgewählt.          │
// │  [ Zeig mir mein personalisiertes Dashboard → ]     │
// └─────────────────────────────────────────────────────┘

// Typ-Generierung (Haiku, 3 Wörter max):
// conservative + long horizon  → "Stabiler Langzeitinvestor"
// moderate + consumer brands   → "Schweizer Qualitätsinvestor"
// aggressive + tech brands     → "Wachstumsorientierter Technikfan"
```

---

### 👤 AURELIUS — Release 2.3 & 2.4

#### Branch: `feature/aurelius-investorprofile`

##### Aufgabe R2.3-5: InvestorProfile Model + DB Migration

**Neue Dateien:**
```
backend/app/domain/entities/investor_profile.py
backend/app/infrastructure/database/models/investor_profile_model.py
backend/alembic/versions/XXXX_add_investor_profiles.py
```

**Domain Entity:**
```python
# backend/app/domain/entities/investor_profile.py
from pydantic import BaseModel, Field
from typing import Literal, List
from uuid import UUID, uuid4
from datetime import datetime

class InvestorProfile(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: str  # Redis-Key für den Gesprächs-State

    # Turn 1 — Beruf & Wissensstand
    profession: str | None = None
    financial_knowledge: Literal["low", "medium", "high"] = "low"

    # Turn 2 — Ziel
    investment_goal: Literal[
        "housing",       # Neue Wohnung
        "retirement",    # Altersvorsorge
        "freedom",       # Finanzielle Freiheit
        "beat_savings",  # Besser als Sparkonto
        "other"
    ] = "beat_savings"

    # Turn 3 — Risiko-Feeling
    time_horizon: Literal["short", "medium", "long"] = "medium"
    # short  = < 3 Jahre
    # medium = 3–10 Jahre
    # long   = > 10 Jahre

    risk_profile: Literal["conservative", "moderate", "aggressive"] = "moderate"

    # Turn 4 — Brand-Mapping
    sector_affinity: List[str] = []
    # Mögliche Werte: "consumer", "pharma", "finance", "industrial", "tech", "luxury"
    known_tickers: List[str] = []
    # Ticker die der Nutzer durch Brand-Mapping identifiziert hat
    # Beispiel: ["NESN.SW", "ROG.SW", "LOGN.SW"]

    # Meta
    confidence_score: float = 0.0  # 0.0 – 1.0
    # < 0.6 = weitere Fragen stellen
    # ≥ 0.8 = Profil komplett, Discovery starten

    onboarding_complete: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Abgeleitetes Feld — wird von DiscoveryService genutzt
    @property
    def risk_label(self) -> str:
        labels = {
            "conservative": "Konservativ — Stabilität über Wachstum",
            "moderate":     "Ausgewogen — Stabilität und Wachstum",
            "aggressive":   "Wachstumsorientiert — Rendite über Stabilität"
        }
        return labels[self.risk_profile]

    class Config:
        use_enum_values = True
```

**SQLAlchemy Model:**
```python
# backend/app/infrastructure/database/models/investor_profile_model.py
from sqlalchemy import Column, String, Float, Boolean, DateTime, ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.infrastructure.database import Base
import uuid

class InvestorProfileModel(Base):
    __tablename__ = "investor_profiles"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String, unique=True, nullable=False, index=True)
    profession = Column(String, nullable=True)
    financial_knowledge = Column(String, default="low")
    investment_goal = Column(String, default="beat_savings")
    time_horizon = Column(String, default="medium")
    risk_profile = Column(String, default="moderate")
    sector_affinity = Column(ARRAY(String), default=[])
    known_tickers = Column(ARRAY(String), default=[])
    confidence_score = Column(Float, default=0.0)
    onboarding_complete = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**Alembic Migration:**
```bash
cd backend
alembic revision --autogenerate -m "add investor_profiles table"
alembic upgrade head
```

---

##### Aufgabe R2.3-6: DiscoveryService + API Endpoints

**Neue Datei:**
```
backend/app/application/services/discovery_service.py
backend/app/interfaces/api/v1/discovery.py
```

**DiscoveryService:**
```python
# backend/app/application/services/discovery_service.py
from app.domain.entities.investor_profile import InvestorProfile
from app.domain.entities.stock import Stock
from typing import List

class DiscoveryService:

    def get_personalized_universe(
        self,
        profile: InvestorProfile,
        max_results: int = 10
    ) -> List[Stock]:
        """
        Gibt personalisierte Titelliste basierend auf Investorprofil zurück.
        KEINE LLM-Entscheide hier — reine Regel-Logik.
        """

        query = db.query(StockModel)

        # 1. Sektor-Filter basierend auf Brand-Affinität
        if profile.sector_affinity:
            query = query.filter(StockModel.sector.in_(profile.sector_affinity))

        # 2. Quant-Quality-Filter — nur Titel mit Score > 50
        query = query.filter(StockModel.quality_score > 50)

        # 3. Risiko-Filter — Volatilitäts-Cap
        volatility_caps = {
            "conservative": 15.0,  # Max 15% annualisierte Volatilität
            "moderate":     25.0,
            "aggressive":   40.0
        }
        max_vol = volatility_caps[profile.risk_profile]
        query = query.filter(StockModel.annualized_volatility <= max_vol)

        # 4. Horizont-Filter
        if profile.time_horizon == "short":
            # Kurzfristig: Dividenden-Fokus, niedrige Schulden
            query = query.filter(StockModel.dividend_yield > 2.0)

        # 5. Brand-Boost: geklickte Marken nach oben priorisieren
        results = query.order_by(
            case(
                (StockModel.ticker.in_(profile.known_tickers), 1),
                else_=2
            ),
            StockModel.quality_score.desc()
        ).limit(max_results).all()

        return [Stock.from_orm(r) for r in results]
```

**API Endpoints:**
```python
# backend/app/interfaces/api/v1/discovery.py
from fastapi import APIRouter, Depends
from app.application.services.discovery_service import DiscoveryService

router = APIRouter(prefix="/discovery", tags=["discovery"])

@router.post("/session")
async def create_session():
    """Neue Discovery-Session starten"""
    session_id = str(uuid4())
    # Leeres Profil in Redis speichern
    redis.setex(f"session:{session_id}", 3600, InvestorProfile(session_id=session_id).json())
    return {"session_id": session_id}

@router.post("/answer")
async def submit_answer(session_id: str, turn: int, answer: str | list[str]):
    """Antwort einreichen, Profil updaten, nächste Frage oder Abschluss"""
    # Profil aus Redis laden
    profile = InvestorProfile.parse_raw(redis.get(f"session:{session_id}"))
    # Haiku klassifiziert Antwort → profile update (siehe Aurelius Aufgabe R2.4-3)
    updated_profile = await classify_and_update(profile, turn, answer)
    # Zurück in Redis
    redis.setex(f"session:{session_id}", 3600, updated_profile.json())
    return {
        "next_turn": turn + 1 if updated_profile.confidence_score < 0.8 else None,
        "partial_profile": updated_profile,
        "confidence": updated_profile.confidence_score
    }

@router.post("/complete")
async def complete_discovery(session_id: str, discovery_service: DiscoveryService = Depends()):
    """Profil abschliessen + personalisierte Titelliste zurückgeben"""
    profile = InvestorProfile.parse_raw(redis.get(f"session:{session_id}"))
    profile.onboarding_complete = True
    # In DB persistieren
    db_profile = save_profile_to_db(profile)
    # Personalisierte Titel
    stocks = discovery_service.get_personalized_universe(profile)
    return {"profile": profile, "recommended_stocks": stocks}
```

---

#### Branch: `feature/aurelius-discovery-agent` (startet nach R2.3-5)

##### Aufgabe R2.4-3: Haiku-Klassifikation + Session-State + Konfidenz

**Ziel:** Freitext-Antworten des Nutzers werden von Claude Haiku in Profil-Dimensionen klassifiziert.

**Neue Datei:**
```
backend/app/application/services/profile_classifier.py
```

```python
# backend/app/application/services/profile_classifier.py
import anthropic
from app.domain.entities.investor_profile import InvestorProfile
from pydantic import BaseModel
from typing import Literal

client = anthropic.Anthropic()

class Turn1Classification(BaseModel):
    """Ergebnis der Haiku-Klassifikation für Turn 1 (Beruf)"""
    financial_knowledge: Literal["low", "medium", "high"]
    # low    = Kindergärtnerin, Handwerker, Student
    # medium = IT, Ingenieur, Lehrer, Verwaltung
    # high   = Banker, Analyst, Buchhalter, Ökonom
    sector_hint: str | None  # z.B. "tech" wenn Softwareentwickler

class Turn2Classification(BaseModel):
    """Turn 2: Ziel"""
    investment_goal: Literal["housing", "retirement", "freedom", "beat_savings", "other"]
    time_horizon: Literal["short", "medium", "long"]

async def classify_turn1(profession_text: str) -> Turn1Classification:
    """Beruf-Text → Wissenslevel + Sektor-Hinweis"""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",  # Haiku: schnell + günstig
        max_tokens=200,
        system="""Du klassifizierst Berufsbezeichnungen für einen Investment-App Onboarding-Flow.
Antworte NUR mit einem JSON-Objekt. Kein Text davor oder danach.
Schema: {"financial_knowledge": "low|medium|high", "sector_hint": "consumer|pharma|finance|industrial|tech|null"}
Beispiele:
- "Softwareentwickler" → {"financial_knowledge": "medium", "sector_hint": "tech"}
- "Bankangestellter" → {"financial_knowledge": "high", "sector_hint": "finance"}
- "Pflegefachfrau" → {"financial_knowledge": "low", "sector_hint": "pharma"}
- "Schreiner" → {"financial_knowledge": "low", "sector_hint": null}""",
        messages=[{"role": "user", "content": f"Beruf: {profession_text}"}]
    )
    return Turn1Classification.parse_raw(response.content[0].text)

async def classify_turn2(goal_selection: str) -> Turn2Classification:
    """Ziel-Auswahl → investment_goal + time_horizon"""
    GOAL_MAP = {
        "Neue Wohnung":            ("housing",      "short"),
        "Altersvorsorge":          ("retirement",   "long"),
        "Finanzielle Freiheit":    ("freedom",      "medium"),
        "Besser als Konto":        ("beat_savings", "medium"),
    }
    goal, horizon = GOAL_MAP.get(goal_selection, ("other", "medium"))
    return Turn2Classification(investment_goal=goal, time_horizon=horizon)

def classify_turn3(emoji_choice: str) -> str:
    """Risk-Feeling → risk_profile"""
    RISK_MAP = {
        "conservative": "conservative",
        "moderate":     "moderate",
        "aggressive":   "aggressive"
    }
    return RISK_MAP.get(emoji_choice, "moderate")

def classify_turn4(clicked_tickers: list[str], brand_data: dict) -> tuple[list[str], list[str]]:
    """Brand-Klicks → sector_affinity + known_tickers"""
    sectors = list({brand_data[t]["sector"] for t in clicked_tickers if t in brand_data})
    return sectors, clicked_tickers

def calculate_confidence(profile: InvestorProfile) -> float:
    """Wie vollständig ist das Profil? 0.0 – 1.0"""
    score = 0.0
    if profile.financial_knowledge != "low" or profile.profession: score += 0.2
    if profile.investment_goal != "beat_savings":                   score += 0.2
    if profile.risk_profile != "moderate":                          score += 0.3
    if len(profile.known_tickers) >= 2:                             score += 0.2
    if len(profile.sector_affinity) >= 1:                           score += 0.1
    return min(score, 1.0)
```

##### Aufgabe R2.4-6: Makro-Agent + RAG verifizieren

**Makro-Agent aktivieren:**
```python
# Prüfe ob MacroIntelligenceAgent bereits implementiert ist:
# backend/app/application/agents/macro_agent.py
# Falls ja: sicherstellen dass SNB-Daten geladen werden
# Falls nein: minimale Implementation:

class MacroIntelligenceAgent:
    """Holt SNB-Daten und berechnet Makro-Score für CH-Aktien"""

    async def get_macro_score(self, ticker: str) -> dict:
        # SNB API: https://data.snb.ch/api/
        # Leitzins, CHF/EUR, Inflation CH
        # Gibt Score 0–100 zurück basierend auf:
        # - Leitzins < 1%: gut für Wachstumstitel (+20)
        # - CHF stark: gut für Import-Firmen, schlecht für Exporteure
        # - Inflation < 2%: stabil (+10)
        ...
```

**RAG verifizieren:**
```bash
# Test-Query auf Swiss Filings
curl -X POST http://localhost:8000/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Was macht Nestlé mit seinen Gewinnen?", "ticker": "NESN.SW"}'

# Erwartete Response:
# {
#   "answer": "Laut dem Geschäftsbericht 2023 von Nestlé...",
#   "sources": [{"document": "Nestlé Annual Report 2023", "page": 42, "section": "Capital Allocation"}],
#   "model": "claude-haiku-4-5-20251001"
# }

# Falls Corpus leer: ingest_swiss_filings.py ausführen (Koordination mit Andrea)
```

---

---

## 15 · STARTPROMPTS PRO PERSON — KOPIEREN & EINFÜGEN

### Startprompt Andrea
```
Lies CLAUDE.md vollständig — besonders Sektion 0 (Rahmenbedingungen) und den STATUS-Block ganz oben.

Prüfe den Status-Block: Was ist meine aktuelle Aufgabe?
Falls kein Branch existiert: git checkout -b feature/andrea-datenpipeline

Mein Fokus heute (Release 2.3):
- Aufgabe R2.3-1: Datenpipeline ausführen (Sektion 14 → Andrea → R2.3-1, alle Befehle dort)
- Aufgabe R2.3-2: /decision echte Signale (nach R2.3-1)
Danach (Release 2.4):
- Aufgabe R2.4-1: /start Conversational Discovery Engine (Sektion 4b + 14 → Andrea → R2.4-1)

Update den STATUS-Block in CLAUDE.md sobald du eine Aufgabe startest (🔄) oder abschliesst (✅).
Starte mit: Analysiere den aktuellen DB-Stand — welche Stocks sind bereits vorhanden?
```

### Startprompt Helin
```
Lies CLAUDE.md vollständig — besonders Sektion 0, den STATUS-Block, Sektion 4 (UX Design Language) und Sektion 4b (Discovery Engine UX).

Prüfe den Status-Block: Was ist meine aktuelle Aufgabe?
Falls kein Branch existiert: git checkout -b feature/helin-ux-components

Mein Fokus heute (Release 2.3):
- Aufgabe R2.3-3: SignalBadge + PrismaScore + ExplainButton (Sektion 14 → Helin → R2.3-3)
- Aufgabe R2.3-4: Glassmorphism Cards + Loading-States (Sektion 14 → Helin → R2.3-4)
- Aufgabe R2.4-4: Navigation umstrukturieren — 5 Bereiche (kann parallel, Sektion 3 + 14)
Danach (Release 2.4, nach Andrea's R2.4-1):
- Aufgabe R2.4-2: Brand Logo Grid + Risk-Feeling-Test + ProfileReveal (Sektion 14 → Helin)
- Aufgabe R2.4-5: AuditTrail Komponente

Update den STATUS-Block in CLAUDE.md sobald du eine Aufgabe startest (🔄) oder abschliesst (✅).
Starte mit: Zeig mir die aktuelle Navigation-Komponente — wie sieht sie jetzt aus?
```

### Startprompt Aurelius
```
Lies CLAUDE.md vollständig — besonders Sektion 0, den STATUS-Block, Sektion 4b (Discovery Engine Architektur) und Sektion 11 (Next Release Analyse).

Prüfe den Status-Block: Was ist meine aktuelle Aufgabe?
Falls kein Branch existiert: git checkout -b feature/aurelius-investorprofile

Mein Fokus heute (Release 2.3):
- Aufgabe R2.3-5: InvestorProfile Model + DB Migration (Sektion 14 → Aurelius → R2.3-5)
- Aufgabe R2.3-6: DiscoveryService + API Endpoints (Sektion 14 → Aurelius → R2.3-6)
Danach (Release 2.4):
- Aufgabe R2.4-3: Haiku-Klassifikation + Session-State Redis + Konfidenz (Sektion 14 → Aurelius)
- Aufgabe R2.4-6: Makro-Agent + RAG verifizieren

Update den STATUS-Block in CLAUDE.md sobald du eine Aufgabe startest (🔄) oder abschliesst (✅).
Starte mit: Prüfe ob die Tabelle investor_profiles bereits in der DB existiert.
```

---

## 16 · SESSION STARTEN — SETUP & REPO

### Repo klonen (für Helin & Aurelius — einmalig)
```bash
# Im prisma-v2 Repo-Ordner:
cp "/Users/andreapetretta/Desktop/Business Intelligence/PRISMA_V2_CLAUDE.md" ./CLAUDE.md

git add CLAUDE.md
git commit -m "docs: add CLAUDE.md — persistent context for all agents"
git push origin main
```
Ab sofort liest **jeder** Claude Code Agent (deiner und die deiner Kollegen) dieses File automatisch beim Start. Claude Code liest `CLAUDE.md` im Root-Verzeichnis bei jeder neuen Session.

---

### Schritt 2: Neue Claude Code Session starten

#### Startprompt (kopieren & einfügen):
```
Lies zuerst CLAUDE.md vollständig. Das ist der Kontext für das gesamte Projekt.

Wir bauen PRISMA V2 — ein BI-Modul-Projekt (NICHT das WPM-Capstone).
Lies die KRITISCHEN RAHMENBEDINGUNGEN in Sektion 0 bevor du irgendetwas tust.

HEUTIGER FOKUS: Release 2.3 — Foundation
Priorität 1: Datenpipeline ausführen
  → python scripts/seed_smi_universe.py
  → python scripts/train_return_predictor.py
Priorität 2: /decision muss echte Signale zeigen (nicht NEUTRAL)
Priorität 3: /start Seite — Conversational Discovery Engine (Sektion 4b in CLAUDE.md)

Starte mit: Analysiere den aktuellen Stand der DB und zeig mir ob Daten vorhanden sind.
```

#### Startprompt für Teamkollegen (wenn sie neu einsteigen):
```
Lies zuerst CLAUDE.md vollständig — das ist der vollständige Projektkontext.
Danach erkläre mir kurz in 5 Sätzen was PRISMA V2 ist und was der aktuelle Stand ist.
Dann fragen wir was du heute angehen sollst.
```

---

### Schritt 3: Repo klonen (für Teamkollegen)
```bash
git clone https://github.com/don69andrea/prisma-v2.git
cd prisma-v2

# .env einrichten
cp .env.example .env
# ANTHROPIC_API_KEY, DATABASE_URL, VOYAGE_API_KEY eintragen

# Backend starten
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend starten
cd ../frontend
npm install
npm run dev
```

---

*Letzte Aktualisierung: Juni 2026 · FHNW BI Module FS 2026*
*Repo: github.com/don69andrea/prisma-v2 · Deployment: prisma-v2-frontend.onrender.com*
*Bei Fragen: andrea.petretta@students.fhnw.ch*
