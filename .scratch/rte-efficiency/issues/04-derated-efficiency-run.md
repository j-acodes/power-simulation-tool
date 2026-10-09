# How does PCS derating reshape an efficiency run?

**Type:** grilling
**Status:** open
**Blocked by:** 01

## Question

When the PCS derating curve caps power below rated at a timestamp's ambient, the run uses the
derated power. Decide what stays fixed and what stretches: is the energy cycled still the
declared-duration energy (longer cycle), or the duration fixed (less energy)? How do auxiliary
consumption over the longer cycle and the loss chain at reduced power enter? Does the output
flag derated timestamps? Depends on the actual shape of the derating curves.
