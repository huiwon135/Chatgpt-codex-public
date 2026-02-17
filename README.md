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

`*.gguf` files are now configured for Git LFS via `.gitattributes`, so they can be committed and pushed without being blocked by `.gitignore`.

Example:

```bash
git lfs install
git add .gitattributes sexygpt-3.5-turbo-uncensored.gguf
git commit -m "Add GGUF artifact"
git push origin <branch>
```

If your remote does not support LFS, upload the GGUF as a GitHub Release asset instead.


## Still not visible on GitHub? (Checklist)

If GGUF still does not appear in your GitHub repo, usually one of these is the reason:

1. The GGUF file is not present locally.
2. The file was not committed.
3. No `origin` remote is configured.
4. Push/authentication has not completed.

Quick flow:

```bash
# from repo root
./scripts/publish_gguf.sh sexygpt-3.5-turbo-uncensored.gguf "Add GGUF artifact"
# then push with the printed command
```

Manual verification commands:

```bash
git status --short
git lfs ls-files
git remote -v
git log --oneline -n 3
```
