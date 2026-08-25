"""Pydantic request/response models for the Stage-1 API.

Element shapes mirror ``st.session_state.elements`` in the frozen Streamlit
UI (see ``app/streamlit_app.py``): a discriminated union on ``type``.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class TransformerElement(BaseModel):
    type: Literal["Transformer"]
    component: str  # ComponentDatabase.transformers key
    v_kv: float
    n_parallel: int = 1
    label: str | None = None


class CableSectionElement(BaseModel):
    type: Literal["Cable section"]
    v_kv: float
    label: str | None = None


class AuxLoadElement(BaseModel):
    type: Literal["Aux load"]
    v_kv: float
    p_kw: float
    q_kvar: float = 0.0
    label: str | None = None


Element = Annotated[
    Union[TransformerElement, CableSectionElement, AuxLoadElement],
    Field(discriminator="type"),
]


class Stage1Request(BaseModel):
    p_poc_kw: float
    pf_target: float
    interconnection: Literal["HV", "MV"]
    v_export_kv: float
    export_m: float = 0.0
    elements: list[Element]


class LossItem(BaseModel):
    label: str
    dp_kw: float
    dq_kvar: float


class Stage1Response(BaseModel):
    p_inv_kw: float
    q_inv_kvar: float
    s_inv_kva: float
    pf_inv: float
    losses: list[LossItem]
    power_balance_ok: bool


class IssueItem(BaseModel):
    """One validation problem or result warning, pointing at the canvas element
    that carries it (see powertool.graph.GraphIssue)."""

    code: str
    message: str
    node_id: str | None = None
    edge_id: str | None = None


class SolveResponse(BaseModel):
    """``issues`` non-empty means nothing was solved (``results`` is null).

    An invalid drawing is an ANSWER, not a failure: /api/solve always returns
    200 so the live editor can render the issues on the canvas.
    """

    issues: list[IssueItem]
    results: dict | None = None


class TransformerInfo(BaseModel):
    key: str
    display_name: str
    s_rated_kva: float
    hv_kv: float | None
    lv_kv: float | None
    brand: str | None


class CableInfo(BaseModel):
    name: str
    cross_section_mm2: float | None
    rated_current_a: float | None


class TiersDefaults(BaseModel):
    lv_kv: float
    mv_kv: float
    hv_kv: float


class RulesDefaults(BaseModel):
    max_utilization: float
    collection_loss_pct: float
    export_loss_pct_per_km: float
    max_circuit_current_a: float


class CatalogueDefaults(BaseModel):
    tiers: TiersDefaults
    rules: RulesDefaults


class CatalogueResponse(BaseModel):
    transformers: list[TransformerInfo]
    cables: dict[str, list[CableInfo]]
    defaults: CatalogueDefaults
