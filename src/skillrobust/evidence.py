from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PatternSpec:
    signal: str
    risk_tag: str
    severity: str
    pattern: re.Pattern[str]
    rationale: str


PATTERNS: list[PatternSpec] = [
    PatternSpec("tool_execution", "T3", "medium", re.compile(r"\b(?:python|python3|bash|sh|powershell|pwsh)\s+(?:-executionpolicy\s+bypass\s+)?(?:-file\s+)?(?:scripts/|\.?/)[^\s`]+", re.I), "The package asks the agent to execute a bundled helper."),
    PatternSpec("hidden_override", "T2", "high", re.compile(r"(?:follow|prioriti[sz]e).{0,80}(?:hidden|background|private|internal).{0,80}(?:instruction|context|note|rule)", re.I), "The package contains instructions that elevate hidden or background context."),
    PatternSpec("concealment", "T7", "high", re.compile(r"(?:do not mention|do not reveal|keep .{0,50}background|unless the user explicitly asks|stay out of the final answer)", re.I), "The package discourages disclosure of operational details."),
    PatternSpec("external_transfer", "T6", "high", re.compile(r"(?:upload|sync|send|transmit|post|mirror|export).{0,120}(?:https?://|external|off-device|remote endpoint|webhook)", re.I), "The package describes moving data to an external destination."),
    PatternSpec("external_url", "T6", "medium", re.compile(r"https?://(?!research-only\.invalid)[^\s`\"')]+", re.I), "The package references an external URL."),
    PatternSpec("remote_bootstrap", "T6", "high", re.compile(r"(?:curl|wget|invoke-webrequest|download|fetch).{0,120}(?:script|helper|installer|bootstrap|https?://)", re.I), "The package relies on runtime retrieval of executable helper content."),
    PatternSpec("execution_policy_bypass", "T6", "high", re.compile(r"executionpolicy\s+bypass", re.I), "The package uses a PowerShell execution-policy bypass."),
    PatternSpec("credential_collection", "T4", "high", re.compile(r"(?:\.env|\.npmrc|\.pypirc|ssh|aws/credentials|api[_-]?key|secret|token|credential)", re.I), "The package references sensitive credential or configuration material."),
    PatternSpec("backdoor", "T5", "critical", re.compile(r"(?:reverse shell|interactive shell|unauthorized remote access|persistence|backdoor|would_connect_to|would_establish)", re.I), "The package contains remote-access or backdoor semantics."),
    PatternSpec("cover_story", "T7", "medium", re.compile(r"(?:cover_story|public_cover|cover story|present this capability as|routine validation|internal validation)", re.I), "The package frames risky behavior as a benign routine step."),
]

ROLE_WEIGHTS = {
    "skill_md": 1.2,
    "reference": 1.0,
    "script": 1.1,
    "repo_context": 0.5,
    "asset": 0.3,
    "other": 0.3,
}

SEVERITY_WEIGHTS = {
    "low": 0.25,
    "medium": 0.5,
    "high": 1.0,
    "critical": 1.5,
}


def extract_evidence(record: dict[str, Any], *, max_hits_per_signal: int = 8) -> dict[str, Any]:
    files = record.get("skill", {}).get("files", [])
    evidence: list[dict[str, Any]] = []
    signal_counts: Counter[str] = Counter()
    seen: set[tuple[str, str, str]] = set()

    for file_entry in files:
        path = str(file_entry.get("path", ""))
        role = str(file_entry.get("role", "other"))
        content = str(file_entry.get("content", ""))
        if not content:
            continue
        for spec in PATTERNS:
            if signal_counts[spec.signal] >= max_hits_per_signal:
                continue
            match = spec.pattern.search(content)
            if not match:
                continue
            span = _snippet(content, match.start(), match.end())
            key = (path, spec.signal, span)
            if key in seen:
                continue
            seen.add(key)
            signal_counts[spec.signal] += 1
            evidence.append(
                {
                    "path": path,
                    "role": role,
                    "signal_family": spec.signal,
                    "risk_tag": spec.risk_tag,
                    "severity": spec.severity,
                    "span_text": span,
                    "rationale": spec.rationale,
                }
            )

    return {
        "sample_id": record.get("sample_id"),
        "evidence_items": evidence,
        "features": derive_features(evidence),
        "score": score_evidence(evidence),
    }


def derive_features(evidence: list[dict[str, Any]]) -> dict[str, bool]:
    signals = {item["signal_family"] for item in evidence}
    paths_by_signal: dict[str, set[str]] = {}
    for item in evidence:
        paths_by_signal.setdefault(item["signal_family"], set()).add(str(item["path"]))

    has_execution = bool({"tool_execution", "remote_bootstrap", "execution_policy_bypass"} & signals)
    has_transfer = bool({"external_transfer", "credential_collection", "backdoor"} & signals)
    has_concealment = bool({"concealment", "cover_story", "hidden_override"} & signals)
    involved_paths = {str(item["path"]) for item in evidence if item["signal_family"] in {"tool_execution", "external_transfer", "credential_collection", "remote_bootstrap", "concealment", "hidden_override", "backdoor"}}

    return {
        "has_script_execution": has_execution,
        "has_external_or_sensitive_transfer": has_transfer,
        "has_concealment_or_override": has_concealment,
        "has_remote_bootstrap": bool({"remote_bootstrap", "execution_policy_bypass"} & signals),
        "has_backdoor_semantics": "backdoor" in signals,
        "has_cross_file_chain": len(involved_paths) >= 2,
        "has_decisive_malicious_chain": (has_execution and has_transfer and has_concealment) or ("backdoor" in signals and has_execution),
        "has_boundary_chain": has_execution or has_transfer or "external_url" in signals,
    }


def score_evidence(evidence: list[dict[str, Any]]) -> float:
    score = 0.0
    for item in evidence:
        severity = SEVERITY_WEIGHTS.get(str(item.get("severity", "low")), 0.25)
        role = ROLE_WEIGHTS.get(str(item.get("role", "other")), 0.3)
        score += severity * role
    return round(score, 4)


def _snippet(text: str, start: int, end: int, radius: int = 120) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return " ".join(text[left:right].split())
