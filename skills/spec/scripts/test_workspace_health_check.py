#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import redact_secrets
import workspace_health_check


class WorkspaceHealthCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "docs").mkdir()
        (self.root / "skills").mkdir()
        (self.root / "biz-tests").mkdir()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write(self, relative: str, content: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_unknown_docs_owner_is_reported(self) -> None:
        (self.root / "docs" / "temporary-layer").mkdir()
        issues = workspace_health_check.check_docs_layout(self.root)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check, "docs-layout")
        self.assertEqual(issues[0].path, "docs/temporary-layer")

    def test_defined_docs_owners_pass(self) -> None:
        for name in ("architecture", "biz-knowledge", "prd", "repo-knowledge"):
            (self.root / "docs" / name).mkdir()
        self.write("docs/README.md", "# Docs\n")
        self.assertEqual(
            workspace_health_check.check_docs_layout(self.root),
            [],
        )

    def test_status_column_in_canonical_index_is_reported(self) -> None:
        self.write(
            "docs/biz-knowledge/INDEX.md",
            "\n".join(
                [
                    "# Index",
                    "",
                    "| 文档 | 状态 |",
                    "|------|------|",
                    "| a | active |",
                    "",
                ]
            ),
        )
        issues = workspace_health_check.check_index_schema(self.root)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check, "index-schema")
        self.assertEqual(issues[0].line, 3)

    def test_missing_skill_route_target_is_reported(self) -> None:
        self.write(
            "skills/example/SKILL.md",
            "[workflow](references/missing.md)\n",
        )
        issues = workspace_health_check.check_skill_links(self.root)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check, "skill-links")
        self.assertEqual(issues[0].path, "skills/example/SKILL.md")

    def test_existing_skill_route_target_passes(self) -> None:
        self.write(
            "skills/example/SKILL.md",
            "[workflow](references/existing.md)\n",
        )
        self.write("skills/example/references/existing.md", "# Existing\n")
        self.assertEqual(
            workspace_health_check.check_skill_links(self.root),
            [],
        )

    def test_missing_inline_skill_resource_is_reported(self) -> None:
        self.write(
            "skills/example/SKILL.md",
            "Run `python3 scripts/missing.py --json`.\n",
        )
        issues = workspace_health_check.check_skill_links(self.root)
        self.assertEqual(len(issues), 1)
        self.assertIn("scripts/missing.py", issues[0].message)

    def test_non_path_inline_code_is_ignored(self) -> None:
        self.write(
            "skills/example/SKILL.md",
            "Run `spec health check`.\n",
        )
        self.assertEqual(
            workspace_health_check.check_skill_links(self.root),
            [],
        )

    def test_symlinked_skill_resources_are_owned_externally(self) -> None:
        external = self.root / "external-skill"
        external.mkdir()
        (external / "SKILL.md").write_text(
            "Inspect `scripts/` in the target project.\n",
            encoding="utf-8",
        )
        (self.root / "skills" / "example").symlink_to(
            external,
            target_is_directory=True,
        )
        self.assertEqual(
            workspace_health_check.check_skill_links(self.root),
            [],
        )

    def test_non_executable_skill_shell_is_reported(self) -> None:
        self.write("skills/example/SKILL.md", "# Example\n")
        script = self.write("skills/example/scripts/run.sh", "#!/bin/sh\n")
        script.chmod(0o644)
        issues = workspace_health_check.check_skill_scripts(self.root)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check, "skill-scripts")
        self.assertEqual(issues[0].path, "skills/example/scripts/run.sh")

    def test_quickstart_platform_runbook_is_reported(self) -> None:
        self.write(
            "skills/quickstart/references/diagnosis.md",
            "## Mew run 失败排查\n",
        )
        issues = workspace_health_check.check_quickstart_boundaries(self.root)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check, "quickstart-boundary")
        self.assertEqual(
            issues[0].path,
            "skills/quickstart/references/diagnosis.md",
        )

    def test_quickstart_failure_mode_table_is_reported(self) -> None:
        self.write(
            "skills/quickstart/references/diagnosis.md",
            "| 模式 | 现象 | 触发条件 | 判别证据 | 根因 | 处理方式 |\n",
        )
        issues = workspace_health_check.check_quickstart_boundaries(self.root)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check, "quickstart-boundary")

    def test_quickstart_owner_routing_language_passes(self) -> None:
        self.write(
            "skills/quickstart/references/diagnosis.md",
            "Failure Mode 应进入对应 Skill 或外部官方 owner。\n",
        )
        self.assertEqual(
            workspace_health_check.check_quickstart_boundaries(self.root),
            [],
        )

    def test_issue_tracker_accepts_active_rows_and_pipe_in_code(self) -> None:
        self.write(
            "ISSUES.md",
            "\n".join(
                [
                    "# Issues",
                    "",
                    "| 工具 | 问题 | 影响 | 优先级 | 状态 |",
                    "|------|------|------|--------|------|",
                    "| demo | `auto|legacy|dbw` 不兼容 | 查询失败 | P2 | 🟡 待修复 |",
                    "| demo2 | auto\\|legacy 不兼容 | 查询失败 | P3 | 🔵 观察项 |",
                    "",
                ]
            ),
        )
        self.assertEqual(
            workspace_health_check.check_issue_tracker(self.root),
            [],
        )

    def test_issue_tracker_reports_resolved_rows(self) -> None:
        self.write(
            "ISSUES.md",
            "\n".join(
                [
                    "| 工具 | 问题 | 影响 | 优先级 | 状态 |",
                    "|------|------|------|--------|------|",
                    "| demo | fixed | none | P3 | ✅ 已修复 |",
                    "",
                ]
            ),
        )
        issues = workspace_health_check.check_issue_tracker(self.root)
        self.assertEqual(len(issues), 1)
        self.assertIn("已解决 Issue", issues[0].message)

    def test_issue_tracker_reports_invalid_schema(self) -> None:
        self.write(
            "ISSUES.md",
            "\n".join(
                [
                    "| 工具 | 问题 | 影响 | 优先级 | 状态 |",
                    "|------|------|------|--------|------|",
                    "| demo | broken | P2 | 🟡 待修复 |",
                    "",
                ]
            ),
        )
        issues = workspace_health_check.check_issue_tracker(self.root)
        self.assertEqual(len(issues), 1)
        self.assertIn("5 列", issues[0].message)

    def test_issue_tracker_reports_side_tracker(self) -> None:
        self.write("ISSUES.md", "# Issues\n")
        self.write("skills/example/Issue.md", "# Side tracker\n")
        issues = workspace_health_check.check_issue_tracker(self.root)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].path, "skills/example/Issue.md")
        self.assertEqual(issues[0].category, "error")

    def test_broken_symlink_is_reported(self) -> None:
        link = self.root / "skills" / "broken"
        link.symlink_to(self.root / "missing", target_is_directory=True)
        issues = workspace_health_check.check_broken_symlinks(self.root)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check, "broken-symlinks")
        self.assertEqual(issues[0].path, "skills/broken")

    def test_nested_git_repository_is_reported(self) -> None:
        (self.root / ".git").mkdir()
        (self.root / "docs" / ".git").mkdir()
        issues = workspace_health_check.check_repository_layout(self.root)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check, "repository-layout")
        self.assertEqual(issues[0].path, "docs/.git")
        self.assertEqual(issues[0].category, "error")

    def test_single_repository_layout_passes(self) -> None:
        (self.root / ".git").mkdir()
        self.assertEqual(
            workspace_health_check.check_repository_layout(self.root),
            [],
        )

    def test_exit_code_distinguishes_findings_and_errors(self) -> None:
        finding = workspace_health_check.HealthIssue(
            "indexes",
            "drift",
        )
        error = workspace_health_check.HealthIssue(
            "distribution",
            "missing dependency",
            category="error",
        )
        self.assertEqual(workspace_health_check.exit_code([]), 0)
        self.assertEqual(workspace_health_check.exit_code([finding]), 1)
        self.assertEqual(workspace_health_check.exit_code([error]), 2)

    def test_real_secret_is_reported(self) -> None:
        self.write(
            "biz-tests/example/case.json",
            '{"Authorization": "Basic '
            + "Q" * 48
            + '"}\n',
        )
        issues = workspace_health_check.check_secrets(self.root)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check, "secrets")
        self.assertEqual(issues[0].path, "biz-tests/example/case.json")
        self.assertEqual(issues[0].category, "error")

    def test_secret_placeholders_pass(self) -> None:
        self.write(
            "skills/example/references/auth.md",
            "\n".join(
                [
                    "Authorization: Basic <credential>",
                    'Authorization: "{{Authorization}}"',
                    "Bearer ${ACCESS_TOKEN}",
                    "",
                ]
            ),
        )
        self.assertEqual(
            workspace_health_check.check_secrets(self.root),
            [],
        )

    def test_secret_redaction_uses_runtime_placeholders(self) -> None:
        text = "\n".join(
            [
                "Authorization: Basic " + "Q" * 48,
                "Authorization: Bearer " + "a" * 48,
                (
                    "Authorization: "
                    + "eyJ"
                    + "a" * 24
                    + "."
                    + "b" * 24
                    + "."
                    + "c" * 24
                ),
                "",
            ]
        )
        redacted, count = redact_secrets.redact_text(text)
        self.assertEqual(count, 3)
        self.assertIn("{{Authorization}}", redacted)
        self.assertIn("Bearer {{ACCESS_TOKEN}}", redacted)
        self.assertIn("{{JWT_TOKEN}}", redacted)
        self.assertEqual(
            [
                pattern.pattern
                for _label, pattern in workspace_health_check.SECRET_PATTERNS
                if pattern.search(redacted)
            ],
            [],
        )

    def test_biz_test_index_drift_is_reported(self) -> None:
        (self.root / "biz-tests" / "actual").mkdir()
        self.write(
            "biz-tests/INDEX.md",
            "\n".join(
                [
                    "# Index",
                    "",
                    "| 领域 slug | Owner |",
                    "|----------|-------|",
                    "| stale | — |",
                    "",
                ]
            ),
        )
        issues = workspace_health_check.check_auxiliary_indexes(self.root)
        self.assertEqual(len(issues), 1)
        self.assertIn("Biz-Test 索引与领域目录不一致", issues[0].message)

    def test_prd_index_matches_clean_documents(self) -> None:
        self.write(
            "biz-tests/INDEX.md",
            "\n".join(
                [
                    "# Index",
                    "",
                    "| 领域 slug | Owner |",
                    "|----------|-------|",
                    "",
                ]
            ),
        )
        self.write(
            "docs/prd/INDEX.md",
            "\n".join(
                [
                    "# Index",
                    "",
                    "| 编号 | slug | 来源 |",
                    "|------|------|------|",
                    "| 01 | feature-a | wiki |",
                    "",
                ]
            ),
        )
        self.write("docs/prd/01-feature-a-clean.md", "# Feature A\n")
        self.assertEqual(
            workspace_health_check.check_auxiliary_indexes(self.root),
            [],
        )


if __name__ == "__main__":
    unittest.main()
