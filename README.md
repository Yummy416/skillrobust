# SkillRobust

SkillRobust is a package-level auditing toolkit for untrusted Agent Skill packages. It implements structured evidence extraction, optional semantic verification with a replaceable LLM verifier, and robust aggregation for `benign`, `suspicious`, and `malicious` decisions.

This repository snapshot is code-only. Benchmark data is not included here and should be distributed separately as a dataset release.

## Repository Layout

```text
.
|-- src/skillrobust/        # reusable auditing package and CLI
|-- docs/                   # public usage guide
|-- tests/                  # lightweight local tests
|-- server/                 # optional vLLM serving helpers
|-- benchmark/schema/       # JSON schemas for package records and evidence bundles
|-- pyproject.toml
|-- requirements-experiments.txt
|-- .env.example
|-- .gitignore
`-- README.md
```

## Install

```bash
python -m pip install -e .
```

The core CLI uses only the Python standard library. Install optional dependencies only for model-based reproduction experiments:

```bash
python -m pip install -r requirements-experiments.txt
```

## Use the Auditor

Audit one materialized skill package:

```bash
skillrobust audit-package /path/to/skill_package
```

Audit a JSONL benchmark split:

```bash
skillrobust audit-jsonl \
  --input /path/to/split.jsonl \
  --output outputs/audit.jsonl
```

Use an OpenAI-compatible verifier endpoint:

```bash
skillrobust audit-jsonl \
  --input /path/to/split.jsonl \
  --output outputs/audit.jsonl \
  --endpoint-url http://127.0.0.1:8000/v1 \
  --model qwen2_5_14b_instruct
```

If the endpoint requires authentication, set `SKILLROBUST_API_KEY` or pass `--api-key`.

## Data Format

For JSONL evaluation, each line should be a package record with:

- `sample_id`: unique package identifier.
- `skill.root_path`: package root path or logical package path.
- `skill.files`: list of package files, where each item has `path`, `role`, and `content`.
- optional `labels`: ground-truth labels for evaluation.

The separate public dataset release follows this format and also includes materialized packages under `data/packages/`.

## Paper Reproduction

The reusable method is in `src/skillrobust/`. Full paper-specific data construction scripts and generated artifacts are intentionally not included in this code-only upload folder. Keep those internal scripts outside the public GitHub repository, or publish them later as a separate reproduction package if needed.

## Safety

Risk samples used with this code may contain simulated or reconstructed unsafe patterns. Evaluate them only in isolated workflows. Do not install or execute untrusted benchmark packages as operational skills.
