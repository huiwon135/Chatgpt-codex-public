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
- If `added_tokens.json` contains IDs that exceed `config.vocab_size`, it removes `added_tokens.json` and prints a reason to avoid GGUF conversion errors.
- When no fix is needed (or parsing fails), it reports why tokenizer and added-token fixes were skipped.


## Build sexyGPT-Uncensored as gpt-3.5-turbo GGUF

Use this one-shot helper to merge and convert in one command:

```bash
python make_sexygpt_turbo_gguf.py --overwrite-merged
```

Default inputs/outputs:
- input primary model: `./sexyGPT-Uncensored`
- input secondary model: `./gpt-3.5-turbo`
- merged HF dir: `./sexygpt-3.5-turbo-uncensored`
- output GGUF: `./sexygpt-3.5-turbo-uncensored.gguf`
- llama.cpp converter path: `./llama.cpp/convert_hf_to_gguf.py`

Example with explicit paths:

```bash
python make_sexygpt_turbo_gguf.py \
  --sexygpt-dir /models/sexyGPT-Uncensored \
  --turbo-dir /models/gpt-3.5-turbo \
  --merged-dir /models/sexygpt-3.5-turbo-uncensored \
  --output-gguf /models/sexygpt-3.5-turbo-uncensored-f16.gguf \
  --llama-cpp-dir /workspace/llama.cpp \
  --outtype f16 \
  --overwrite-merged
```

## Large file download helper (ZIP/GGUF)

If branch artifact downloads are unstable, use the retry/resume downloader:

```bash
python download_model_artifact.py <direct_url> <output_file> [--token <HF_TOKEN>]
```

Example:

```bash
python download_model_artifact.py \
  "https://huggingface.co/<repo>/resolve/main/model.gguf?download=true" \
  ./model.gguf
```

This helper retries transient failures, resumes partial downloads automatically, validates `Content-Range` on resumed responses, and safely restarts when a server ignores `Range` requests.
