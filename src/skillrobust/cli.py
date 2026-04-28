from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .llm import OpenAICompatibleClient
from .pipeline import audit_jsonl, audit_package


def build_verifier(args: argparse.Namespace) -> OpenAICompatibleClient | None:
    if not args.endpoint_url:
        return None
    model = args.model or os.getenv("SKILLROBUST_VERIFIER_MODEL")
    if not model:
        raise SystemExit("--model is required when --endpoint-url is provided")
    return OpenAICompatibleClient(
        endpoint_url=args.endpoint_url,
        model=model,
        api_key=args.api_key or os.getenv("SKILLROBUST_API_KEY", ""),
        timeout=args.timeout,
    )


def cmd_audit_package(args: argparse.Namespace) -> int:
    verifier = build_verifier(args)
    result = audit_package(Path(args.package_dir), verifier=verifier, sample_id=args.sample_id)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


def cmd_audit_jsonl(args: argparse.Namespace) -> int:
    verifier = build_verifier(args)
    audit_jsonl(Path(args.input), Path(args.output), verifier=verifier)
    print(f"Wrote audit results to {args.output}")
    return 0


def add_verifier_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--endpoint-url", help="OpenAI-compatible endpoint base URL, for example http://127.0.0.1:8000/v1")
    parser.add_argument("--model", help="Verifier model name registered by the endpoint")
    parser.add_argument("--api-key", default="", help="Optional bearer token. Defaults to SKILLROBUST_API_KEY.")
    parser.add_argument("--timeout", type=int, default=120, help="Verifier request timeout in seconds")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SkillRobust package-level skill auditing CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_package_parser = subparsers.add_parser("audit-package", help="Audit one materialized skill package directory")
    audit_package_parser.add_argument("package_dir")
    audit_package_parser.add_argument("--sample-id")
    audit_package_parser.add_argument("--output")
    add_verifier_args(audit_package_parser)
    audit_package_parser.set_defaults(func=cmd_audit_package)

    audit_jsonl_parser = subparsers.add_parser("audit-jsonl", help="Audit a JSONL benchmark file")
    audit_jsonl_parser.add_argument("--input", required=True)
    audit_jsonl_parser.add_argument("--output", required=True)
    add_verifier_args(audit_jsonl_parser)
    audit_jsonl_parser.set_defaults(func=cmd_audit_jsonl)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
