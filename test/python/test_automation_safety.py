import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import autonomous_daemon, git_sync, install_hooks, two_key_gate, verify
from scripts.killswitch_state import read_verdict


def completed(stdout="", stderr="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def temporary_directory():
    return tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)


class VerifyLeaseTests(unittest.TestCase):
    def _check(self, leases_dir, now=None):
        with patch.object(verify, "results", []):
            return verify.check_5_orphaned_leases(leases_dir, now)

    def test_missing_invalid_and_naive_expiry_fail_closed(self):
        now = datetime(2026, 10, 17, tzinfo=timezone.utc)
        invalid_payloads = {
            "missing.json": {"lease_id": "missing-expiry"},
            "invalid.json": {"expires_at": "not-a-timestamp"},
            "naive.json": {"expires_at": "2026-10-18T00:00:00"},
        }
        for name, payload in invalid_payloads.items():
            with self.subTest(name=name), temporary_directory() as temporary:
                leases_dir = Path(temporary)
                (leases_dir / name).write_text(json.dumps(payload), encoding="utf-8")
                self.assertFalse(self._check(leases_dir, now))

    def test_timezone_aware_future_expiry_passes_and_expired_fails(self):
        now = datetime(2026, 10, 17, tzinfo=timezone.utc)
        with temporary_directory() as temporary:
            leases_dir = Path(temporary)
            future = leases_dir / "future.json"
            future.write_text(json.dumps({"expires_at": "2026-10-18T00:00:00+00:00"}), encoding="utf-8")
            self.assertTrue(self._check(leases_dir, now))
            future.unlink()
            expired = leases_dir / "expired.json"
            expired.write_text(json.dumps({"expires_at": "2026-10-16T00:00:00+00:00"}), encoding="utf-8")
            self.assertFalse(self._check(leases_dir, now))

    def test_sensitive_lease_paths_are_rejected_without_reading_contents(self):
        with temporary_directory() as temporary:
            leases_dir = Path(temporary)
            sensitive = leases_dir / "credentials.json"
            sensitive.write_text("secret sentinel must never be read", encoding="utf-8")
            original_read_text = Path.read_text

            def guarded_read_text(path, *args, **kwargs):
                if Path(path) == sensitive:
                    raise AssertionError("sensitive lease content was read")
                return original_read_text(path, *args, **kwargs)

            with patch.object(Path, "read_text", new=guarded_read_text):
                self.assertFalse(self._check(leases_dir))

    def test_symlinked_leases_directory_is_rejected_before_listing(self):
        with temporary_directory() as temporary:
            leases_dir = Path(temporary)
            original_is_symlink = Path.is_symlink

            def mark_directory_as_symlink(path):
                if Path(path) == leases_dir:
                    return True
                return original_is_symlink(path)

            with (
                patch.object(Path, "is_symlink", new=mark_directory_as_symlink),
                patch.object(Path, "glob", side_effect=AssertionError("symlinked lease directory was traversed")),
            ):
                self.assertFalse(self._check(leases_dir))

    def test_symlinked_state_parent_is_rejected_before_listing(self):
        with temporary_directory() as temporary:
            state_dir = Path(temporary) / "state"
            leases_dir = state_dir / "leases"
            original_is_symlink = Path.is_symlink

            def mark_parent_as_symlink(path):
                if Path(path) == state_dir:
                    return True
                return original_is_symlink(path)

            with (
                patch.object(Path, "is_symlink", new=mark_parent_as_symlink),
                patch.object(Path, "glob", side_effect=AssertionError("symlinked lease parent was traversed")),
            ):
                self.assertFalse(self._check(leases_dir))


class VerifyNpmCommandTests(unittest.TestCase):
    def test_npm_commands_are_argv_on_posix_and_fixed_cmd_invocations_on_windows(self):
        self.assertEqual(verify.npm_command("test", windows=False), ["npm", "test"])
        self.assertEqual(verify.npm_command("build", windows=False), ["npm", "run", "build"])
        self.assertEqual(
            verify.npm_command("test", windows=True),
            ["cmd.exe", "/d", "/s", "/c", "npm test"],
        )
        self.assertEqual(
            verify.npm_command("build", windows=True),
            ["cmd.exe", "/d", "/s", "/c", "npm run build"],
        )
        with self.assertRaises(ValueError):
            verify.npm_command("test && arbitrary-command", windows=True)


class KillSwitchTests(unittest.TestCase):
    def test_verification_failure_log_includes_exit_code_stdout_and_stderr(self):
        messages = []
        with (
            patch.object(autonomous_daemon, "log", side_effect=messages.append),
            patch.object(
                autonomous_daemon.subprocess,
                "run",
                return_value=completed(stdout="stdout diagnostic", stderr="stderr diagnostic", returncode=7),
            ),
        ):
            self.assertFalse(autonomous_daemon.run_verification())
        failure = next(message for message in messages if "Verification FAILED" in message)
        self.assertIn("code 7", failure)
        self.assertIn("stdout diagnostic", failure)
        self.assertIn("stderr diagnostic", failure)

    def test_shared_parser_falls_back_only_when_primary_is_missing(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            state = root / "STATE.json"
            kill = root / "killswitch.json"
            state.write_text(json.dumps({"kill_switch": {"verdict": "running"}}), encoding="utf-8")
            self.assertEqual(read_verdict(kill, state), "running")
            kill.write_text(json.dumps({"verdict": "paused"}), encoding="utf-8")
            self.assertEqual(read_verdict(kill, state), "paused")
            kill.write_text("{broken", encoding="utf-8")
            self.assertEqual(read_verdict(kill, state), "stopped")
            kill.write_text(json.dumps({"verdict": "unknown"}), encoding="utf-8")
            self.assertEqual(read_verdict(kill, state), "stopped")

    def test_primary_stop_overrides_running_fallback_for_daemon_and_verify(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            state_dir = root / "state"
            state_dir.mkdir()
            (state_dir / "STATE.json").write_text(
                json.dumps({"kill_switch": {"verdict": "running"}}), encoding="utf-8"
            )
            (state_dir / "killswitch.json").write_text(
                json.dumps({"verdict": "stopped"}), encoding="utf-8"
            )
            with patch.object(autonomous_daemon, "STATE_DIR", state_dir):
                self.assertEqual(autonomous_daemon.get_killswitch_verdict(), "stopped")
            with patch.object(verify, "PROJECT_ROOT", root), patch.object(verify, "results", []):
                self.assertFalse(verify.check_2_kill_switch())

    def test_daemon_treats_paused_state_as_active(self):
        with temporary_directory() as temporary:
            state_dir = Path(temporary)
            (state_dir / "STATE.json").write_text(
                json.dumps({"kill_switch": {"verdict": "paused"}}), encoding="utf-8"
            )
            with patch.object(autonomous_daemon, "STATE_DIR", state_dir):
                self.assertTrue(autonomous_daemon.is_killswitch_active())

    def test_daemon_fails_closed_on_corrupt_state(self):
        with temporary_directory() as temporary:
            state_dir = Path(temporary)
            (state_dir / "STATE.json").write_text("{broken", encoding="utf-8")
            with patch.object(autonomous_daemon, "STATE_DIR", state_dir):
                self.assertTrue(autonomous_daemon.is_killswitch_active())

    def test_verify_fails_closed_when_primary_switch_is_corrupt(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            state = root / "state"
            state.mkdir()
            (state / "killswitch.json").write_text("{broken", encoding="utf-8")
            (state / "STATE.json").write_text(
                json.dumps({"kill_switch": {"verdict": "running"}}), encoding="utf-8"
            )
            with patch.object(verify, "PROJECT_ROOT", root), patch.object(verify, "results", []):
                self.assertFalse(verify.check_2_kill_switch())

    def test_daemon_exits_on_stopped_switch_without_verification(self):
        with temporary_directory() as temporary:
            state_dir = Path(temporary)
            (state_dir / "STATE.json").write_text(
                json.dumps({"kill_switch": {"verdict": "stopped"}}), encoding="utf-8"
            )
            written = []
            with (
                patch.object(autonomous_daemon, "STATE_DIR", state_dir),
                patch.object(autonomous_daemon, "get_file_snapshot", return_value={}),
                patch.object(autonomous_daemon, "write_daemon_status", side_effect=lambda s: written.append(dict(s))),
                patch.object(autonomous_daemon, "log"),
                patch.object(autonomous_daemon.time, "sleep"),
                patch.object(autonomous_daemon, "run_verification") as verify_run,
            ):
                self.assertEqual(autonomous_daemon.main(["--poll-interval", "0"]), 0)
            verify_run.assert_not_called()
            self.assertEqual(written[-1]["daemon_status"], "stopped_by_killswitch")

    def test_daemon_keeps_paused_status_until_stopped(self):
        written = []
        with (
            patch.object(autonomous_daemon, "get_killswitch_verdict", side_effect=["paused", "stopped"]),
            patch.object(autonomous_daemon, "get_file_snapshot", return_value={}),
            patch.object(autonomous_daemon, "write_daemon_status", side_effect=lambda s: written.append(dict(s))),
            patch.object(autonomous_daemon, "log"),
            patch.object(autonomous_daemon.time, "sleep"),
            patch.object(autonomous_daemon, "run_verification") as verify_run,
        ):
            self.assertEqual(autonomous_daemon.main(["--poll-interval", "0"]), 0)
        verify_run.assert_not_called()
        self.assertIn("paused_by_killswitch", [item["daemon_status"] for item in written])
        self.assertEqual(written[-1]["daemon_status"], "stopped_by_killswitch")

    def test_daemon_records_sync_time_only_after_success(self):
        for sync_result, expected in ((True, True), (False, False)):
            with self.subTest(sync_result=sync_result):
                written = []
                snapshots = iter([{}, {"changed.py": 1}])
                sleeps = iter([None, KeyboardInterrupt])

                def sleep_once(_):
                    value = next(sleeps)
                    if value is KeyboardInterrupt:
                        raise KeyboardInterrupt

                with (
                    patch.object(autonomous_daemon, "get_killswitch_verdict", return_value="running"),
                    patch.object(autonomous_daemon, "get_file_snapshot", side_effect=lambda: next(snapshots)),
                    patch.object(autonomous_daemon, "write_daemon_status", side_effect=lambda s: written.append(dict(s))),
                    patch.object(autonomous_daemon, "log"),
                    patch.object(autonomous_daemon.time, "sleep", side_effect=sleep_once),
                    patch.object(autonomous_daemon, "run_verification", return_value=True),
                    patch.object(autonomous_daemon, "run_git_sync", return_value=sync_result) as sync_run,
                ):
                    self.assertEqual(
                        autonomous_daemon.main([
                            "--poll-interval", "0", "--debounce", "0", "--auto-sync",
                            "--push-target", "origin:codex/safe-target",
                        ]),
                        0,
                    )
                sync_run.assert_called_once_with("origin:codex/safe-target")
                has_synced_at = any("last_synced_at" in item for item in written)
                self.assertEqual(has_synced_at, expected)

    def test_daemon_stops_before_sync_when_kill_switch_changes_during_verification(self):
        with temporary_directory() as temporary:
            state_dir = Path(temporary)
            state_file = state_dir / "STATE.json"
            state_file.write_text(
                json.dumps({"kill_switch": {"verdict": "running"}}), encoding="utf-8"
            )
            written = []
            snapshots = iter([{}, {"changed.py": 1}])

            def verification_passes_after_stop():
                state_file.write_text(
                    json.dumps({"kill_switch": {"verdict": "stopped"}}), encoding="utf-8"
                )
                return True

            with (
                patch.object(autonomous_daemon, "STATE_DIR", state_dir),
                patch.object(autonomous_daemon, "get_file_snapshot", side_effect=lambda: next(snapshots)),
                patch.object(autonomous_daemon, "write_daemon_status", side_effect=lambda s: written.append(dict(s))),
                patch.object(autonomous_daemon, "log"),
                patch.object(autonomous_daemon.time, "sleep"),
                patch.object(autonomous_daemon, "run_verification", side_effect=verification_passes_after_stop),
                patch.object(autonomous_daemon, "run_git_sync") as sync_run,
            ):
                self.assertEqual(
                    autonomous_daemon.main([
                        "--poll-interval", "0", "--debounce", "0", "--auto-sync",
                        "--push-target", "origin:codex/safe-target",
                    ]),
                    0,
                )

            sync_run.assert_not_called()
            self.assertEqual(written[-1]["daemon_status"], "stopped_by_killswitch")


class GitSyncTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.root = Path(self.temporary.name)
        state_dir = self.root / "state"
        state_dir.mkdir()
        (state_dir / "STATE.json").write_text(
            json.dumps({"kill_switch": {"verdict": "running"}}), encoding="utf-8"
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_sync_requires_explicit_target_without_running_git(self):
        with patch.object(git_sync.subprocess, "run") as run:
            self.assertNotEqual(git_sync.sync(root=self.root), 0)
        run.assert_not_called()

    def test_sync_rejects_protected_branch_target_without_running_git(self):
        with patch.object(git_sync.subprocess, "run") as run:
            self.assertNotEqual(git_sync.sync("origin:main", root=self.root), 0)
        run.assert_not_called()

    def test_sync_fetch_failure_stops_before_verification_or_push(self):
        calls = []

        def fake_run(command, **kwargs):
            calls.append((command, kwargs))
            if command[:2] == ["git", "check-ref-format"]:
                return completed()
            return completed(stderr="fetch failed", returncode=1)

        with patch.object(git_sync.subprocess, "run", side_effect=fake_run):
            self.assertNotEqual(git_sync.sync("origin:codex/safe-target", root=self.root), 0)
        self.assertEqual(len(calls), 2)
        self.assertIn("fetch", calls[1][0])
        self.assertFalse(calls[1][1].get("shell", True))

    def test_sync_pushes_only_to_the_explicit_nonprotected_target(self):
        calls = []

        def fake_run(command, **kwargs):
            calls.append((command, kwargs))
            return completed()

        with patch.object(git_sync.subprocess, "run", side_effect=fake_run):
            self.assertEqual(git_sync.sync("origin:codex/safe-target", root=self.root), 0)
        push = next(command for command, _ in calls if command[:2] == ["git", "push"])
        self.assertEqual(push, ["git", "push", "origin", "HEAD:refs/heads/codex/safe-target"])
        self.assertFalse(any(command[:2] == ["git", "add"] for command, _ in calls))
        self.assertTrue(all(kwargs.get("shell") is False for _, kwargs in calls))

    def test_sync_rejects_git_invalid_branch_before_fetch(self):
        calls = []

        def fake_run(command, **kwargs):
            calls.append(command)
            return completed(returncode=1, stderr="invalid branch")

        with patch.object(git_sync.subprocess, "run", side_effect=fake_run):
            self.assertNotEqual(git_sync.sync("origin:codex/bad?", root=self.root), 0)
        self.assertEqual(len(calls), 1)
        self.assertIn("check-ref-format", calls[0])

    def test_sync_cli_requires_a_push_target(self):
        with self.assertRaises(SystemExit) as error:
            git_sync.main([])
        self.assertEqual(error.exception.code, 2)

    def test_sync_does_not_stage_dirty_files_and_fails(self):
        calls = []

        def fake_run(command, **kwargs):
            calls.append(command)
            if command[:2] == ["git", "check-ref-format"]:
                return completed()
            if command[:2] == ["git", "fetch"]:
                return completed()
            if command[:3] == ["git", "status", "--porcelain"]:
                return completed(stdout=" M private.txt\n")
            return completed()

        with patch.object(git_sync.subprocess, "run", side_effect=fake_run):
            self.assertNotEqual(git_sync.sync("origin:codex/safe-target", root=self.root), 0)
        self.assertFalse(any(command[:2] == ["git", "add"] for command in calls))
        self.assertFalse(any(command[:2] == ["git", "push"] for command in calls))

    def test_sync_fails_verification_and_push_errors(self):
        for failed_stage in ("verify", "push"):
            with self.subTest(failed_stage=failed_stage):
                calls = []

                def fake_run(command, **kwargs):
                    calls.append(command)
                    if command[:2] == ["git", "check-ref-format"]:
                        return completed()
                    if command[:2] == ["git", "fetch"]:
                        return completed()
                    if command[:3] == ["git", "status", "--porcelain"]:
                        return completed()
                    if "verify.py" in str(command):
                        return completed(returncode=1 if failed_stage == "verify" else 0)
                    if command[:2] == ["git", "push"]:
                        return completed(returncode=1 if failed_stage == "push" else 0)
                    return completed()

                with patch.object(git_sync.subprocess, "run", side_effect=fake_run):
                    self.assertNotEqual(
                        git_sync.sync("origin:codex/safe-target", root=self.root), 0
                    )
                if failed_stage == "verify":
                    self.assertFalse(any(command[:2] == ["git", "push"] for command in calls))

    def test_sync_rechecks_kill_switch_after_verification_and_before_push(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            state_dir = root / "state"
            state_dir.mkdir()
            state_file = state_dir / "STATE.json"
            state_file.write_text(
                json.dumps({"kill_switch": {"verdict": "running"}}), encoding="utf-8"
            )
            calls = []

            def fake_run(command, **kwargs):
                calls.append(command)
                if "verify.py" in str(command):
                    state_file.write_text(
                        json.dumps({"kill_switch": {"verdict": "stopped"}}), encoding="utf-8"
                    )
                if command[:3] == ["git", "status", "--porcelain"]:
                    return completed(stdout="")
                return completed()

            with patch.object(git_sync.subprocess, "run", side_effect=fake_run):
                self.assertNotEqual(git_sync.sync("origin:codex/safe-target", root=root), 0)

            self.assertFalse(any(command[:2] == ["git", "push"] for command in calls))


class HookInstallerTests(unittest.TestCase):
    def test_installer_creates_hooks_that_run_two_key_gate(self):
        with temporary_directory() as temporary:
            hooks = Path(temporary)
            self.assertEqual(install_hooks.install_hooks(hooks), 0)
            for name in ("pre-commit", "pre-push"):
                content = (hooks / name).read_text(encoding="utf-8")
                self.assertIn("scripts/two_key_gate.py run", content)

    def test_installer_refuses_custom_hook_without_overwriting_it(self):
        with temporary_directory() as temporary:
            hooks = Path(temporary)
            custom = hooks / "pre-commit"
            custom.write_text("#!/bin/sh\necho custom\n", encoding="utf-8")
            before = custom.read_text(encoding="utf-8")
            self.assertNotEqual(install_hooks.install_hooks(hooks), 0)
            self.assertEqual(custom.read_text(encoding="utf-8"), before)
            self.assertFalse((hooks / "pre-push").exists())

    def test_installer_does_not_trust_a_generic_two_key_marker(self):
        with temporary_directory() as temporary:
            hooks = Path(temporary)
            custom = hooks / "pre-commit"
            custom.write_text("#!/bin/sh\n# Marzneshin Agent OS — Two-Key reviewer hook\necho custom\n", encoding="utf-8")
            before = custom.read_text(encoding="utf-8")
            self.assertNotEqual(install_hooks.install_hooks(hooks), 0)
            self.assertEqual(custom.read_text(encoding="utf-8"), before)

    def test_installer_upgrades_a_legacy_managed_hook(self):
        with temporary_directory() as temporary:
            hooks = Path(temporary)
            (hooks / "pre-commit").write_text(
                "#!/bin/sh\n# Marzneshin Agent OS — Two-Key Pre-Commit Gate\npython scripts/verify.py\n",
                encoding="utf-8",
            )
            self.assertEqual(install_hooks.install_hooks(hooks), 0)
            self.assertIn("scripts/two_key_gate.py run", (hooks / "pre-commit").read_text(encoding="utf-8"))


class TwoKeyGateTests(unittest.TestCase):
    def test_key2_audits_tracked_staged_and_untracked_content(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            (root / "src").mkdir()
            (root / "src" / "untracked.py").write_text("console.log('pass')\n", encoding="utf-8")
            calls = []

            def fake_run(command, **kwargs):
                calls.append((command, kwargs))
                if command[:2] == ["git", "status"]:
                    return completed(stdout="M  src/staged.py\0?? src/untracked.py\0")
                if command[:2] == ["git", "rev-parse"]:
                    return completed(stdout="a" * 40 + "\n")
                if command[:2] == ["git", "diff"]:
                    if "--name-only" in command:
                        return completed(stdout="src/staged.py\0")
                    return completed(stdout=(
                        "diff --git a/src/staged.py b/src/staged.py\n"
                        "+++ b/src/staged.py\n"
                        "+console.log('pass')\n"
                    ))
                return completed(returncode=1, stderr="unexpected git command")

            with (
                patch.object(two_key_gate, "PROJECT_ROOT", root),
                patch.object(two_key_gate.subprocess, "run", side_effect=fake_run),
            ):
                result = two_key_gate.run_key2("HEAD")
            self.assertFalse(result["passed"])
            self.assertTrue(any("staged.py" in violation for violation in result["violations"]))
            self.assertTrue(any("untracked.py" in violation for violation in result["violations"]))
            self.assertTrue(all(kwargs.get("shell") is False for _, kwargs in calls))

    def test_key2_fails_on_invalid_ref_or_git_error(self):
        def fake_run(command, **kwargs):
            if command[:2] == ["git", "status"]:
                return completed()
            return completed(returncode=128, stderr="invalid ref")

        with patch.object(two_key_gate.subprocess, "run", side_effect=fake_run):
            result = two_key_gate.run_key2("bad ref")
        self.assertFalse(result["passed"])

    def test_key2_rejects_empty_ref_before_calling_git(self):
        with patch.object(two_key_gate.subprocess, "run", return_value=completed()) as run:
            result = two_key_gate.run_key2("")
        self.assertFalse(result["passed"])
        run.assert_not_called()

    def test_key2_refuses_sensitive_paths_before_reading_file_contents(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            secret = root / ".env"
            secret.write_text("API_KEY=do-not-read-this-secret\n", encoding="utf-8")
            credential = root / "credential-store" / "credentials.json"
            credential.parent.mkdir()
            credential.write_text("do-not-read-credential\n", encoding="utf-8")
            private_key = root / ".ssh" / "id_ed25519"
            private_key.parent.mkdir()
            private_key.write_text("do-not-read-private-key\n", encoding="utf-8")
            calls = []
            reads = []
            original_read_text = Path.read_text

            def fake_run(command, **kwargs):
                calls.append(command)
                if command[:2] == ["git", "status"]:
                    return completed(
                        stdout="?? .env\0?? credential-store/credentials.json\0?? .ssh/id_ed25519\0"
                    )
                if command[:2] == ["git", "rev-parse"]:
                    return completed(stdout="a" * 40 + "\n")
                if command[:2] == ["git", "diff"]:
                    return completed()
                if command[:2] == ["git", "ls-files"]:
                    return completed(stdout=".env\0")
                return completed(returncode=1, stderr="unexpected git command")

            def track_read_text(path, *args, **kwargs):
                reads.append(Path(path))
                return original_read_text(path, *args, **kwargs)

            with (
                patch.object(two_key_gate, "PROJECT_ROOT", root),
                patch.object(two_key_gate.subprocess, "run", side_effect=fake_run),
                patch.object(Path, "read_text", new=track_read_text),
            ):
                result = two_key_gate.run_key2("HEAD")
            self.assertFalse(result["passed"])
            self.assertEqual(reads, [])
            self.assertTrue(any(".env" in item for item in result["violations"]))
            self.assertTrue(any("credentials.json" in item for item in result["violations"]))
            self.assertTrue(any("id_ed25519" in item for item in result["violations"]))
            self.assertFalse(any("do-not-read-this-secret" in item for item in result["violations"]))
            self.assertEqual(len(calls), 1)

    def test_key2_refuses_untracked_symlinks_before_reading_targets(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            alias = root / "ordinary-name.txt"
            alias.write_text("secret sentinel must never be read", encoding="utf-8")
            calls = []
            reads = []
            original_is_symlink = Path.is_symlink

            def fake_run(command, **kwargs):
                calls.append(command)
                if command[:2] == ["git", "status"]:
                    return completed(stdout="?? ordinary-name.txt\0")
                if command[:2] == ["git", "rev-parse"]:
                    return completed(stdout="a" * 40 + "\n")
                if command[:2] == ["git", "diff"]:
                    return completed()
                return completed(returncode=1, stderr="unexpected git command")

            def mark_alias_as_symlink(path):
                if Path(path) == alias:
                    return True
                return original_is_symlink(path)

            def reject_read(path, *args, **kwargs):
                reads.append(Path(path))
                raise AssertionError("untracked symlink target was read")

            with (
                patch.object(two_key_gate, "PROJECT_ROOT", root),
                patch.object(two_key_gate.subprocess, "run", side_effect=fake_run),
                patch.object(Path, "is_symlink", new=mark_alias_as_symlink),
                patch.object(Path, "read_text", new=reject_read),
            ):
                result = two_key_gate.run_key2("HEAD")
            self.assertFalse(result["passed"])
            self.assertEqual(reads, [])
            self.assertTrue(any("ordinary-name.txt" in item for item in result["violations"]))
            self.assertEqual(len(calls), 4)

    def test_key2_uses_path_only_diff_to_exclude_sensitive_committed_files(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            calls = []
            reads = []
            original_read_text = Path.read_text

            def fake_run(command, **kwargs):
                calls.append(command)
                if command[:2] == ["git", "status"]:
                    return completed()
                if command[:2] == ["git", "rev-parse"]:
                    return completed(stdout="a" * 40 + "\n")
                if command[:2] == ["git", "diff"] and "--name-only" in command:
                    return completed(stdout="private.pem\0")
                if command[:2] == ["git", "diff"]:
                    return completed(stdout="must-not-be-read\n")
                return completed(returncode=1, stderr="unexpected git command")

            def track_read_text(path, *args, **kwargs):
                reads.append(Path(path))
                return original_read_text(path, *args, **kwargs)

            with (
                patch.object(two_key_gate, "PROJECT_ROOT", root),
                patch.object(two_key_gate.subprocess, "run", side_effect=fake_run),
                patch.object(Path, "read_text", new=track_read_text),
            ):
                result = two_key_gate.run_key2("HEAD~1")
        self.assertFalse(result["passed"])
        self.assertEqual(reads, [])
        self.assertTrue(any("private.pem" in item for item in result["violations"]))
        self.assertFalse(any("must-not-be-read" in item for item in result["violations"]))
        self.assertFalse(any("--unified=0" in command for command in calls))

    def test_key2_allows_env_example_without_exposing_other_env_files(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            (root / ".env.example").write_text("API_KEY=replace-me\n", encoding="utf-8")

            def fake_run(command, **kwargs):
                if command[:2] == ["git", "status"]:
                    return completed(stdout="?? .env.example\0")
                if command[:2] == ["git", "rev-parse"]:
                    return completed(stdout="a" * 40 + "\n")
                if command[:2] == ["git", "diff"]:
                    return completed()
                if command[:2] == ["git", "ls-files"]:
                    return completed(stdout=".env.example\0")
                return completed(returncode=1, stderr="unexpected git command")

            with (
                patch.object(two_key_gate, "PROJECT_ROOT", root),
                patch.object(two_key_gate.subprocess, "run", side_effect=fake_run),
            ):
                result = two_key_gate.run_key2("HEAD")
        self.assertTrue(result["passed"])

    def test_key2_fails_when_audit_has_no_changes(self):
        with temporary_directory() as temporary:
            root = Path(temporary)

            def fake_run(command, **kwargs):
                if command[:2] == ["git", "status"]:
                    return completed()
                if command[:2] == ["git", "rev-parse"]:
                    return completed(stdout="a" * 40 + "\n")
                if command[:2] == ["git", "diff"]:
                    return completed()
                return completed(returncode=1)

            with (
                patch.object(two_key_gate, "PROJECT_ROOT", root),
                patch.object(two_key_gate.subprocess, "run", side_effect=fake_run),
            ):
                result = two_key_gate.run_key2("HEAD")
        self.assertFalse(result["passed"])
        self.assertEqual(result.get("note"), "empty audit")

    def test_key2_cli_returns_failure_exit_code(self):
        with patch.object(two_key_gate, "run_key2", return_value={"passed": False, "key": "key2_adversarial"}):
            self.assertEqual(two_key_gate.main(["key2", "HEAD"]), 1)

    def test_event_writer_uses_unique_files_when_timestamps_and_ids_collide(self):
        from datetime import datetime, timezone

        fixed_time = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)
        with temporary_directory() as temporary:
            with patch.object(two_key_gate.uuid, "uuid4", return_value=SimpleNamespace(hex="same")):
                first = two_key_gate.write_event(Path(temporary), {}, fixed_time, True)
                second = two_key_gate.write_event(Path(temporary), {}, fixed_time, True)
            self.assertNotEqual(first, second)
            self.assertEqual(len(list(Path(temporary).glob("*.json"))), 2)


if __name__ == "__main__":
    unittest.main()
