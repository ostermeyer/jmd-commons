# jmd-commons

Copyright © 2026 Andreas Ostermeyer.
Apache-2.0.

Shared Python utilities for the JMD ecosystem. Single place to put
cross-cutting concerns that would otherwise drift across multiple
MCP servers and tools.

## Status

**M0 — paths module.** `jmd_commons.paths` is the source of truth
for the [MSYS2-canonical path convention](CONVENTIONS.md#paths) on
Windows. Every JMD MCP server that needs to translate or canonicalize
paths imports from here; no encoder duplication across repos.

## Scope

Python-only. Mac and Windows. No external runtime dependencies.

The library will grow one module at a time as cross-cutting concerns
surface in real code:

| Module       | Status   | Concern                                 |
| ------------ | -------- | --------------------------------------- |
| `paths`      | M0 ✓     | MSYS2 ↔ Windows-native, workspace-id    |
| `security`   | planned  | command allow-listing, classification   |
| `credentials`| planned  | platform-keyring access, scrubbing      |
| `envelope`   | planned  | JMD §3.6 envelope unwrap helpers        |
| `errors`     | planned  | `# Error` JMD rendering                 |
| `results`    | planned  | `# Result` JMD rendering                |

Modules graduate from "planned" to "shipped" only when at least two
consumers would otherwise duplicate the same code.

## Install

    pip install jmd-commons

Or from source:

    pip install -e .

## Usage

```python
from pathlib import Path

from jmd_commons.paths import to_msys2, to_native, encode_workspace_id

to_msys2(r"C:\Users\me\foo")        # → "/c/Users/me/foo"
to_native("/c/Users/me/foo")        # → "C:\\Users\\me\\foo" on Windows
encode_workspace_id(Path.cwd())     # → "-c-Users-me-Workspace"
```

See `jmd_commons/paths.py` for the full API and accepted input
shapes.

## Development

    uv sync
    uv run ruff check .
    uv run mypy src tests
    uv run pytest

All three gates must be green before commit.

## Conventions

See [CONVENTIONS.md](CONVENTIONS.md) — Python-flavored adaptation
of [libjmd's C conventions](https://github.com/ostermeyer/libjmd/blob/main/CONVENTIONS.md).
