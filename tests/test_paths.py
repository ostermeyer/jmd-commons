"""Tests for jmd_commons.paths.

The accepted-input matrix is pinned here so that future refactors
can't silently drop support for a notation that downstream MCPs
are emitting.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from jmd_commons.paths import (
    encode_workspace_id,
    is_windows,
    normalize_path,
    to_msys2,
    to_native,
)

# ---------------------------------------------------------------
# to_msys2
# ---------------------------------------------------------------


class TestToMsys2:
    """Every accepted Windows-shape collapses to canonical MSYS2."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            (r"C:\Users\me\foo", "/c/Users/me/foo"),
            (r"c:\Users\me\foo", "/c/Users/me/foo"),
            ("C:/Users/me/foo", "/c/Users/me/foo"),
            ("c:/Users/me/foo", "/c/Users/me/foo"),
            ("/c/Users/me/foo", "/c/Users/me/foo"),
            ("/C/Users/me/foo", "/c/Users/me/foo"),
            ("C:\\", "/c/"),
            ("C:/", "/c/"),
            ("/c/", "/c/"),
            ("/c", "/c/"),
            (r"D:\projects\x", "/d/projects/x"),
            # Trailing slash collapse:
            (r"C:\Users\me\foo\\", "/c/Users/me/foo"),
            ("/c/Users/me/foo/", "/c/Users/me/foo"),
        ],
    )
    def test_windows_shapes_canonicalize(
        self, raw: str, expected: str
    ) -> None:
        assert to_msys2(raw) == expected

    def test_posix_path_passthrough(self) -> None:
        assert to_msys2("/home/me/foo") == "/home/me/foo"

    def test_relative_path_passthrough(self) -> None:
        # Relative paths can't be canonicalized — caller's problem.
        assert to_msys2("foo/bar") == "foo/bar"
        assert to_msys2("./foo") == "./foo"

    def test_pathlib_input(self) -> None:
        # Accepts pathlib.Path; backslash-stringification on
        # Windows must not break canonicalization.
        assert to_msys2(Path("/c/Users/me")) == "/c/Users/me"

    def test_idempotent(self) -> None:
        # to_msys2(to_msys2(x)) == to_msys2(x) for all accepted x.
        for raw in [
            r"C:\Users\me",
            "/c/Users/me",
            "/home/me",
            "C:/x",
        ]:
            once = to_msys2(raw)
            twice = to_msys2(once)
            assert once == twice, f"not idempotent for {raw!r}"


# ---------------------------------------------------------------
# to_native
# ---------------------------------------------------------------


class TestToNativeOnWindows:
    """Windows-host behaviour — MSYS2 / mixed → backslash form."""

    pytestmark = pytest.mark.skipif(
        not is_windows(), reason="Windows-only behaviour"
    )

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("/c/Users/me/foo", r"C:\Users\me\foo"),
            ("/C/Users/me/foo", r"C:\Users\me\foo"),
            ("C:/Users/me/foo", r"C:\Users\me\foo"),
            (r"C:\Users\me\foo", r"C:\Users\me\foo"),
            (r"c:\Users\me", r"C:\Users\me"),
            ("/c/", "C:\\"),
            ("/c", "C:\\"),
        ],
    )
    def test_shapes_translate(
        self, raw: str, expected: str
    ) -> None:
        assert to_native(raw) == expected

    def test_posix_absolute_rejected(self) -> None:
        with pytest.raises(ValueError, match="ambiguous"):
            to_native("/home/me/foo")

    def test_relative_passthrough(self) -> None:
        assert to_native("foo/bar") == "foo/bar"


class TestToNativeOnPosix:
    """POSIX-host behaviour — everything passes through."""

    pytestmark = pytest.mark.skipif(
        is_windows(), reason="POSIX-only behaviour"
    )

    @pytest.mark.parametrize(
        "raw",
        [
            "/home/me/foo",
            "/c/Users/me/foo",  # nonsensical on POSIX, but pass.
            r"C:\Users\me",
            "foo/bar",
        ],
    )
    def test_passthrough(self, raw: str) -> None:
        assert to_native(raw) == raw


# ---------------------------------------------------------------
# normalize_path
# ---------------------------------------------------------------


class TestNormalizePath:
    """Convenience wrapper delegates to to_msys2 / to_native."""

    def test_target_msys2(self) -> None:
        assert (
            normalize_path("/c/Users/me", target="msys2")
            == "/c/Users/me"
        )

    def test_target_native_posix(self) -> None:
        if is_windows():
            assert (
                normalize_path("/c/x", target="native")
                == r"C:\x"
            )
        else:
            assert (
                normalize_path("/home/me", target="native")
                == "/home/me"
            )

    def test_invalid_target_rejected(self) -> None:
        with pytest.raises(ValueError, match="target"):
            normalize_path(
                "/c/x",
                target="bogus",  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------
# encode_workspace_id
# ---------------------------------------------------------------


class TestEncodeWorkspaceId:
    """Workspace-id is stable, dirname-safe, lexical only."""

    def test_basic(self, tmp_path: Path) -> None:
        # tmp_path resolves to an absolute host-native path; the
        # encoded form must start with the canonical MSYS2 prefix.
        wid = encode_workspace_id(tmp_path)
        assert wid.startswith("-")
        # No path separators survive — encoded form is dirname-safe.
        assert "/" not in wid
        assert "\\" not in wid
        assert ":" not in wid

    def test_idempotent_under_pathlib(
        self, tmp_path: Path
    ) -> None:
        # Same logical workspace → same id regardless of how the
        # Path was spelled.
        a = encode_workspace_id(tmp_path)
        b = encode_workspace_id(Path(str(tmp_path)))
        assert a == b

    def test_drive_letter_lowercased_on_windows(self) -> None:
        # The encoded form is derived from the MSYS2-canonical
        # representation, where the drive letter is always
        # lowercase.
        if not is_windows():
            pytest.skip("Windows-only path semantics")
        # Resolve makes the path absolute, which yields an
        # uppercase drive on Windows — to_msys2 then lowercases it.
        p = Path("C:/")
        wid = encode_workspace_id(p)
        # The encoded form starts with "-c-" (lowercase), not
        # "-C-".
        assert wid.startswith("-c-") or wid == "-c-"


# ---------------------------------------------------------------
# is_windows
# ---------------------------------------------------------------


def test_is_windows_matches_platform() -> None:
    assert is_windows() == (sys.platform == "win32")
