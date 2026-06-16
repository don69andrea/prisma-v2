# Audit-Findings — Discovery & Onboarding (2026-06-16)

## Getestete Funktionen
- POST /api/v1/discovery/session: OK
- POST /api/v1/discovery/answer (Turn 1-7): OK
- POST /api/v1/discovery/answer mit leerem String: UX-ISSUE
- POST /api/v1/discovery/answer mit ungültiger session_id: OK (404 korrekt)
- POST /api/v1/discovery/answer mit >1000 Zeichen Freitext: OK (kein Crash, aber keine Längen-Validierung)
- POST /api/v1/discovery/complete (Happy Path): OK
- POST /api/v1/discovery/complete zweimal auf dieselbe Session: BUG
- GET /api/v1/discover mit ungültiger session_id: OK (404 korrekt)
- Frontend Happy Path (7 Schritte, /start → /discover): OK
- Browser-Reload mitten im Flow: BUG
- Race Condition Turns 1-4 (Hintergrund-Fire) vs. Turns 5-7: BUG
- Doppelklick-Schutz auf "Profil fertigstellen": UX-ISSUE
- Mobile Viewport 375x812: OK (kein horizontales Overflow)
- Step-Übergangs-Animation (fadeIn): NICE-TO-HAVE

## Befunde

### F-DISC-1 — Browser-Reload mitten im Flow verwirft den gesamten Fortschritt
- **Bereich:** UX
- **Schweregrad:** Wichtig
- **Ort:** `frontend/app/start/start-client.tsx` (State nur in `useState`, kein Storage/URL-Sync)
- **Beschreibung:** Der gesamte Discovery-State (`step`, `beruf`, `ziel`, `risiko`, `sessionId`, ...) lebt nur in React-`useState` im Hauptkomponenten. Ein Reload (F5) während eines beliebigen Schritts wirft den Nutzer zurück auf den Landing-Screen (`btn-entdecker`/`btn-kenner`), die bereits beantworteten Turns 1-4 in der Backend-DB bleiben aber als verwaiste, nie abgeschlossene Session bestehen.
- **Reproduktion:** `/start` öffnen → "Ich weiss noch nicht..." → Beruf eingeben → Weiter → Ziel wählen → Weiter → bei Schritt 3 (Risiko) Seite neu laden (F5/Cmd+R). Ergebnis: Landing-Screen statt Fortsetzung bei Schritt 3. Verifiziert per Playwright (`landing=true`, `risiko=false` nach Reload).
- **Vorschlag:** Discovery-State (zumindest `sessionId` + aktueller `step`) in `sessionStorage`/`localStorage` oder Query-Param spiegeln, damit ein Reload den Flow fortsetzen kann statt komplett neu zu starten.

### F-DISC-2 — Race Condition: Turns 1-4 laufen im Hintergrund, Turns 5-7 setzen ungeprüft auf fertige Session
- **Bereich:** Funktional
- **Schweregrad:** Wichtig
- **Ort:** `frontend/app/start/start-client.tsx:1245-1261` (`handleBrandsSubmit`) und `:1165-1242` (`handleContinue`)
- **Beschreibung:** `handleBrandsSubmit` setzt den UI-Schritt sofort auf `'betrag'` und feuert `createDiscoverySession()` + `submitAnswer(turn 1..4)` unawaited im Hintergrund weiter. Klickt der Nutzer schnell durch Betrag/Nachhaltigkeit/Ertrag, kann `handleContinue` ausgeführt werden, bevor `sessionId` gesetzt ist — dann wird `sessionId ?? crypto.randomUUID()` verwendet, also eine nie über `/discovery/session` registrierte UUID. `submitAnswer`/`completeDiscovery` schlagen dann mit 404 fehl, der Catch-Block in `handleContinue` greift und zeigt eine Fallback-Antwort mit `preferred_sectors: []` — obwohl der Nutzer tatsächlich Brands ausgewählt hatte. Reproduziert im eigenen Testlauf: NESN+ROG ausgewählt, Reveal-Screen zeigte trotzdem "Sektoren: —".
- **Reproduktion:** `/start` durchlaufen, bei Schritt 4 (Brands) zwei Marken anklicken und sofort "Profil fertigstellen" klicken, dann zügig (schneller als ~1s) durch Betrag/Nachhaltigkeit/Ertrag klicken. Im Reveal-Screen erscheint "Sektoren: —" trotz ausgewählter Marken.
- **Vorschlag:** `handleBrandsSubmit` sollte das `createDiscoverySession`+Turn-1-4-Promise zurückgeben/awaiten und `handleContinue` sollte darauf warten (z.B. via gespeichertem Promise-Ref), bevor Turns 5-7 gesendet werden — statt sich auf Timing zu verlassen.

### F-DISC-3 — POST /discovery/complete liefert HTTP 500 statt sauberem Fehler bei Session ohne Turn 1
- **Bereich:** Funktional
- **Schweregrad:** Wichtig
- **Ort:** `backend/domain/entities/investor_profile.py:60-73` (`_validate_onboarding_consistency`) + `backend/interfaces/rest/routers/discovery.py:261-284` (`complete_discovery`)
- **Beschreibung:** Der Pydantic-Validator wirft `ValueError`, wenn `onboarding_complete=True` und `profession is None`. Da `model_copy(update=...)` in Pydantic v2 Validatoren NICHT erneut ausführt, läuft der erste `complete`-Call (der `onboarding_complete` via `model_copy` setzt) durch — der `ValueError` schlägt aber beim zweiten Aufruf zu, weil `repo.get_by_session_id` das Profil aus der DB über `_to_domain()` als frischkonstruiertes `InvestorProfile(...)`-Objekt lädt (Validator läuft hier wieder) und `profession` weiterhin `None` ist (Turn 1 nie beantwortet). Der `ValueError` wird vom globalen Exception-Handler als HTTP 500 "Interner Serverfehler." zurückgegeben statt als 400/409. Reproduziert direkt per curl: Session ohne Turn-1-Antwort, Turn 2+3 beantwortet, `complete` Call #1 → 200, Call #2 → 500. Mit Turn 1 beantwortet (echter Happy Path) ist `complete` dagegen idempotent (Call #1 und #2 beide 200, identische Stocks).
- **Reproduktion:**
  ```
  SID=$(curl -s -X POST $BASE/api/v1/discovery/session | jq -r .session_id)
  curl -X POST $BASE/api/v1/discovery/answer -d '{"session_id":"'$SID'","turn":2,"answer":"retirement"}'
  curl -X POST $BASE/api/v1/discovery/answer -d '{"session_id":"'$SID'","turn":3,"answer":"moderate"}'
  curl -X POST $BASE/api/v1/discovery/complete -d '{"session_id":"'$SID'"}'   # → 200
  curl -X POST $BASE/api/v1/discovery/complete -d '{"session_id":"'$SID'"}'   # → 500 "Interner Serverfehler."
  ```
- **Vorschlag:** Entweder (a) den Validator auch als `field_validator`/expliziten Check im Router laufen lassen und bei Verstoss eine 400 statt 500 zurückgeben, oder (b) `complete_discovery` vor dem Setzen von `onboarding_complete=True` prüfen, ob `profession is not None`, und sonst 422 mit klarer Fehlermeldung liefern. Zusätzlich: kein Server-Fehler sollte bei einem zweiten, identischen `complete`-Call auftreten — Endpoint sollte generell idempotent sein (auch im Edge-Case ohne Turn 1).

### F-DISC-4 — "Profil fertigstellen" / "Meine Aktien entdecken" Buttons ohne Disabled-State während Request
- **Bereich:** UX
- **Schweregrad:** Nice-to-have
- **Ort:** `frontend/app/start/start-client.tsx:700-703` (`StepErtrag` Button), `:1300-1305` (`onNext` Handler ruft `handleContinue` auf)
- **Beschreibung:** Der "Profil fertigstellen"-Button in `StepErtrag` und der "Weiter"-Button in `StepReveal` lösen einen asynchronen Request aus (`handleContinue`), bleiben aber bis zum globalen `loading`-State-Wechsel klickbar. Es gibt keinen sofortigen `disabled`/Spinner-State auf dem Button selbst — zwischen Klick und dem Render von `<PrismaLoader>` liegt ein kurzes Zeitfenster, in dem ein zweiter Klick denselben Request nochmal auslösen kann (relevant in Kombination mit F-DISC-3).
- **Reproduktion:** Auf langsamer Verbindung (Chrome DevTools Throttling) bei Schritt 7 zweimal schnell auf "Profil fertigstellen" klicken.
- **Vorschlag:** Button beim ersten Klick synchron `disabled` setzen (z.B. lokaler `isSubmitting`-State), bevor der async Call startet.

### F-DISC-5 — Leere Freitext-Antwort wird ohne Hinweis akzeptiert und führt zu "other"-Ziel
- **Bereich:** UX
- **Schweregrad:** Nice-to-have
- **Ort:** `backend/interfaces/rest/schemas/investor_profile.py:68-72` (`AnswerRequest.answer: str | list[str]`, kein `min_length`); `backend/application/services/profile_classifier.py` `_GOAL_MAP.get(goal_selection, ("other", "medium"))`
- **Beschreibung:** `POST /discovery/answer` mit `"answer": ""` für Turn 2 wird mit HTTP 200 akzeptiert und ordnet automatisch `investment_goal: "other"` zu — ohne Validierungsfehler oder Hinweis. Im Frontend kann dieser Fall durch die UI eigentlich nicht erreicht werden (Buttons sind disabled ohne Auswahl), aber jeder direkte API-Konsument (z.B. künftige Mobile-App, Power-User-Skripte) bekommt stillschweigend ein semantisch unklares Profil statt eines klaren Fehlers.
- **Reproduktion:** `curl -X POST $BASE/api/v1/discovery/answer -d '{"session_id":"<SID>","turn":2,"answer":""}'` → HTTP 200, `investment_goal: "other"`.
- **Vorschlag:** `AnswerRequest.answer` mit `min_length=1` (für `str`-Variante) validieren und bei leerem String 422 zurückgeben, statt stillschweigend auf einen Default-Wert zu fallen.

### F-DISC-6 — Step-Übergänge nutzen durchgängig fadeIn-Animation (opacity 0→1), führt zu kurzem "Ausblassen" bei jedem Schritt
- **Bereich:** UX / Performance
- **Schweregrad:** Nice-to-have
- **Ort:** `frontend/app/globals.css:156-160` (`@keyframes fadeIn`), angewendet in praktisch jeder Step-Komponente in `frontend/app/start/start-client.tsx` (z.B. Zeilen 302, 344, 389, 472, 576, 621, 665, 727, 1090)
- **Beschreibung:** Jeder der 7 Frage-Schritte sowie Landing/Reveal nutzt `animation: fadeIn 0.4s-0.6s ease` mit `opacity: 0 → 1`. Das ist beabsichtigtes Design, führt aber dazu, dass unmittelbar nach jedem "Weiter"-Klick der neue Screen für ~400-600ms in sehr geringem Kontrast erscheint, bevor er volle Deckkraft erreicht — bei Screenshots/automatisierten Tests, die direkt nach `visible`-State zugreifen, ist der Screen fast unlesbar (in eigenen Tests reproduzierbar bei jedem Schritt). Für echte Nutzer auf langsameren Geräten könnte sich der Flow dadurch träger anfühlen als nötig, insbesondere bei den ohnehin schon zahlreichen 7 Schritten.
- **Reproduktion:** Playwright-Screenshot direkt nach `await expect(stepElement).toBeVisible()` ohne zusätzliche Wartezeit — Screenshot zeigt fast schwarzen/kontrastarmen Screen; nach +1.5s Wartezeit ist der Screen voll sichtbar.
- **Vorschlag:** Animationsdauer auf z.B. 150-200ms reduzieren oder `prefers-reduced-motion` respektieren; alternativ Inhalt mit `opacity: 1` rendern und nur eine leichte Transform-Animation verwenden, damit Lesbarkeit nicht von Anfang an beeinträchtigt ist.
