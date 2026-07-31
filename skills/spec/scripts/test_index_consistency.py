from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import index_consistency


class ArchitectureIndexConsistencyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary_directory.name)
        self.architecture = self.workspace / "docs" / "architecture"
        self.architecture.mkdir(parents=True)
        (self.architecture / "README.md").write_text(
            "# Architecture Contract\n",
            encoding="utf-8",
        )
        self.target = index_consistency.get_target("architecture")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_index(self, entries: list[str]) -> None:
        lines = [
            "# Architecture Index",
            "",
            "| Owner | 内容 |",
            "|-------|------|",
            *[
                f"| [{entry}](./{entry}) | test |"
                for entry in entries
            ],
            "",
        ]
        (self.architecture / "INDEX.md").write_text(
            "\n".join(lines),
            encoding="utf-8",
        )

    def test_matching_architecture_index_passes(self) -> None:
        (self.architecture / "01-core.md").write_text(
            "# Core\n",
            encoding="utf-8",
        )
        self.write_index(["01-core.md"])
        result = index_consistency.check_target(
            self.target,
            self.workspace,
        )
        self.assertTrue(result["ok"])

    def test_unindexed_architecture_document_is_reported(self) -> None:
        (self.architecture / "01-core.md").write_text(
            "# Core\n",
            encoding="utf-8",
        )
        self.write_index([])
        result = index_consistency.check_target(
            self.target,
            self.workspace,
        )
        self.assertEqual(
            result["on_disk_not_indexed"],
            ["01-core.md"],
        )

    def test_missing_architecture_index_is_reported(self) -> None:
        result = index_consistency.check_target(
            self.target,
            self.workspace,
        )
        self.assertEqual(result["status"], "index_missing")


if __name__ == "__main__":
    unittest.main()
