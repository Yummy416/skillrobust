# Server Scripts

This directory contains helper scripts for serving guardrail or judge models and validating OpenAI-compatible endpoints used by the SkillRobust evaluation pipeline.

## Supported scripts

- `serve_granite_guardian_3_3_8b.sh`
- `serve_llama_guard_3_8b.sh`
- `serve_llama_guard_4_12b.sh`
- `serve_llama_prompt_guard_2_86m.sh`
- `serve_qwen2_5_7b_instruct.sh`
- `serve_qwen2_5_14b_instruct.sh`
- `check_vllm_endpoints.py`
- `run_single_gpu_smoke_validation.sh`
- `run_single_gpu_guardrail_eval.sh`

## Configuration

All shell scripts support environment-variable configuration and can optionally load `.env` from the repository root.

Most relevant variables:

- `SKILLROBUST_MODEL_ROOT` or `MODEL_ROOT`
- `SKILLROBUST_SERVER_IP` or `SERVER_IP`
- `SKILLROBUST_API_KEY` or `API_KEY`
- `HOST`
- `PORT`
- `TP_SIZE`
- `MAX_MODEL_LEN`
- `GPU_MEMORY_UTILIZATION`

If `API_KEY` is empty, the scripts start or call endpoints without an authentication header.

## Start a single server

```bash
CUDA_VISIBLE_DEVICES=0 bash server/serve_qwen2_5_14b_instruct.sh
```

Override the model directory explicitly if needed:

```bash
MODEL_DIR=/path/to/Qwen2.5-14B-Instruct \
CUDA_VISIBLE_DEVICES=0 \
bash server/serve_qwen2_5_14b_instruct.sh
```

## Validate endpoints

Check all configured endpoints:

```bash
python server/check_vllm_endpoints.py
```

Check one endpoint only:

```bash
python server/check_vllm_endpoints.py --models qwen2_5_14b_instruct
```

## Single-GPU smoke validation

```bash
CUDA_DEVICE=0 bash server/run_single_gpu_smoke_validation.sh
```

This script:

1. starts one model
2. waits until `/health` and `/v1/models` are ready
3. runs a short smoke test
4. stops the model
5. moves to the next model

## Single-GPU benchmark run

```bash
CUDA_DEVICE=0 bash server/run_single_gpu_guardrail_eval.sh
```

Useful overrides:

```bash
CUDA_DEVICE=0 \
MODELS=qwen2_5_7b_instruct,qwen2_5_14b_instruct \
RESULT_ROOT=benchmark/results/remote_guardrails_v1_alpha \
CLEAN_PATH=benchmark/data/clean/v1-alpha-clean-provisional.jsonl \
RISK_PATH=benchmark/data/risk/v1-alpha-risk-provisional.jsonl \
REWRITE_PATH=benchmark/data/attack_rewrite/v1-alpha-attack-rewrite-provisional.jsonl \
bash server/run_single_gpu_guardrail_eval.sh
```

## Notes

- The serve scripts do not hardcode private filesystem paths, internal IP addresses, or API keys.
- The default model root is `./models` relative to the repository root.
- `Llama-Prompt-Guard-2-86M` may still require a separate `transformers` path depending on local vLLM support.
