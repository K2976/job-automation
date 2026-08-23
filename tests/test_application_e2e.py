"""Full V1→V2→V3 integration through the REAL worker: discover → prepare a real reportlab
résumé → queue.execute opens its own Chromium, uploads the PDF, submits → CONFIRMED and the
opportunity flips to APPLIED. Kept in its own module (no held Playwright session) because the
worker opens a sync_playwright() itself, which can't nest inside another in the same thread.
Skipped if Chromium can't launch."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("playwright")

SITE = Path(__file__).parent / "fixtures" / "app_site"


@pytest.fixture(scope="module", autouse=True)
def _require_chromium():
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:      # launch + close fully — leave nothing held
            p.chromium.launch(headless=True).close()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Chromium not launchable here: {e}")


def test_full_stack_real_worker(candidate_id):
    from app import db
    from app.applications import queue
    from app.models import ApprovalMode, ApplicationStatus, OpportunityStatus, SearchPreferences
    from app.opportunities import batches, discovery, packages

    run = discovery.execute_run(discovery.start_run(candidate_id, SearchPreferences(
        target_roles=["Engineer"], experience_level="internship", sources=["fixtures"])))
    oid = run.opportunity_ids[0]
    b = batches.create_batch(candidate_id, "E2E", 1)
    batches.set_selection(b.id, [oid])
    packages.prepare_batch(b.id)                       # real tailored résumé on the job

    opp = db.get_opportunity(oid)
    opp.application_url = (SITE / "basic.html").as_uri()
    db.save_opportunity(opp)

    queue.create_tasks_for_batch(b.id)
    task = db.list_tasks(batch_id=b.id)[0]
    task.approval_mode = ApprovalMode.AUTONOMOUS
    db.save_task(task)

    result = queue.execute(task.id, submit=True)       # real Chromium + real résumé PDF upload
    assert result.status == ApplicationStatus.CONFIRMED
    assert any(e.event == "FILE_UPLOADED" for e in result.logs)
    assert db.get_opportunity(oid).status == OpportunityStatus.APPLIED
