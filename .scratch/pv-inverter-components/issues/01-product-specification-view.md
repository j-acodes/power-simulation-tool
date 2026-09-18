# 01: Make the specification view product-generic

**What to build:** A sizing engineer can open a PV Transformer Station through the same complete,
read-only product specification experience used by BESS products. The view presents identity,
simulated parameters, grouped typed parameters, pairing information and provenance without
teaching each caller a product-specific rendering contract. Existing BESS catalogue and
specification behavior remains unchanged.

This is the prefactor that makes later inverter products cheap to add. Prefer one deep product
specification interface over parallel PV and BESS renderers.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] The specification view accepts PV Transformer Stations without labeling them as BESS
- [ ] PV Transformer Stations are clickable from the catalogue and a placed catalogue station
- [ ] Simulated parameters render before grouped typed parameters and provenance
- [ ] The existing BESS solution and BESS transformer specification behavior is unchanged
- [ ] Custom stations expose no supplier specification view
- [ ] Focused catalogue/specification component tests pass
- [ ] Frontend typechecking passes
