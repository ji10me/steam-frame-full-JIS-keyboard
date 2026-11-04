"""Run the shell entry point with local downloads and a recording-only Python."""
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Bootstrap(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        spec = importlib.util.spec_from_file_location("package_jis_setup", ROOT / "tools/package_jis_setup.py")
        package = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(package)
        self.archive, self.digest = package.build(self.root / "assets")
        self.executed = self.root / "executed"
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                        TMPDIR=str(self.root), JIS_BOOTSTRAP_ARCHIVE=str(self.archive),
                        JIS_BOOTSTRAP_EXECUTED=str(self.executed))
        self.script("uname", '#!/bin/sh\ncase "$1" in -s) echo Linux;; -m) echo aarch64;; esac\n')
        self.script("id", '#!/bin/sh\necho 1000\n')
        self.script("curl", '#!' + sys.executable + '\nimport os,shutil,sys\n'
                    'shutil.copyfile(os.environ["JIS_BOOTSTRAP_ARCHIVE"],sys.argv[sys.argv.index("-o")+1])\n')
        self.script("sha256sum", '#!' + sys.executable + '\nimport hashlib,pathlib,sys\n'
                    'digest,name=sys.stdin.read().strip().split("  ",1)\n'
                    'sys.exit(0 if hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()==digest else 1)\n')
        self.script("python3", '#!/bin/sh\nprintf "%s\\n" "$@" > "$JIS_BOOTSTRAP_EXECUTED"\n')

    def script(self, name, content):
        target = self.bin / name
        target.write_text(content)
        target.chmod(0o755)

    def test_verified_bundle_is_invoked_with_arguments_then_cleaned_up(self):
        expected = re.search(r"^expected=([0-9a-f]{64})$", (ROOT / "install-jis.sh").read_text(), re.M).group(1)
        self.assertEqual(expected, self.digest)
        result = subprocess.run(["sh", str(ROOT / "install-jis.sh"), "--desktop", "--chrome"], env=self.env,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        invocation = self.executed.read_text().splitlines()
        self.assertTrue(invocation[0].endswith("/extras/setup_jis.py"))
        self.assertEqual(invocation[1:], ["--desktop", "--chrome"])
        self.assertEqual(list(self.root.glob("frame-jis-bootstrap.*")), [])

    def test_bad_download_does_not_reach_setup(self):
        self.archive.write_bytes(b"corrupt download")
        result = subprocess.run(["sh", str(ROOT / "install-jis.sh"), "--desktop"], env=self.env,
                                text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SHA256", result.stderr)
        self.assertFalse(self.executed.exists())
        self.assertEqual(list(self.root.glob("frame-jis-bootstrap.*")), [])


if __name__ == "__main__":
    unittest.main()
