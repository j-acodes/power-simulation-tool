# Which losses sit between the battery and the POC, from a design and without one?

**Type:** grilling
**Status:** resolved
**Blocked by:** None

## Question

Define the loss chain the efficiency run applies between the PCS and the point of connection:

- With a design: which existing engine losses apply (station transformer load and no-load,
  MV circuit cables, busbar, HV transformer, export cable), evaluated at full power in both
  the charge and discharge directions. In a hybrid design, how losses in shared equipment
  (HV transformer, export cable) are attributed when PV shares it: does the run assume PV at
  zero?
- Where auxiliary consumption enters (MV busbar) and which downstream losses it therefore
  carries.
- Without a design: the exact set of typed-in fallback loss figures (which elements, as % or
  kW, load vs no-load).

The engine already computes transformer losses (`pk`/`p0`) and cable series losses along the
forward cascade, so this is a mapping decision, not new physics.

## Answer

Resolved by grilling, 2026-10-09.

1. **Hybrid designs:** PV is assumed at zero. The battery runs alone through the shared HV
   transformer and export cable; their no-load losses count in full.
2. **Direction:** the loss chain is one kW loss function of the power flowing through it,
   symmetric in direction (the engine evaluates losses from current at nominal voltage). The
   existing forward calculation is reused; no new reverse-flow physics. Each leg is anchored
   where its power is fixed:
   - **Discharge** is anchored at the battery's DC output at rated power; flow is DC → PCS →
     station AC → loss chain → minus auxiliary consumption → POC export. Its loss is a % of DC
     power.
   - **Charge** is anchored at an import of the POC capacity; flow is POC → minus auxiliary
     consumption → loss chain → station AC → PCS → DC. Its loss is a % of the POC import. The
     calculation starts at the POC and walks inward, the order the engine already walks in,
     subtracting losses instead of adding them.
   - The two legs differ because the stations carry different power on each leg and each leg
     divides by a different base, not because the kW loss function differs.
3. **Auxiliary consumption** is a load on the MV busbar inside the flow, so it carries HV
   transformer and export cable losses (export cable only for an MV interconnection) but not
   station transformer or collection cable losses.
4. **No-load losses** of station and HV transformers are a constant draw over both legs.
5. **Elements:** only those the engine already models: station transformers (load and
   no-load), collection cables, HV transformer (load and no-load), export cable. PCS losses
   belong to the energy-accounting step with the DC efficiency. Busbar, switchgear and LV
   cable losses are ignored.
6. **Transformer figures:** the design's own catalogue load and no-load losses, against the
   40 °C rating (`DEFAULT_AMBIENT_C`), with no ambient dependence. Load loss follows current;
   measuring it against a hot-ambient rating would overstate it. Sizing is unchanged.
7. **With a design:** the design supplies the BESS solution, station count (the whole BESS
   fleet, across all its busbars) and POC capacity. A conflicting BESS solution, or a design
   with no BESS fleet, is an error.
8. **Without a design:** three typed-in figures: load loss as a % of rated power at full power
   (scaled with the square of power below it), no-load loss as a % of rated power, and the POC
   capacity (required). Auxiliary consumption is added at the POC with no extra losses (an
   error of roughly 1 % of 1 %).
9. **PCS power is always above the POC capacity.** A typed-in POC capacity that breaks this is
   an input error. Hot-ambient derating can break it; that case belongs to
   [How does PCS derating reshape an efficiency run?](04-derated-efficiency-run.md).
