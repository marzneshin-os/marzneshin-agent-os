# Schema Migrations (BUILD-SPEC §3.7, I18)

Event sourcing without upcasters loses replay at the first breaking change —
which is the entire value of event sourcing. Every historical event, receipt,
and agent card must remain readable forever.

## Rules (mandatory)

- An upcaster is a **pure function**: no network, no files, no clock. It takes
  one artifact dict and returns the next-version dict. It must not mutate its
  input.
- Upcasters are registered with `@validate.register_upcaster(kind, from, to)`
  and chain transitively (`validate.upcast` walks v1.0 → v1.1 → v2.0).
- `scripts/verify.py --schemas` calls `validate.load_migrations()`, which
  imports every non-underscore `*.py` in this directory so decorators run.
  Files starting with `_` (like `_template.py`) are not loaded.
- Readers must read **all** historical versions; upcasters apply in order up
  to the current version.
- Compaction never rewrites a raw event; it only writes a new snapshot.
- CI fails on deleting a field or changing its meaning **without** an
  upcaster in the same commit (I18). The same mechanism covers Receipt and
  Agent Card: an old receipt must stay verifiable in the chain.

## Current state

`schema_version` is `2.0.0` everywhere. Per ADR-002 D11, version `1.1.0` never
produced data, so no upcasters exist yet. The first real migration will be
`2.0.0 → 2.1.0` and lands here as e.g. `event_v2_0__v2_1.py` using
`_template.py` as the starting point, plus a round-trip test over real samples
from `state/archive/`.
