# {{project_name}} Project Structure

**Generated from:** `{{root_path}}`  
**Total files analyzed:** {{total_files}}  
**Total lines:** {{total_lines}}  

## File Type Breakdown

| Extension | Count |
|-----------|-------|
| {{ext}} | {{count}} |

## Top-Level Directory Layout

```
{{project_name}}/
├── {{dir}}/
│   ├── {{file}}
│   └── ...
└── ...
```

## Directory Summaries

| Directory | Files | Main Extensions |
|-----------|-------|-----------------|
| `{{dir}}` | {{files}} | {{extensions}} |

## File Abilities and Code References

### `{{directory}}`

| File | Ability | Code Reference |
|------|---------|----------------|
| `{{file}}` | {{ability}} | {{ref_kind}} `{{symbol}}` (L{{line}}) |

## Architecture & Design Highlights

- {{highlight}}

## Notes

- Files marked with `(root)` live in the project root.
- Code references show the first few class/namespace/function symbols found in each file.
- Generated files and deep vendored subdirectories may be summarized at directory level.
