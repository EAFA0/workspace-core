# Workspace Core

A shareable, tool-neutral knowledge workspace for AI-assisted software development.

Workspace Core provides a small governance layer for organizing durable knowledge, routing tasks to the right documentation owner, validating references, and publishing a sanitized core without copying private project data.

## What is included

- Knowledge ownership and lifecycle principles
- Canonical indexes for product, repository, and test knowledge
- `spec`: deterministic checks, routing, and distribution tooling
- `workflows`: reusable knowledge and dossier maintenance workflows
- Empty content owners that can be initialized for a private workspace

Private project knowledge, runtime configuration, sessions, personal memory, and credentials are intentionally excluded from the distributed core.

## Start here

1. Use [`AGENTS.md`](AGENTS.md) as the routing entry for agents.
2. Read [`docs/architecture/01-core-principles.md`](docs/architecture/01-core-principles.md).
3. Review the [knowledge model](docs/architecture/03-knowledge-model.md).
4. Use [`skills/spec/SKILL.md`](skills/spec/SKILL.md) for validation and distribution commands.
5. Use [`skills/workflows/SKILL.md`](skills/workflows/SKILL.md) when organizing dossiers, knowledge, or skills.

To initialize a private workspace from this core:

```bash
python3 skills/spec/scripts/spec.py dist init /path/to/private-workspace
python3 skills/spec/scripts/spec.py dist doctor /path/to/private-workspace
```

The public repository is a generated distribution. Maintain canonical sources in the private workspace and publish through `workspace-core.manifest.yaml`.
