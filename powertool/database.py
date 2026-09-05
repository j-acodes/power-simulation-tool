"""Load component parameters from the YAML files in ``data/`` into component objects.

This is the only place that touches the YAML files, keeping the data model (the
dataclasses in :mod:`powertool.components`) separate from how it is stored on disk.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .components import BessSolution, Cable, Transformer

# data/ lives next to the powertool/ package, one level up from this file.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_cables(path: str | Path | None = None) -> dict[str, Cable]:
    """Load cable types from a YAML file, keyed by name."""
    path = Path(path) if path else DATA_DIR / "cables.yaml"
    raw = yaml.safe_load(path.read_text()) or {}
    return {name: Cable(name=name, **params) for name, params in (raw.get("cables") or {}).items()}


def load_transformers(path: str | Path | None = None) -> dict[str, Transformer]:
    """Load transformer types from a YAML file, keyed by name."""
    path = Path(path) if path else DATA_DIR / "transformers.yaml"
    raw = yaml.safe_load(path.read_text()) or {}
    return {
        name: Transformer(name=name, **params)
        for name, params in (raw.get("transformers") or {}).items()
    }


def load_bess_solutions(path: str | Path | None = None) -> dict[str, BessSolution]:
    """Load BESS supplier solutions from a YAML file, keyed by name."""
    path = Path(path) if path else DATA_DIR / "bess.yaml"
    raw = yaml.safe_load(path.read_text()) or {}
    return {
        name: BessSolution(name=name, **params)
        for name, params in (raw.get("bess_solutions") or {}).items()
    }


def load_bess_transformers(
    path: str | Path | None = None,
) -> tuple[dict[str, Transformer], dict[str, dict[str, int]]]:
    """Load BESS station transformer types from a YAML file, keyed by name.

    A separate catalogue from :func:`load_transformers` (the PV string-inverter
    stations) — deliberately not a category field on the same one.

    Each entry may nest a ``paired_solutions`` mapping (BESS solution key ->
    containers per station) — the solutions this station transformer is sold
    with. It is popped out of the params before building the ``Transformer``
    (which stays BESS-agnostic, shared with the PV catalogue) and returned
    separately, keyed by the same station transformer name, for
    ``ComponentDatabase.bess_pairings``.
    """
    path = Path(path) if path else DATA_DIR / "bess_transformers.yaml"
    raw = yaml.safe_load(path.read_text()) or {}
    transformers: dict[str, Transformer] = {}
    pairings: dict[str, dict[str, int]] = {}
    for name, params in (raw.get("bess_transformers") or {}).items():
        params = dict(params)
        pairings[name] = dict(params.pop("paired_solutions", None) or {})
        transformers[name] = Transformer(name=name, **params)
    return transformers, pairings


class ComponentDatabase:
    """In-memory catalogue of component types loaded from the YAML files."""

    def __init__(
        self,
        cables: dict[str, Cable] | None = None,
        transformers: dict[str, Transformer] | None = None,
        bess_solutions: dict[str, BessSolution] | None = None,
        bess_transformers: dict[str, Transformer] | None = None,
        bess_pairings: dict[str, dict[str, int]] | None = None,
    ) -> None:
        self.cables = cables or {}
        self.transformers = transformers or {}
        self.bess_solutions = bess_solutions or {}
        self.bess_transformers = bess_transformers or {}
        # Station-transformer key -> solution key -> containers per station.
        # The solutions each BESS station transformer is sold with (see
        # data/bess_transformers.yaml's ``paired_solutions``).
        self.bess_pairings = bess_pairings or {}

    @classmethod
    def load(cls, data_dir: str | Path | None = None) -> "ComponentDatabase":
        """Load the full catalogue from a data directory (defaults to ``data/``)."""
        if data_dir is None:
            bess_transformers, bess_pairings = load_bess_transformers()
            return cls(load_cables(), load_transformers(), load_bess_solutions(),
                       bess_transformers, bess_pairings)
        data_dir = Path(data_dir)
        bess_transformers, bess_pairings = load_bess_transformers(
            data_dir / "bess_transformers.yaml")
        return cls(
            load_cables(data_dir / "cables.yaml"),
            load_transformers(data_dir / "transformers.yaml"),
            load_bess_solutions(data_dir / "bess.yaml"),
            bess_transformers,
            bess_pairings,
        )

    def cable(self, name: str) -> Cable:
        try:
            return self.cables[name]
        except KeyError:
            raise KeyError(
                f"Cable '{name}' not found in database. Available: {sorted(self.cables)}"
            ) from None

    def transformer(self, name: str) -> Transformer:
        try:
            return self.transformers[name]
        except KeyError:
            raise KeyError(
                f"Transformer '{name}' not found in database. Available: {sorted(self.transformers)}"
            ) from None

    def bess_solution(self, name: str) -> BessSolution:
        try:
            return self.bess_solutions[name]
        except KeyError:
            raise KeyError(
                f"BESS solution '{name}' not found in database. "
                f"Available: {sorted(self.bess_solutions)}"
            ) from None

    def bess_transformer(self, name: str) -> Transformer:
        try:
            return self.bess_transformers[name]
        except KeyError:
            raise KeyError(
                f"BESS transformer '{name}' not found in database. "
                f"Available: {sorted(self.bess_transformers)}"
            ) from None

    def cables_for_voltage(self, v_kv: float) -> list[Cable]:
        """Candidate cables for a section at ``v_kv``, sorted by cross-section.

        Returns cables of the *lowest voltage class that still covers* the section
        voltage (e.g. a 20 kV section gets 20 kV cables, not 35 kV ones that merely
        qualify), with the data needed for auto-selection (ampacity + cross-section).
        """
        usable = [
            c for c in self.cables.values()
            if c.rated_voltage_kv is not None
            and c.rated_current_a is not None
            and c.cross_section_mm2 is not None
        ]
        suitable = [c for c in usable if c.rated_voltage_kv >= v_kv - 1e-9]
        if not suitable:
            return []
        target_class = min(c.rated_voltage_kv for c in suitable)
        return sorted(
            (c for c in suitable if abs(c.rated_voltage_kv - target_class) < 1e-9),
            key=lambda c: c.cross_section_mm2,
        )
