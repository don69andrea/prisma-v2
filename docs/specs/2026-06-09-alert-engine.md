# Spec: Alert Engine — Preis- und Signal-Alerts

**Issue:** #20  
**Milestone:** v2.0 Swiss Intelligence Layer  
**Date:** 2026-06-09  
**Author:** Andrea Petretta (Coding-Agent: Claude Sonnet 4.6)  
**Status:** Implemented

---

## Ziel

Nutzer können Preis- und Signal-Alerts für Swiss Stocks konfigurieren. Täglicher Scheduler (08:00 Europe/Zurich) prüft alle aktiven Alerts und benachrichtigt via E-Mail (SendGrid) oder Webhook.

---

## Nicht-Ziele

- Push-Notifications (Mobile)
- Intraday-Alerts (nur täglicher Check)
- Alert-Templates / Gruppenbenachrichtigungen
- SMS / Telegram-Kanal

---

## Architektur

### Domain
- `Alert` Entity (frozen dataclass): `ticker`, `trigger_type` (SIGNAL_CHANGE | PRICE_CHANGE), `threshold`, `channel` (EMAIL | WEBHOOK), `target`, `is_active`, Zeitstempel
- `AlertRepository` ABC: save, get_by_id, list_active, list_by_owner, delete, update

### Application
- `AlertService`: CRUD + `check_and_notify()` — iteriert aktive Alerts, vergleicht aktuellen Preis/Signal mit Baseline, löst Benachrichtigung aus wenn Schwellwert überschritten
- Price-Alert: `|current_price - baseline_price| / baseline_price * 100 >= threshold`
- Signal-Alert: `current_signal != last_signal`

### Infrastructure
- `AlertORM` SQLAlchemy-Modell → `alerts`-Tabelle (Index auf ticker + is_active)
- `NotificationAdapter`: `send_email()` via SendGrid REST API (httpx, 5s Timeout), `send_webhook()` via httpx POST
- `AlertWorker`: `AsyncIOScheduler` (APScheduler 3.11+), CronTrigger 08:00 Europe/Zurich
- Alembic Migration `0017_create_alerts` (down_revision: 0016)

### Interface
- `POST /api/v1/alerts` → Alert erstellen (201)
- `GET /api/v1/alerts` → Alle Alerts (optional nach target filtern)
- `DELETE /api/v1/alerts/{id}` → Alert löschen (204)
- Scheduler gestartet in `app.py` Lifespan

---

## Sicherheit

- `SENDGRID_API_KEY` ausschliesslich via Umgebungsvariable — nie im Code
- Webhook-Target nicht ins Log (potentiell sensitiv)
- SQL: parameterisierte Queries via SQLAlchemy ORM

---

## Abhängigkeiten

- `apscheduler>=3.10` (pyproject.toml dependencies)
- httpx (bereits vorhanden)
- Alembic Migration 0016 (Decision Audit) muss zuerst laufen
