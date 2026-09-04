"""Puts the repo root on ``sys.path`` so ``pytest`` finds ``powertool`` and ``backend``.

This file exists only for its location. pytest prepends the directory holding
the topmost conftest.py to ``sys.path``; without one here, the root is never
added and every test module fails to import at collection time. There is no
packaging config in this project (no pyproject.toml, no setup.cfg, nothing
installed into the venv), so this is what makes a bare ``pytest`` work from the
repo root. ``python -m pytest`` worked already, because that form adds the
current directory itself.

Do not delete: it holds no code, but removing it breaks collection entirely.
"""
