#!/usr/bin/env python3
"""Configure ncnn for Release build with Vulkan backend enabled."""

import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.path.join(SCRIPT_DIR, "build")

def main():
    os.makedirs(BUILD_DIR, exist_ok=True)

    cmake_args = [
        "cmake",
        "-S", SCRIPT_DIR,
        "-B", BUILD_DIR,
        "-A", "x64",
        "-DNCNN_VULKAN=ON",
        "-DNCNN_BUILD_EXAMPLES=ON",
        "-DNCNN_BUILD_BENCHMARK=ON",
        "-DNCNN_BUILD_TESTS=ON",
    ]

    print("Configuring ncnn Release build...")
    print(" ".join(cmake_args))
    ret = subprocess.call(cmake_args, cwd=SCRIPT_DIR)
    if ret != 0:
        print("CMake configuration failed!")
        sys.exit(ret)

    # Write marker so build.py knows which config to use
    marker_path = os.path.join(BUILD_DIR, ".ncnn_build_type")
    with open(marker_path, "w") as f:
        f.write("Release")

    print("Release configuration complete.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
