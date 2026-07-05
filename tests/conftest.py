from __future__ import annotations

import pytest

from dashbot.db.session import Database


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    return Database(f"sqlite:///{db_path}")
