"""Build and verify a deterministic HACS release archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import tomllib
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import Final

ARCHIVE_FILENAME: Final = "bitaxe_fleet.zip"
CHECKSUM_FILENAME: Final = f"{ARCHIVE_FILENAME}.sha256"
COMPONENT_PATH: Final = Path("custom_components/bitaxe_fleet")
MANIFEST_PATH: Final = COMPONENT_PATH / "manifest.json"
FRONTEND_SOURCE_PATH: Final = Path("frontend/dist/bitaxe-fleet-panel.js")
FRONTEND_ARCHIVE_PATH: Final = COMPONENT_PATH / "frontend/bitaxe-fleet-panel.js"
REQUIRED_ARCHIVE_PATHS: Final = frozenset(
    {
        (COMPONENT_PATH / "__init__.py").as_posix(),
        MANIFEST_PATH.as_posix(),
        (COMPONENT_PATH / "translations/en.json").as_posix(),
        FRONTEND_ARCHIVE_PATH.as_posix(),
    }
)
PROHIBITED_PATH_PARTS: Final = frozenset(
    {".git", "..", "__pycache__", "node_modules", "tests"}
)
SEMVER_PATTERN: Final = re.compile(
    r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
ARCHIVE_TIMESTAMP: Final = (1980, 1, 1, 0, 0, 0)


def _read_json_object(path: Path) -> dict[str, object]:
    """Read a JSON object from a UTF-8 file."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        msg = f"Expected a JSON object in {path}"
        raise ValueError(msg)
    return value


def _read_manifest_version(repository: Path) -> str:
    """Return the integration version declared in the source manifest."""
    version = _read_json_object(repository / MANIFEST_PATH).get("version")
    if not isinstance(version, str):
        msg = "The integration manifest must declare a string version"
        raise ValueError(msg)
    return version


def _read_project_version(repository: Path) -> str:
    """Return the project version declared in pyproject.toml."""
    document = tomllib.loads(
        (repository / "pyproject.toml").read_text(encoding="utf-8")
    )
    project = document.get("project")
    if not isinstance(project, dict):
        msg = "pyproject.toml must contain a [project] table"
        raise ValueError(msg)

    version = project.get("version")
    if not isinstance(version, str):
        msg = "pyproject.toml must declare a string project version"
        raise ValueError(msg)
    return version


def _validate_version(version: str) -> None:
    """Reject versions that cannot be represented by a SemVer tag."""
    if SEMVER_PATTERN.fullmatch(version) is None:
        msg = f"{version!r} is not a valid Semantic Version"
        raise ValueError(msg)


def _validate_source_versions(repository: Path, version: str) -> None:
    """Require all source metadata to match the release version."""
    _validate_version(version)
    manifest_version = _read_manifest_version(repository)
    project_version = _read_project_version(repository)
    if manifest_version != version or project_version != version:
        msg = (
            "Release version must match both manifest.json and pyproject.toml "
            f"(requested={version}, manifest={manifest_version}, "
            f"pyproject={project_version})"
        )
        raise ValueError(msg)


def _copy_release_tree(repository: Path, staging_directory: Path, version: str) -> None:
    """Copy runtime files and the compiled panel into a clean archive tree."""
    component_source = repository / COMPONENT_PATH
    frontend_source = repository / FRONTEND_SOURCE_PATH
    if not component_source.is_dir():
        msg = f"Missing integration source directory: {component_source}"
        raise FileNotFoundError(msg)
    if not frontend_source.is_file():
        msg = f"Missing compiled panel: {frontend_source}"
        raise FileNotFoundError(msg)

    component_destination = staging_directory / COMPONENT_PATH
    shutil.copytree(
        component_source,
        component_destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )

    frontend_destination = staging_directory / FRONTEND_ARCHIVE_PATH
    frontend_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(frontend_source, frontend_destination)

    manifest_path = staging_directory / MANIFEST_PATH
    manifest = _read_json_object(manifest_path)
    manifest["version"] = version
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
    )


def _archive_files(staging_directory: Path) -> list[Path]:
    """Return archive members in a deterministic order."""
    return sorted(path for path in staging_directory.rglob("*") if path.is_file())


def _write_archive(staging_directory: Path, archive_path: Path) -> None:
    """Write a reproducible ZIP with stable member ordering and timestamps."""
    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        for source_path in _archive_files(staging_directory):
            archive_path_name = source_path.relative_to(staging_directory).as_posix()
            member = zipfile.ZipInfo(archive_path_name, date_time=ARCHIVE_TIMESTAMP)
            member.compress_type = zipfile.ZIP_DEFLATED
            member.external_attr = 0o100644 << 16
            archive.writestr(member, source_path.read_bytes(), compresslevel=9)


def verify_release_archive(archive_path: Path, version: str) -> None:
    """Verify package layout, required files, and release metadata."""
    component_prefix = f"{COMPONENT_PATH.as_posix()}/"
    with zipfile.ZipFile(archive_path) as archive:
        names = tuple(info.filename for info in archive.infolist())
        if len(names) != len(set(names)):
            msg = "Release archive contains duplicate paths"
            raise ValueError(msg)

        invalid_paths = [
            name
            for name in names
            if not name.startswith(component_prefix)
            or any(part in PROHIBITED_PATH_PARTS for part in Path(name).parts)
            or name.endswith((".map", ".pyc", ".pyo"))
        ]
        if invalid_paths:
            msg = f"Release archive contains prohibited paths: {invalid_paths}"
            raise ValueError(msg)

        missing_paths = REQUIRED_ARCHIVE_PATHS.difference(names)
        if missing_paths:
            msg = f"Release archive is missing required paths: {sorted(missing_paths)}"
            raise ValueError(msg)

        manifest = json.loads(archive.read(MANIFEST_PATH.as_posix()))
        if not isinstance(manifest, dict) or manifest.get("version") != version:
            msg = "Release archive manifest version does not match the release version"
            raise ValueError(msg)

        if not archive.read(FRONTEND_ARCHIVE_PATH.as_posix()):
            msg = "Release archive contains an empty compiled panel"
            raise ValueError(msg)


def release_notes(repository: Path, version: str) -> str:
    """Extract the curated changelog section for one release version."""
    changelog = (repository / "CHANGELOG.md").read_text(encoding="utf-8")
    heading = re.compile(
        rf"^## \[{re.escape(version)}\](?: - .+)?$", flags=re.MULTILINE
    )
    match = heading.search(changelog)
    if match is None:
        msg = f"CHANGELOG.md has no section for version {version}"
        raise ValueError(msg)

    next_heading = re.compile(r"^## \[", flags=re.MULTILINE).search(
        changelog, match.end()
    )
    notes = changelog[
        match.end() : next_heading.start() if next_heading else None
    ].strip()
    if not notes:
        msg = f"CHANGELOG.md section for version {version} is empty"
        raise ValueError(msg)
    return f"{notes}\n"


def package_release(
    repository: Path, output_directory: Path, version: str | None = None
) -> tuple[Path, Path]:
    """Build the HACS archive and its SHA-256 checksum."""
    release_version = version or _read_manifest_version(repository)
    _validate_source_versions(repository, release_version)

    output_directory.mkdir(parents=True, exist_ok=True)
    archive_path = output_directory / ARCHIVE_FILENAME
    checksum_path = output_directory / CHECKSUM_FILENAME
    archive_path.unlink(missing_ok=True)
    checksum_path.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory(prefix="bitaxe-fleet-release-") as temporary:
        staging_directory = Path(temporary)
        _copy_release_tree(repository, staging_directory, release_version)
        _write_archive(staging_directory, archive_path)

    verify_release_archive(archive_path, release_version)
    with archive_path.open("rb") as archive_file:
        checksum = hashlib.file_digest(archive_file, "sha256").hexdigest()
    checksum_path.write_text(f"{checksum}  {ARCHIVE_FILENAME}\n", encoding="ascii")
    return archive_path, checksum_path


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the release packaging command-line interface."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root to package",
    )
    parser.add_argument("--output", required=True, type=Path, help="Output directory")
    parser.add_argument("--version", help="Expected Semantic Version")
    parser.add_argument("--notes-file", type=Path, help="Write curated release notes")
    args = parser.parse_args(arguments)

    try:
        archive_path, checksum_path = package_release(
            args.repository.resolve(), args.output.resolve(), args.version
        )
        if args.notes_file is not None:
            version = args.version or _read_manifest_version(args.repository)
            args.notes_file.parent.mkdir(parents=True, exist_ok=True)
            args.notes_file.write_text(
                release_notes(args.repository.resolve(), version), encoding="utf-8"
            )
    except (FileNotFoundError, OSError, ValueError, zipfile.BadZipFile) as error:
        parser.error(str(error))

    print(archive_path)
    print(checksum_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
