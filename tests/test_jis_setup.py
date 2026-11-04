"""Exercise setup/rollback against a temporary home; never touch a live bus."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("setup_jis", ROOT / "extras/setup_jis.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class Setup(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.commands = []
        self.enabled = set()
        self.ime = {"typing-method": "1", "input-mode": "2"}
        self.fail_command = None
        self.installer = setup.Installer(self.home, ROOT / "extras", self.command)
        self.release = self.installer.release
        binary = self.release / "bin/framekeyboard"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"test binary: never execute")
        defaults = self.release / "share/framekeyboard/config/default.json"
        defaults.parent.mkdir(parents=True)
        defaults.write_text((ROOT / "config/default.json").read_text())
        self.config = self.home / ".config/framekeyboard/config.json"
        self.config.parent.mkdir(parents=True)
        self.original = json.dumps({"schema_version": 1, "active": {"layout": "old", "language": "old", "theme": "midnight"},
                                    "unrelated_preference": {"keep": True}, "favorites": [{"id": "personal"}]})
        self.config.write_text(self.original)

    def command(self, args, **kwargs):
        self.commands.append(args)
        if self.fail_command and self.fail_command(args):
            raise subprocess.CalledProcessError(2, args)
        if args[:3] == ["systemctl", "--user", "is-enabled"]:
            if args[3] not in self.enabled:
                raise subprocess.CalledProcessError(1, args)
            return subprocess.CompletedProcess(args, 0, "enabled\n")
        if args[:3] == ["systemctl", "--user", "is-active"]:
            raise subprocess.CalledProcessError(3, args)
        if args[:3] == ["systemctl", "--user", "enable"]:
            self.enabled.add(args[3])
        if args[:3] == ["systemctl", "--user", "disable"]:
            self.enabled.discard(args[3])
        if args[0] == "gsettings":
            if args[1] == "get":
                return subprocess.CompletedProcess(args, 0, self.ime[args[3]] + "\n")
            self.ime[args[3]] = args[4]
        return subprocess.CompletedProcess(args, 0, "Full Keyboard for Steam Frame 0.8.2\n" if args[-1] == "--help" else "")

    def test_desktop_preserves_other_preferences_and_leaves_autostart_off(self):
        self.installer.install("desktop")
        prefs = json.loads(self.config.read_text())
        self.assertEqual(prefs["unrelated_preference"], {"keep": True})
        self.assertEqual(prefs["favorites"], [{"id": "personal"}])
        self.assertEqual(prefs["active"], {"layout": "ja-jis-frame-full", "language": "ja-jis-frame", "theme": "midnight"})
        self.assertFalse(any(command[:3] == ["systemctl", "--user", "enable"] for command in self.commands))
        self.assertFalse(any("install.py" in arg for command in self.commands for arg in command))
        self.assertEqual(self.ime, {"typing-method": "0", "input-mode": "0"})
        recovery = self.installer.state / "restore_setup.py"
        self.assertEqual(recovery.read_bytes(), (ROOT / "extras/setup_jis.py").read_bytes())

    def test_fresh_preferences_are_created_without_launching_ui(self):
        self.config.unlink()
        self.installer.install("desktop")
        self.assertEqual(json.loads(self.config.read_text())["active"]["language"], "ja-jis-frame")
        binary_calls = [args for args in self.commands if args[0].endswith("/bin/framekeyboard")]
        self.assertTrue(binary_calls and all("--check" in args for args in binary_calls))

    def test_validation_failure_restores_files_and_ime(self):
        self.fail_command = lambda args: "--check" in args
        with self.assertRaises(subprocess.CalledProcessError):
            self.installer.install("desktop")
        self.assertEqual(self.config.read_text(), self.original)
        self.assertFalse((self.home / ".local/bin/framekeyboard-toggle").exists())
        self.assertEqual(self.ime, {"typing-method": "1", "input-mode": "2"})
        self.assertEqual(json.loads(self.installer.record.read_text())["status"], "restored")

    def test_unified_failure_rolls_back_after_ime_configuration(self):
        self.fail_command = lambda args: any(arg.endswith("unified-jis/install.py") for arg in args)
        with self.assertRaises(subprocess.CalledProcessError):
            self.installer.install("unified")
        self.assertEqual(self.config.read_text(), self.original)
        self.assertEqual(self.ime, {"typing-method": "1", "input-mode": "2"})

    def test_explicit_restore_retains_later_edits_and_restores_old_symlink(self):
        target = self.home / ".local/bin/framekeyboard-toggle"
        target.parent.mkdir(parents=True)
        target.symlink_to("old-helper")
        self.enabled.add(setup.UNITS[1])
        self.installer.install("desktop")
        self.config.write_text("later edit")
        self.installer.restore()
        self.assertEqual(self.config.read_text(), self.original)
        self.assertTrue(target.is_symlink())
        self.assertEqual(target.readlink(), Path("old-helper"))
        record = json.loads(self.installer.record.read_text())
        after = list((self.installer.state / record["backup"]).glob("after-*/.config/framekeyboard/config.json"))
        self.assertEqual(len(after), 1)
        self.assertEqual(after[0].read_text(), "later edit")
        self.assertIn(setup.UNITS[1], self.enabled)

    def test_chrome_is_untouched_unless_selected_including_restore(self):
        flags = self.home / setup.FILES[-1]
        flags.parent.mkdir(parents=True)
        flags.write_text("--some-preference\n")
        self.installer.install("desktop")
        flags.write_text("changed separately\n")
        self.installer.restore()
        self.assertEqual(flags.read_text(), "changed separately\n")
        self.assertFalse(any(args[0] == "flatpak" for args in self.commands))

    def test_chrome_preserves_flags_and_restores_original(self):
        flags = self.home / setup.FILES[-1]
        flags.parent.mkdir(parents=True)
        flags.write_text("--some-preference\n")
        self.installer.install("desktop", chrome=True)
        self.assertIn("--some-preference\n", flags.read_text())
        self.assertTrue(flags.read_text().endswith("--ozone-platform=x11\n"))
        self.installer.restore()
        self.assertEqual(flags.read_text(), "--some-preference\n")

    def test_platform_check_fails_before_writes(self):
        with patch.object(setup.platform, "system", return_value="Darwin"), self.assertRaises(setup.SetupError):
            self.installer.check("desktop")
        self.assertFalse(self.installer.record.exists())
        self.assertEqual(self.config.read_text(), self.original)

    def test_reject_existing_unified_before_any_command(self):
        (self.home / ".config/framekeyboard-unified-jis").mkdir()
        with patch.object(setup.platform, "system", return_value="Linux"), \
             patch.object(setup.platform, "machine", return_value="aarch64"), \
             patch.object(setup.os, "geteuid", return_value=1000), \
             patch.object(setup.shutil, "which", return_value="/usr/bin/test"), \
             patch.object(Path, "is_file", return_value=True), self.assertRaises(setup.SetupError):
            self.installer.check("unified")
        self.assertEqual(self.commands, [])

    def test_other_version_is_not_downgraded(self):
        def command(args, **kwargs):
            if args[-1] == "--help":
                return subprocess.CompletedProcess(args, 0, "Full Keyboard for Steam Frame 0.14.1\n")
            return self.command(args, **kwargs)
        self.installer.run = command
        with patch.object(setup.platform, "system", return_value="Linux"), \
             patch.object(setup.platform, "machine", return_value="aarch64"), \
             patch.object(setup.os, "geteuid", return_value=1000), \
             patch.object(setup.shutil, "which", return_value="/usr/bin/test"), \
             patch.object(Path, "is_file", return_value=True), \
             patch.object(Path, "glob", return_value=[]), self.assertRaises(setup.SetupError):
            self.installer.check("desktop")
        self.assertEqual(self.config.read_text(), self.original)
        self.assertFalse(self.installer.record.exists())

    def test_snapshot_rejects_tampered_restore_file_list(self):
        self.installer.install("desktop")
        record = json.loads(self.installer.record.read_text())
        record["files"].append("../outside")
        setup.save_json(self.installer.record, record)
        with self.assertRaises(setup.SetupError):
            self.installer.restore()

    def test_atomic_copy_never_writes_through_old_launcher_link(self):
        external = self.home / "other-helper"
        external.write_text("keep this helper")
        target = self.home / ".local/bin/framekeyboard-toggle"
        target.parent.mkdir(parents=True)
        target.symlink_to(external)
        self.installer.install("desktop")
        self.assertFalse(target.is_symlink())
        self.assertEqual(external.read_text(), "keep this helper")
        self.installer.restore()
        self.assertEqual(target.readlink(), external)

    def test_corrupt_download_is_never_extracted_or_executed(self):
        class Response(io.BytesIO):
            def geturl(self):
                return setup.BASE_URL
        with patch.object(setup.urllib.request, "urlopen", return_value=Response(b"corrupt")), self.assertRaises(setup.SetupError):
            setup.download_base(self.home / "base.tar.gz")
        self.assertEqual(self.commands, [])

    def test_unsafe_tar_paths_and_links_leave_no_files(self):
        for name, kind in (("../escape", tarfile.REGTYPE), ("/escape", tarfile.REGTYPE),
                           ("framekeyboard-0.8.2-aarch64/link", tarfile.SYMTYPE)):
            archive = self.home / "bad.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                entry = tarfile.TarInfo(name)
                entry.type = kind
                bundle.addfile(entry)
            destination = self.home / "extract"
            with self.subTest(name=name), self.assertRaises(setup.SetupError):
                setup.extract_base(archive, destination)
            self.assertFalse(destination.exists())

    def test_source_bundle_is_deterministic_and_manifest_matches(self):
        spec = importlib.util.spec_from_file_location("package_jis_setup", ROOT / "tools/package_jis_setup.py")
        package = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(package)
        first, digest = package.build(self.home / "one")
        second, other = package.build(self.home / "two")
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(digest, other)
        with tarfile.open(first) as bundle:
            content = {entry.name.split("/", 1)[1]: bundle.extractfile(entry).read() for entry in bundle}
        manifest = content.pop("MANIFEST.sha256").decode()
        expected = {line.split("  ", 1)[1]: line.split("  ", 1)[0] for line in manifest.splitlines()}
        self.assertEqual(set(expected), set(content))
        for name, data in content.items():
            self.assertEqual(hashlib.sha256(data).hexdigest(), expected[name])
        self.assertIn("LICENSE", content)
        self.assertTrue(all(name in package.FILES or name in ("install.sh", "README.txt") for name in content))
        self.assertFalse(any("__pycache__" in name or name.endswith(".so") for name in content))


if __name__ == "__main__":
    unittest.main()
