#!/usr/bin/env python
"""Standalone AI-evaluation runner. Runs all evaluation JDs through the full pipeline for
one provider and writes a JSON artifact.

    python tests/evaluation/run_eval.py --provider mock
    python tests/evaluation/run_eval.py --provider groq
    python tests/evaluation/run_eval.py --provider gemini

Provider/keys come from .env (never printed). Each JD runs in its OWN throwaway SQLite DB
seeded fresh from the master fixture, so accept/edit test modifications never contaminate
the real profile and runs are repeatable (§29). Retrieval uses the local embedder for
determinism regardless of provider.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(HERE))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="mock", choices=["mock", "gemini", "groq"])
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    from app.config import settings
    from app import db
    from app.providers.llm import get_llm_provider, LLMError

    from eval_lib import evaluate_jd
    from labels import LABELS

    try:
        llm = get_llm_provider(args.provider)
    except LLMError as e:
        print(f"provider init failed: {e}", file=sys.stderr)
        return 2
    model = getattr(llm, "model", args.provider)

    results = []
    for key, label in LABELS.items():
        # fresh DB + candidate per JD → isolation + repeatability
        settings.database_url = tempfile.mktemp(suffix=".sqlite3")
        db.init_db()
        from app import pipeline
        candidate_id = pipeline.seed_from_fixture()
        t0 = time.perf_counter()
        try:
            r = evaluate_jd(candidate_id, key, label, llm)
            r["ok"] = True
        except Exception as e:  # never abort the whole run on one provider hiccup
            r = {"key": key, "ok": False, "error": f"{type(e).__name__}: {e}"}
        r.setdefault("latency", {})["wall_ms"] = round((time.perf_counter() - t0) * 1000)
        results.append(r)
        _print_row(r)

    report = {
        "provider": args.provider, "model": model,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {"embeddings": "local", "retrieval_top_k": settings.retrieval_top_k},
        "results": results, "summary": _summarize(results),
    }
    out = Path(args.out) if args.out else ROOT / "docs" / "eval-runs" / f"{args.provider}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nwrote {out}")
    print(json.dumps(report["summary"], indent=2))
    return 0


def _print_row(r: dict) -> None:
    if not r.get("ok"):
        print(f"  {r['key']:26} FAILED  {r.get('error','')[:80]}")
        return
    m = r["matching"]
    print(f"  {r['key']:26} role={r['role_ok']!s:5} "
          f"strong_ok={m['strong_ok']!s:5} missing_ok={m['missing_ok']!s:5} "
          f"jd_recall={r['jd_extraction']['recall']:.2f} "
          f"unsupp={r['validation']['unsupported']} "
          f"ats Δ{r['ats']['delta']:+.2f} {r['latency'].get('total_ms','?')}ms")


def _summarize(results: list[dict]) -> dict:
    ok = [r for r in results if r.get("ok")]
    if not ok:
        return {"runs": len(results), "ok": 0}
    def avg(f):
        return round(sum(f(r) for r in ok) / len(ok), 3)
    return {
        "runs": len(results), "ok": len(ok),
        "role_ok_all": all(r["role_ok"] for r in ok),
        "strong_ok_all": all(r["matching"]["strong_ok"] for r in ok),
        "missing_ok_all": all(r["matching"]["missing_ok"] for r in ok),
        "no_false_positives": all(not r["false_positives"] for r in ok),
        "hitl_ok_all": all(all(v["ok"] for v in r["human_in_the_loop"].values())
                           for r in ok),
        "anti_hallucination_clean":
            all(not r["anti_hallucination"]["claimed_forbidden"] for r in ok),
        "avg_jd_recall": avg(lambda r: r["jd_extraction"]["recall"]),
        "avg_ats_delta": avg(lambda r: r["ats"]["delta"]),
        "total_unsupported_claims": sum(r["validation"]["unsupported"] for r in ok),
        "avg_total_ms": avg(lambda r: r["latency"].get("total_ms", 0)),
    }


if __name__ == "__main__":
    raise SystemExit(main())
