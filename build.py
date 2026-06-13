#!/usr/bin/env python3
"""Unified ncnn Windows CMake build script.

Supports Debug and Release configurations, automatically discovers MSVC
(via vswhere), prefers the Ninja generator, and generates a
compile_commands.json file at the project root for C++ LSP support.

Usage:
    python build.py --config Release
    python build.py --config Debug --clean
    python build.py --all
    python build.py --config Release --configure-only
    python build.py --config Debug --build-only -j 8
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_BUILD_TYPE = "Release"
DEFAULT_GENERATOR = "Ninja"
SOURCE_DIR = Path(__file__).resolve().parent


NCNN_OPTIONS = {
    "NCNN_VULKAN": "ON",
    "NCNN_BUILD_EXAMPLES": "ON",
    "NCNN_BUILD_BENCHMARK": "ON",
    "NCNN_BUILD_TESTS": "ON",
    "NCNN_BUILD_TOOLS": "ON",
    "NCNN_SHARED_LIB": "OFF",
    "NCNN_OPENMP": "ON",
}


def run(cmd: list[str], cwd=None, timeout: int = 300, env=None,
        check: bool = True) -> subprocess.CompletedProcess:
    """Run a command, streaming output. Exits on failure if check=True."""
    print(f"[RUN] {' '.join(str(c) for c in cmd)}")
    proc = subprocess.run(cmd, cwd=cwd, timeout=timeout,
                          env=env or os.environ, capture_output=False)
    if check and proc.returncode != 0:
        sys.exit(proc.returncode)
    return proc


def run_capture(cmd: list[str], cwd=None, timeout: int = 30,
                encoding: str = "utf-8", errors: str = "ignore") -> str:
    """Run a command, capture stdout, raise on failure."""
    proc = subprocess.run(cmd, cwd=cwd, timeout=timeout,
                          capture_output=True, text=True,
                          encoding=encoding, errors=errors)
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        sys.exit(proc.returncode)
    return proc.stdout.strip()


def find_program(name: str) -> str | None:
    """Find a program in PATH, .deps, or common locations."""
    # 1. PATH
    path = shutil.which(name)
    if path:
        print(f"[FOUND] {name}: {path}")
        return path

    # 2. Bootstrap .deps directory
    script_dir = SOURCE_DIR
    deps = script_dir / ".deps"
    if deps.is_dir():
        candidate = deps / f"{name}.exe" if sys.platform == "win32" else deps / name
        if candidate.is_file():
            print(f"[FOUND] {name}: {candidate}")
            return str(candidate)

    # 3. Python scripts dir (for ninja installed via pip)
    if name == "ninja":
        pip_ninja = Path(sys.executable).parent / "ninja.exe"
        if pip_ninja.is_file():
            print(f"[FOUND] {name}: {pip_ninja}")
            return str(pip_ninja)

    # 4. Common Windows locations
    if sys.platform == "win32":
        common_paths = []
        if name == "vswhere.exe":
            program_files_x86 = os.environ.get("ProgramFiles(x86)")
            if program_files_x86:
                common_paths.append(Path(program_files_x86) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe")
        for candidate in common_paths:
            if candidate.is_file():
                print(f"[FOUND] {name}: {candidate}")
                return str(candidate)

    print(f"[MISSING] {name}")
    return None


def find_msvc(pattern: str) -> list[str]:
    """Find MSVC installation files using vswhere."""
    vswhere = find_program("vswhere.exe")
    if not vswhere:
        return []

    result = run_capture([
        vswhere, "-format", "json", "-utf8", "-nologo", "-sort",
        "-products", "*", "-find", pattern, "-latest",
    ])
    data = json.loads(result)
    return [x.replace("\\", "/") for x in data]


def prepare_msvc_environment() -> dict:
    """Detect and activate MSVC environment using vswhere."""
    vcvars = find_msvc("**/Auxiliary/Build/vcvars64.bat")
    if not vcvars:
        print("[WARN] Could not find vcvars64.bat. Proceeding without MSVC environment.")
        return os.environ.copy()

    vcvars_bat = vcvars[0]
    print(f"[MSVC] Using: {vcvars_bat}")

    dump_cmd = (
        f'"{vcvars_bat}" && python -c '
        f'"import os, json; print(json.dumps(dict(os.environ)))"'
    )
    result = subprocess.run(
        dump_cmd, shell=True, capture_output=True, text=True, timeout=60,
        encoding="utf-8", errors="ignore",
    )
    if result.returncode != 0:
        print(f"[WARN] vcvars failed: {result.stderr}")
        return os.environ.copy()

    stdout = result.stdout.strip()
    # vcvars64.bat may print a banner before the JSON payload.
    json_start = stdout.find("{")
    if json_start == -1:
        print("[WARN] Could not locate JSON environment dump in vcvars output.")
        return os.environ.copy()
    env_vars = json.loads(stdout[json_start:])
    env = os.environ.copy()
    env.update(env_vars)
    print("[MSVC] Environment prepared.")
    return env


def select_generator() -> str:
    """Prefer Ninja, fall back to a Visual Studio generator."""
    if find_program("ninja"):
        return DEFAULT_GENERATOR
    print("[GENERATOR] Ninja not found, using Visual Studio 17 2022")
    return "Visual Studio 17 2022"


def build_dir_for(build_type: str) -> Path:
    """Return the build directory for the requested configuration."""
    return SOURCE_DIR / "build" / build_type


def configure(build_type: str, generator: str | None, env: dict,
              extra_flags: list[str] | None = None,
              export_compile_commands: bool = True):
    """Run CMake configure for the given build type."""
    build_dir = build_dir_for(build_type)
    build_dir.mkdir(parents=True, exist_ok=True)

    cmake = find_program("cmake")
    if not cmake:
        sys.exit("ERROR: cmake not found. Install it or run from a VS Developer Command Prompt.")

    if generator is None:
        generator = select_generator()

    cmd = [
        cmake, "-S", str(SOURCE_DIR), "-B", str(build_dir),
        "-G", generator,
        f"-DCMAKE_BUILD_TYPE={build_type}",
    ]

    if export_compile_commands:
        cmd.append("-DCMAKE_EXPORT_COMPILE_COMMANDS=ON")

    if generator == DEFAULT_GENERATOR:
        ninja = find_program("ninja")
        if ninja:
            cmd.append(f"-DCMAKE_MAKE_PROGRAM={ninja}")

    for key, value in NCNN_OPTIONS.items():
        cmd.append(f"-D{key}={value}")

    if extra_flags:
        cmd.extend(extra_flags)

    run(cmd, env=env)


def build(build_type: str, env: dict, jobs: int | None = None):
    """Run CMake build for the given build type."""
    build_dir = build_dir_for(build_type)
    if not build_dir.is_dir():
        sys.exit(f"ERROR: build directory {build_dir} does not exist. Run configure first.")

    if jobs is None:
        jobs = os.cpu_count() or 8

    cmake = find_program("cmake")
    if not cmake:
        sys.exit("ERROR: cmake not found.")

    run([cmake, "--build", str(build_dir), "-j", str(jobs)], env=env)


def copy_compile_commands(build_type: str):
    """Copy the generated compile_commands.json to the project root."""
    build_dir = build_dir_for(build_type)
    source = build_dir / "compile_commands.json"
    dest = SOURCE_DIR / "compile_commands.json"
    if source.is_file():
        shutil.copy2(source, dest)
        print(f"[LSP] Copied compile_commands.json from {source} to {dest}")
    else:
        print(f"[WARN] compile_commands.json not found at {source}")


def clean(build_type: str):
    """Remove CMake cache for the given build type to force re-configure."""
    build_dir = build_dir_for(build_type)
    cache = build_dir / "CMakeCache.txt"
    if cache.is_file():
        print(f"[CLEAN] Removing {cache}")
        cache.unlink()
    cmake_files = build_dir / "CMakeFiles"
    if cmake_files.is_dir():
        print(f"[CLEAN] Removing {cmake_files}")
        shutil.rmtree(cmake_files, ignore_errors=True)


def build_one(build_type: str, args) -> int:
    """Configure and/or build a single configuration."""
    print(f"\n{'='*60}")
    print(f"[BUILD] Configuration: {build_type}")
    print(f"{'='*60}")

    env = prepare_msvc_environment()

    if args.clean:
        clean(build_type)

    if not args.build_only:
        configure(
            build_type=build_type,
            generator=args.generator,
            env=env,
            extra_flags=[f"-D{d}" for d in args.define],
            export_compile_commands=not args.no_compile_commands,
        )

    if not args.configure_only:
        build(build_type=build_type, env=env, jobs=args.j)

    if not args.no_compile_commands:
        copy_compile_commands(build_type)

    print(f"[DONE] {build_type} build completed successfully.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Unified ncnn Windows CMake build script")
    parser.add_argument(
        "--config", default=None, choices=["Debug", "Release"],
        help="Build configuration (default: Release, or both with --all)")
    parser.add_argument(
        "--all", action="store_true",
        help="Configure and build both Debug and Release")
    parser.add_argument(
        "--configure-only", action="store_true",
        help="Run CMake configure only")
    parser.add_argument(
        "--build-only", action="store_true",
        help="Run CMake build only (build directory must already be configured)")
    parser.add_argument(
        "--clean", action="store_true",
        help="Clean build cache before configure")
    parser.add_argument(
        "--no-compile-commands", action="store_true",
        help="Do not generate compile_commands.json")
    parser.add_argument(
        "-G", "--generator", default=None,
        help="CMake generator (default: Ninja if available)")
    parser.add_argument(
        "-D", "--define", action="append", default=[],
        help="Extra CMake definitions, e.g. -DFOO=BAR")
    parser.add_argument(
        "-j", type=int, default=None,
        help="Parallel jobs (default: cpu_count)")
    args = parser.parse_args()

    if args.all:
        configs = ["Debug", "Release"]
    else:
        configs = [args.config or DEFAULT_BUILD_TYPE]

    for build_type in configs:
        build_one(build_type, args)

    print("\n[DONE] All requested builds completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
