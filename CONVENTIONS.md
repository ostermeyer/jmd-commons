# jmd-commons — Python Conventions

This document fixes the coding conventions for **jmd-commons**, the
shared-utility library underlying the JMD MCP servers. It is a
Python-flavored adaptation of
[libjmd's C conventions](https://github.com/ostermeyer/libjmd/blob/main/CONVENTIONS.md):
the surface differs (Python instead of C), the spirit is the same
(teach as well as execute; pin the convention with tests).

Two layers of discipline apply. The first (§1–§3) is hard — code
must comply or it will not work correctly with downstream
consumers. The second (§4–§7) is stylistic — it keeps the
codebase internally consistent.

---

## §1 API stability

jmd-commons is consumed in-process by every JMD MCP server in the
ecosystem. Each MCP pins jmd-commons as a regular dependency; ABI
churn translates directly into a fan-out of `pip install -U`
events across the workspace.

### Must-follow rules

- **Public API lives in `jmd_commons/<module>.py`'s `__all__`.**
  Nothing not listed there is part of the contract. Internal
  helpers go in `_<name>.py` files (underscore prefix) or are
  module-private (`_function_name`).
- **Public functions never depend on a host environment.** No
  `os.environ` reads, no `Path.home()` lookups, no
  `subprocess` calls inside the helpers. Take an explicit
  parameter; let the caller decide. *Exception:* `is_windows()`
  reads `os.name` — that's the one platform detection helper
  every module is allowed to use.
- **Use `from __future__ import annotations` in every module.**
  Future-proofs string-annotations across 3.10 → 3.13.
- **Type-annotate everything.** `mypy --strict` is a quality gate.
  Returning `Any` from a public function is a bug.
- **Inputs accept the most permissive form; outputs return the
  most canonical form.** The `paths` module models this — accept
  every Windows notation in, return one specific canonical form
  out.

### Versioning

- Semantic versioning. `__version__` in `jmd_commons/__init__.py`
  is the source of truth.
- During `0.y.z`: any change may break consumers; downstream MCPs
  pin a specific `==0.y.z`.
- `1.0.0` and later: ABI breaks require a major-version bump.

---

## §2 Naming

- **Functions and variables**: `snake_case`.
- **Public types**: `PascalCase`. Example: `Allocator`, `EnvelopeMode`.
- **Module-private names**: leading underscore. Example:
  `_WIN_ABS_RE`, `_resolve_position`.
- **Constants**: `UPPER_SNAKE_CASE`. Example:
  `DEFAULT_LINE_LENGTH = 80`.
- **Test classes**: `TestX` where `X` names the unit under test.
  Test methods use full `snake_case` sentences:
  `test_drive_letter_lowercased_on_windows`.

---

## §3 Cross-platform discipline

jmd-commons must work *byte-identically* on Mac and Windows for
the same logical input. The single source of OS-conditional
behaviour is `is_windows()`; calls to it stay inside the function
that needs them — they do not bubble up to module-scope branches.

If a helper has POSIX-only or Windows-only semantics (like
`to_native`), the docstring states it explicitly and the test
suite has paired `TestXOnWindows` / `TestXOnPosix` classes
gated with `pytest.mark.skipif`.

---

## §4 Formatting

- **Indent: 4 spaces.** No tabs.
- **Line length: 80 columns soft, 100 hard.** Set by `ruff` —
  configured in `pyproject.toml`.
- **String quoting**: double quotes (`"foo"`), per Black's
  default. Single quotes acceptable inside f-strings for
  readability.
- **Trailing commas**: required on multi-line collections, the
  way Black formats them.
- **No trailing whitespace.** Every file ends with a single
  newline.

`ruff format` is the formatter; `ruff check` is the linter. Both
are part of the quality gate.

---

## §5 Imports

From top to bottom of every `.py` file:

1. `from __future__ import annotations`
2. Blank line
3. Standard-library imports, sorted alphabetically.
4. Blank line
5. Third-party imports, sorted alphabetically (none for
   jmd-commons at M0 — no runtime deps).
6. Blank line
7. First-party imports: `from jmd_commons.x import y`.

`isort` rules are encoded under `[tool.ruff.lint]` with
`select = ["I"]`.

---

## §6 Commenting — the long rule

jmd-commons is the **canonical home** for shared utilities in the
JMD ecosystem. Anyone who wants to know how MSYS2 canonicalization
works, or which path notations are accepted, will read this code.
Treat the docstrings as documentation that ships with the library.

### Module docstring

Every `.py` file opens with a module docstring describing:

- **Purpose** in one sentence.
- **2–6 lines of narrative** on what the module owns, what
  invariants it preserves, and (if it implements a documented
  convention like the MSYS2 Standing Order) which Standing Order
  drives it.
- **Public API summary** — a compact listing so readers don't
  have to scroll to `__all__`.

### Function docstrings (Google-style)

`pydocstyle` is configured for Google convention. Every public
function has:

- **Summary line**: one-line imperative.
- **Args**: each non-obvious parameter with its semantics.
- **Returns**: return-value semantics.
- **Raises**: every exception type the function can raise.
- **Examples** (for transformation helpers): one or two doctested
  inputs showing the canonical mapping.

Trivial accessors and one-liners may skip the full block, but
must still have a summary line — `ruff` enforces this via the
`D` rule selection.

### Inline comments

Inline comments explain **why**, not what. The reader can see that
`s.replace("/", "-")` is a string replace; they cannot see that
this implements the workspace-id encoder defined by the MSYS2
Standing Order unless we tell them.

Use inline comments at:

- **Invariants being established or relied upon**.
- **Subtle convention requirements**: `# Standing Order — MSYS2
  Notation: drive letter lowercased on canonical form.`
- **Intentional non-obvious choices**: `# Match drive letter
  loosely — Windows paths in the wild sometimes carry uppercase`.
- **Cross-references** to the broader system: `# Used by
  jmd-mcp-memory.config.db_path_for_workspace`.

Avoid what-not-why noise. `# increment counter` before `i += 1`
is not a comment.

### TODO / FIXME

Use `TODO(milestone): description` for deferred work:

    # TODO(M1): add security/allow-list module here

`FIXME` is reserved for bugs being explicitly deferred.

---

## §7 Tests

- Every public function has at least one test.
- Tests live under `tests/<test_name>.py` and use pytest.
- **Parametrize the accepted-input matrix.** When a helper accepts
  multiple shapes (like `to_msys2`), the matrix lives in a
  `@pytest.mark.parametrize` so adding a shape is a one-line
  change. The test name documents the contract.
- **Pair Windows-only and POSIX-only suites** when a helper has
  branch behaviour. Use `pytest.mark.skipif(not is_windows(), ...)`
  / `pytest.mark.skipif(is_windows(), ...)` and a clear class
  docstring.
- **No external dependencies in tests.** All tests must pass on a
  fresh machine with only `pytest` installed.

The quality gate is:

    ruff check .
    mypy --strict src tests
    pytest

All three must be green before commit.

---

## §8 Commits and pre-commit doc audit

Per [Standing Order — Pre-Commit Doc Audit](https://github.com/ostermeyer/jmd-commons):
before `git add`, audit whether the change makes any of the
following documentation drift:

1. Module docstring still accurate?
2. Function docstring (signature, args, returns, raises) still
   accurate?
3. `__all__` still complete?
4. README's "Status" / "Scope" tables still accurate?
5. This `CONVENTIONS.md` — did the change introduce a new pattern
   worth pinning here?
6. Cross-MCP contract — does a downstream MCP that consumes this
   helper need a corresponding doc update?
7. `__version__` — does the change warrant a bump (every public
   change during 0.y.z does)?

Adjust doc *before* the commit, so the commit and its
documentation land together.

---

*This document evolves with the codebase. Amend it in the same
commit as the behavior that motivates the amendment.*
