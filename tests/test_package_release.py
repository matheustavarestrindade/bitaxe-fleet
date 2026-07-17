"""Tests for the HACS release packager."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.package_release import (
    ARCHIVE_FILENAME,
    FRONTEND_ARCHIVE_PATH,
    MANIFEST_PATH,
    package_release,
    release_notes,
    verify_release_archive,
)


def _write_release_repository(repository: Path, version: str = "0.1.0") -> None:
    """Create a minimal source tree suitable for packaging."""
    component = repository / "custom_components/bitaxe_fleet"
    translations = component / "translations"
    frontend = repository / "frontend/dist"
    translations.mkdir(parents=True)
    frontend.mkdir(parents=True)

    (repository / "pyproject.toml").write_text(
        f"[project]\nname = 'bitaxe-fleet'\nversion = '{version}'\n", encoding="utf-8"
    )
    (component / "__init__.py").write_text(
        "DOMAIN = 'bitaxe_fleet'\n", encoding="utf-8"
    )
    (component / "manifest.json").write_text(
        json.dumps({"domain": "bitaxe_fleet", "version": version}), encoding="utf-8"
    )
    (translations / "en.json").write_text("{}\n", encoding="utf-8")
    (component / "__pycache__").mkdir()
    (component / "__pycache__/ignored.pyc").write_bytes(b"ignored")
    (frontend / "bitaxe-fleet-panel.js").write_text("export {};\n", encoding="utf-8")
    (repository / "CHANGELOG.md").write_text(
        "# Changelog\n\n"
        "## [Unreleased]\n\n"
        "## [0.1.0] - 2026-07-17\n\n"
        "### Added\n\n"
        "- Initial development preview.\n\n"
        "## [0.0.1] - 2026-07-16\n\n"
        "- Earlier release.\n",
        encoding="utf-8",
    )


def test_package_release_creates_a_deterministic_hacs_archive(tmp_path: Path) -> None:
    """The archive contains only installable runtime files and a checksum."""
    repository = tmp_path / "repository"
    _write_release_repository(repository)

    first_archive, first_checksum = package_release(
        repository, tmp_path / "first", "0.1.0"
    )
    second_archive, _ = package_release(repository, tmp_path / "second", "0.1.0")

    assert first_archive.name == ARCHIVE_FILENAME
    assert first_checksum.read_text(encoding="ascii").endswith(
        f"  {ARCHIVE_FILENAME}\n"
    )
    assert first_archive.read_bytes() == second_archive.read_bytes()

    with zipfile.ZipFile(first_archive) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read(MANIFEST_PATH.as_posix()))

    assert manifest["version"] == "0.1.0"
    assert FRONTEND_ARCHIVE_PATH.as_posix() in names
    assert not any("__pycache__" in name for name in names)


def test_package_release_rejects_mismatched_source_versions(tmp_path: Path) -> None:
    """A tag cannot publish metadata with inconsistent versions."""
    repository = tmp_path / "repository"
    _write_release_repository(repository, version="0.1.1")

    with pytest.raises(ValueError, match="Release version must match"):
        package_release(repository, tmp_path / "release", "0.1.0")


def test_verify_release_archive_rejects_path_traversal(tmp_path: Path) -> None:
    """Archive validation rejects members that could escape the install root."""
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, mode="w") as archive:
        archive.writestr("custom_components/bitaxe_fleet/../../outside.py", "unsafe")

    with pytest.raises(ValueError, match="prohibited paths"):
        verify_release_archive(archive_path, "0.1.0")


def test_release_notes_extracts_only_the_requested_version(tmp_path: Path) -> None:
    """Generated GitHub notes preserve the curated changelog section."""
    repository = tmp_path / "repository"
    _write_release_repository(repository)

    assert (
        release_notes(repository, "0.1.0")
        == "### Added\n\n- Initial development preview.\n"
    )
