#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/.env}"
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  source "${ENV_FILE}"
  set +a
fi

MODEL_ROOT="${MODEL_ROOT:-${SKILLROBUST_MODEL_ROOT:-${REPO_ROOT}/models}}"
MODEL_DIR="${MODEL_DIR:-${MODEL_ROOT}/Qwen2.5-7B-Instruct}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-38135}"
TP_SIZE="${TP_SIZE:-1}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-16384}"
API_KEY="${API_KEY:-${SKILLROBUST_API_KEY:-}}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen2.5-7b-instruct}"

if [[ ! -d "${MODEL_DIR}" ]]; then
  echo "Model directory not found: ${MODEL_DIR}" >&2
  exit 1
fi

echo "Serving ${SERVED_MODEL_NAME} from ${MODEL_DIR}"
echo "Endpoint: http://${HOST}:${PORT}/v1"
echo "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-<not-set>}"

ARGS=(
  "${MODEL_DIR}"
  --host "${HOST}"
  --port "${PORT}"
  --served-model-name "${SERVED_MODEL_NAME}"
  --tensor-parallel-size "${TP_SIZE}"
  --dtype auto
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}"
  --max-model-len "${MAX_MODEL_LEN}"
  --trust-remote-code
)
if [[ -n "${API_KEY}" ]]; then
  ARGS+=(--api-key "${API_KEY}")
fi

exec vllm serve "${ARGS[@]}"
