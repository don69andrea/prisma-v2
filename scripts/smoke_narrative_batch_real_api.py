"""Smoke-Test: Multi-Memo Batch gegen echte Anthropic-API.

Verifiziert Acceptance §10:
- POST /batch top_n=3 (kleiner Batch zur Cost-Kontrolle, ~$0.10)
- Polling bis complete
- 3 Memos in DB mit Tickers in Response

Vorbedingung:
- docker-compose up (PG + Backend)
- Stocks + Run mit min. 3 Stocks geseeded (z.B. via scripts/seed_demo_universe.py)
- ANTHROPIC_API_KEY in .env

Ausfuehrung:
    source .venv/bin/activate
    python scripts/smoke_narrative_batch_real_api.py <model_run_id>
"""

from __future__ import annotations

import asyncio
import sys
import time

import httpx


async def main(run_id: str) -> None:
    base_url = "http://localhost:8000/api/v1"
    async with httpx.AsyncClient(timeout=30.0) as client:
        # POST /batch
        print(f"POST /memos/batch run_id={run_id} top_n=3 ...")
        resp = await client.post(
            f"{base_url}/memos/batch",
            json={"model_run_id": run_id, "top_n": 3, "language": "de"},
        )
        resp.raise_for_status()
        job = resp.json()
        job_id = job["job_id"]
        print(f"  Job created: {job_id} (status={job['status']})")

        # Polling
        print("\nPolling /jobs/{job_id} every 2s ...")
        start = time.perf_counter()
        body: dict[str, object] | None = None
        for _ in range(60):
            await asyncio.sleep(2)
            poll = await client.get(f"{base_url}/memos/jobs/{job_id}")
            poll.raise_for_status()
            body = poll.json()
            elapsed = time.perf_counter() - start
            progress = body["progress"]  # type: ignore[index]
            print(
                f"  [{elapsed:5.1f}s] status={body['status']:9s}  "
                f"progress={progress['completed']}/{progress['expected']} "
                f"failed={progress['failed']}"
            )
            if body["status"] in ("complete", "partial", "failed"):
                break
        else:
            print("\nFAIL: Job did not finish in 120s")
            sys.exit(1)

        # Final report
        assert body is not None
        print(f"\n{'=' * 64}")
        print(f"VERDICT: status={body['status']}")
        print(f"{'=' * 64}")
        memos = body["memos"]  # type: ignore[index]
        print(f"\nMemos generated: {len(memos)}")
        for m in memos:  # type: ignore[union-attr]
            print(f"  - {m['ticker']:6s}: {m['one_liner']}")
        if body.get("failed_stock_ids"):
            print(f"\nFailed stocks: {body['failed_stock_ids']}")
        if body.get("error_message"):
            print(f"\nError: {body['error_message']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/smoke_narrative_batch_real_api.py <model_run_id>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
