# 05: Complete the Sungrow and Huawei PV catalogue

**What to build:** A sizing engineer can browse and use only the agreed Sungrow and Huawei PV
Transformer Stations and inverters, each in the complete component format. Every product exposes
the simulation values, grouped supplier fields, source provenance and pairings needed to defend a
design. Obsolete TBEA entries and explicitly rejected conversion products are absent.

**Blocked by:** 03: Make inverter capacity govern PV solving.

**Status:** done

- [x] The five Sungrow MVS-LV station products have complete identity, simulated/typed groups and provenance
- [x] Published Sungrow 30 °C transformer-station ratings are populated
- [x] The three Huawei JUPITER-H1 station products have complete identity, simulated/typed groups and provenance
- [x] SUN2000-330KTL-H1 is the only Huawei PV inverter and pairs at maximum/default counts 11, 22 and 30
- [x] Huawei H1 simulation power is 330 kW/kVA at 30 °C and 300 kW/kVA at 40 °C
- [x] Huawei ambient simulation power is visibly labeled as owner-declared engineering provenance
- [x] Official Huawei nominal/max active and apparent values remain typed supplier facts
- [x] SG350HX-20 is the only Sungrow inverter; SG350HX without `-20` is absent
- [x] All TBEA products, Huawei H2 and Huawei LUNA PCS are absent
- [x] Missing simulated fields make a product unavailable; missing typed fields render as not published
- [x] Catalogue endpoint and complete specification views cover every supported product
- [x] Catalogue/API and focused frontend rendering tests pass
- [x] Python and frontend typechecking pass
