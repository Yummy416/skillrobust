from __future__ import annotations

from pathlib import Path
from typing import Any

from .evidence import extract_evidence
from .llm import OpenAICompatibleClient, parse_json_object
from .records import load_skill_package, read_jsonl, write_jsonl


LABELS = {"benign", "suspicious", "malicious"}


def audit_package(
    package_dir: Path,
    *,
    verifier: OpenAICompatibleClient | None = None,
    sample_id: str | None = None,
) -> dict[str, Any]:
    record = load_skill_package(package_dir, sample_id=sample_id)
    return audit_record(record, verifier=verifier)


def audit_jsonl(
    input_path: Path,
    output_path: Path,
    *,
    verifier: OpenAICompatibleClient | None = None,
) -> list[dict[str, Any]]:
    records = read_jsonl(input_path)
    outputs = [audit_record(record, verifier=verifier) for record in records]
    write_jsonl(output_path, outputs)
    return outputs


def audit_record(record: dict[str, Any], *, verifier: OpenAICompatibleClient | None = None) -> dict[str, Any]:
    structured = extract_evidence(record)
    verification = run_semantic_verification(record, structured, verifier) if verifier else None
    decision = robust_decision(structured, verification)
    return {
        "sample_id": record.get("sample_id"),
        "release_package_path": record.get("release_package_path") or record.get("skill", {}).get("root_path"),
        "method": "SkillGuard-Robust",
        "prediction": decision["label"],
        "confidence": decision["confidence"],
        "reason": decision["reason"],
        "structured_evidence": structured,
        "semantic_verification": verification,
    }


def run_semantic_verification(
    record: dict[str, Any],
    structured: dict[str, Any],
    verifier: OpenAICompatibleClient,
) -> dict[str, Any]:
    messages = [
        {
            "role": "system",
            "content": (
                "You are auditing an untrusted Agent Skill package before it is loaded. "
                "Classify the package as benign, suspicious, or malicious. "
                "Use malicious only when the package contains a decisive harmful chain, "
                "such as hidden override, disguised exfiltration, remote bootstrap, credential theft, or backdoor semantics. "
                "Return only compact JSON."
            ),
        },
        {
            "role": "user",
            "content": build_verifier_prompt(record, structured),
        },
    ]
    raw = verifier.chat(messages, temperature=0.0, max_tokens=700)
    parsed = parse_json_object(raw)
    label = normalize_label(parsed.get("package_label") or parsed.get("label"))
    confidence = clamp_float(parsed.get("confidence"), default=0.5)
    return {
        "raw": raw,
        "package_label": label,
        "confidence": confidence,
        "rationale": str(parsed.get("rationale") or parsed.get("reason") or ""),
        "chains": parsed.get("chains", {}),
    }


def build_verifier_prompt(record: dict[str, Any], structured: dict[str, Any], max_files: int = 8, max_chars: int = 1800) -> str:
    frontmatter = record.get("skill", {}).get("frontmatter", {})
    files = record.get("skill", {}).get("files", [])
    evidence = structured.get("evidence_items", [])[:10]
    selected_paths = {item.get("path") for item in evidence}
    selected = [item for item in files if item.get("path") in selected_paths]
    if not selected:
        selected = files[:max_files]
    selected = selected[:max_files]

    chunks = [
        f"sample_id: {record.get('sample_id')}",
        f"frontmatter: {frontmatter}",
        "structured_evidence:",
        *[f"- {item.get('signal_family')} {item.get('severity')} {item.get('path')}: {item.get('span_text')}" for item in evidence],
        "files:",
    ]
    for item in selected:
        content = str(item.get("content", ""))
        if len(content) > max_chars:
            content = content[:max_chars] + "\n...[truncated]"
        chunks.append(f"\n### {item.get('path')} ({item.get('role')})\n{content}")

    chunks.append(
        '\nReturn JSON with keys: "package_label", "confidence", "rationale", and "chains". '
        'The package_label must be one of "benign", "suspicious", "malicious".'
    )
    return "\n".join(chunks)


def robust_decision(structured: dict[str, Any], verification: dict[str, Any] | None) -> dict[str, Any]:
    features = structured.get("features", {})
    score = float(structured.get("score", 0.0))

    if features.get("has_decisive_malicious_chain"):
        local = {"label": "malicious", "confidence": min(0.99, 0.78 + score / 20), "reason": "decisive cross-file malicious chain"}
    elif features.get("has_remote_bootstrap") or features.get("has_backdoor_semantics"):
        local = {"label": "malicious", "confidence": min(0.95, 0.72 + score / 25), "reason": "remote bootstrap or backdoor semantics"}
    elif features.get("has_boundary_chain"):
        local = {"label": "suspicious", "confidence": min(0.88, 0.58 + score / 30), "reason": "review-worthy execution or transfer boundary"}
    else:
        local = {"label": "benign", "confidence": 0.72, "reason": "no decisive risk chain found"}

    if not verification:
        return local

    verifier_label = normalize_label(verification.get("package_label"))
    verifier_conf = clamp_float(verification.get("confidence"), default=0.5)
    if verifier_label == "malicious" and local["label"] in {"malicious", "suspicious"}:
        return {"label": "malicious", "confidence": max(local["confidence"], verifier_conf), "reason": "verifier confirms risk chain"}
    if local["label"] == "malicious" and verifier_label in {"benign", "suspicious"}:
        return {**local, "reason": f"{local['reason']}; verifier disagreement preserved for safety"}
    if verifier_label in LABELS and verifier_conf >= 0.75 and local["label"] == "benign":
        return {"label": verifier_label, "confidence": verifier_conf, "reason": "high-confidence verifier decision"}
    return local


def normalize_label(value: Any) -> str:
    label = str(value or "").strip().lower()
    return label if label in LABELS else "suspicious"


def clamp_float(value: Any, *, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, number))
