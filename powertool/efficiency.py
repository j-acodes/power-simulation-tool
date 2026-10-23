"""The BESS efficiency run: weather-dependent round-trip efficiency at the POC.

For each ``(timestamp, ambient °C)`` row this evaluates one efficiency run
(CONTEXT.md's "Efficiency run") and reports the operating round-trip efficiency
at the point of connection, the idle loss and the PCS power available. Each row
is evaluated independently; timestamps are echoed verbatim. Warnings are
returned separately from the rows.

Spec: .scratch/rte-efficiency/spec.md. Curve lookup follows ADR-0009.

This module has no web or UI dependency. Not yet implemented (later tickets):
the idle figure (``idle_loss_pct`` is None), PCS derating (``pcs_power_pct`` is
always 100), and a run from a solved design.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

from .components import BessSolution, ContainerAuxLookup, mvs_aux_band, resolve_container_aux
from .database import ComponentDatabase


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
class EfficiencyRow:
    """One output row. ``idle_loss_pct`` is None until the idle figure is
    implemented; ``pcs_power_pct`` is 100 until derating is."""

    timestamp: str
    operating_rte_pct: float
    idle_loss_pct: float | None
    pcs_power_pct: float


@dataclass
class EfficiencyResult:
    rows: list[EfficiencyRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _Fleet:
    """The resolved, validated configuration the per-row physics runs on."""

    solution: BessSolution
    containers: int
    stations: int
    poc_capacity_kw: float
    rated_kw: float           # fleet rated active power, N x Pn
    load_loss_coeff: float    # a in load loss = a x P^2 [1/kW]
    no_load_kw: float
    eta: float                # one-way conversion efficiency
    rho: float                # cell round-trip efficiency
    aux_table: ContainerAuxLookup  # operating and standby kW per container
    mvs_bands: tuple          # empty: no MVS table, counted as zero


def _resolve(config: TypedConfiguration, db: ComponentDatabase) -> tuple[_Fleet, list[str]]:
    warnings: list[str] = []
    try:
        solution = db.bess_solution(config.solution)
        transformer = db.bess_transformer(config.station_transformer)
    except KeyError as exc:
        raise EfficiencyRunError(exc.args[0]) from None

    pn = solution.rated_active_power_kw
    if pn is None:
        raise EfficiencyRunError(
            f"BESS solution {config.solution!r} publishes no rated active power; "
            "it cannot be used in an efficiency run (ADR-0008 amendment)")
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

    if not solution.aux_consumption:
        raise EfficiencyRunError(
            f"BESS solution {config.solution!r} publishes no auxiliary-consumption table")
    eta = solution.conversion_efficiency
    if eta is None:
        raise EfficiencyRunError(
            f"BESS solution {config.solution!r} publishes no conversion efficiency")
    rho_pct = config.cell_rte_pct if config.cell_rte_pct is not None else solution.cell_rte_pct
    if rho_pct is None:
        raise EfficiencyRunError(
            f"BESS solution {config.solution!r} has no cell RTE default; give one")
    if not 0 < rho_pct <= 100:
        raise EfficiencyRunError("cell RTE must be in (0, 100] %")

    try:
        aux_table, aux_warnings = resolve_container_aux(
            solution.aux_consumption, config.cycles_per_day)
    except ValueError as exc:
        raise EfficiencyRunError(f"BESS solution {config.solution!r}: {exc}") from None
    warnings.extend(aux_warnings)

    if not transformer.mvs_aux_consumption:
        warnings.append(
            f"station transformer {config.station_transformer!r} publishes no MVS "
            "auxiliary-consumption table; counted as zero")

    return _Fleet(
        solution=solution,
        containers=config.containers,
        stations=config.stations,
        poc_capacity_kw=float(config.poc_capacity_kw),
        rated_kw=rated_kw,
        load_loss_coeff=config.load_loss_pct / 100.0 / rated_kw,
        no_load_kw=config.no_load_loss_pct / 100.0 * rated_kw,
        eta=eta,
        rho=rho_pct / 100.0,
        aux_table=aux_table,
        mvs_bands=transformer.mvs_aux_consumption,
    ), warnings


def _ac_for_export(a: float, export_kw: float) -> float:
    """AC power at the container terminals whose output, after load losses
    a x P^2, is ``export_kw``: the smaller root of a P^2 - P + export = 0."""
    if a == 0:
        return export_kw
    return (1 - math.sqrt(1 - 4 * a * export_kw)) / (2 * a)


def _ac_from_import(a: float, available_kw: float) -> float:
    """AC power into the containers when ``available_kw`` enters the loss
    chain from the POC side: the root of P + a x P^2 = available."""
    if a == 0:
        return available_kw
    return (-1 + math.sqrt(1 + 4 * a * available_kw)) / (2 * a)


def _operating_rte(fleet: _Fleet, ambient_c: float) -> float:
    """One efficiency run at full rated power; returns RTE at the POC as a fraction."""
    a = fleet.load_loss_coeff
    aux_kw = fleet.containers * fleet.aux_table.operating_kw_at(ambient_c)
    if fleet.mvs_bands:
        aux_kw += fleet.stations * mvs_aux_band(fleet.mvs_bands, ambient_c).operating_kw
    fixed_kw = fleet.no_load_kw + aux_kw            # drawn over both legs
    energy_dc_kwh = fleet.containers * fleet.solution.e_nominal_kwh

    # Discharge: rated power at the AC terminals, unless the export would
    # exceed the POC capacity (ticket 11); then AC power drops until it equals it.
    p_ac = fleet.rated_kw
    export_kw = p_ac - a * p_ac ** 2 - fixed_kw
    if export_kw > fleet.poc_capacity_kw:
        p_ac = _ac_for_export(a, fleet.poc_capacity_kw + fixed_kw)
        export_kw = fleet.poc_capacity_kw
    discharge_h = energy_dc_kwh * fleet.eta / p_ac

    # Charge: import the lesser of the POC capacity and what drives the PCS at
    # rated power; walk inward to the AC power into the containers. The cycle
    # closes: the DC side takes back the discharged energy over cell RTE.
    p_full = fleet.rated_kw
    import_kw = min(fleet.poc_capacity_kw, p_full + a * p_full ** 2 + fixed_kw)
    p_in = _ac_from_import(a, import_kw - fixed_kw)
    charge_h = (energy_dc_kwh / fleet.rho) / (p_in * fleet.eta)

    return (export_kw * discharge_h) / (import_kw * charge_h)


def run_efficiency(
    rows: Iterable[tuple[str, float]],
    config: TypedConfiguration,
    db: ComponentDatabase,
) -> EfficiencyResult:
    """Evaluate one efficiency run per ``(timestamp, ambient °C)`` row.

    Raises :class:`EfficiencyRunError` for an invalid configuration. Warnings
    (e.g. a missing MVS table) are returned on the result, never in the rows.
    """
    fleet, warnings = _resolve(config, db)
    result = EfficiencyResult(warnings=warnings)
    for timestamp, ambient_c in rows:
        result.rows.append(EfficiencyRow(
            timestamp=timestamp,
            operating_rte_pct=_operating_rte(fleet, float(ambient_c)) * 100.0,
            idle_loss_pct=None,
            pcs_power_pct=100.0,
        ))
    return result
