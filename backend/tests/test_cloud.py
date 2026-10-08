"""Tests for cloud-account credential handling.

These are unit tests over the crypto and env-mapping helpers — no database and
no AWS. The DB-backed CRUD is covered by the API smoke test.
"""
import pytest

from app.core import crypto
from app.schemas.cloud import CloudAccountResponse
from app.services.cloud_service import build_aws_env


def test_credentials_round_trip():
    creds = {
        "access_key_id": "AKIAEXAMPLE",
        "secret_access_key": "supersecret",
        "session_token": None,
        "region": "eu-west-1",
    }
    token = crypto.encrypt_credentials(creds)
    assert token != "supersecret"
    assert crypto.decrypt_credentials(token) == creds


def test_credentials_are_not_plaintext():
    token = crypto.encrypt_credentials({"secret_access_key": "topsecretvalue"})
    assert "topsecretvalue" not in token


def test_tampered_token_raises():
    token = crypto.encrypt_credentials({"a": "b"})
    with pytest.raises(ValueError):
        crypto.decrypt_credentials(token[:-4] + "AAAA")


def test_build_aws_env_maps_only_present_values():
    env = build_aws_env(
        {"access_key_id": "AK", "secret_access_key": "SK", "session_token": None, "region": "us-east-2"}
    )
    assert env == {
        "AWS_ACCESS_KEY_ID": "AK",
        "AWS_SECRET_ACCESS_KEY": "SK",
        "AWS_DEFAULT_REGION": "us-east-2",
    }
    assert build_aws_env({}) == {}


def test_response_schema_never_exposes_secrets():
    # The response model has no credential fields at all.
    fields = set(CloudAccountResponse.model_fields)
    assert not fields & {"access_key_id", "secret_access_key", "session_token", "encrypted_credentials"}
