"""Generation sizing via a backward loss-cascade along a radial chain.

This is the core engine. Given the power we want to deliver at the Point of
Connection (POC) and a power-factor target, it walks the electrical chain
*backward* from the POC toward the conversion level, accumulating active and
reactive losses, to find the P / Q / S the inverters (PV) or PCS units (BESS)
must actually deliver.

Sign convention (see the team's worst-case sizing rationale):
    Q_poc > 0 means reactive power *injected* by the plant at the POC. This is
    the design worst case: it maximises the reactive the inverters must produce
    and therefore the inverter apparent power S_inv.

Assumptions: three-phase, balanced, positive-sequence, RMS, steady-state; losses
computed at each section's nominal line-to-line voltage (see powertool.chain).
"""

from __future__ import annotations

import dataclasses
import math
import warnings
from dataclasses import dataclass

from .cable_sizing import AutoCable, select_cable, select_cable_worst_case
from .chain import Chain, ChainElement
from .components import AuxLoad, Cable, Transformer, TransformerGroup

# Relative tolerance for the internal power-balance conservation check.
_BALANCE_RTOL = 1e-6

# Conductor material -> short symbol for the display label.
_MATERIAL_SYMBOL = {"aluminium": "Al", "aluminum": "Al", "copper": "Cu"}


def format_cable_label(cable: Cable, n_parallel: int) -> str:
    """Human-readable cable tag: ``Al_3x{circuits}x{section}_{voltage}kV``.

    The ``3`` denotes the three phases (always present in a three-phase circuit);
    ``n_parallel`` is the number of parallel circuits the sizer chose. Voltage
    class and section come from the cable type. Fields that are missing are
    rendered as ``?`` (voltage is omitted entirely when unknown).
    """
    material = (cable.material or "").lower()
    symbol = _MATERIAL_SYMBOL.get(material, (cable.material or "?").capitalize())
    section = f"{cable.cross_section_mm2:g}" if cable.cross_section_mm2 is not None else "?"
    label = f"{symbol}_3x{n_parallel}x{section}"
    if cable.rated_voltage_kv is not None:
        label += f"_{cable.rated_voltage_kv:g}kV"
    return label


@dataclass
class ElementLoss:
    """The loss contribution of one chain element, for the breakdown table."""

    name: str
    kind: str  # "Cable" | "Transformer" | "AuxLoad"
    s_through_kva: float  # apparent power flowing through it (POC-facing side)
    dp_kw: float  # active loss consumed
    dq_kvar: float  # series reactive consumed (>= 0); charging is NOT netted in (see solver)
    q_charging_kvar: float  # capacitive reactive generated (cables only) — informational
    n_parallel: int = 1  # circuits/units (auto-selected for AutoCable sections)
    selected_cable: str | None = None  # which cable was auto-picked (AutoCable only)
    cable_label: str | None = None  # display tag, e.g. "Al_3x2x500_30kV" (AutoCable only)
    utilization: float | None = None  # I_per_circuit / rated_current (AutoCable only)
    loss_percent: float | None = None  # active loss as % of local power (AutoCable only)
    vdrop_percent: float | None = None  # section voltage drop (AutoCable only)
    length_km: float | None = None  # given length, or the implied worst-case one


@dataclass
class SizingResult:
    """Result of a PV inverter-sizing run, with a per-element loss breakdown."""

    # Inputs echoed back
    p_poc_kw: float
    q_poc_kvar: float
    pf_target: float
    # Results at inverter level
    p_inv_kw: float
    q_inv_kvar: float
    s_inv_kva: float
    pf_inv: float
    # Breakdown
    losses: list[ElementLoss]
    power_balance_ok: bool

    @property
    def total_active_loss_kw(self) -> float:
        return sum(e.dp_kw for e in self.losses)

    @property
    def total_charging_kvar(self) -> float:
        return sum(e.q_charging_kvar for e in self.losses)

    @property
    def total_net_reactive_kvar(self) -> float:
        return sum(e.dq_kvar for e in self.losses)

    def report(self) -> str:
        """A human-readable summary table for scripts / the CLI."""
        lines = []
        lines.append("Generation sizing — backward loss cascade (POC -> inverter)")
        lines.append("=" * 64)
        lines.append(
            f"POC target:  P = {self.p_poc_kw:,.1f} kW   "
            f"Q = {self.q_poc_kvar:,.1f} kvar (injected)   PF = {self.pf_target:.3f}"
        )
        lines.append("")
        lines.append(
            f"{'Element':<22}{'Type':<13}{'S [kVA]':>12}{'dP [kW]':>11}{'dQ [kvar]':>12}"
        )
        lines.append("-" * 70)
        for e in self.losses:
            name = e.name
            if e.cable_label:
                name = f"{e.name} [{e.cable_label}]"
            lines.append(
                f"{name:<22}{e.kind:<13}{e.s_through_kva:>12,.1f}"
                f"{e.dp_kw:>11,.2f}{e.dq_kvar:>12,.2f}"
            )
        lines.append("-" * 70)
        lines.append(
            f"{'TOTAL losses':<35}{self.total_active_loss_kw:>10,.2f}"
            f"{self.total_net_reactive_kvar:>12,.2f}"
        )
        lines.append("")
        lines.append("Required at inverter level:")
        lines.append(
            f"  P_inv = {self.p_inv_kw:,.1f} kW    "
            f"Q_inv = {self.q_inv_kvar:,.1f} kvar    "
            f"S_inv = {self.s_inv_kva:,.1f} kVA    PF_inv = {self.pf_inv:.3f}"
        )
        lines.append("")
        lines.append(
            "Assumptions: 3-phase balanced, positive-sequence, RMS, steady-state; "
            "losses at nominal section voltage."
        )
        ok = "OK" if self.power_balance_ok else "FAILED"
        lines.append(f"Power-balance check (P_poc + losses == P_inv): {ok}")
        return "\n".join(lines)


def _cable_contribution(
    cable: Cable, v_kv: float, length_km: float, n: int, s_kva: float
) -> tuple[float, float, float]:
    """Cable losses with ``n`` parallel circuits sharing the load: series losses
    scale as 1/n, charging scales as n (n cables each charging)."""
    dp_full, dq_full = cable.series_losses(s_kva, v_kv, length_km)
    q_charging = cable.charging_kvar(v_kv, length_km) * n
    return dp_full / n, dq_full / n, q_charging


def _element_contribution(
    element: ChainElement, s_kva: float
) -> tuple[float, float, float]:
    """Return (dp_kw, dq_series_consumed_kvar, q_charging_kvar) for a non-auto element.

    Transformer: each of the n units carries S/n; computing the per-unit loss and
    multiplying by n correctly makes copper/reactive scale as 1/n while iron/
    magnetising scale as n.
    """
    comp = element.component
    n = element.n_parallel

    if isinstance(comp, Cable):
        return _cable_contribution(comp, element.v_kv, element.length_km, n, s_kva)

    if isinstance(comp, Transformer):
        dp_unit, dq_unit = comp.losses(s_kva / n, element.v_kv)
        return dp_unit * n, dq_unit * n, 0.0

    if isinstance(comp, TransformerGroup):
        # The group splits the load internally (equal per-unit loading across
        # its mixed units); n_parallel is validated to 1 by ChainElement.
        dp, dq = comp.losses(s_kva, element.v_kv)
        return dp, dq, 0.0

    if isinstance(comp, AuxLoad):
        return comp.p_kw, comp.q_kvar, 0.0

    raise TypeError(f"Unsupported component type in chain: {type(comp).__name__}")


def size_generation_pq(
    chain: Chain, p_head_kw: float, q_head_kvar: float
) -> SizingResult:
    """Size the generation for an active/reactive power pair at the head of the chain.

    This is the reactive-in sibling of :func:`size_generation`: it takes the
    active and reactive power already *assigned* at the head of the chain,
    rather than deriving the reactive figure from a power-factor target the
    chain owns. It exists for callers that split one point-of-connection
    reactive requirement across several chains, where each chain's reactive
    duty is assigned to it rather than expressed as its own power factor.

    Parameters
    ----------
    chain : Chain
        Electrical path, ordered from the head (first element) to inverter (last).
    p_head_kw : float
        Active power to deliver at the head of the chain [kW].
    q_head_kvar : float
        Reactive power to deliver at the head of the chain [kvar], *injected*
        (the worst case for inverter sizing).

    Returns
    -------
    SizingResult
        P / Q / S at inverter level plus a per-element loss breakdown.
    """
    if p_head_kw <= 0:
        raise ValueError(f"p_head_kw must be positive, got {p_head_kw}")

    # Walk the chain head -> inverter, accumulating losses into the running P, Q.
    p = p_head_kw
    q = q_head_kvar
    losses: list[ElementLoss] = []

    for element in chain:
        s_through = math.hypot(p, q)
        comp = element.component

        # Defaults for the breakdown record; overwritten for auto-sized cables.
        n_parallel = element.n_parallel
        selected_cable = None
        cable_label = None
        utilization = None
        loss_percent = None
        vdrop_percent = None

        if isinstance(comp, AutoCable):
            # Local power factor at this point drives the loss budget and voltage drop.
            cos_phi = p / s_through if s_through > 0 else 1.0
            sin_phi = q / s_through if s_through > 0 else 0.0
            if element.length_km is None:
                # Worst case (conceptual stage, length unknown): the section is
                # assumed to consume its FULL admissible base budget; the
                # implied length is reported back for transparency.
                sel, length_km = select_cable_worst_case(
                    comp.candidates,
                    s_through,
                    element.v_kv,
                    cos_phi,
                    sin_phi,
                    max_utilization=comp.max_utilization,
                    loss_percent=comp.max_loss_percent_base,
                    max_parallel=comp.max_parallel,
                )
                kind = "Cable (worst case)"
            else:
                length_km = element.length_km
                sel = select_cable(
                    comp.candidates,
                    s_through,
                    element.v_kv,
                    length_km,
                    cos_phi,
                    sin_phi,
                    max_utilization=comp.max_utilization,
                    max_loss_percent=comp.admissible_loss_percent(length_km),
                    max_vdrop_percent=comp.max_vdrop_percent,
                    max_parallel=comp.max_parallel,
                )
                kind = "Cable (auto)"
            n_parallel = sel.n_parallel
            selected_cable = sel.cable.name
            cable_label = format_cable_label(sel.cable, sel.n_parallel)
            utilization = sel.utilization
            loss_percent = sel.loss_percent
            vdrop_percent = sel.vdrop_percent
            element_length_km = length_km
            dp, dq_series, q_charging = _cable_contribution(
                sel.cable, element.v_kv, length_km, sel.n_parallel, s_through
            )
        else:
            dp, dq_series, q_charging = _element_contribution(element, s_through)
            kind = type(comp).__name__
            element_length_km = element.length_km

        if not math.isfinite(dp) or not math.isfinite(dq_series):
            raise ArithmeticError(
                f"Non-finite loss computed at element '{element.name}' — check inputs."
            )

        # Reactive sign convention (worst-case sizing): the plant ALWAYS injects
        # reactive, so every element's reactive contribution is the series loss only,
        # kept >= 0. Cable charging is recorded for information but is NEVER netted in
        # here — allowing it to reduce the reactive would optimistically under-size the
        # inverters. (Charging matters for the separate low-load/absorbing study.)
        net_dq = dq_series
        losses.append(
            ElementLoss(
                name=element.name,
                kind=kind,
                s_through_kva=s_through,
                dp_kw=dp,
                dq_kvar=net_dq,
                q_charging_kvar=q_charging,
                n_parallel=n_parallel,
                selected_cable=selected_cable,
                cable_label=cable_label,
                utilization=utilization,
                loss_percent=loss_percent,
                vdrop_percent=vdrop_percent,
                length_km=element_length_km,
            )
        )
        p += dp
        q += net_dq

    s_inv = math.hypot(p, q)
    pf_inv = p / s_inv if s_inv > 0 else 1.0

    # Conservation check: P at inverter must equal head power plus all active losses.
    expected_p = p_head_kw + sum(e.dp_kw for e in losses)
    power_balance_ok = math.isclose(p, expected_p, rel_tol=_BALANCE_RTOL)

    # Effective power factor at the head, for display/echo purposes only —
    # this form takes P and Q directly rather than a power-factor target.
    s_head = math.hypot(p_head_kw, q_head_kvar)
    pf_head = p_head_kw / s_head if s_head > 0 else 1.0

    return SizingResult(
        p_poc_kw=p_head_kw,
        q_poc_kvar=q_head_kvar,
        pf_target=pf_head,
        p_inv_kw=p,
        q_inv_kvar=q,
        s_inv_kva=s_inv,
        pf_inv=pf_inv,
        losses=losses,
        power_balance_ok=power_balance_ok,
    )


def size_generation(
    chain: Chain, p_poc_kw: float, pf_target: float = 1.0
) -> SizingResult:
    """Size the generation for a target POC power and power factor.

    Computes the reactive power implied by ``pf_target`` and delegates to
    :func:`size_generation_pq`.

    Parameters
    ----------
    chain : Chain
        Electrical path, ordered from POC (first element) to inverter (last).
    p_poc_kw : float
        Active power to deliver at the Point of Connection [kW].
    pf_target : float
        Power-factor target at the POC (0 < pf <= 1). Reactive power is taken as
        *injected* at the POC (the worst case for inverter sizing).

    Returns
    -------
    SizingResult
        P / Q / S at inverter level plus a per-element loss breakdown.
    """
    if not 0.0 < pf_target <= 1.0:
        raise ValueError(f"pf_target must be in (0, 1], got {pf_target}")
    # Checked here as well as in size_generation_pq so the message names the
    # parameter this caller actually passed, not the delegate's.
    if p_poc_kw <= 0:
        raise ValueError(f"p_poc_kw must be positive, got {p_poc_kw}")

    # Reactive target at the POC from the power factor (injected => positive).
    q_poc_kvar = p_poc_kw * math.tan(math.acos(pf_target))

    # Echo the caller's target back verbatim. size_generation_pq derives an
    # *effective* power factor from P and Q, which round-trips to within an ulp
    # of the target but is a different quantity: what was asked for, versus what
    # the numbers imply. Callers of this form asked for a target.
    result = size_generation_pq(chain, p_poc_kw, q_poc_kvar)
    return dataclasses.replace(result, pf_target=pf_target)


def size_pv_inverters(
    chain: Chain, p_poc_kw: float, pf_target: float = 1.0
) -> SizingResult:
    """Deprecated alias for :func:`size_generation`.

    .. deprecated::
        Use :func:`size_generation` instead. This name predates the module
        going asset-neutral and will be removed in a future release.
    """
    warnings.warn(
        "size_pv_inverters is deprecated; use size_generation instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return size_generation(chain, p_poc_kw, pf_target)
