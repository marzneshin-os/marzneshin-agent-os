#!/usr/bin/env python3
"""escrow.py — the encrypted §11.2 recovery bundle (VS-4).

A non-technical human must be able to stop or hand over this system. The
bundle is what they receive: RECOVERY.md (plain-language kill-switch paths),
a generated access inventory with revocation notes, the contacts, and the
"never stored here" declaration — encrypted at rest, rebuilt daily by the
mirror workflow.

    escrow.py build [--out PATH]     build + encrypt the bundle (needs env)
    escrow.py verify <bundle>        decrypt, check hashes, check drift

Fail-closed rules (I12), in order of importance:

1. No passphrase, no bundle. The passphrase comes from the
   MARZ_ESCROW_PASSPHRASE environment variable and nowhere else (Iron Rule 4:
   it is never written to the repo, an event, or a receipt). An *unencrypted*
   bundle is worse than none: it is a single file mapping every access path
   and how to revoke it. Exit 2, nothing written.
2. Encryption is real: openssl AES-256-CBC, PBKDF2, 200k iterations, salted.
   openssl is ubiquitous (present on every CI runner) so scripts/lib stays
   stdlib-only (G9) — the passphrase travels via `-pass env:` so it never
   appears in argv or a shell ps.
3. verify() treats drift as failure, not warning: if the bundled RECOVERY.md
   differs from the repo's current one, the bundle is stale — a rescue manual
   that describes last month's system is a liability. Exit 1.
4. A bundle that fails its own manifest hashes is tampered or corrupt. Exit 1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import atomic, clock, events, paths  # noqa: E402

PASSPHRASE_ENV = "MARZ_ESCROW_PASSPHRASE"
# The payload: the rescue manual first, then everything a handover needs to
# reconstruct intent and ownership. security/ is optional (arrives later).
PAYLOAD_PATHS = ("RECOVERY.md", "BUILD-SPEC.md", "CODEOWNERS", "CLAUDE.md",
                 "decisions", "security")
OPENSSL_ITER = "200000"


class EscrowError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _passphrase() -> str:
    pw = os.environ.get(PASSPHRASE_ENV, "").strip()
    if not pw:
        raise EscrowError(
            f"{PASSPHRASE_ENV} is not set — refusing to build an unencrypted "
            f"escrow bundle (fail-closed: the plaintext bundle maps every "
            f"access path and how to revoke it).")
    return pw


def _openssl() -> str:
    exe = shutil.which("openssl")
    if not exe:
        raise EscrowError("openssl not found on PATH; cannot encrypt (fail-closed)")
    return exe


def _run_openssl(args: list[str]) -> bytes:
    proc = subprocess.run([_openssl(), *args], capture_output=True, timeout=120)
    if proc.returncode != 0:
        raise EscrowError(f"openssl failed: {proc.stderr.decode(errors='replace')[:200]}")
    return proc.stdout


def _access_inventory(root: Path) -> dict:
    """Machine-generated so it cannot silently drift from the registry."""
    inv: dict = {"generated_at": clock.iso(),
                 "kill_switch_paths": [
                     "K1 state/KILL (file)", "K2 env KILL_SWITCH",
                     "K3 Moxt Control Room task", "K4 scripts/killswitch.py",
                     "K5 automatic findings"],
                 "never_stored": "see RECOVERY.md §5",
                 "contacts": "see RECOVERY.md §6"}
    reg = atomic.read_json(paths.registry_file(), default=None)
    if isinstance(reg, dict):
        inv["agents"] = {name: {"role": e.get("role", ""),
                                "autonomy_max": e.get("autonomy_max"),
                                "moxt_agent": e.get("moxt_agent"),
                                "revoked": bool(e.get("revoked"))}
                         for name, e in (reg.get("agents") or {}).items()}
    codeowners = root / "CODEOWNERS"
    if codeowners.exists():
        inv["human_owned_paths"] = [
            ln.strip() for ln in codeowners.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")]
    wf = root / ".github" / "workflows"
    if wf.exists():
        inv["workflows"] = sorted(p.name for p in wf.glob("*.yml"))
    return inv


def _stage_payload(root: Path, stage: Path) -> dict[str, str]:
    """Copy the payload into stage/, return {relpath: sha256} for the manifest."""
    hashes: dict[str, str] = {}
    for rel in PAYLOAD_PATHS:
        src = root / rel
        if not src.exists():
            continue  # optional paths (security/) are skipped, recorded by absence
        dst = stage / rel
        if src.is_dir():
            for f in sorted(src.rglob("*")):
                if f.is_file():
                    target = dst / f.relative_to(src)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    data = f.read_bytes()
                    target.write_bytes(data)
                    hashes[(Path(rel) / f.relative_to(src)).as_posix()] = _sha256(data)
        else:
            data = src.read_bytes()
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            hashes[rel] = _sha256(data)
    if "RECOVERY.md" not in hashes:
        raise EscrowError("RECOVERY.md missing — the bundle without the rescue "
                          "manual is not a rescue bundle (fail-closed)")
    return hashes


def cmd_build(args) -> int:
    try:
        _passphrase()  # validated up front: no passphrase, nothing is built
        root = paths.repo_root()
        with tempfile.TemporaryDirectory(prefix="marz-escrow-") as td:
            stage = Path(td) / "stage"
            stage.mkdir()
            hashes = _stage_payload(root, stage)
            inventory = _access_inventory(root)
            (stage / "ACCESS-INVENTORY.json").write_text(
                json.dumps(inventory, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8")
            hashes["ACCESS-INVENTORY.json"] = _sha256(
                (stage / "ACCESS-INVENTORY.json").read_bytes())
            manifest = {
                "schema_version": "2.0.0",
                "built_at": clock.iso(),
                "builder": args.by,
                "purpose": "§11.2 recovery escrow: stop or hand over the system "
                           "without its builder",
                "encryption": "openssl aes-256-cbc, pbkdf2, 200k iterations, salted",
                "files": hashes,
            }
            (stage / "manifest.json").write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8")
            tar_bytes = Path(td, "bundle.tar.gz")
            with tarfile.open(tar_bytes, "w:gz") as tar:
                for f in sorted(stage.rglob("*")):
                    if f.is_file():
                        tar.add(f, arcname=f.relative_to(stage).as_posix())
            encrypted = _run_openssl(
                ["enc", "-aes-256-cbc", "-pbkdf2", "-iter", OPENSSL_ITER,
                 "-salt", "-pass", f"env:{PASSPHRASE_ENV}",
                 "-in", str(tar_bytes)])
        out = Path(args.out) if args.out else (
            paths.archive_dir() / "escrow"
            / f"escrow-{clock.now().strftime('%Y-%m-%d')}.tar.gz.enc")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(encrypted)
        digest = _sha256(encrypted)
        events.emit("escrow.built", events.Actor(kind="system", id="escrow"),
                    events.Subject(kind="artifact", id=paths.rel(out)),
                    {"files": len(hashes), "sha256": digest,
                     "recovery_md": hashes.get("RECOVERY.md")},
                    trust="internal")
        print(f"[ok] escrow bundle: {out}")
        print(f"[ok] {len(hashes)} files, {digest}")
        print(f"[ok] RECOVERY.md {hashes['RECOVERY.md'][:23]}…")
        return 0
    except EscrowError as exc:
        print(f"escrow: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"escrow: cannot build: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


def cmd_verify(args) -> int:
    try:
        _passphrase()
        bundle = Path(args.bundle)
        if not bundle.exists():
            raise EscrowError(f"bundle not found: {bundle}")
        with tempfile.TemporaryDirectory(prefix="marz-escrow-vfy-") as td:
            plain = Path(td) / "bundle.tar.gz"
            proc = subprocess.run(
                [_openssl(), "enc", "-d", "-aes-256-cbc", "-pbkdf2",
                 "-iter", OPENSSL_ITER, "-pass", f"env:{PASSPHRASE_ENV}",
                 "-in", str(bundle)], capture_output=True, timeout=120)
            if proc.returncode != 0:
                raise EscrowError("cannot decrypt (wrong passphrase or corrupt "
                                  "bundle) — fail-closed")
            plain.write_bytes(proc.stdout)
            extract = Path(td) / "x"
            with tarfile.open(plain, "r:gz") as tar:
                tar.extractall(extract)
            manifest = json.loads((extract / "manifest.json").read_text(
                encoding="utf-8"))
            problems: list[str] = []
            for rel, want in (manifest.get("files") or {}).items():
                f = extract / rel
                if not f.exists():
                    problems.append(f"missing from bundle: {rel}")
                elif _sha256(f.read_bytes()) != want:
                    problems.append(f"hash mismatch (tampered or corrupt): {rel}")
            # Drift: a rescue manual describing an older system is a stale
            # bundle, and stale here means failed.
            repo_recovery = paths.repo_root() / "RECOVERY.md"
            bundled = manifest.get("files", {}).get("RECOVERY.md")
            if repo_recovery.exists() and bundled:
                if _sha256(repo_recovery.read_bytes()) != bundled:
                    problems.append(
                        "drift: bundled RECOVERY.md differs from the repo's "
                        "current one — the bundle is stale, rebuild it")
            ok = not problems
            events.emit("escrow.verified", events.Actor(kind="system", id="escrow"),
                        events.Subject(kind="artifact", id=str(bundle)),
                        {"ok": ok, "built_at": manifest.get("built_at"),
                         "problems": problems[:5]},
                        trust="internal")
            for p in problems:
                print(f"[FAIL] {p}")
            print(f"escrow verify: {'GREEN' if ok else 'RED'} | built_at "
                  f"{manifest.get('built_at')} | {len(manifest.get('files', {}))} files")
            return 0 if ok else 1
    except EscrowError as exc:
        print(f"escrow: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"escrow: cannot verify: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="escrow.py",
                                description="Encrypted §11.2 recovery bundle")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build + encrypt the bundle")
    b.add_argument("--out", help="output path (default: state/archive/escrow/)")
    b.add_argument("--by", default="escrow")
    v = sub.add_parser("verify", help="decrypt + check hashes + check drift")
    v.add_argument("bundle")
    args = p.parse_args(argv)
    return cmd_build(args) if args.cmd == "build" else cmd_verify(args)


if __name__ == "__main__":
    raise SystemExit(main())
