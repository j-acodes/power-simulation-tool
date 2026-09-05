# 02: Pair a station transformer with the solutions it is sold with

**What to build:** A sizing engineer places a BESS station, chooses its station transformer,
then a discharge duration, then a BESS solution — and at each step the next choice is narrowed to
what a supplier would actually quote. The container count arrives filled in.

The first real datasheet is why this exists. Sungrow's container is **transformerless**: it emits
690 V and reaches MV only through a station transformer its own datasheet says nothing about.
Nothing currently records which solutions a station transformer is sold with, so an engineer can
specify a pairing no supplier offers and the tool will size it happily.

The station transformer carries the pairing: a list of the solutions it is sold with, each with
the number of containers that station transformer serves. It lives on the station transformer
because one station transformer pairs with few solutions while one solution pairs with many
ratings — the shorter list to maintain by hand. It is displayed from both sides.

Container count per station is read from this pairing. It is still never interpolated, derived or
rounded; it is now **defaulted from the pairing and overridable**, because a partially populated
station is a real arrangement. This supersedes the sizing ticket in the BESS module, which states
the count comes from the duration table and is never overridable.

The guarantee that an unsupported duration is unreachable by construction survives, but changes
its source: the durations offered are those available among the solutions paired with the chosen
station transformer. A hand-edited payload naming an unpaired combination, or an unavailable
duration, is still rejected server-side.

The existing LV-voltage-match check stays — a pairing whose voltages disagree is a data error
worth catching — but it is no longer the only thing standing between an engineer and an
unbuildable station.

**Blocked by:** 01 (Reshape the BESS solution around a declared discharge duration).

**Status:** ready-for-agent

- [ ] A BESS station transformer declares the solutions it is sold with, each with a container
      count, and the pairing is served by the catalogue endpoint and typed in the frontend
- [ ] Choosing a station transformer restricts the discharge durations on offer to those
      available among its paired solutions
- [ ] Choosing a duration restricts the solutions on offer to those paired with that station
      transformer at that duration
- [ ] Container count per station defaults from the pairing
- [ ] The engineer can override the container count, and the override survives a save and reload
- [ ] A payload naming a solution not paired with its station transformer is rejected
      server-side with a validation issue
- [ ] A payload naming a duration unavailable for its station transformer is rejected
      server-side
- [ ] The existing LV-voltage-match check still fires on a pairing whose voltages disagree
- [ ] Delivered energy and the energy compliance gate still behave as before, now reading the
      count from the pairing
