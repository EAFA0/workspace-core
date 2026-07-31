#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import doc_refs


class DocRefsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "docs").mkdir()
        (self.root / "skills").mkdir()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write(self, relative: str, content: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_parser_ignores_fenced_and_inline_code(self) -> None:
        source = self.write(
            "docs/source.md",
            "\n".join(
                [
                    "[real](target.md)",
                    "`[inline](ignored.md)`",
                    "```markdown",
                    "[fenced](ignored.md)",
                    "```",
                ]
            )
            + "\n",
        )
        links = doc_refs.parse_markdown_links(
            source,
            source.read_text(encoding="utf-8"),
            self.root,
        )
        self.assertEqual([link.destination for link in links], ["target.md"])

    def test_target_move_rewrites_inbound_link_and_keeps_anchor(self) -> None:
        source = self.write(
            "docs/source.md",
            "[target](general/environment/topic.md#details)\n",
        )
        target = self.write(
            "docs/general/environment/topic.md",
            "# Topic\n\n## Details\n",
        )
        destination = self.root / "docs/general/topic.md"
        rewritten, markdown_count, inline_count = doc_refs.rewrite_markdown(
            source,
            source.read_text(encoding="utf-8"),
            target,
            destination,
            self.root,
        )
        self.assertEqual(rewritten, "[target](general/topic.md#details)\n")
        self.assertEqual(markdown_count, 1)
        self.assertEqual(inline_count, 0)

    def test_source_move_rewrites_outbound_link(self) -> None:
        source = self.write(
            "docs/general/environment/source.md",
            "[target](../../repo/target.md)\n",
        )
        self.write("docs/repo/target.md", "# Target\n")
        destination = self.root / "docs/general/source.md"
        rewritten, markdown_count, _ = doc_refs.rewrite_markdown(
            source,
            source.read_text(encoding="utf-8"),
            source,
            destination,
            self.root,
        )
        self.assertEqual(rewritten, "[target](../repo/target.md)\n")
        self.assertEqual(markdown_count, 1)

    def test_inline_placeholder_is_not_a_hard_error(self) -> None:
        source = self.write(
            "docs/source.md",
            "Template: `skills/<skill>/references/<topic>.md`\n",
        )
        parsed = doc_refs.inline_path_target(
            source,
            "skills/<skill>/references/<topic>.md",
            self.root,
        )
        self.assertIsNone(parsed)
        _, masked_codes = doc_refs.protected_markdown(
            source.read_text(encoding="utf-8")
        )
        self.assertEqual(
            masked_codes[0].value,
            "skills/<skill>/references/<topic>.md",
        )


if __name__ == "__main__":
    unittest.main()
