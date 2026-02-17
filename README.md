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
