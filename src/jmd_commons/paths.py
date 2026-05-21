r"""MSYS2-canonical path handling for the JMD ecosystem.

Andreas's Standing Order (2026-05-21) makes MSYS2 notation
(``/c/Users/me/foo``) the canonical Windows path form across all
JMD MCP servers. The convention has three layers:

1. **Input boundary** (LLM → MCP): accept every common Windows
   notation — native (``C:\Users\me\foo``), mixed-slash
   (``C:/Users/me/foo``), MSYS2 (``/c/Users/me/foo``),
   lowercase-drive (``c:\Users\me``). POSIX paths pass through
   unchanged on POSIX hosts; on Windows they're rejected as
   ambiguous (no drive letter).

2. **Internal canonical**: MSYS2 form wherever a path is used as
   an identity key — workspace-id encoding, cache keys, hashes,
   audit log entries.

3. **Host-API output**: translate to Windows-native form right
   before calling subprocess/pygit2/sqlite/``open()``.

On POSIX hosts every conversion is a no-op, so the same code path
works platform-symmetrically without ``if is_windows()`` scatter.

Public API:

    to_msys2(p)            — any → MSYS2 form
    to_native(p)           — any → Windows-native on Windows,
                              passthrough on POSIX
    normalize_path(p, *,   — convenience wrapper picking either
                   target)   target form
    encode_workspace_id(p) — Path → directory-name-safe id used
                              for per-workspace storage roots

See ``tests/test_paths.py`` for the full accepted-input matrix.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal

__all__ = [
    "encode_workspace_id",
    "is_windows",
    "normalize_path",
    "to_msys2",
    "to_native",
]


# Matches Windows-absolute paths in native or mixed-slash form:
# group 1 = drive letter, group 2 = rest (possibly empty).
_WIN_ABS_RE = re.compile(r"^([A-Za-z]):[\\/](.*)$")

# Matches MSYS2-absolute paths: ``/<letter>/...`` where the single
# letter is a drive. The trailing slash is optional so ``/c`` and
# ``/c/`` both parse.
_MSYS2_ABS_RE = re.compile(r"^/([A-Za-z])(/.*)?$")


def _stringify(p: str | Path) -> str:
    """Render *p* as a forward-slash string, regardless of host.

    ``pathlib.Path`` on Windows stringifies with backslashes and
    has surprising semantics for paths that look MSYS2-shaped
    (``/c/...`` is treated as drive-relative). ``as_posix()``
    sidesteps both issues.
    """
    if isinstance(p, Path):
        return p.as_posix()
    return p


def is_windows() -> bool:
    """Return True on Windows hosts.

    Wraps ``os.name`` so callers don't have to import ``os`` just
    for the platform check.
    """
    return os.name == "nt"


def to_msys2(p: str | Path) -> str:
    r"""Normalize *p* to MSYS2 form.

    Accepted inputs:
        - Windows-native: ``C:\Users\me\foo``
        - Mixed-slash:    ``C:/Users/me/foo``
        - MSYS2:          ``/c/Users/me/foo`` (idempotent)
        - Lowercase:      ``c:\Users\me``
        - POSIX paths:    passthrough (no drive letter)

    Args:
        p: Path string or ``pathlib.Path``.

    Returns:
        MSYS2-form string. Drive letter is lowercased; backslashes
        become forward slashes; the leading drive becomes
        ``/<letter>/``. Trailing slashes are collapsed.

    Examples:
        >>> to_msys2("C:/Users/me/foo")
        '/c/Users/me/foo'
        >>> to_msys2("/c/Users/me/foo")
        '/c/Users/me/foo'
        >>> to_msys2("/home/me/foo")
        '/home/me/foo'
    """
    s = _stringify(p)
    # Already MSYS2 form? Normalize drive-letter casing only.
    m = _MSYS2_ABS_RE.match(s)
    if m is not None:
        drive = m.group(1).lower()
        rest = (m.group(2) or "").rstrip("/")
        return f"/{drive}{rest}" if rest else f"/{drive}/"

    # Windows absolute (native or mixed)?
    m = _WIN_ABS_RE.match(s)
    if m is not None:
        drive = m.group(1).lower()
        rest = m.group(2).replace("\\", "/").lstrip("/").rstrip("/")
        return f"/{drive}/{rest}" if rest else f"/{drive}/"
    # POSIX path or relative — passthrough (relative paths keep
    # their backslashes; caller's problem if that matters).
    return s


def to_native(p: str | Path) -> str:
    r"""Translate *p* to the host OS's native form.

    On Windows:
        - MSYS2 form → Windows-native with backslashes
        - Mixed-slash → Windows-native (slash normalized)
        - Already native → unchanged (but slash-normalized)
        - POSIX-absolute (``/home/me/foo``) → ``ValueError``
          (ambiguous: no drive letter on Windows)

    On POSIX:
        - Everything passes through unchanged. Calling ``to_native``
          on a Windows path on a POSIX host is almost certainly a
          bug, but we don't try to detect it here.

    Args:
        p: Path string or ``pathlib.Path``.

    Returns:
        Host-native path string.

    Raises:
        ValueError: On Windows when *p* is a POSIX-absolute path
            without a drive letter (``/home/me/foo``).

    Examples:
        >>> import os
        >>> os.name == "nt" and to_native("/c/Users/me") == r"C:\Users\me"
        True
    """
    if not is_windows():
        return _stringify(p)
    s = _stringify(p)
    # MSYS2 form → Windows-native.
    m = _MSYS2_ABS_RE.match(s)
    if m is not None:
        drive = m.group(1).upper()
        rest = (m.group(2) or "").lstrip("/").rstrip("/")
        rest_bs = rest.replace("/", "\\")
        return f"{drive}:\\{rest_bs}" if rest_bs else f"{drive}:\\"
    # Windows absolute (native or mixed-slash).
    m = _WIN_ABS_RE.match(s)
    if m is not None:
        drive = m.group(1).upper()
        rest = m.group(2).replace("/", "\\").lstrip("\\").rstrip("\\")
        return f"{drive}:\\{rest}" if rest else f"{drive}:\\"
    # POSIX-absolute on Windows is ambiguous — fail fast.
    if s.startswith("/"):
        raise ValueError(
            f"POSIX-absolute path is ambiguous on Windows: {s!r} "
            f"(no drive letter). Use MSYS2 form (/c/...) or "
            f"Windows-native (C:\\...) instead."
        )
    # Relative path — passthrough.
    return s


def normalize_path(
    p: str | Path, *, target: Literal["msys2", "native"] = "native"
) -> str:
    """Convenience wrapper picking either target form.

    Args:
        p: Path string or ``pathlib.Path``.
        target: ``"msys2"`` for canonical MSYS2 form,
            ``"native"`` for host-native form.

    Returns:
        Path string in the requested form.

    Raises:
        ValueError: When *target* is invalid, or when
            ``target="native"`` and *p* is POSIX-absolute on
            Windows (see :func:`to_native`).
    """
    if target == "msys2":
        return to_msys2(p)
    if target == "native":
        return to_native(p)
    raise ValueError(
        f"target must be 'msys2' or 'native', got {target!r}"
    )


def encode_workspace_id(p: Path) -> str:
    r"""Encode *p* into a directory-name-safe identity string.

    Used as the per-workspace storage root segment under e.g.
    ``~/.claude/projects/<workspace-id>/``. The encoding is:

    1. Resolve to an absolute path.
    2. Normalize to MSYS2 form (drive lowercased, forward slashes).
    3. Replace every ``/`` with ``-``.

    The result is stable across Mac and Windows for paths that
    refer to the same logical workspace location, and it never
    contains characters that NTFS or POSIX filesystems reject.

    Args:
        p: A ``pathlib.Path`` (need not exist; ``resolve()`` is
            purely lexical for non-existing paths on 3.6+).

    Returns:
        Directory-name-safe identity string.

    Examples:
        >>> import os
        >>> from pathlib import Path
        >>> os.name == "nt" or encode_workspace_id(
        ...     Path("/home/me/Workspace")
        ... ) == "-home-me-Workspace"
        True
    """
    canonical = to_msys2(p.resolve())
    return canonical.replace("/", "-")
