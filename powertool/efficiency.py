"""The BESS efficiency run: weather-dependent round-trip efficiency at the POC.

For each ``(timestamp, ambient °C)`` row this evaluates one efficiency run
(CONTEXT.md's "Efficiency run") and reports the operating round-trip efficiency
at the point of connection, the idle loss and the PCS power available. Each row
is evaluated independently; timestamps are echoed verbatim. Warnings are
returned separately from the rows.

The configuration is either typed in (:class:`TypedConfiguration`) or read from
a design's diagram (:class:`DesignConfiguration`). Both resolve to one fleet
whose loss chain is the only difference: typed-in percentages, or the design's
own elements evaluated with the engine's existing loss functions.

Spec: .scratch/rte-efficiency/spec.md. Curve lookup follows ADR-0009.

This module has no web or UI dependency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Protocol

from .architecture import BranchArchitecture, ExportResult, SegmentResult
from .cable_sizing import CableSelection
from .components import (BessSolution, ContainerAuxLookup, DeratingCurve, StationAuxBand,
                         Transformer, resolve_container_aux, station_aux_band)
from .database import ComponentDatabase
from .graph import graph_to_inputs, validate_graph
from .plant import solve_architecture


class EfficiencyRunError(ValueError):
    """The efficiency run's configuration is invalid; nothing was computed."""


@dataclass(frozen=True)
class TypedConfiguration:
    """An efficiency run's configuration when there is no design: everything
    typed by the caller. Loss percentages are of the fleet's rated active power
    (containers x Pn); the load loss is at full power and scales with the
    square of power below it."""

    solution: str                      # BESS solution catalogue key
    station_transformer: str           # paired BESS station transformer key
    stations: int
    containers: int
    poc_capacity_kw: float
    load_loss_pct: float
    no_load_loss_pct: float
    cycles_per_day: float | None = None
    cell_rte_pct: float | None = None  # None: the solution's catalogue default


@dataclass(frozen=True)
class DesignConfiguration:
    """An efficiency run's configuration read from a design's diagram JSON (the
    API contract). The design supplies the BESS solution, the stations and
    their containers, the POC capacity and the loss chain. ``solution``, when
    given, must be the design's own: a different one is an error."""

    diagram: dict
    solution: str | None = None
    cycles_per_day: float | None = None
    cell_rte_pct: float | None = None  # None: the solution's catalogue default


@dataclass(frozen=True)
class EfficiencyRow:
    """One output row. ``idle_loss_pct`` is % of nominal energy per hour,
    imported at the POC; ``pcs_power_pct`` is the PCS power available at the
    row's ambient (100 unless derated), a power cap, never a loss."""

    timestamp: str
    operating_rte_pct: float
    idle_loss_pct: float
    pcs_power_pct: float


@dataclass
class EfficiencyResult:
    rows: list[EfficiencyRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# --- the loss chain ----------------------------------------------------------
# Between the container AC terminals and the POC. One kW loss function of the
# power through it, symmetric in direction (ticket 03): discharge evaluates it
# outward from the containers, charge inward from the POC. Auxiliary
# consumption ``aux_kw`` is drawn inside the chain at the MV busbar (with a
# design) or at the POC (typed in).

class LossChain(Protocol):
    no_load_kw: float  # constant draw of every energised transformer

    def export_kw(self, p_ac_kw: float, aux_kw: float) -> float:
        """Discharge: power at the POC when ``p_ac_kw`` leaves the containers."""

    def import_kw(self, p_in_kw: float, aux_kw: float) -> float:
        """Charge: power imported at the POC to put ``p_in_kw`` into the containers."""

    def ac_for_export(self, export_kw: float, aux_kw: float) -> float:
        """Inverse of :meth:`export_kw` in its first argument."""

    def ac_from_import(self, import_kw: float, aux_kw: float) -> float:
        """Inverse of :meth:`import_kw` in its first argument."""


@dataclass(frozen=True)
class _TypedLossChain:
    """Typed-in losses: load loss a x P^2 at the container side, a constant
    no-load loss, auxiliary consumption at the POC with no extra losses."""

    load_loss_coeff: float    # a [1/kW]
    no_load_kw: float

    def export_kw(self, p_ac_kw: float, aux_kw: float) -> float:
        return p_ac_kw - self.load_loss_coeff * p_ac_kw ** 2 - self.no_load_kw - aux_kw

    def import_kw(self, p_in_kw: float, aux_kw: float) -> float:
        return p_in_kw + self.load_loss_coeff * p_in_kw ** 2 + self.no_load_kw + aux_kw

    def ac_for_export(self, export_kw: float, aux_kw: float) -> float:
        """The smaller root of a P^2 - P + (export + fixed) = 0."""
        a, target = self.load_loss_coeff, export_kw + self.no_load_kw + aux_kw
        if a == 0:
            return target
        return (1 - math.sqrt(1 - 4 * a * target)) / (2 * a)

    def ac_from_import(self, import_kw: float, aux_kw: float) -> float:
        """The root of P + a P^2 = import - fixed."""
        a, available = self.load_loss_coeff, import_kw - self.no_load_kw - aux_kw
        if a == 0:
            return available
        return (-1 + math.sqrt(1 + 4 * a * available)) / (2 * a)


def _invert(f, target: float) -> float:
    """``x`` with ``f(x) == target`` for a monotone, nearly linear ``f`` (the
    design's loss chain), by the secant method."""
    x0, x1 = target, target * 1.01 + 1.0
    f0, f1 = f(x0) - target, f(x1) - target
    for _ in range(50):
        if abs(f1) <= 1e-9 * max(1.0, abs(target)):
            return x1
        x0, x1 = x1, x1 - f1 * (x1 - x0) / (f1 - f0)
        f0, f1 = f1, f(x1) - target
    raise EfficiencyRunError("the design's loss chain did not converge")  # pragma: no cover


@dataclass(frozen=True)
class _Station:
    transformer: Transformer
    share: float                    # of the fleet's container AC power
    cable: CableSelection | None    # the sized segment feeding it, if any
    length_km: float


@dataclass(frozen=True)
class _Busbar:
    """One BESS busbar: its circuits (each far station first), its share of
    the auxiliary draw, and its own MV export run when it has one."""

    v_mv_kv: float
    circuits: tuple[tuple[_Station, ...], ...]
    aux_share: float
    mv_export: SegmentResult | None  # only with a cable selection


@dataclass(frozen=True)
class DesignLossChain:
    """A design's own loss chain, from its solved architecture with every cable
    selection frozen: station transformers (load and no-load), collection
    cables, the BESS busbars' MV export runs, the HV transformer and the export
    cable.

    It is the engine's forward calculation (``architecture.
    _delivered_with_frozen_cables``) with the same element loss functions
    (``Transformer.losses`` against the 40 °C rating, ``Cable.series_losses``),
    walked with signed power so it runs in both directions: positive power
    leaves the containers (discharge), negative power enters them (charge);
    each element's loss depends only on the magnitude of what flows through
    it. Power splits between stations as the design allocates it; the reactive
    power at the containers is zero (unity power factor). Only the BESS fleet's
    branch is walked: in a hybrid, PV is at zero and the shared HV transformer
    and export cable carry the battery alone.
    """

    busbars: tuple[_Busbar, ...]
    export: ExportResult | None
    no_load_kw: float

    @classmethod
    def from_architecture(cls, branches: list[BranchArchitecture],
                          export: ExportResult | None) -> "DesignLossChain":
        p_total = sum(plan.p_lv_kw for b in branches
                      for plans in b.layout.circuit_plans for plan in plans)
        busbars: list[_Busbar] = []
        for branch in branches:
            pairs = list(zip(branch.circuits, branch.layout.circuit_plans))
            for section in branch.sections:
                indices = set(section.circuit_indices)
                circuits = tuple(
                    tuple(_Station(plan.transformer, plan.p_lv_kw / p_total, seg.selection,
                                   seg.length_km)
                          for seg, plan in zip(reversed(circuit.segments), reversed(plans)))
                    for circuit, plans in pairs if circuit.index in indices)
                mv_export = section.mv_export
                busbars.append(_Busbar(
                    v_mv_kv=branch.layout.v_mv_kv,
                    circuits=circuits,
                    aux_share=sum(st.share for c in circuits for st in c),
                    mv_export=mv_export if mv_export is not None
                    and mv_export.selection is not None else None,
                ))
        no_load = sum(st.transformer.p0_kw for b in busbars for c in b.circuits for st in c)
        if export is not None and export.hv_transformer is not None:
            no_load += export.hv_transformer.p0_kw * export.hv_n_parallel
        return cls(tuple(busbars), export, no_load)

    def _poc_kw(self, p_ac_kw: float, aux_kw: float) -> float:
        """Signed power at the POC for signed ``p_ac_kw`` at the containers."""
        p_total = q_total = 0.0
        for busbar in self.busbars:
            p_sec = q_sec = 0.0
            for circuit in busbar.circuits:
                p = q = 0.0
                for st in circuit:               # far station first
                    p_lv = p_ac_kw * st.share
                    dp, dq = st.transformer.losses(abs(p_lv))
                    p += p_lv - dp
                    q -= dq
                    if st.cable is not None:
                        dp, dq = st.cable.cable.series_losses(
                            math.hypot(p, q), busbar.v_mv_kv, st.length_km)
                        p -= dp / st.cable.n_parallel
                        q -= dq / st.cable.n_parallel
                p_sec += p
                q_sec += q
            p_sec -= aux_kw * busbar.aux_share
            if busbar.mv_export is not None:
                sel = busbar.mv_export.selection
                dp, dq = sel.cable.series_losses(
                    math.hypot(p_sec, q_sec), busbar.v_mv_kv, busbar.mv_export.length_km)
                p_sec -= dp / sel.n_parallel
                q_sec -= dq / sel.n_parallel
            p_total += p_sec
            q_total += q_sec

        export = self.export
        if export is not None:
            if export.hv_transformer is not None:
                n = export.hv_n_parallel
                dp, dq = export.hv_transformer.losses(math.hypot(p_total, q_total) / n)
                p_total -= dp * n
                q_total -= dq * n
            hv = export.hv_cable
            if hv is not None and hv.selection is not None:
                dp, dq = hv.selection.cable.series_losses(
                    math.hypot(p_total, q_total), export.v_hv_kv, hv.length_km)
                p_total -= dp / hv.selection.n_parallel
        return p_total

    def export_kw(self, p_ac_kw: float, aux_kw: float) -> float:
        return self._poc_kw(p_ac_kw, aux_kw)

    def import_kw(self, p_in_kw: float, aux_kw: float) -> float:
        return -self._poc_kw(-p_in_kw, aux_kw)

    def ac_for_export(self, export_kw: float, aux_kw: float) -> float:
        return _invert(lambda p: self.export_kw(p, aux_kw), export_kw)

    def ac_from_import(self, import_kw: float, aux_kw: float) -> float:
        return _invert(lambda p: self.import_kw(p, aux_kw), import_kw)


# --- configuration -----------------------------------------------------------

@dataclass(frozen=True)
class _Fleet:
    """The resolved, validated configuration the per-row physics runs on."""

    solution: BessSolution
    containers: int
    stations: int
    poc_capacity_kw: float
    rated_kw: float           # fleet rated active power, N x Pn
    chain: LossChain
    eta: float                # one-way conversion efficiency
    rho: float                # cell round-trip efficiency
    aux_table: ContainerAuxLookup  # operating and standby kW per container
    # (transformer-station auxiliary bands, station count) per station
    # transformer model; a model with no published table is absent, counted
    # as zero.
    station_aux_tables: tuple[tuple[tuple[StationAuxBand, ...], int], ...]
    derating: DeratingCurve | None  # None: no curve, 100 % of rated power
    ambient_range_c: tuple[float, float]  # published range every curve covers

    def derating_at(self, ambient_c: float) -> float:
        """Fraction of rated active power available at ``ambient_c``."""
        return self.derating.fraction_at(ambient_c) if self.derating else 1.0

    def _station_bands(self, ambient_c: float):
        for bands, count in self.station_aux_tables:
            yield station_aux_band(bands, ambient_c), count

    def station_operating_kw_at(self, ambient_c: float) -> float:
        """Operating auxiliary consumption of every transformer station [kW]."""
        return sum(count * band.operating_kw
                   for band, count in self._station_bands(ambient_c))

    def station_standby_kw_at(self, ambient_c: float) -> float:
        """Standby auxiliary consumption of every transformer station [kW]."""
        return sum(count * band.standby_kw
                   for band, count in self._station_bands(ambient_c))


@dataclass(frozen=True)
class DesignFleet:
    """What a design supplies to an efficiency run: its BESS solution, the
    whole BESS fleet's station and container counts, the POC capacity of the
    BESS fleet, and its own loss chain."""

    solution: str
    stations: int
    containers: int
    poc_capacity_kw: float
    chain: DesignLossChain
    # (station transformer, count) over the BESS fleet, first appearance first
    station_transformers: tuple[tuple[Transformer, int], ...]


def _station_aux_tables(station_transformers, warnings: list[str]) -> tuple:
    tables = []
    for transformer, count in station_transformers:
        if transformer.station_aux_consumption:
            tables.append((transformer.station_aux_consumption, count))
        else:
            warnings.append(
                f"station transformer {transformer.name!r} publishes no transformer-station "
                "auxiliary-consumption table; counted as zero")
    return tuple(tables)


def _solution_parameters(solution: BessSolution, cycles_per_day, cell_rte_pct,
                         warnings: list[str]):
    """The solution's efficiency-run data, validated: conversion efficiency,
    cell RTE, the container table."""
    if not solution.aux_consumption:
        raise EfficiencyRunError(
            f"BESS solution {solution.name!r} publishes no auxiliary-consumption table")
    eta = solution.conversion_efficiency
    if eta is None:
        raise EfficiencyRunError(
            f"BESS solution {solution.name!r} publishes no conversion efficiency")
    rho_pct = cell_rte_pct if cell_rte_pct is not None else solution.cell_rte_pct
    if rho_pct is None:
        raise EfficiencyRunError(
            f"BESS solution {solution.name!r} has no cell RTE default; give one")
    if not 0 < rho_pct <= 100:
        raise EfficiencyRunError("cell RTE must be in (0, 100] %")

    try:
        aux_table, aux_warnings = resolve_container_aux(solution.aux_consumption, cycles_per_day)
    except ValueError as exc:
        raise EfficiencyRunError(f"BESS solution {solution.name!r}: {exc}") from None
    warnings.extend(aux_warnings)
    return eta, rho_pct / 100.0, aux_table


def _published_range(solution: BessSolution, station_aux_tables) -> tuple[float, float]:
    """The published ambient range: where every curve the run reads (the
    container tables, the derating curve, each transformer station's band
    table) has data. Outside it the run clamps (ADR-0009)."""
    ranges = [(t.ambient_c[0], t.ambient_c[-1]) for t in solution.aux_consumption]
    if solution.derating is not None:
        ranges.append((solution.derating.ambient_c[0], solution.derating.ambient_c[-1]))
    ranges.extend((bands[0].ambient_min_c, bands[-1].ambient_max_c)
                  for bands, _count in station_aux_tables)
    return max(low for low, _ in ranges), min(high for _, high in ranges)


def _rated_active_power(solution: BessSolution) -> float:
    pn = solution.rated_active_power_kw
    if pn is None:
        raise EfficiencyRunError(
            f"BESS solution {solution.name!r} publishes no rated active power; "
            "it cannot be used in an efficiency run (ADR-0008 amendment)")
    return pn


def _fleet(solution: BessSolution, containers: int, stations: int, poc_capacity_kw: float,
           chain: LossChain, station_transformers, cycles_per_day, cell_rte_pct,
           warnings: list[str]) -> _Fleet:
    pn = _rated_active_power(solution)
    eta, rho, aux_table = _solution_parameters(
        solution, cycles_per_day, cell_rte_pct, warnings)
    station_aux_tables = _station_aux_tables(station_transformers, warnings)
    if solution.derating is None:
        warnings.append(
            f"BESS solution {solution.name!r} publishes no PCS derating curve; "
            "run at 100 % of rated active power at every ambient")
    return _Fleet(
        solution=solution,
        containers=containers,
        stations=stations,
        poc_capacity_kw=float(poc_capacity_kw),
        rated_kw=containers * pn,
        chain=chain,
        eta=eta,
        rho=rho,
        aux_table=aux_table,
        station_aux_tables=station_aux_tables,
        derating=solution.derating,
        ambient_range_c=_published_range(solution, station_aux_tables),
    )


def _resolve_typed(config: TypedConfiguration,
                   db: ComponentDatabase) -> tuple[_Fleet, list[str]]:
    warnings: list[str] = []
    try:
        solution = db.bess_solution(config.solution)
        transformer = db.bess_transformer(config.station_transformer)
    except KeyError as exc:
        raise EfficiencyRunError(exc.args[0]) from None

    pn = _rated_active_power(solution)
    per_station = db.bess_pairings.get(config.station_transformer, {}).get(config.solution)
    if per_station is None:
        raise EfficiencyRunError(
            f"station transformer {config.station_transformer!r} is not paired with "
            f"BESS solution {config.solution!r}")
    if config.stations < 1 or config.containers < 1:
        raise EfficiencyRunError("station and container counts must be at least 1")
    if config.containers > config.stations * per_station:
        raise EfficiencyRunError(
            f"{config.containers} containers exceed {config.stations} stations x "
            f"{per_station} containers per station")
    rated_kw = config.containers * pn
    if config.poc_capacity_kw <= 0:
        raise EfficiencyRunError("POC capacity must be positive")
    if config.poc_capacity_kw >= rated_kw:
        raise EfficiencyRunError(
            f"POC capacity {config.poc_capacity_kw:g} kW must be below the installed "
            f"rated active power {rated_kw:g} kW")
    if config.load_loss_pct < 0 or config.no_load_loss_pct < 0:
        raise EfficiencyRunError("loss percentages must not be negative")

    chain = _TypedLossChain(load_loss_coeff=config.load_loss_pct / 100.0 / rated_kw,
                            no_load_kw=config.no_load_loss_pct / 100.0 * rated_kw)
    fleet = _fleet(solution, config.containers, config.stations, config.poc_capacity_kw,
                   chain, [(transformer, config.stations)], config.cycles_per_day,
                   config.cell_rte_pct, warnings)
    return fleet, warnings


def resolve_design(diagram: dict, db: ComponentDatabase) -> DesignFleet:
    """Read and solve a design's diagram and return what it supplies to an
    efficiency run. Raises :class:`EfficiencyRunError` when the diagram does
    not validate or solve, has no BESS fleet, or its BESS stations do not share
    one solution with a readable container count."""
    issues = validate_graph(diagram, db)
    if issues:
        raise EfficiencyRunError(f"the design does not validate: {issues[0].message}")
    inputs = graph_to_inputs(diagram, db)
    bess = [i for i, b in enumerate(inputs.branches) if b.kind == "bess"]
    if not bess:
        raise EfficiencyRunError("the design has no BESS fleet")
    try:
        _stage1s, _layouts, arch = solve_architecture(inputs, db)
    except ValueError as exc:
        raise EfficiencyRunError(f"the design does not solve: {exc}") from None

    branches = [inputs.branches[i] for i in bess]
    station_ids = [sid for b in branches for circuit in b.station_ids for sid in circuit]
    by_station = {sid: v for b in branches for sid, v in b.bess_by_station.items()}
    solutions = {by_station[sid][0].name for sid in station_ids if sid in by_station}
    if len(solutions) != 1 or len(by_station) != len(station_ids):
        raise EfficiencyRunError(
            "every BESS station of the design must use one and the same BESS solution "
            f"(found {sorted(solutions) or 'none'})")
    containers = [by_station[sid][1] for sid in station_ids]
    if any(n is None for n in containers):
        raise EfficiencyRunError("a BESS station of the design has no container count")

    # Grouped by catalogue key (Transformer is not hashable); a dict keeps
    # first appearance first.
    grouped: dict[str, tuple[Transformer, int]] = {}
    for b in branches:
        for tx, count in b.fleet:
            first, total = grouped.get(tx.name, (tx, 0))
            grouped[tx.name] = (first, total + count)

    return DesignFleet(
        solution=solutions.pop(),
        stations=len(station_ids),
        containers=sum(containers),
        poc_capacity_kw=sum(b.p_poc_target_kw for b in branches),
        chain=DesignLossChain.from_architecture([arch.branches[i] for i in bess], arch.export),
        station_transformers=tuple(grouped.values()),
    )


def _resolve_design(config: DesignConfiguration,
                    db: ComponentDatabase) -> tuple[_Fleet, list[str]]:
    design = resolve_design(config.diagram, db)
    if config.solution is not None and config.solution != design.solution:
        raise EfficiencyRunError(
            f"BESS solution {config.solution!r} conflicts with the design's "
            f"{design.solution!r}")
    warnings: list[str] = []
    fleet = _fleet(db.bess_solution(design.solution), design.containers, design.stations,
                   design.poc_capacity_kw, design.chain, design.station_transformers,
                   config.cycles_per_day, config.cell_rte_pct, warnings)
    return fleet, warnings


# --- the per-row physics -----------------------------------------------------

def _operating_rte(fleet: _Fleet, ambient_c: float) -> float:
    """One efficiency run at the full power available at ``ambient_c``
    (rated, or derated: same energy over a longer cycle); returns RTE at the
    POC as a fraction. Derating is never counted as a loss (ticket 04)."""
    chain = fleet.chain
    aux_kw = (fleet.containers * fleet.aux_table.operating_kw_at(ambient_c)
              + fleet.station_operating_kw_at(ambient_c))   # drawn over both legs
    energy_dc_kwh = fleet.containers * fleet.solution.e_nominal_kwh

    # Discharge: rated power at the AC terminals, unless the export would
    # exceed the POC capacity (ticket 11); then AC power drops until it equals it.
    p_full = fleet.rated_kw * fleet.derating_at(ambient_c)
    p_ac = p_full
    export_kw = chain.export_kw(p_ac, aux_kw)
    if export_kw > fleet.poc_capacity_kw:
        p_ac = chain.ac_for_export(fleet.poc_capacity_kw, aux_kw)
        export_kw = fleet.poc_capacity_kw
    discharge_h = energy_dc_kwh * fleet.eta / p_ac

    # Charge: import the lesser of the POC capacity and what drives the PCS at
    # its (derated) power; walk inward to the AC power into the containers. The
    # cycle closes: the DC side takes back the discharged energy over cell RTE.
    import_kw = min(fleet.poc_capacity_kw, chain.import_kw(p_full, aux_kw))
    p_in = chain.ac_from_import(import_kw, aux_kw)
    charge_h = (energy_dc_kwh / fleet.rho) / (p_in * fleet.eta)

    return (export_kw * discharge_h) / (import_kw * charge_h)


@dataclass
class _AmbientClamp:
    """Clamps each row's ambient to the published range once, so every figure
    of the row reads the same clamped ambient, and reports the clamping as one
    warning for the whole run."""

    low_c: float
    high_c: float
    clamped: list[float] = field(default_factory=list)

    def __call__(self, ambient_c: float) -> float:
        if self.low_c <= ambient_c <= self.high_c:
            return ambient_c
        self.clamped.append(ambient_c)
        return min(max(ambient_c, self.low_c), self.high_c)

    def warning(self) -> str | None:
        if not self.clamped:
            return None
        n = len(self.clamped)
        return (f"{n} timestamp{'s' if n != 1 else ''} had an ambient outside the "
                f"published range {self.low_c:g} to {self.high_c:g} °C (coldest seen "
                f"{min(self.clamped):g} °C, hottest seen {max(self.clamped):g} °C); "
                "clamped to the nearest edge")


def _idle_loss(fleet: _Fleet, ambient_c: float) -> float:
    """Idle draw imported at the POC per hour, as a fraction of the fleet's
    nominal energy: standby auxiliaries plus no-load losses, with no load
    losses and no dependence on PCS derating (spec, "The idle figure")."""
    idle_kw = (fleet.containers * fleet.aux_table.standby_kw_at(ambient_c)
               + fleet.station_standby_kw_at(ambient_c) + fleet.chain.no_load_kw)
    return idle_kw / (fleet.containers * fleet.solution.e_nominal_kwh)


def run_efficiency(
    rows: Iterable[tuple[str, float]],
    config: TypedConfiguration | DesignConfiguration,
    db: ComponentDatabase,
) -> EfficiencyResult:
    """Evaluate one efficiency run per ``(timestamp, ambient °C)`` row.

    Raises :class:`EfficiencyRunError` for an invalid configuration. Warnings
    (e.g. a missing transformer-station table) are returned on the result, never in the rows.
    """
    if isinstance(config, DesignConfiguration):
        fleet, warnings = _resolve_design(config, db)
    else:
        fleet, warnings = _resolve_typed(config, db)
    result = EfficiencyResult(warnings=warnings)
    clamp = _AmbientClamp(*fleet.ambient_range_c)
    for timestamp, ambient_c in rows:
        ambient_c = clamp(float(ambient_c))
        result.rows.append(EfficiencyRow(
            timestamp=timestamp,
            operating_rte_pct=_operating_rte(fleet, ambient_c) * 100.0,
            idle_loss_pct=_idle_loss(fleet, ambient_c) * 100.0,
            pcs_power_pct=fleet.derating_at(ambient_c) * 100.0,
        ))
    clamp_warning = clamp.warning()
    if clamp_warning is not None:
        result.warnings.append(clamp_warning)
    return result
