# Chatgpt-codex-public

Utilities for quick local experiments.

## Merge two local Hugging Face model folders

Use the helper script:

```bash
python merge_hf_model_dirs.py <primary_model_dir> <secondary_model_dir> <output_dir>
```

Example used in this workspace:

```bash
python merge_hf_model_dirs.py sexyGPT-Uncensored gpt-3.5-turbo sexygpt-3.5-turbo-uncensored
```

Conflict rule: files from the first folder are kept when both folders contain the same relative path; missing files are copied from the second folder.

If `config.json` + `vocab.json` exist but a copied `tokenizer.json` has token IDs outside `config.vocab_size`, the script automatically removes that incompatible `tokenizer.json` so GGUF conversion tools can use the compatible GPT-2 vocab files.
