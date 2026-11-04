"""Regression tests for LWFE 0.1.3 archive session output routing."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lwfe_archive import create_archive
from lwfe_engine import LWFEError, output_path_for, render_sound


class SessionWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp.name) / "LWFE"
        self.project_root.mkdir()
        (self.project_root / "sounds").mkdir()
        (self.project_root / "sounds" / "legacy_master.WAV").write_bytes(b"legacy master")

        self.sound = {
            "id": "session_test",
            "name": "Session routing test",
            "output": "sounds/session_test_LWFE.WAV",
            "canvas": {
                "duration": 0.08,
                "sample_rate": 22050,
                "master_gain": 0.8,
                "target_peak": 0.8,
            },
            "strokes": [
                {
                    "brush": "voice",
                    "start": 0.0,
                    "duration": 0.07,
                    "contour": [[0.0, 220.0], [1.0, 180.0]],
                    "pressure": [[0.0, 0.0], [0.1, 1.0], [1.0, 0.0]],
                }
            ],
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_render_and_output_lookup_use_session_archive(self) -> None:
        session = create_archive(self.project_root, "0.1.3")

        expected = session / "sounds" / "session_test_LWFE.WAV"
        self.assertEqual(output_path_for(self.sound, self.project_root, session), expected)

        rendered = render_sound(self.sound, self.project_root, output_root=session)
        self.assertEqual(rendered, expected)
        self.assertTrue(expected.is_file())
        self.assertFalse((self.project_root / "sounds" / "session_test_LWFE.WAV").exists())

    def test_archive_copies_legacy_sounds_but_new_render_stays_in_archive(self) -> None:
        session = create_archive(self.project_root, "0.1.3")
        self.assertTrue((session / "sounds" / "legacy_master.WAV").is_file())

        render_sound(self.sound, self.project_root, output_root=session)

        self.assertTrue((session / "sounds" / "session_test_LWFE.WAV").is_file())
        self.assertEqual(
            (self.project_root / "sounds" / "legacy_master.WAV").read_bytes(),
            b"legacy master",
        )
        self.assertFalse((self.project_root / "sounds" / "session_test_LWFE.WAV").exists())

    def test_existing_archive_is_never_overwritten(self) -> None:
        first = create_archive(self.project_root, "0.1.3")
        marker = first / "sounds" / "do_not_overwrite.txt"
        marker.write_text("preserve me", encoding="utf-8")

        second = create_archive(self.project_root, "0.1.3")

        self.assertNotEqual(first, second)
        self.assertEqual(marker.read_text(encoding="utf-8"), "preserve me")

    def test_output_cannot_escape_session_archive(self) -> None:
        unsafe = dict(self.sound)
        unsafe["output"] = "../outside.wav"
        session = create_archive(self.project_root, "0.1.3")

        with self.assertRaises(LWFEError):
            output_path_for(unsafe, self.project_root, session)


if __name__ == "__main__":
    unittest.main()
