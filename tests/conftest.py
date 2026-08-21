import tempfile
from pathlib import Path

import pytest

from app.config import settings
from app import db, pipeline


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path):
    """Every test gets a fresh SQLite file."""
    settings.database_url = str(tmp_path / "test.sqlite3")
    db.init_db()
    yield


@pytest.fixture
def candidate_id() -> int:
    return pipeline.seed_from_fixture()
