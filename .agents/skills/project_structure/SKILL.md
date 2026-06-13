---
name: project_structure
description: Analyze a codebase and produce a comprehensive project-structure markdown document that explains directories, key files, their abilities, and code references. Use when the user asks for a project overview, project_structure.md, codebase map, or file-by-file explanation.
---

# project_structure

Generate a readable, maintainable project-structure report for a codebase.

## Trigger

Use this skill when the user asks for:
- "analyze the whole project"
- "create project_structure"
- "project structure introduction"
- "explain each file"
- "codebase overview / map"

## Goal

Produce a markdown document (default `project_structure.md` in the project root) containing:
1. Project overview (purpose, language, build system, scale).
2. Top-level directory layout.
3. Per-directory / per-file breakdown with **ability** (what it does) and **code reference** (key classes, functions, lines, symbols).
4. Architecture highlights and design notes.

## Workflow

1. **Determine scope**
   - Project root: current working directory unless user specifies another path.
   - Output path: `project_structure.md` in the project root unless user specifies otherwise.
   - Respect `.gitignore` and skip build artifacts, `.git`, submodules unless explicitly requested.

2. **Collect metadata**
   - Run `scripts/analyze_project.py <root> [--output <path>]`.
   - The script returns a JSON summary of directories, files, extensions, sizes, and inferred purposes.

3. **Read key project files**
   - `README.md`, `CMakeLists.txt`, `setup.py`, `pyproject.toml`, `package.json`, etc.
   - Top-level source headers in `src/`, `include/`, `lib/`, or equivalent.
   - Build / config files in `cmake/`, `.github/`, `tools/`, `tests/`.

4. **Extract file abilities and code references**
   - For each important source/header file, inspect the first 60 lines and grep for:
     - `class`, `struct`, `namespace`, `enum class`
     - function definitions / declarations
     - module-level docstrings / comments
   - Record line numbers and symbol names for code references.
   - Skip generated files, vendored third-party code, or mark them clearly as vendored.

5. **Generate the report**
   - Use `references/output-template.md` as the structural template.
   - Fill in:
     - Repository stats table
     - Directory tree
     - Per-directory tables with columns: `File`, `Ability`, `Code Reference`
     - Architecture & design section
   - Keep tables concise; move long explanations into subsections.

6. **Review and refine**
   - Ensure every listed file has an ability description.
   - Ensure code references are accurate (symbol name + approximate line).
   - Add cross-links between related sections (e.g., layer base class → layer implementations).

7. **Deliver**
   - Write the final markdown to the output path.
   - Report the output path and a 3-sentence summary to the user.

## Output quality standards

- Accurate: do not invent files or symbols.
- Hierarchical: directories first, then files inside them.
- Referenced: each non-trivial file entry includes at least one code reference (class/function/line).
- Concise: avoid copying entire file contents; summarize intent.
- Skippable: clearly mark generated/vendored files so readers know to ignore them.

## Script usage

```bash
python scripts/analyze_project.py <project_root> [--output project_structure.md]
```

The script prints a JSON summary to stdout and writes the generated markdown to the output path.

## Notes

- For very large projects, focus on the top 2–3 levels of the directory tree and summarize deep leaves by pattern (e.g., "259 ARM NEON kernel files").
- When the project is a well-known framework (ncnn, PyTorch, LLVM, etc.), use the README and existing docs to guide organization but still derive file abilities from source.
- If a `project_structure.md` already exists, read it first and decide whether to overwrite, append, or create a new timestamped file.
