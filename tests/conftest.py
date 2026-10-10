import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("XDG_RUNTIME_DIR", "/tmp")
# keep tests away from the real user config
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="snipshot-test-")

from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _clean_toplevel(qapp):
    """Destroy leftover top-level widgets between tests.

    QTest.mouseMove delivers to whichever *window* covers the point —
    a stale overlay from a previous test would silently swallow moves.
    """
    yield
    for w in QApplication.topLevelWidgets():
        if w.isWindow():
            w.close()
    qapp.sendPostedEvents()
    qapp.processEvents()
