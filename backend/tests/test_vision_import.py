"""Tests for the vision (image) import path — advisory only."""
import asyncio
import json

import pytest

from app.services import ai_service
from app.services.diagram_import import finalize_proposal


@pytest.mark.parametrize("model,expected", [
    ("gpt-4o-mini", True),
    ("gpt-4o", True),
    ("gpt-5", True),
    ("claude-3-5-sonnet", True),
    ("qwen2.5-vl", True),
    ("llava", True),
    ("qwen2.5:3b", False),
    ("llama3.1", False),
    ("", False),
])
def test_is_vision_capable(model, expected):
    assert ai_service.is_vision_capable(model) is expected


def test_analyze_diagram_image_sends_multimodal_message(monkeypatch):
    captured = {}

    async def fake_chat(messages, response_json=True, schema=None, max_tokens=None):
        captured["messages"] = messages
        captured["max_tokens"] = max_tokens
        return json.dumps({
            "nodes": [
                {"id": "vpc", "resourceType": "vpc",
                 "properties": {"name": "vpc", "cidr": "10.0.0.0/16"}},
                {"id": "web", "resourceType": "ec2",
                 "properties": {"name": "web", "instanceType": "t3.micro"}},
                {"id": "waf", "resourceType": "waf", "properties": {}},
            ],
            "edges": [{"source": "vpc", "target": "web"}],
            "unrecognized": [{"label": "AWS WAF", "reason": "no matching type"}],
            "rationale": "A VPC with a web server.",
        })

    monkeypatch.setenv("AI_API_KEY", "sk-test")
    monkeypatch.setattr(ai_service, "_chat", fake_chat)
    arch = asyncio.run(ai_service.analyze_diagram_image("data:image/png;base64,AAAA"))

    assert arch.nodes and arch.unrecognized[0]["label"] == "AWS WAF"
    user = [m for m in captured["messages"] if m["role"] == "user"][0]
    assert isinstance(user["content"], list)
    assert user["content"][1]["image_url"]["url"] == "data:image/png;base64,AAAA"
    assert captured["max_tokens"] == 1500


def test_to_canvas_drops_unsupported_types():
    from app.schemas.ai import AIArchitecture

    arch = AIArchitecture.model_validate({
        "nodes": [
            {"id": "vpc", "resourceType": "vpc", "properties": {"name": "v", "cidr": "10.0.0.0/16"}},
            {"id": "waf", "resourceType": "waf", "properties": {}},
        ],
        "edges": [{"source": "vpc", "target": "waf"}],
    })
    nodes, edges = ai_service.to_canvas(arch)
    assert [n["id"] for n in nodes] == ["vpc"]
    assert edges == []


def test_finalize_proposal_image_shape():
    nodes = [{
        "id": "vpc", "type": "resourceNode", "position": {"x": 0, "y": 0},
        "data": {"label": "VPC", "resourceType": "vpc", "provider": "aws",
                 "properties": {"name": "vpc", "cidr": "10.0.0.0/16"}},
    }]
    result = finalize_proposal("image", "architecture image", nodes, [], [("AWS WAF", "no match")], [])
    assert result["format"] == "image"
    assert result["recognized"] == 1
    assert result["unrecognized"][0]["label"] == "AWS WAF"
    assert result["validation"] is not None
    assert "architecture image" in result["summary"]
