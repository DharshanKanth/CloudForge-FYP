"""Advisory AI layer.

Provider-agnostic and disabled by default. The assistant only ever produces
*structured suggestions* (or explanatory text) — the deterministic validator
gates the architecture and the user must apply anything. It never runs
Terraform or touches infrastructure. When no provider is configured the
endpoints report ``configured: false`` instead of fabricating output.
"""
import json
import os
from typing import Dict, List, Optional, Tuple

import httpx

from app.schemas.ai import AIArchitecture
from app.services.validation_service import SUPPORTED_RESOURCE_TYPES


class AIUnavailable(RuntimeError):
    """Raised when no AI provider is configured."""


DEFAULT_BASE = {
    "openai": "https://api.openai.com/v1",
    "ollama": "http://localhost:11434/v1",
}
DEFAULT_MODEL = {
    "openai": "gpt-4o-mini",
    "ollama": "llama3.1",
}


def _provider() -> str:
    explicit = (os.getenv("AI_PROVIDER") or "").strip().lower()
    if explicit in ("none", "disabled"):
        return "none"
    if explicit in ("openai", "ollama"):
        return explicit
    # Auto-detect: any OpenAI-compatible endpoint (key or base URL) is usable.
    if os.getenv("AI_API_KEY") or os.getenv("AI_BASE_URL"):
        return "openai"
    return "none"


def _base_url() -> Optional[str]:
    url = os.getenv("AI_BASE_URL")
    if url:
        return url.rstrip("/")
    return DEFAULT_BASE.get(_provider())


def _model() -> str:
    return os.getenv("AI_MODEL") or DEFAULT_MODEL.get(_provider(), "")


def status() -> Dict:
    provider = _provider()
    configured = provider != "none"
    return {
        "configured": configured,
        "provider": provider,
        "model": _model() if configured else "",
        "base_url": _base_url() if configured else None,
    }


async def _chat(messages: List[Dict[str, str]], response_json: bool = True) -> str:
    provider = _provider()
    if provider == "none":
        raise AIUnavailable("AI is not configured. Set AI_PROVIDER/AI_API_KEY on the backend.")

    url = (_base_url() or "").rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    key = os.getenv("AI_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"

    payload: Dict = {"model": _model(), "messages": messages, "temperature": 0.2}
    if response_json:
        # OpenAI uses response_format; Ollama uses format="json".
        if provider == "ollama":
            payload["format"] = "json"
        else:
            payload["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"]


_ALLOWED_TYPES = ", ".join(sorted(SUPPORTED_RESOURCE_TYPES))
_SYSTEM_ARCHITECT = (
    "You are an AWS cloud architecture assistant. Given a plain-English request, "
    "reply with ONLY minified JSON of the form "
    '{"nodes":[{"id":"vpc","resourceType":"vpc","properties":{"name":"main-vpc","cidr":"10.0.0.0/16"}}],'
    '"edges":[{"source":"vpc","target":"subnet"}],"rationale":"short explanation"}. '
    f"Allowed resourceType values: {_ALLOWED_TYPES}. "
    "Include the required properties for each resource. Do not output anything else."
)


def to_canvas(arch: AIArchitecture) -> Tuple[List[Dict], List[Dict]]:
    """Convert an AI proposal into builder-canvas nodes/edges (not yet validated)."""
    nodes: List[Dict] = []
    for i, n in enumerate(arch.nodes):
        nodes.append({
            "id": n.id or f"ai-{i}",
            "type": "resourceNode",
            "position": {"x": 220 * (i % 4), "y": 160 * (i // 4)},
            "data": {
                "label": n.id,
                "resourceType": n.resourceType,
                "provider": "aws",
                "properties": n.properties,
            },
        })
    edges = [
        {"id": f"ai-e{i}", "source": e.source, "target": e.target}
        for i, e in enumerate(arch.edges)
    ]
    return nodes, edges


async def recommend_architecture(prompt: str) -> AIArchitecture:
    messages = [
        {"role": "system", "content": _SYSTEM_ARCHITECT},
        {"role": "user", "content": prompt},
    ]
    content = await _chat(messages, response_json=True)
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("The AI did not return valid JSON") from exc
    return AIArchitecture.model_validate(data)


def _join_files(files, limit: int) -> str:
    parts = [f"# {getattr(f, 'filename', 'file')}\n{getattr(f, 'content', '')}" for f in files]
    return "\n\n".join(parts)[:limit]


async def explain_terraform(files) -> str:
    messages = [
        {"role": "system", "content": "Explain Terraform configuration to a beginner, concisely, in markdown."},
        {"role": "user", "content": _join_files(files, 20000)},
    ]
    return await _chat(messages, response_json=False)


async def troubleshoot(error: str, files) -> str:
    messages = [
        {"role": "system", "content": "You are a Terraform troubleshooting assistant. Explain the cause and the fix concisely."},
        {"role": "user", "content": f"Terraform error:\n{error}\n\nConfiguration:\n{_join_files(files, 12000)}"},
    ]
    return await _chat(messages, response_json=False)
