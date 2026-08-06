"""Upcaster template (BUILD-SPEC §3.7). Copy to <kind>_vX_Y__vX_Z.py and edit.

Files starting with `_` are NOT loaded by validate.load_migrations(), so this
template is inert. A real migration module registers pure functions like:

    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
    from lib.validate import register_upcaster

    @register_upcaster("event", "2.0.0", "2.1.0")
    def upcast_event_2_0__2_1(event: dict) -> dict:
        out = dict(event)                 # never mutate the input
        out["new_field"] = "default"      # add / rename / reshape
        return out

Rules: pure function (no I/O, no clock), one version step per registration,
chains resolve transitively, and every migration ships with a round-trip test
over archived samples in tests/.
"""
