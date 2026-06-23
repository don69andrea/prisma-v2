---
phase: 4
slug: v4-4-rag-sentiment-planned
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-22
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.1+ with pytest-asyncio |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest backend/tests/unit/application/test_analyst_agents.py -q` |
| **Full suite command** | `pytest backend/tests/ -q --cov=backend --cov-fail-under=80` |
| **Estimated runtime** | ~60 seconds (unit), ~180 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `pytest backend/tests/unit/ -q`
- **After every plan wave:** Run `pytest backend/tests/ -q --cov=backend --cov-fail-under=80`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds (unit), 180 seconds (full)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 4-01 | W0 | 0 | REQ-4-03 | — | N/A | unit | `pytest backend/tests/unit/domain/entities/test_news_article.py -x` | ❌ W0 | ⬜ pending |
| 4-02 | W0 | 0 | REQ-4-04 | — | N/A | unit | `pytest backend/tests/unit/domain/entities/test_news_retrieval_result.py -x` | ❌ W0 | ⬜ pending |
| 4-03 | W0 | 0 | REQ-4-09 | — | N/A | unit | `pytest backend/tests/unit/test_settings.py -x` | ❌ W0 | ⬜ pending |
| 4-04 | W0 | 0 | REQ-4-06 | — | Pydantic rejects non-bool news_surprise | unit | `pytest backend/tests/unit/domain/schemas/test_agent_schemas.py -x` | ❌ W0 | ⬜ pending |
| 4-05 | W0 | 0 | REQ-4-07 | — | N/A | unit | `pytest backend/tests/unit/application/test_sentiment_score_formula.py -x` | ❌ W0 | ⬜ pending |
| 4-06 | W1 | 1 | REQ-4-01 | T-4-02 | Adapter returns [] on malformed JSON | unit | `pytest backend/tests/unit/infrastructure/test_cryptopanic_adapter.py -x` | ❌ W0 | ⬜ pending |
| 4-07 | W1 | 1 | REQ-4-02 | — | N/A | unit | `pytest backend/tests/unit/application/test_news_ingestion_cryptopanic.py -x` | ❌ W0 | ⬜ pending |
| 4-08 | W2 | 2 | REQ-4-05 | T-4-01, T-4-03 | LLM output Pydantic-validated; score deterministic | unit | `pytest backend/tests/unit/application/test_analyst_agents.py::TestSentimentAnalystAgent -x` | ✅ (replace) | ⬜ pending |
| 4-09 | W2 | 2 | REQ-4-08 | T-4-04 | veto→HOLD; positive score does not amplify size | unit | `pytest backend/tests/integration/test_agent_mandatory_suite.py -x` | ✅ (extend) | ⬜ pending |
| 4-10 | W3 | 3 | REQ-4-10 | — | N/A | integration | `pytest backend/tests/integration/test_backtest_sentiment_comparison.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/unit/infrastructure/test_cryptopanic_adapter.py` — stubs for REQ-4-01
- [ ] `backend/tests/unit/application/test_news_ingestion_cryptopanic.py` — stubs for REQ-4-02
- [ ] `backend/tests/unit/domain/entities/test_news_article.py` — modify existing, add CRYPTOPANIC source test (REQ-4-03)
- [ ] `backend/tests/unit/domain/entities/test_news_retrieval_result.py` — stubs for REQ-4-04 (url field)
- [ ] `backend/tests/unit/domain/schemas/test_agent_schemas.py` — stubs for REQ-4-06 (SentimentLLMOutput)
- [ ] `backend/tests/unit/application/test_sentiment_score_formula.py` — stubs for REQ-4-07 (8 boundary values)
- [ ] `backend/tests/unit/test_settings.py` — extend or create for REQ-4-09 (sentiment_enabled env var)
- [ ] `backend/tests/integration/test_backtest_sentiment_comparison.py` — stubs for REQ-4-10

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CryptoPanic free API connectivity (`auth_token=free`) | REQ-4-01 | External service; CI has no network access | Run `python -c "import httpx; r=httpx.get('https://cryptopanic.com/api/v1/posts/?auth_token=free&currencies=BTC&kind=news'); print(r.status_code, r.json()['results'][0]['title'])"` |
| Walk-forward backtest honest comparison (ENABLED vs DISABLED) | REQ-4-10 | Requires live DB with backtest data | Run `SENTIMENT_ENABLED=false python scripts/compare_sentiment_backtest.py; SENTIMENT_ENABLED=true python scripts/compare_sentiment_backtest.py` — verify results written to `docs/PRISMA_V4_FORTSCHRITT.md` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s (unit), < 180s (full)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
