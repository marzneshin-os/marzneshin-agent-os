"""Upcaster from event v2.0.0 to v2.1.0 (BUILD-SPEC §3.7, VS-8).

Adds growth spine taxonomy fields (§13.1):
  - campaign: optional marketing / attribution campaign identifier
  - consent_state: user consent state ('granted', 'denied', 'unspecified')
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "scripts") not in sys.path:
    sys.path.append(str(REPO / "scripts"))

from lib.validate import register_upcaster  # noqa: E402


@register_upcaster("event", "2.0.0", "2.1.0")
def upcast_event_2_0__2_1(event: dict) -> dict:
    """Migrate event artifact from schema version 2.0.0 to 2.1.0."""
    out = dict(event)  # never mutate the input
    if "campaign" not in out:
        out["campaign"] = out.get("payload", {}).get("campaign")
    if "consent_state" not in out:
        out["consent_state"] = out.get("payload", {}).get("consent_state", "granted")
    out["schema_version"] = "2.1.0"
    return out
