"""Build/check the installable Uni-Gear Blender add-on archive."""
from __future__ import annotations

import pathlib
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
ADDON_DIR = ROOT / "uni_gear"
ZIP_PATH = ROOT / "dist" / "uni_gear.zip"
SKIP_DIRS = {"__pycache__", ".pytest_cache"}
SKIP_SUFFIXES = {".pyc", ".pyo"}


def _files() -> list[pathlib.Path]:
    result = []
    for path in ADDON_DIR.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(ADDON_DIR).parts
        if any(part in SKIP_DIRS for part in rel_parts) or path.suffix in SKIP_SUFFIXES:
            continue
        result.append(path)
    return sorted(result)


def build() -> pathlib.Path:
    files = _files()
    if not files:
        raise SystemExit(f"No add-on source files found in {ADDON_DIR}")
    ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
    return ZIP_PATH


def check() -> int:
    if not ZIP_PATH.is_file():
        print(f"Missing {ZIP_PATH.relative_to(ROOT)}; run python build_addon_zip.py")
        return 1
    expected = {path.relative_to(ROOT).as_posix(): path.read_bytes() for path in _files()}
    with zipfile.ZipFile(ZIP_PATH) as archive:
        actual_names = {name for name in archive.namelist() if not name.endswith("/")}
        expected_names = set(expected)
        problems = [f"missing in ZIP: {name}" for name in sorted(expected_names - actual_names)]
        problems += [f"unexpected ZIP entry: {name}" for name in sorted(actual_names - expected_names)]
        for name in sorted(expected_names & actual_names):
            if archive.read(name) != expected[name]:
                problems.append(f"content differs: {name}")
    if problems:
        print("Packaged add-on is out of sync:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"Package is synchronized ({len(expected)} files).")
    return 0


if __name__ == "__main__":
    if "--check" in sys.argv[1:]:
        raise SystemExit(check())
    result = build()
    print(f"Wrote {result.relative_to(ROOT)} ({result.stat().st_size} bytes)")
    raise SystemExit(0)
