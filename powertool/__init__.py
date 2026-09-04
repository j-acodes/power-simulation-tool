"""powertool — UI-agnostic engine for PV/BESS sizing and efficiency calculations.

Milestone 1: PV inverter sizing via a backward loss-cascade along a radial chain.
The engine intentionally has no interface code so it can run from a script today
and behind a web app later.
"""

from .architecture import (
    CircuitResult,
    ExportResult,
    PlantArchitecture,
    PlantLayout,
    SegmentResult,
    StationPlan,
    StationResult,
    arrange_plant,
    arrange_plant_manual,
    assign_circuits,
    auto_hv_transformer,
    size_architecture,
    size_circuits,
)
from .cable_sizing import AutoCable, CableSelection, select_cable
from .chain import Chain, ChainElement
from .components import AuxLoad, BessSolution, Cable, Transformer, TransformerGroup, current_a
from .database import ComponentDatabase
from .diagram import architecture_to_dot
from .pdf_report import build_pdf_report
from .report import build_report
from .sizing import (
    ElementLoss,
    SizingResult,
    size_generation,
    size_generation_pq,
    size_pv_inverters,
)

__all__ = [
    "Cable",
    "Transformer",
    "AuxLoad",
    "BessSolution",
    "current_a",
    "ComponentDatabase",
    "Chain",
    "ChainElement",
    "AutoCable",
    "CableSelection",
    "select_cable",
    "size_generation",
    "size_generation_pq",
    "size_pv_inverters",
    "SizingResult",
    "ElementLoss",
    "TransformerGroup",
    "arrange_plant",
    "arrange_plant_manual",
    "assign_circuits",
    "auto_hv_transformer",
    "size_circuits",
    "size_architecture",
    "PlantLayout",
    "PlantArchitecture",
    "CircuitResult",
    "SegmentResult",
    "StationPlan",
    "StationResult",
    "ExportResult",
    "architecture_to_dot",
    "build_report",
    "build_pdf_report",
]
