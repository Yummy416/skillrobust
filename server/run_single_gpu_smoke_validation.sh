#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR_DEFAULT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROOT_DIR="${ROOT_DIR:-${SKILLROBUST_ROOT_DIR:-${ROOT_DIR_DEFAULT}}}"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  source "${ENV_FILE}"
  set +a
fi

SERVER_IP="${SERVER_IP:-${SKILLROBUST_SERVER_IP:-127.0.0.1}}"
CUDA_DEVICE="${CUDA_DEVICE:-0}"
API_KEY="${API_KEY:-${SKILLROBUST_API_KEY:-}}"
STARTUP_RETRIES="${STARTUP_RETRIES:-120}"
STARTUP_SLEEP_SECONDS="${STARTUP_SLEEP_SECONDS:-10}"
SLEEP_BETWEEN_MODELS="${SLEEP_BETWEEN_MODELS:-5}"
MODELS="${MODELS:-granite_guardian_3_3_8b,llama_guard_3_8b,llama_guard_4_12b,qwen2_5_7b_instruct,qwen2_5_14b_instruct}"
STATUS_FILE="${STATUS_FILE:-${ROOT_DIR}/server/guardrail_smoke_status.txt}"

export NO_PROXY="${NO_PROXY:-127.0.0.1,localhost,${SERVER_IP}}"
export no_proxy="${no_proxy:-127.0.0.1,localhost,${SERVER_IP}}"

mkdir -p "${ROOT_DIR}/server/logs"

declare -A START_SCRIPTS=(
  [granite_guardian_3_3_8b]="server/serve_granite_guardian_3_3_8b.sh"
  [llama_guard_3_8b]="server/serve_llama_guard_3_8b.sh"
  [llama_guard_4_12b]="server/serve_llama_guard_4_12b.sh"
  [llama_prompt_guard_2_86m]="server/serve_llama_prompt_guard_2_86m.sh"
  [qwen2_5_7b_instruct]="server/serve_qwen2_5_7b_instruct.sh"
  [qwen2_5_14b_instruct]="server/serve_qwen2_5_14b_instruct.sh"
)

SERVER_PID=""

render_bar() {
  local current="$1"
  local total="$2"
  local width=24
  local filled=$(( current * width / total ))
  local empty=$(( width - filled ))
  local bar
  bar="$(printf '%*s' "${filled}" '' | tr ' ' '#')"
  bar="${bar}$(printf '%*s' "${empty}" '' | tr ' ' '-')"
  printf '[%s] %d/%d' "${bar}" "${current}" "${total}"
}

write_status() {
  printf '%s\n' "$1" > "${STATUS_FILE}"
}

cleanup() {
  if [[ -n "${SERVER_PID}" ]] && kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
    kill -TERM -- "-${SERVER_PID}" >/dev/null 2>&1 || kill -TERM "${SERVER_PID}" >/dev/null 2>&1 || true
    for ((j=1; j<=30; j++)); do
      if ! kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
        break
      fi
      sleep 1
    done
    if kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
      kill -KILL -- "-${SERVER_PID}" >/dev/null 2>&1 || kill -KILL "${SERVER_PID}" >/dev/null 2>&1 || true
    fi
    wait "${SERVER_PID}" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

run_one_model() {
  local model_name="$1"
  local model_index="$2"
  local total_models="$3"
  local script_path="${START_SCRIPTS[$model_name]:-}"
  local progress_bar
  local log_path="${ROOT_DIR}/server/logs/${model_name}.log"

  if [[ -z "${script_path}" ]]; then
    echo "Unknown model name: ${model_name}" >&2
    exit 1
  fi

  progress_bar="$(render_bar "${model_index}" "${total_models}")"
  echo "== ${progress_bar} Smoke validating ${model_name} =="
  echo "Log: ${log_path}"
  write_status "${progress_bar} | model=${model_name} | phase=starting"

  cleanup
  setsid bash -c "cd '${ROOT_DIR}' && export CUDA_VISIBLE_DEVICES='${CUDA_DEVICE}' && exec bash '${script_path}'" \
    >"${log_path}" 2>&1 &
  SERVER_PID=$!

  local ready=0
  for ((i=1; i<=STARTUP_RETRIES; i++)); do
    if (
      cd "${ROOT_DIR}"
      python server/check_vllm_endpoints.py \
        --server-ip "${SERVER_IP}" \
        --api-key "${API_KEY}" \
        --models "${model_name}" \
        --skip-smoke
    ); then
      ready=1
      break
    fi
    echo "Waiting for ${model_name} to become ready (${i}/${STARTUP_RETRIES})..."
    write_status "${progress_bar} | model=${model_name} | phase=waiting_ready | retry=${i}/${STARTUP_RETRIES}"
    sleep "${STARTUP_SLEEP_SECONDS}"
  done

  if [[ "${ready}" -ne 1 ]]; then
    echo "Model ${model_name} failed to become ready. See ${log_path}" >&2
    write_status "${progress_bar} | model=${model_name} | phase=failed_ready | log=${log_path}"
    exit 1
  fi

  write_status "${progress_bar} | model=${model_name} | phase=smoke_check"
  (
    cd "${ROOT_DIR}"
    python server/check_vllm_endpoints.py \
      --server-ip "${SERVER_IP}" \
      --api-key "${API_KEY}" \
      --models "${model_name}"
  )

  echo "== ${progress_bar} Smoke passed for ${model_name} =="
  write_status "${progress_bar} | model=${model_name} | phase=completed"
  cleanup
  SERVER_PID=""
  sleep "${SLEEP_BETWEEN_MODELS}"
}

IFS=',' read -r -a MODEL_LIST <<< "${MODELS}"
TOTAL_MODELS="${#MODEL_LIST[@]}"

write_status "$(render_bar 0 "${TOTAL_MODELS}") | phase=queued | total_models=${TOTAL_MODELS}"

for idx in "${!MODEL_LIST[@]}"; do
  run_one_model "${MODEL_LIST[$idx]}" "$((idx + 1))" "${TOTAL_MODELS}"
done

echo "All smoke validations completed."
write_status "$(render_bar "${TOTAL_MODELS}" "${TOTAL_MODELS}") | phase=all_completed | total_models=${TOTAL_MODELS}"
