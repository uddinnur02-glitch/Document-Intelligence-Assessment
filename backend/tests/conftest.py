import os
import tempfile
from pathlib import Path

# Set before importing app/database modules.
TEST_DIR = tempfile.TemporaryDirectory()
os.environ['DATABASE_URL'] = f"sqlite:///{(Path(TEST_DIR.name) / 'test.db').as_posix()}"
os.environ['UPLOAD_DIR'] = str(Path(TEST_DIR.name) / 'uploads')

import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
