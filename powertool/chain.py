"""The electrical chain: the ordered path from the Point of Connection to the inverter.

The chain is a plain data structure (a list of elements). It carries no solver logic
itself — the solver in :mod:`powertool.sizing` walks it. This separation is what will
later let a visual block-diagram editor produce the *same* Chain object the solver
already consumes.

Ordering convention: ``elements[0]`` is the element adjacent to the Point of Connection
(POC); the last element is adjacent to the inverter. The solver walks POC -> inverter.

Voltage convention: each element carries the *nominal* line-to-line voltage of the
section it sits in (e.g. 132 kV on the HV side, 20 kV on the MV side). Losses are
computed at this nominal voltage — a standard simplification for sizing studies that
avoids tracking the few-percent voltage drop and transformer turns ratios. This is an
explicit assumption; full voltage-drop tracking is a future refinement.
"""

from __future__ import annotations

from dataclasses import dataclass

from .cable_sizing import AutoCable
from .components import AuxLoad, Cable, Transformer, TransformerGroup

Component = Cable | Transformer | AuxLoad | AutoCable | TransformerGroup


@dataclass
class ChainElement:
    """One element in the electrical chain, with its placement parameters."""

    component: Component
    v_kv: float  # nominal line-to-line voltage of this element's section
    length_km: float | None = None  # required for fixed cables; None on an
    # AutoCable means "worst case": the section is assumed to consume its full
    # admissible loss budget and the implied length is derived from it.
    n_parallel: int = 1  # number of parallel circuits/units sharing the load
    label: str | None = None  # optional human-readable name for outputs

    def __post_init__(self) -> None:
        if self.v_kv <= 0:
            raise ValueError(f"{self.name}: section voltage must be positive, got {self.v_kv} kV")
        if self.n_parallel < 1:
            raise ValueError(f"{self.name}: n_parallel must be >= 1, got {self.n_parallel}")
        if isinstance(self.component, Cable) and self.length_km is None:
            raise ValueError(f"{self.name}: a cable element requires length_km")
        if self.length_km is not None and self.length_km <= 0:
            raise ValueError(f"{self.name}: length_km must be positive, got {self.length_km}")
        if isinstance(self.component, TransformerGroup) and self.n_parallel != 1:
            raise ValueError(
                f"{self.name}: a TransformerGroup carries its unit counts internally — "
                f"set n_parallel = 1 (got {self.n_parallel})"
            )

    @property
    def name(self) -> str:
        """Display name: the explicit label if given, else the component's name."""
        return self.label or self.component.name


@dataclass
class Chain:
    """An ordered electrical path from the POC (first element) to the inverter (last)."""

    elements: list[ChainElement]
    name: str = "chain"

    def __post_init__(self) -> None:
        if not self.elements:
            raise ValueError("A Chain must contain at least one element")

    @property
    def poc_v_kv(self) -> float:
        """Nominal voltage at the Point of Connection (the first element's section)."""
        return self.elements[0].v_kv

    def __iter__(self):
        return iter(self.elements)

    def __len__(self) -> int:
        return len(self.elements)
