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
from .components import (
    AuxLoad,
    BessSolution,
    BUSBAR_SWITCHGEAR_LADDER_A,
    Cable,
    PvInverter,
    PvInverterPairing,
    Transformer,
    TransformerGroup,
    current_a,
    size_busbar_switchgear_rating,
)
from .database import CatalogueDataWarning, ComponentDatabase
from .pdf_report import build_pdf_report
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
    "PvInverter",
    "PvInverterPairing",
    "current_a",
    "BUSBAR_SWITCHGEAR_LADDER_A",
    "size_busbar_switchgear_rating",
    "ComponentDatabase",
    "CatalogueDataWarning",
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
    "build_pdf_report",
]
