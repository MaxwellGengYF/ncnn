#!/usr/bin/env python3
"""Generate .vscode/compile_commands.json using CMake."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence


def run(cmd: Sequence[str | Path], cwd: Path | None = None) -> None:
    """Run a command and raise on failure."""
    cmd_str = [str(c) for c in cmd]
    print(f"$ {' '.join(cmd_str)}")
    subprocess.run(cmd_str, cwd=cwd, check=True)


def generate_compile_commands(
    project_root: Path,
    build_dir: Path,
    build_type: str = "Release",
    cmake_args: Sequence[str] | None = None,
    force_configure: bool = False,
) -> Path:
    """Configure with CMake exporting compile commands and return the json path."""
    build_dir.mkdir(parents=True, exist_ok=True)

    # Ninja or MSBuild both honor CMAKE_EXPORT_COMPILE_COMMANDS.
    cache = build_dir / "CMakeCache.txt"
    if not cache.exists() or force_configure:
        configure_cmd: list[str | Path] = [
            "cmake",
            "-S", project_root,
            "-B", build_dir,
            f"-DCMAKE_BUILD_TYPE={build_type}",
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
        ]
        if cmake_args:
            configure_cmd.extend(cmake_args)
        run(configure_cmd)
    else:
        # Re-run cmake to refresh compile_commands.json in case sources changed.
        run(["cmake", build_dir])

    compile_commands = build_dir / "compile_commands.json"
    if not compile_commands.exists():
        raise FileNotFoundError(
            f"CMake did not produce {compile_commands}. "
            "Ensure your CMake generator supports compile_commands.json."
        )
    return compile_commands


def copy_to_vscode(vscode_dir: Path, source: Path) -> Path:
    """Copy (and validate) compile_commands.json into .vscode/."""
    vscode_dir.mkdir(parents=True, exist_ok=True)
    destination = vscode_dir / "compile_commands.json"

    # Validate JSON before copying.
    with source.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("compile_commands.json must contain a JSON array")

    shutil.copy2(source, destination)
    print(f"Copied {source} -> {destination} ({len(data)} entries)")
    return destination


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate .vscode/compile_commands.json with CMake."
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=None,
        help="CMake build directory (default: build/Release or build/lsp).",
    )
    parser.add_argument(
        "--build-type",
        default="Release",
        choices=["Debug", "Release", "RelWithDebInfo", "MinSizeRel"],
        help="CMake build type.",
    )
    parser.add_argument(
        "--cmake-arg",
        action="append",
        default=[],
        help="Additional argument(s) to pass to cmake configure.",
    )
    parser.add_argument(
        "--force-configure",
        action="store_true",
        help="Force a clean CMake reconfigure.",
    )
    args = parser.parse_args(argv)

    project_root = Path(__file__).resolve().parent
    vscode_dir = project_root / ".vscode"

    # Prefer the canonical per-config build directory if it exists.
    build_dir = args.build_dir
    if build_dir is None:
        candidate = project_root / "build" / args.build_type
        build_dir = candidate if (candidate / "CMakeCache.txt").exists() else project_root / "build" / "lsp"

    if args.force_configure and build_dir.exists():
        print(f"Removing {build_dir} for forced reconfigure")
        shutil.rmtree(build_dir)

    try:
        source = generate_compile_commands(
            project_root,
            build_dir,
            build_type=args.build_type,
            cmake_args=args.cmake_arg,
            force_configure=args.force_configure,
        )
        destination = copy_to_vscode(vscode_dir, source)
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"clangd will use: {destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
