"""Offline deployment safety preflight (no applicant IO and no model calls).

Run: python -m scripts.production_preflight [--remote] [--json]
This is a configuration check, NOT a penetration test or production approval.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import tomllib

import cv_ranker.config  # noqa: F401  # Load .env with the same precedence as the application.
from cv_ranker.access_control import access_env, allowed_emails, evaluate_access
from cv_ranker.runtime_check import assert_runtime_current


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Check:
    check: str
    passed: bool
    note: str


def run_checks(*, remote: bool = False) -> list[Check]:
    checks: list[Check] = []
    try:
        runtime = assert_runtime_current()
    except (RuntimeError, OSError, ValueError) as exc:
        checks.append(Check("source integrity", False, f"Runtime verification failed ({type(exc).__name__})"))
    else:
        strict_source = runtime.get("source_integrity") == "strict_verified"
        checks.append(Check("source integrity", strict_source or not remote,
                            (f"Verified release file hashes and protocol v{runtime['assessment_protocol_version']}"
                             if strict_source else
                             "Local editable development mode; file hashes are NOT verified")))
    try:
        config = tomllib.loads((ROOT / ".streamlit/config.toml").read_text(encoding="utf-8"))
        server = config["server"]
    except (OSError, ValueError, KeyError, TypeError):
        checks.append(Check("Streamlit protections", False, "No valid Streamlit server security configuration"))
        server = {}
    protections = (
        server.get("enableXsrfProtection") is True and
        server.get("enableCORS") is True and
        server.get("enableStaticServing") is False and
        type(server.get("maxUploadSize")) is int and 1 <= server["maxUploadSize"] <= 48 and
        type(server.get("maxMessageSize")) is int and
        server["maxMessageSize"] >= server["maxUploadSize"]
    )
    checks.append(Check("Streamlit protections", protections,
                        "CORS, XSRF, upload and static-file limits configured" if protections
                        else "Review CORS, XSRF, upload/message sizes and static-file policy"))
    mode, allowlist = access_env()
    listener = os.getenv("STREAMLIT_SERVER_ADDRESS", server.get("address"))
    decision = evaluate_access(mode=mode, server_address=listener, emails=allowlist)
    if mode.strip().lower() == "local":
        checks.append(Check("local binding", decision.action == "allow",
                            "Loopback listener only" if decision.action == "allow"
                            else "Local mode requires a loopback-only listener"))
    elif mode.strip().lower() == "oidc":
        checks.append(Check("OIDC allowlist", decision.action == "login",
                            "Explicit allowlist configured; live OIDC login still needs verification"
                            if decision.action == "login" else
                            "OIDC requires valid CVR_ALLOWED_EMAILS"))
    else:
        checks.append(Check("access configuration", False, "Unsupported access mode"))

    manifest = ROOT / "cv_ranker/build_manifest.json"
    try:
        files = json.loads(manifest.read_text(encoding="utf-8"))["files"]
        unsafe = [name for name in files if "/.cv_ranker_cache/" in f"/{name}" or
                  name.startswith(".streamlit/secrets") or
                  name in {".env", "secrets.toml"} or name.endswith((".pem", ".key", ".p12", ".pfx"))]
    except (OSError, ValueError, KeyError, TypeError):
        unsafe = ["invalid manifest"]
    checks.append(Check("release secret exclusion", not unsafe,
                        "No secret/cache file paths in the hashed release" if not unsafe
                        else "Manifest contains or cannot exclude sensitive paths"))

    if remote:
        checks.append(Check("network authentication", mode.strip().lower() == "oidc",
                            "Remote access requires native OIDC and individual verified-email authorization"))
        # These controls cannot be inferred from a source checkout. Never
        # label an internet deployment as cleared by a local script alone.
        checks.extend([
            Check("live OIDC and TLS", False,
                  "Identity-provider callback, cookie rotation, HTTPS and reverse-proxy rules require external verification"),
            Check("durable protected storage", False,
                  "Encrypted transactional job recovery, scoped user storage and deletion policy are not implemented"),
            Check("operational acceptance", False,
                  "Multi-user load, real-model evidence quality, alerting and HR/privacy approval remain unverified"),
        ])
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", action="store_true",
                        help="Check remote deployment blockers; this always requires external acceptance")
    parser.add_argument("--json", action="store_true", help="Print machine-readable results without sensitive values")
    args = parser.parse_args(argv)
    results = run_checks(remote=args.remote)
    passed = all(item.passed for item in results)
    if args.json:
        print(json.dumps({"passed": passed, "scope": "remote" if args.remote else "local",
                          "checks": [asdict(item) for item in results]}, indent=2))
    else:
        for item in results:
            print(f"{'PASS' if item.passed else 'BLOCK'}  {item.check}: {item.note}")
        print("LOCAL SUPERVISED CHECK PASSED" if passed and not args.remote else
              "REMOTE PRODUCTION NOT CLEARED" if args.remote else "LOCAL CONFIGURATION NEEDS ATTENTION")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
