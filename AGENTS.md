# AGENTS.md

## Hangul Encoding Rules (Always Apply)
- All file reads/writes for Korean text must use UTF-8 explicitly.
- Never rely on shell/codepage defaults for Korean text handling.
- For scripted Korean text replacement, use Unicode escape-safe replacement (`unicode_escape`) to avoid mojibake.
- After editing Korean text, verify the changed lines and run a quick syntax check (e.g., `python -m py_compile` for Python files).
- If mojibake (`?`, `??`, `???`) appears, immediately restore intended Korean text and re-save as UTF-8.
