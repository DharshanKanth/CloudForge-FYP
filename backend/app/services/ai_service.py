"""Advisory AI layer.

Provider-agnostic and disabled by default. The assistant only ever produces
*structured suggestions* (or explanatory text) — the deterministic validator
gates the architecture and the user must apply anything. It never runs
Terraform or touches infrastructure. When no provider is configured the
endpoints report ``configured: false`` instead of fabricating output.
"""
import json
import logging
import os
from typing import Dict, List, Optional, Tuple

import httpx

from app.schemas.ai import AIArchitecture
from app.services.validation_service import SUPPORTED_RESOURCE_TYPES

logger = logging.getLogger("cloudforge.ai")


class AIUnavailable(RuntimeError):
    """Raised when no AI provider is configured."""


class AIProviderError(RuntimeError):
    """Raised when a configured provider fails (unreachable, timeout, bad status)."""


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


async def _chat(messages: List[Dict[str, str]], response_json: bool = True, schema: Optional[Dict] = None) -> str:
    provider = _provider()
    if provider == "none":
        raise AIUnavailable("AI is not configured. Set AI_PROVIDER/AI_API_KEY on the backend.")

    url = (_base_url() or "").rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    key = os.getenv("AI_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"

    payload: Dict = {
        "model": _model(),
        "messages": messages,
        "temperature": 0,
        # Bound latency: a small local model can otherwise loop until it fills
        # the context window.
        "max_tokens": int(os.getenv("AI_MAX_TOKENS", "900")),
    }
    if schema is not None:
        # Constrain output to a JSON schema (Ollama accepts a schema in `format`;
        # OpenAI uses response_format.json_schema).
        if provider == "ollama":
            payload["format"] = schema
        else:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "result", "schema": schema, "strict": True},
            }
    elif response_json:
        if provider == "ollama":
            payload["format"] = "json"
        else:
            payload["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=float(os.getenv("AI_TIMEOUT", "300"))) as client:
        try:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            # Provider unreachable / error — surfaced distinctly, never faked.
            raise AIProviderError(f"AI provider request failed: {exc}") from exc
        data = resp.json()
    return data["choices"][0]["message"]["content"]


_ALLOWED_TYPES = ", ".join(sorted(SUPPORTED_RESOURCE_TYPES))
_SYSTEM_ARCHITECT = (
    "You are an AWS cloud architecture assistant. Given a plain-English request, "
    "design an architecture and reply with JSON only (no prose, no markdown).\n"
    "Rules: use ONLY these resourceType values: " + _ALLOWED_TYPES + ".\n"
    "Every node id must be unique and lowercase. Include required properties for "
    "each resource (vpc: name+cidr; subnet: name+cidr; ec2: name+instanceType; "
    "security_group: name). Draw only valid relationships "
    "(vpc->subnet, subnet->ec2, security_group->ec2).\n"
    "Example reply for 'a vpc with a subnet and a web server':\n"
    '{"nodes":[{"id":"vpc","resourceType":"vpc","properties":{"name":"main-vpc","cidr":"10.0.0.0/16"}},'
    '{"id":"subnet","resourceType":"subnet","properties":{"name":"public-subnet","cidr":"10.0.1.0/24"}},'
    '{"id":"web","resourceType":"ec2","properties":{"name":"web-server","instanceType":"t3.micro"}},'
    '{"id":"sg","resourceType":"security_group","properties":{"name":"web-sg"}}],'
    '"edges":[{"source":"vpc","target":"subnet"},{"source":"subnet","target":"web"},'
    '{"source":"sg","target":"web"}],"rationale":"A VPC with one public subnet and a web server."}'
)

# JSON schema passed to the model to constrain the output shape and the
# resourceType enum (Ollama structured outputs / OpenAI json_schema).
_ARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "rationale": {"type": "string"},
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "resourceType": {"type": "string", "enum": sorted(SUPPORTED_RESOURCE_TYPES)},
                    "properties": {"type": "object"},
                },
                "required": ["id", "resourceType"],
            },
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"source": {"type": "string"}, "target": {"type": "string"}},
                "required": ["source", "target"],
            },
        },
    },
    "required": ["nodes", "edges"],
}


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


def _extract_json(text: str) -> Dict:
    """Best-effort extraction of a JSON object from model output.

    Small local models often wrap JSON in prose or code fences; we take the
    outermost ``{...}`` and parse it. Anything still unparseable is an error.
    """
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned[:4].lower() == "json":
            cleaned = cleaned[4:].strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        pass
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            pass
    raise ValueError("The AI did not return valid JSON")


async def recommend_architecture(prompt: str) -> AIArchitecture:
    messages = [
        {"role": "system", "content": _SYSTEM_ARCHITECT},
        {"role": "user", "content": prompt},
    ]
    # Local CPU models struggle with grammar-constrained output, so enforce the
    # schema only for hosted providers; otherwise rely on the few-shot prompt and
    # the deterministic validator.
    use_schema = _provider() != "ollama"
    content = await _chat(messages, response_json=True, schema=_ARCH_SCHEMA if use_schema else None)
    try:
        data = _extract_json(content)
    except ValueError:
        logger.warning("AI returned unparseable output (%d chars): %.600s", len(content or ""), content)
        raise
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
