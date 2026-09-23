# 02: Seed a BESS plant

**What to build:** On a design whose declared technology is BESS, the seed wizard shows only BESS
inputs: point-of-connection BESS power, discharge duration, then a BESS solution that sells that
duration, then a station model paired with that solution, plus maximum loading, trunk length and
spacing alongside the shared fields (interconnection, voltages, power-factor target, export
length, auxiliary load, feeders per busbar). The seed sizes the station count to power using
installed PCS at the pairing maximum, then sizes containers to power × duration: stations are
filled to the pairing maximum in circuit order with the remainder on the last; if full stations
fall short, stations are added until energy is met. The proposed diagram carries the duration as
its discharge duration setting, the BESS power on the point of connection, the BESS maximum-loading
rule, a BESS busbar with the auxiliary load, and `bess` stations. PV-design seeding is unchanged.

**Blocked by:** 01: PCS governs BESS allocation; container count capped at the pairing.

**Status:** ready-for-agent

- [ ] Seed request accepts a technology and a BESS block; PV fields are required only when PV is permitted
- [ ] Request rejects a solution that does not sell the duration and a station not paired with the solution
- [ ] Container fill: stations at the maximum in order, remainder on the last, override written only where below the maximum
- [ ] Energy shortfall at the maximum adds stations until energy is met
- [ ] Seeded BESS diagram validates and solves with energy met and loading within the limit
- [ ] Seeding is deterministic
- [ ] Wizard on a BESS design shows only BESS inputs; selectors cascade duration → solution → station
- [ ] Wizard on a PV design is unchanged; existing PV seed tests pass untouched
- [ ] Focused seed tests, wizard test and type checks pass
