"""Offline security gates, sensitive release files and shared-cache stress."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import tomllib

import numpy as np
import pytest

from cv_ranker.access_control import access_env, allowed_emails, evaluate_access
from cv_ranker.semantic.cache import SQLiteVectorCache
from cv_ranker.semantic.embedding import EmbeddingError


@pytest.mark.parametrize("address", ["127.0.0.1", "localhost", "::1"])
def test_local_supervisor_only_on_loopback(address):
    result = evaluate_access(mode="local", server_address=address, emails="")
    assert result.action == "allow"


@pytest.mark.parametrize("address", [None, "", "0.0.0.0", "192.168.0.8", "example.com", "[::]"])
def test_local_supervisor_denies_missing_or_external_listener(address):
    result = evaluate_access(mode="local", server_address=address, emails="")
    assert result.action == "misconfigured"


@pytest.mark.parametrize("mode", ["", "development", "basic", "unauthenticated"])
def test_unknown_access_modes_fail_closed(mode):
    assert evaluate_access(mode=mode, server_address="127.0.0.1", emails="").action == "misconfigured"


def test_oidc_requires_allowlist_verified_email_and_session():
    base = {"mode": "oidc", "server_address": "0.0.0.0",
            "emails": "reviewer@example.com, deputy@example.org"}
    assert evaluate_access(**base).action == "login"
    assert evaluate_access(**base, is_logged_in=True, email="reviewer@example.com").action == "deny"
    assert evaluate_access(**base, is_logged_in=True, email="random@example.com",
                           email_verified=True).action == "deny"
    assert evaluate_access(**base, is_logged_in=True, email="REVIEWER@EXAMPLE.COM",
                           email_verified=True).action == "allow"
    assert evaluate_access(**base, is_logged_in=True, email="deputy@example.org",
                           email_verified=True).action == "allow"


@pytest.mark.parametrize("emails", ["", "*@example.com", "example.com", ",",
                                     "reviewer@example.com,", "reviewer@", "@example.com"])
def test_oidc_denies_invalid_or_wildcard_allowlists(emails):
    assert not allowed_emails(emails)
    assert evaluate_access(mode="oidc", server_address="0.0.0.0",
                           emails=emails, is_logged_in=True,
                           email="reviewer@example.com", email_verified=True).action == "misconfigured"


def test_access_env_is_configurable_without_exposing_credentials():
    assert access_env({}) == ("local", "")
    assert access_env({"CVR_ACCESS_MODE": "oidc", "CVR_ALLOWED_EMAILS": "a@example.org"}) == (
        "oidc", "a@example.org")


def test_local_streamlit_config_uses_safe_upload_limits():
    root = Path(__file__).resolve().parents[1]
    config = tomllib.loads((root / ".streamlit/config.toml").read_text())
    server = config["server"]
    assert server["address"] == "127.0.0.1"
    assert server["enableXsrfProtection"] is True
    assert server["enableCORS"] is True
    assert server["enableStaticServing"] is False
    assert server["maxUploadSize"] == 48
    assert server["maxMessageSize"] >= server["maxUploadSize"]


def test_local_access_gate_runs_in_streamlit_without_external_identity():
    from streamlit.testing.v1 import AppTest

    def page():
        import streamlit as st
        from cv_ranker.ui.dashboard import _access_gate

        if _access_gate():
            st.success("Supervised local workspace allowed")

    app = AppTest.from_function(page).run(timeout=15)
    assert not app.exception
    assert any("Supervised local workspace allowed" in item.value for item in app.success)


def test_supervisor_full_app_renders_under_safe_local_policy():
    from streamlit.testing.v1 import AppTest

    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run(timeout=30)
    assert not app.exception
    assert len(app.tabs) == 4
    assert not app.error


def test_release_manifest_excludes_oidc_secrets_and_cache(tmp_path, monkeypatch):
    from scripts import rebuild_manifest

    source = tmp_path / "cv_ranker"
    source.mkdir()
    (source / "build_info.py").write_text(
        'BUILD_ID = "test"\nASSESSMENT_PROTOCOL = "test"\nASSESSMENT_PROTOCOL_VERSION = 1\n')
    (tmp_path / "app.py").write_text("# public source\n")
    config_dir = tmp_path / ".streamlit"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text("# public\n")
    (config_dir / "secrets.toml").write_text("token = 'SECRET'\n")
    (config_dir / "secrets.production.toml").write_text("token = 'SECRET'\n")
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=SECRET\n")
    (tmp_path / ".env.production").write_text("OPENROUTER_API_KEY=SECRET\n")
    cached = tmp_path / ".cv_ranker_cache"
    cached.mkdir()
    (cached / "recovery_signing.key").write_bytes(b"K" * 32)
    monkeypatch.setattr(rebuild_manifest, "ROOT", tmp_path)
    monkeypatch.setattr(rebuild_manifest, "MANIFEST", source / "build_manifest.json")

    rebuild_manifest.rebuild()
    manifest = json.loads((source / "build_manifest.json").read_text())
    assert "app.py" in manifest["files"]
    assert ".streamlit/config.toml" in manifest["files"]
    assert not any("SECRET" in (tmp_path / name).read_text(errors="ignore")
                   for name in manifest["files"])
    assert not any("secrets" in name or ".env.production" in name
                   or ".cv_ranker_cache" in name for name in manifest["files"])


def test_preflight_preserves_remote_deployment_blockers(monkeypatch):
    from scripts import production_preflight as preflight

    monkeypatch.setattr(preflight, "assert_runtime_current", lambda: {
        "assessment_protocol_version": "32"})
    monkeypatch.setattr(preflight, "access_env", lambda: ("oidc", "reviewer@example.com"))
    checks = preflight.run_checks(remote=True)
    assert next(c for c in checks if c.check == "OIDC allowlist").passed
    assert any(not c.passed for c in checks if c.check == "durable protected storage")
    assert preflight.main(["--remote", "--json"]) != 0


def test_sqlite_cache_private_permissions_and_multi_connection_writes(tmp_path):
    path = tmp_path / "private" / "embeddings.db"
    with SQLiteVectorCache(path) as cache:
        cache.put("seed", np.array([1.0, 0.0, 0.0], dtype=np.float32))
        assert cache._conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert path.is_file()
    if os.name == "posix" and path.stat().st_mode & 0o077:
        pytest.fail("Private embedding vectors were readable by another OS account")

    def write_worker(slot):
        with SQLiteVectorCache(path) as cache:
            for j in range(5):
                cache.put(f"candidate-{slot}-{j}", np.array([1.0, slot + 1.0, j + 1.0]))
            return cache.get(f"candidate-{slot}-4") is not None

    with ThreadPoolExecutor(max_workers=6) as pool:
        assert all(pool.map(write_worker, range(6)))
    with SQLiteVectorCache(path) as cache:
        assert cache.get("seed") is not None
        count = cache._conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    assert count == 31


def test_symlink_to_embedding_database_is_rejected(tmp_path):
    actual = tmp_path / "existing.db"
    actual.write_bytes(b"not a valid database")
    link = tmp_path / "cache.db"
    link.symlink_to(actual)
    with pytest.raises(EmbeddingError, match="symbolic link"):
        SQLiteVectorCache(link)
