"""Point the backend at a throwaway SQLite file before any test module
imports ``backend.main`` (which builds the engine once at module load, from
``DATABASE_URL``). pytest imports conftest.py before collecting test modules
in this directory, so this always wins over the real ``powertool.db``.
"""

import os
import tempfile

_tmp_dir = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_dir.name}/test.db"
