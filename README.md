# Chatgpt-codex-public

Utilities for quick local experiments.

## Merge two local Hugging Face model folders

Use the helper script:

```bash
python merge_hf_model_dirs.py <primary_model_dir> <secondary_model_dir> <output_dir> [--overwrite-dst]
```

Example used in this workspace:

```bash
python merge_hf_model_dirs.py sexyGPT-Uncensored gpt-3.5-turbo sexygpt-3.5-turbo-uncensored --overwrite-dst
```

Conflict rule: files from the first folder are kept when both folders contain the same relative path; missing files are copied from the second folder.

### Safety behavior

- The script no longer deletes an existing output directory unless you pass `--overwrite-dst`.
- If `config.json` and `tokenizer.json` are both present, the script validates tokenizer IDs against `config.vocab_size`.
- If tokenizer IDs exceed the model vocab size (`max_id >= vocab_size`), it removes `tokenizer.json` and prints a reason to keep GGUF conversion from failing.
- When no fix is needed (or parsing fails), it reports why the tokenizer fix was skipped.

## Publish GGUF to GitHub

GGUF files are tracked through Git LFS (`*.gguf filter=lfs ...`) via `.gitattributes`.

### Fast path

```bash
# from repo root
./scripts/publish_gguf.sh sexygpt-3.5-turbo-uncensored.gguf "Add GGUF artifact" --push
```

If you omit `--push`, the script still commits and prints the exact push command.

### If GGUF is still not visible on GitHub


Quick diagnosis command:

```bash
./scripts/check_gguf_visibility.sh sexygpt-3.5-turbo-uncensored.gguf
```

It reports exactly which step is missing (file generation, git add/commit, LFS tracking, origin remote, or push).
Check these in order:

1. GGUF file exists locally.
2. GGUF file was committed.
3. `origin` remote is configured.
4. Push/authentication succeeded.

Verification commands:

```bash
git status --short
git lfs ls-files
git remote -v
git log --oneline -n 3
```
