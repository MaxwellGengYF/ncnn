#!/usr/bin/env python3
"""Analyze a project and produce a structured markdown overview.

Usage:
    python analyze_project.py <project_root> [--output project_structure.md]
"""

import argparse
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path


def get_git_tracked(root: Path):
    """Return set of tracked files if inside a git repo, else None."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "ls-files"], text=True, stderr=subprocess.DEVNULL
        )
        return {root / p for p in out.splitlines()}
    except Exception:
        return None


def is_ignored(path: Path, root: Path, gitignore_rules: list):
    """Naive .gitignore matching for common build dirs and patterns."""
    rel = path.relative_to(root).as_posix()
    parts = path.relative_to(root).parts
    ignored_prefixes = {
        ".git", ".github", ".vscode", ".idea", ".agents",
        "build", "dist", "out", "target", "node_modules",
        "__pycache__", ".pytest_cache", ".mypy_cache",
    }
    if any(p in ignored_prefixes for p in parts):
        return True
    for rule in gitignore_rules:
        if rule in rel or rel.endswith(rule):
            return True
    return False


def load_gitignore(root: Path):
    rules = []
    gi = root / ".gitignore"
    if gi.exists():
        for line in gi.read_text(errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                rules.append(line.strip("/"))
    return rules


def infer_file_ability(path: Path, first_lines: str) -> str:
    """Return a short description based on filename, extension, and header content."""
    ext = path.suffix.lower()
    name = path.name.lower()

    name_map = {
        "cmakelists.txt": "Root CMake build configuration",
        "setup.py": "Python package setup",
        "pyproject.toml": "Python project metadata",
        "package.json": "Node.js package metadata",
        ".gitignore": "Git ignore rules",
        ".gitmodules": "Git submodule configuration",
        ".gitattributes": "Git attributes configuration",
        ".clang-format": "ClangFormat style configuration",
        ".astylerc": "AStyle formatter configuration",
    }
    if name in name_map:
        return name_map[name]

    ability_map = {
        ".md": "Documentation",
        ".txt": "Text / license / config",
        ".yml": "CI/CD or config",
        ".yaml": "CI/CD or config",
        ".json": "JSON configuration or metadata",
        ".toml": "Project metadata / config",
        ".ini": "INI configuration",
        ".cfg": "Configuration",
        ".cmake": "CMake module",
        ".comp": "Vulkan compute shader",
        ".proto": "Protocol Buffers schema",
        ".td": "LLVM TableGen definition",
        ".png": "Image asset",
        ".jpg": "Image asset",
        ".svg": "Vector image asset",
    }
    if ext in ability_map:
        return ability_map[ext]

    # Pattern-based descriptions for common project conventions
    stem = path.stem
    low_name = name
    if "/tests/" in path.as_posix().lower() or stem.startswith("test_"):
        return "Unit test"
    if "/perf/" in path.as_posix().lower() or stem.startswith("perf_"):
        return "Performance benchmark"
    if "/examples/" in path.as_posix().lower():
        return "Example application"
    if "/python/" in path.as_posix().lower() and ext == ".py":
        if "/model_zoo/" in path.as_posix().lower():
            return "Python model-zoo wrapper"
        return "Python binding / example"
    if "/toolchains/" in path.as_posix().lower():
        return "Cross-compilation toolchain file"
    if "/shader/" in path.as_posix().lower() and ext == ".comp":
        return "Vulkan compute shader"
    if "/layer/" in path.as_posix().lower():
        if ext in (".h", ".hpp"):
            return "Layer class declaration"
        if ext in (".cpp", ".cc"):
            return "Layer implementation"
        return "Layer kernel header"

    # Try to extract a one-line summary from leading comments, skipping copyright
    skip_prefixes = (
        "#include", "#pragma", "#ifndef", "#define", "using ", "import ",
        "copyright", "license", "spdx", "author", "@file", "//",
    )
    for line in first_lines.splitlines()[:20]:
        stripped = line.strip(" /*#")
        low = stripped.lower()
        if len(stripped) > 10 and not low.startswith(skip_prefixes) and not low.startswith("copyright"):
            return stripped[:140]

    if ext in (".h", ".hpp", ".c", ".cc", ".cpp"):
        return "Source/header file"
    if ext == ".py":
        return "Python script/module"
    if ext in (".sh", ".cmd", ".bat", ".ps1"):
        return "Shell/build script"
    return "Project file"


def extract_code_references(path: Path, content: str, max_refs: int = 5) -> list:
    """Return list of (symbol_type, symbol_name, line_no) tuples.

    Focus on declarations/definitions, avoiding calls to stdlib/control-flow.
    """
    refs = []
    seen = set()
    # Skip common call-only identifiers and control-flow keywords
    noise = {
        "for", "while", "if", "else", "switch", "case", "return", "break",
        "continue", "goto", "sizeof", "static_cast", "dynamic_cast", "const_cast",
        "memset", "memcpy", "malloc", "free", "fopen", "fclose", "fprintf",
        "printf", "sprintf", "snprintf", "exit", "abort", "assert", "qsort",
        "floor", "ceil", "round", "fabs", "fmod", "exp", "log", "sqrt",
        "vst1q_f32", "vst1q_f16", "vst1q_u16", "vst1q_s16", "vst1q_s32",
        "vst1_f32", "vst1_f16", "vst1_u16", "vst1_s16", "vst2q_f32",
        "vcombine_f16", "vmax_s8", "vst3_u8", "vst4q_f32", "vst4q_u16",
    }
    patterns = [
        (r"^\s*(?:class|struct)\s+(\w+)", "class"),
        (r"^\s*namespace\s+(\w+)", "namespace"),
        (r"^\s*enum\s+(?:class\s+)?(\w+)", "enum"),
        # Function definition: type name(args) { or type name(args) const { ...
        (r"^\s*(?:static\s+|inline\s+|NCNN_FORCEINLINE\s+)*[\w:<>,\s*&*]+\s+(\w+)\s*\([^)]*\)\s*(?:const\s*)?(?:override\s*)?(?:noexcept\s*)?(?:->\s*[\w:<>,\s*]+)?\s*\{", "func"),
        # Virtual method declaration
        (r"^\s*(?:virtual\s+)[\w:<>,\s*&*]+\s+(\w+)\s*\([^)]*\)\s*(?:const\s*)?(?:=\s*0\s*)?;", "method"),
        # Python class / function
        (r"^\s*class\s+(\w+)\s*\(?", "class"),
        (r"^\s*def\s+(\w+)\s*\(", "func"),
    ]
    lines = content.splitlines()
    for i, line in enumerate(lines[:250], start=1):
        # Skip comment-only lines
        code = line.split("//")[0].strip()
        if not code or code.startswith("*") or code.startswith("/*"):
            continue
        for pat, kind in patterns:
            m = re.match(pat, code)
            if m:
                sym = m.group(1)
                if sym and sym not in seen and sym not in noise and not sym.startswith(("__", "_")):
                    # Heuristic: avoid macro expansions in all-caps
                    if sym.isupper() and kind == "func":
                        continue
                    seen.add(sym)
                    refs.append((kind, sym, i))
                    if len(refs) >= max_refs:
                        return refs
    return refs


def summarize_directory(files: list) -> dict:
    """Return summary stats for a directory."""
    exts = Counter(f.suffix.lower() for f in files if f.suffix)
    total_size = sum(f.stat().st_size for f in files if f.exists())
    return {
        "file_count": len(files),
        "extensions": dict(exts.most_common(10)),
        "total_bytes": total_size,
    }


def build_tree(root: Path, tracked: set = None, max_depth: int = 4):
    """Build a nested dict of directories and files."""
    gitignore = load_gitignore(root)
    tree = {"_files": [], "_meta": {"path": str(root)}}

    for dirpath, dirnames, filenames in os.walk(root):
        dpath = Path(dirpath)
        rel = dpath.relative_to(root)

        # Filter ignored directories
        keep_dirs = []
        for d in dirnames:
            dp = dpath / d
            if not is_ignored(dp, root, gitignore):
                keep_dirs.append(d)
        dirnames[:] = keep_dirs

        # Skip if too deep
        depth = len(rel.parts) if str(rel) != "." else 0
        if depth > max_depth:
            continue

        files = []
        for f in filenames:
            fp = dpath / f
            if is_ignored(fp, root, gitignore):
                continue
            if tracked is not None and fp not in tracked:
                continue
            files.append(fp)

        # Place files in tree
        node = tree
        for part in rel.parts:
            if part not in node:
                node[part] = {"_files": []}
            node = node[part]
        node["_files"].extend(files)

    return tree


def render_tree(node, root: Path, prefix="", max_files: int = 20):
    """Render a directory tree as markdown lines."""
    lines = []
    dirs = sorted(k for k in node.keys() if not k.startswith("_"))
    files = sorted(f.name for f in node.get("_files", []))

    if prefix == "":
        lines.append(f"{root.name}/")
        prefix = ""

    for i, d in enumerate(dirs):
        is_last = (i == len(dirs) - 1) and not files
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{d}/")
        child_prefix = prefix + ("    " if is_last else "│   ")
        lines.extend(render_tree(node[d], root, child_prefix, max_files))

    displayed_files = files[:max_files]
    for i, f in enumerate(displayed_files):
        is_last = (i == len(displayed_files) - 1)
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{f}")
    if len(files) > max_files:
        lines.append(f"{prefix}└── ... ({len(files) - max_files} more files)")

    return lines


def analyze_project(root: Path, output: Path, max_depth: int = 4):
    tracked = get_git_tracked(root)
    tree = build_tree(root, tracked, max_depth)

    # Collect all files
    all_files = []
    def collect(node):
        all_files.extend(node.get("_files", []))
        for k, v in node.items():
            if not k.startswith("_"):
                collect(v)
    collect(tree)

    # Overall stats
    exts = Counter(f.suffix.lower() for f in all_files if f.suffix)
    total_lines = 0
    for f in all_files:
        try:
            with open(f, "rb") as fh:
                total_lines += sum(1 for _ in fh)
        except Exception:
            pass

    stats = {
        "total_files": len(all_files),
        "total_lines": total_lines,
        "top_extensions": dict(exts.most_common(15)),
    }

    # Per-directory summaries
    dir_summaries = {}
    def summarize(node, rel_parts):
        files = node.get("_files", [])
        if files or any(not k.startswith("_") for k in node):
            rel = "/".join(rel_parts) if rel_parts else "."
            dir_summaries[rel] = summarize_directory(files)
        for k, v in node.items():
            if not k.startswith("_"):
                summarize(v, rel_parts + [k])
    summarize(tree, [])

    # Key file details (top-level and src/include/tools only)
    key_dirs = {"src", "include", "lib", "tools", "tests", "examples", "python", "cmake", "benchmark"}
    interesting_names = {"cmakelists.txt", ".gitignore", ".gitmodules", ".gitattributes"}
    interesting_exts = {".h", ".hpp", ".c", ".cc", ".cpp", ".py", ".cmake", ".sh", ".cmd", ".yml", ".yaml"}
    key_files = []
    for f in all_files:
        rel_parts = f.relative_to(root).parts
        in_key_dir = rel_parts[0] in key_dirs
        is_root = len(rel_parts) == 1
        if in_key_dir or is_root:
            if f.name.lower() in interesting_names or f.suffix.lower() in interesting_exts:
                key_files.append(f)

    file_details = []
    for f in sorted(key_files):
        try:
            content = f.read_text(errors="ignore")[:8000]
        except Exception:
            continue
        first = "\n".join(content.splitlines()[:20])
        ability = infer_file_ability(f, first)
        refs = extract_code_references(f, content)
        file_details.append({
            "path": f.relative_to(root).as_posix(),
            "ability": ability,
            "refs": refs,
        })

    summary = {
        "root": str(root),
        "stats": stats,
        "directories": dir_summaries,
        "tree": tree,
        "file_details": file_details,
    }

    # Generate markdown
    md = generate_markdown(root, summary, max_depth)
    output.write_text(md, encoding="utf-8")
    print(json.dumps(stats, indent=2))
    return summary


def generate_markdown(root: Path, summary: dict, max_depth: int) -> str:
    stats = summary["stats"]
    dirs = summary["directories"]
    tree = summary["tree"]
    details = summary["file_details"]

    lines = []
    lines.append(f"# {root.name} Project Structure")
    lines.append("")
    lines.append(f"**Generated from:** `{root}`  ")
    lines.append(f"**Total files analyzed:** {stats['total_files']}  ")
    lines.append(f"**Total lines:** {stats['total_lines']:,}  ")
    lines.append("")

    # Top extensions
    lines.append("## File Type Breakdown")
    lines.append("")
    lines.append("| Extension | Count |")
    lines.append("|-----------|-------|")
    for ext, count in stats["top_extensions"].items():
        lines.append(f"| {ext or '(no ext)'} | {count} |")
    lines.append("")

    # Directory tree
    lines.append("## Top-Level Directory Layout")
    lines.append("")
    lines.append("```")
    lines.extend(render_tree(tree, root, "", 12))
    lines.append("```")
    lines.append("")

    # Directory summaries
    lines.append("## Directory Summaries")
    lines.append("")
    lines.append("| Directory | Files | Main Extensions |")
    lines.append("|-----------|-------|-----------------|")
    for d, s in sorted(dirs.items()):
        exts = ", ".join(f"{k}: {v}" for k, v in s["extensions"].items())
        lines.append(f"| `{d}` | {s['file_count']} | {exts} |")
    lines.append("")

    # File details grouped by directory
    lines.append("## File Abilities and Code References")
    lines.append("")

    grouped = defaultdict(list)
    for fd in details:
        d = Path(fd["path"]).parent.as_posix()
        if d == ".":
            d = "(root)"
        grouped[d].append(fd)

    for d in sorted(grouped.keys()):
        lines.append(f"### `{d}`")
        lines.append("")
        lines.append("| File | Ability | Code Reference |")
        lines.append("|------|---------|----------------|")
        for fd in sorted(grouped[d], key=lambda x: x["path"]):
            refs = "; ".join(
                f"{kind} `{name}` (L{ln})" for kind, name, ln in fd["refs"][:3]
            ) or "—"
            lines.append(f"| `{Path(fd['path']).name}` | {fd['ability']} | {refs} |")
        lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append("- Files marked with `(root)` live in the project root.")
    lines.append("- Code references show the first few class/namespace/function symbols found in each file.")
    lines.append("- Generated files and deep vendored subdirectories may be summarized at directory level.")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Analyze project structure")
    parser.add_argument("root", help="Project root directory")
    parser.add_argument("--output", "-o", default="project_structure.md", help="Output markdown path")
    parser.add_argument("--max-depth", type=int, default=4, help="Max directory depth to display")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output

    if not root.is_dir():
        raise SystemExit(f"Root is not a directory: {root}")

    analyze_project(root, output, args.max_depth)
    print(f"\nWrote project structure to: {output}")


if __name__ == "__main__":
    main()
