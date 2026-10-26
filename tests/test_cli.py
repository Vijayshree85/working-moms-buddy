"""Exercise human-facing feedback and resume using actual terminal processes."""

from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from buddy.storage import Store


def practice_process(directory, user_input, *extra):
    return subprocess.run([sys.executable, "-X", "utf8", "-m", "buddy", "run", "--practice",
                           "--data-dir", directory, *extra], input=user_input,
                          text=True, encoding="utf-8", capture_output=True, timeout=30)


class TerminalChecks(unittest.TestCase):
    def test_rejection_is_visible_and_creates_no_records(self):
        with TemporaryDirectory() as directory:
            process = practice_process(directory, "2026\nreject\n")
            self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
            self.assertIn("Rejected", process.stdout)
            self.assertEqual(Store(Path(directory) / "family.sqlite3").counts(), (0, 0))

    def test_correct_quit_restart_approve(self):
        with TemporaryDirectory() as directory:
            first = practice_process(directory, "2026\nedit\nConsent is due 2026-11-04\nquit\n")
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            self.assertEqual(first.stdout.count("Proposed content"), 2)
            self.assertIn("Correction received: Consent is due 2026-11-04", first.stdout)
            self.assertIn("Return the consent form: due 2026-11-04", first.stdout)
            self.assertEqual(Store(Path(directory) / "family.sqlite3").counts(), (0, 0))
            session = re.search(r"Session ID: ([a-f0-9-]+)", first.stdout).group(1)
            second = practice_process(directory, "approve\n", "--resume", session)
            self.assertEqual(second.returncode, 0, second.stderr + second.stdout)
            self.assertIn("Saved one notice and 2 tasks", second.stdout)
            store = Store(Path(directory) / "family.sqlite3")
            self.assertEqual(store.counts(), (1, 2))
            consent = next(task for task in store.search_notes("field trip")[0]["tasks"] if "consent" in task["title"])
            self.assertEqual(consent["due_date"], "2026-11-04")


if __name__ == "__main__":
    unittest.main()
