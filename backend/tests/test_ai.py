"""AI layer unit tests — no network, no real provider."""
import asyncio
import json

import pytest

from app.schemas.ai import AIArchitecture
from app.services import ai_service
from app.services.validation_service import validate_architecture


@pytest.fixture(autouse=True)
def _clear_ai_env(monkeypatch):
    for var in ("AI_PROVIDER", "AI_API_KEY", "AI_BASE_URL", "AI_MODEL"):
        monkeypatch.delenv(var, raising=False)


def test_status_disabled_by_default():
    status = ai_service.status()
    assert status["configured"] is False
    assert status["provider"] == "none"


def test_status_openai_when_key_present(monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "sk-test")
    status = ai_service.status()
    assert status["configured"] is True
    assert status["provider"] == "openai"
    assert status["base_url"].startswith("https://api.openai.com")


def test_status_ollama_uses_local_base(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    status = ai_service.status()
    assert status["provider"] == "ollama"
    assert "localhost:11434" in status["base_url"]


def test_recommend_parses_structured_response(monkeypatch):
    payload = {
        "nodes": [
            {"id": "vpc", "resourceType": "vpc", "properties": {"name": "v", "cidr": "10.0.0.0/16"}},
            {"id": "sub", "resourceType": "subnet", "properties": {"name": "s", "cidr": "10.0.1.0/24"}},
        ],
        "edges": [{"source": "vpc", "target": "sub"}],
        "rationale": "A VPC with one subnet.",
    }

    async def fake_chat(messages, response_json=True, schema=None):
        return json.dumps(payload)

    monkeypatch.setenv("AI_API_KEY", "sk-test")
    monkeypatch.setattr(ai_service, "_chat", fake_chat)

    arch = asyncio.run(ai_service.recommend_architecture("a vpc with a subnet"))
    assert isinstance(arch, AIArchitecture)
    assert len(arch.nodes) == 2

    nodes, edges = ai_service.to_canvas(arch)
    # Canvas shape + the deterministic validator gates the suggestion.
    assert nodes[0]["data"]["resourceType"] == "vpc"
    assert nodes[0]["type"] == "resourceNode"
    assert edges[0]["source"] == "vpc"
    assert validate_architecture(nodes, edges).valid is True


def test_recommend_raises_when_unconfigured():
    with pytest.raises(ai_service.AIUnavailable):
        asyncio.run(ai_service.recommend_architecture("anything"))


def test_recommend_rejects_non_json(monkeypatch):
    async def fake_chat(messages, response_json=True, schema=None):
        return "not json"

    monkeypatch.setenv("AI_API_KEY", "sk-test")
    monkeypatch.setattr(ai_service, "_chat", fake_chat)
    with pytest.raises(ValueError):
        asyncio.run(ai_service.recommend_architecture("x"))


def test_extract_json_handles_fences_and_prose():
    assert ai_service._extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert ai_service._extract_json('Here you go: {"nodes": [], "edges": []} done') == {
        "nodes": [],
        "edges": [],
    }


def test_extract_json_rejects_garbage():
    with pytest.raises(ValueError):
        ai_service._extract_json("no json at all")


def test_analyze_security_returns_model_text(monkeypatch):
    async def fake_chat(messages, response_json=True, schema=None):
        assert response_json is False  # free text, not JSON
        return "Prioritised review: restrict SSH and add a private subnet."

    monkeypatch.setenv("AI_API_KEY", "sk-test")
    monkeypatch.setattr(ai_service, "_chat", fake_chat)
    text = asyncio.run(ai_service.analyze_security(
        [], [], [{"severity": "high", "title": "SSH open", "recommendation": "restrict"}]
    ))
    assert "review" in text.lower()


def test_optimize_cost_returns_model_text(monkeypatch):
    async def fake_chat(messages, response_json=True, schema=None):
        return "Right-size the EC2 instance to t3.small."

    monkeypatch.setenv("AI_API_KEY", "sk-test")
    monkeypatch.setattr(ai_service, "_chat", fake_chat)
    text = asyncio.run(ai_service.optimize_cost(
        {"monthly_total": 82, "items": [{"resource_type": "ec2", "label": "web", "monthly_cost": 30, "note": "t3.medium"}]},
        [],
    ))
    assert "EC2" in text


def test_config_from_input_applies_defaults():
    from app.services import ai_config_service

    cfg = ai_config_service.config_from_input("ollama", None, "", None)
    assert cfg.provider == "ollama"
    assert "11434" in cfg.base_url
    assert cfg.model  # provider default
    cfg2 = ai_config_service.config_from_input("openai", "https://api.example.com/v1/", "my-model", "sk-1")
    assert cfg2.base_url == "https://api.example.com/v1"
    assert cfg2.model == "my-model"
    assert cfg2.api_key == "sk-1"
