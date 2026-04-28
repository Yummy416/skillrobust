# SkillRobust Usage

This page documents the public, reusable entry points. The historical scripts under `benchmark/scripts/` remain available for paper reproduction, but new users should start with the `skillrobust` CLI.

## Install

```bash
python -m pip install -e .
```

The core CLI has no runtime dependency beyond the Python standard library.

## Audit One Skill Package

Use local evidence extraction and robust aggregation:

```bash
skillrobust audit-package skillrobust_bench_data/data/packages/ar_2510_001
```

Write the result to a file:

```bash
skillrobust audit-package \
  skillrobust_bench_data/data/packages/ar_2510_001 \
  --output outputs/ar_2510_001.audit.json
```

## Audit a JSONL Split

```bash
skillrobust audit-jsonl \
  --input skillrobust_bench_data/data/jsonl/combined/v1-heldout-batch8-public-large.jsonl \
  --output outputs/batch8.audit.jsonl
```

Each input line should contain a `skill.files` list with file paths, roles, and text content. The standalone data release already follows this format.

## Add a Verifier Model

If an OpenAI-compatible model endpoint is available, pass its base URL and model name:

```bash
skillrobust audit-jsonl \
  --input skillrobust_bench_data/data/jsonl/combined/v1-heldout-batch8-public-large.jsonl \
  --output outputs/batch8.audit.jsonl \
  --endpoint-url http://127.0.0.1:8000/v1 \
  --model qwen2_5_14b_instruct
```

Set `SKILLROBUST_API_KEY` if the endpoint requires a bearer token:

```bash
export SKILLROBUST_API_KEY=your_token
```

## Output Format

The CLI emits one JSON object per audited package with:

- `prediction`: final `benign`, `suspicious`, or `malicious` decision.
- `confidence`: calibrated confidence from the local or verifier-assisted decision.
- `reason`: short explanation for the final decision.
- `structured_evidence`: deterministic evidence signals extracted from package files.
- `semantic_verification`: optional verifier result when an endpoint is configured.

## Paper Reproduction

Use `benchmark/scripts/` only when reproducing the paper-specific tables and ablations. Those scripts assume the benchmark build layout and may require the optional dependencies in `requirements-experiments.txt`.
