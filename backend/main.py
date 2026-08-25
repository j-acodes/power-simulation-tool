"""FastAPI app: sizing API, wrapping the unchanged ``powertool`` engine.

M0/M1 scope: catalogue, Stage-1 solve and the diagram solve, plus serving the
built frontend (``frontend/dist``) when it exists. No DB, no auth yet.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Body, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from powertool import ComponentDatabase, size_pv_inverters

from .schemas import (
    CableInfo,
    CatalogueDefaults,
    CatalogueResponse,
    LossItem,
    RulesDefaults,
    SolveResponse,
    Stage1Request,
    Stage1Response,
    TiersDefaults,
    TransformerInfo,
)
from .solve import (
    COLLECTION_LOSS_PCT,
    EXPORT_LOSS_PCT_PER_KM,
    MAX_UTILIZATION,
    build_chain,
    solve_diagram,
)

# Stage-2 planning constant mirrored from app/streamlit_app.py — used only for
# the catalogue's default-rules payload in M0 (no /solve endpoint yet).
MAX_CIRCUIT_CURRENT_A = 400.0

db = ComponentDatabase.load()

app = FastAPI(title="PV Plant Sizing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/catalogue", response_model=CatalogueResponse)
def get_catalogue() -> CatalogueResponse:
    transformers = [
        TransformerInfo(
            key=key,
            display_name=tx.display_name,
            s_rated_kva=tx.s_rated_kva,
            hv_kv=tx.hv_kv,
            lv_kv=tx.lv_kv,
            brand=tx.brand,
            uk_percent=tx.uk_percent,
            pk_kw=tx.pk_kw,
            p0_kw=tx.p0_kw,
            i0_percent=tx.i0_percent,
        )
        for key, tx in db.transformers.items()
    ]

    cables: dict[str, list[CableInfo]] = {}
    for cable in sorted(
        db.cables.values(),
        key=lambda c: (c.rated_voltage_kv is None, c.rated_voltage_kv or 0.0, c.cross_section_mm2 or 0.0),
    ):
        if cable.rated_voltage_kv is None:
            continue
        group = f"{cable.rated_voltage_kv:g}"
        cables.setdefault(group, []).append(
            CableInfo(
                name=cable.name,
                cross_section_mm2=cable.cross_section_mm2,
                rated_current_a=cable.rated_current_a,
            )
        )

    defaults = CatalogueDefaults(
        tiers=TiersDefaults(lv_kv=0.8, mv_kv=20.0, hv_kv=132.0),
        rules=RulesDefaults(
            max_utilization=MAX_UTILIZATION,
            collection_loss_pct=COLLECTION_LOSS_PCT,
            export_loss_pct_per_km=EXPORT_LOSS_PCT_PER_KM,
            max_circuit_current_a=MAX_CIRCUIT_CURRENT_A,
        ),
    )

    return CatalogueResponse(transformers=transformers, cables=cables, defaults=defaults)


@app.post("/api/stage1", response_model=Stage1Response)
def post_stage1(req: Stage1Request) -> Stage1Response:
    elements = [el.model_dump() for el in req.elements]
    chain = build_chain(
        elements,
        db,
        interconnection=req.interconnection,
        v_export_kv=req.v_export_kv,
        export_m=req.export_m,
        p_poc_kw=req.p_poc_kw,
        pf_target=req.pf_target,
    )
    result = size_pv_inverters(chain, p_poc_kw=req.p_poc_kw, pf_target=req.pf_target)

    return Stage1Response(
        p_inv_kw=result.p_inv_kw,
        q_inv_kvar=result.q_inv_kvar,
        s_inv_kva=result.s_inv_kva,
        pf_inv=result.pf_inv,
        losses=[LossItem(label=e.name, dp_kw=e.dp_kw, dq_kvar=e.dq_kvar) for e in result.losses],
        power_balance_ok=result.power_balance_ok,
    )


@app.post("/api/solve", response_model=SolveResponse)
def post_solve(diagram: dict = Body(...)) -> SolveResponse:
    """Solve a drawn diagram — the request body IS the diagram payload.

    Serves both the live validation and the debounced auto-solve of the editor,
    so it always answers 200: a drawing that cannot be solved comes back as
    ``issues`` keyed to the offending nodes/edges. The diagram is taken as a
    plain dict on purpose — its schema is validated by ``powertool.graph``,
    which reports problems as issues instead of raising 422s at the user.
    """
    return SolveResponse(**solve_diagram(diagram, db))


# Serve the built frontend, if present. Mounted last so /api routes above take
# precedence; guarded so the API still works before the first `npm run build`.
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
