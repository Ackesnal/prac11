"""Check actual Bash scripts with stub commands; no Google Cloud requests."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "requires Linux Bash")
class ShellConfigTests(unittest.TestCase):
    def check_line_endings(self, newline):
        template = (ROOT / "config.env.example").read_text(encoding="utf-8")
        config = template.replace("REPLACE_WITH_YOUR_PROJECT_ID", "test-project-123")
        config = config.replace("REPLACE_WITH_YOUR_GOOGLE_ACCOUNT_EMAIL", "student@example.com")
        for script in ("admin_setup.sh", "deploy.sh", "grant_invoker.sh", "cleanup.sh"):
            with self.subTest(script=script), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                shutil.copyfile(ROOT / script, directory / script)
                (directory / "config.env").write_bytes(config.replace("\n", newline).encode())
                commands = directory / "bin"
                commands.mkdir()
                # Neither setup nor cleanup can reach the real gcloud binary.
                for name, body in (
                    ("gcloud", 'printf "%s\\n" "$@" >> "$CALL_LOG"\n'),
                    ("python", "exit 0\n"),
                ):
                    stub = commands / name
                    stub.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
                    stub.chmod(0o755)
                log = directory / "calls.txt"
                environment = dict(os.environ, PATH=str(commands) + os.pathsep + os.environ["PATH"],
                                   CALL_LOG=str(log))
                result = subprocess.run(["bash", str(directory / script)], env=environment,
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                arguments = log.read_bytes()
                self.assertNotIn(b"\r", arguments)
                self.assertIn(b"test-project-123\n", arguments)
                self.assertNotIn(b"\r", (directory / "config.env").read_bytes())
                if script in ("admin_setup.sh", "deploy.sh"):
                    for identity in ("runtime", "build"):
                        expected = f"infs3208-rag-{identity}@test-project-123.iam.gserviceaccount.com"
                        self.assertIn(expected.encode(), arguments)

    def test_lf_configuration(self):
        self.check_line_endings("\n")

    def test_crlf_configuration(self):
        self.check_line_endings("\r\n")


if __name__ == "__main__":
    unittest.main()
