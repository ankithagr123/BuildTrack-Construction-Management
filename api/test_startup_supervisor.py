import unittest
from pathlib import Path
from unittest.mock import patch

from api import startup_supervisor


class StartupSupervisorTests(unittest.TestCase):
    def test_supervisor_is_locked_to_configured_buildtrack_port(self):
        self.assertEqual(startup_supervisor.EXPECTED_PORT, 5001)
        self.assertEqual(startup_supervisor.Config.SERVER_PORT, 5001)
        self.assertEqual(startup_supervisor.HEALTH_URL, "http://127.0.0.1:5001/api/health")

    def test_health_check_requires_successful_buildtrack_identity(self):
        class HealthyResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"service":"BuildTrack","status":"ok"}'

        class HealthyOpener:
            def open(self, *_args, **_kwargs):
                return HealthyResponse()

        with patch.object(startup_supervisor, "build_opener", return_value=HealthyOpener()):
            self.assertTrue(startup_supervisor._healthy())
        with patch.object(startup_supervisor, "build_opener", side_effect=OSError("offline")):
            self.assertFalse(startup_supervisor._healthy())

    def test_app_launcher_uses_the_canonical_5001_origin(self):
        with (
            patch.dict("os.environ", {"LOCALAPPDATA": r"C:\Chrome", "ProgramFiles": r"C:\Program Files"}, clear=False),
            patch.object(Path, "is_file", return_value=True),
            patch.object(startup_supervisor.subprocess, "Popen") as popen,
            patch.object(startup_supervisor, "_log"),
        ):
            startup_supervisor._open_installed_app()

        command = popen.call_args.args[0]
        self.assertIn("--app=http://127.0.0.1:5001", command)
        self.assertNotIn("--app=http://127.0.0.1:5000", command)


if __name__ == "__main__":
    unittest.main()
