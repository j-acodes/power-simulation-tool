# Which losses sit between the battery and the POC, from a design and without one?

**Type:** grilling
**Status:** open
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
