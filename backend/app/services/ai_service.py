"""Advisory AI layer.

Provider-agnostic and disabled by default. The assistant only ever produces
*structured suggestions* (or explanatory text) — the deterministic validator
gates the architecture and the user must apply anything. It never runs
Terraform or touches infrastructure. When no provider is configured the
endpoints report ``configured: false`` instead of fabricating output.
"""
import contextvars
import json
import logging
import os
from dataclasses import dataclass
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


@dataclass
class AIConfig:
    provider: str = "none"          # none | openai | ollama
    base_url: Optional[str] = None
    model: str = ""
    api_key: Optional[str] = None


# The active config for the current request. A per-user saved setting sets this;
# otherwise it falls back to the process environment.
_config_var: contextvars.ContextVar[Optional[AIConfig]] = contextvars.ContextVar(
    "cloudforge_ai_config", default=None
)


def config_from_env() -> AIConfig:
    """Provider config derived from environment variables (server default)."""
    explicit = (os.getenv("AI_PROVIDER") or "").strip().lower()
    if explicit in ("none", "disabled"):
        provider = "none"
    elif explicit in ("openai", "ollama"):
        provider = explicit
    elif os.getenv("AI_API_KEY") or os.getenv("AI_BASE_URL"):
        provider = "openai"
    else:
        provider = "none"
    if provider == "none":
        return AIConfig()
    base = os.getenv("AI_BASE_URL")
    base = base.rstrip("/") if base else DEFAULT_BASE.get(provider)
    model = os.getenv("AI_MODEL") or DEFAULT_MODEL.get(provider, "")
    return AIConfig(provider=provider, base_url=base, model=model, api_key=os.getenv("AI_API_KEY"))


def set_config(cfg: Optional[AIConfig]) -> None:
    """Set the config used for this request (None -> environment fallback)."""
    _config_var.set(cfg)


def current_config() -> AIConfig:
    return _config_var.get() or config_from_env()


def _provider() -> str:
    return current_config().provider


def _base_url() -> Optional[str]:
    return current_config().base_url


def _model() -> str:
    return current_config().model


def status() -> Dict:
    cfg = current_config()
    configured = cfg.provider != "none"
    return {
        "configured": configured,
        "provider": cfg.provider,
        "model": cfg.model if configured else "",
        "base_url": cfg.base_url if configured else None,
    }


async def test_connection(cfg: AIConfig) -> Dict:
    """Validate a candidate config with a minimal chat call. Never raises."""
    if cfg.provider == "none":
        return {"ok": False, "message": "No provider selected."}
    token = _config_var.set(cfg)
    try:
        await _chat([{"role": "user", "content": "Reply with the single word: ok"}], response_json=False)
        return {"ok": True, "message": "Connection successful."}
    except Exception as exc:  # noqa: BLE001 - surface the provider error
        return {"ok": False, "message": str(exc)}
    finally:
        _config_var.reset(token)


async def _chat(messages: List[Dict[str, str]], response_json: bool = True, schema: Optional[Dict] = None) -> str:
    provider = _provider()
    if provider == "none":
        raise AIUnavailable("AI is not configured. Set AI_PROVIDER/AI_API_KEY on the backend.")

    url = (_base_url() or "").rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    key = current_config().api_key
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
    """Convert an AI proposal into builder-canvas nodes/edges.

    A deterministic safety net: nodes with an unsupported resourceType are
    dropped, and edges referencing unknown nodes are dropped. The result is
    still validated by the caller.
    """
    kept = [
        n for n in arch.nodes
        if n.resourceType in SUPPORTED_RESOURCE_TYPES and n.id
    ]
    kept_ids = {n.id for n in kept}

    nodes: List[Dict] = []
    for i, n in enumerate(kept):
        nodes.append({
            "id": n.id,
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
        if e.source in kept_ids and e.target in kept_ids and e.source != e.target
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


async def _design_from_messages(messages: List[Dict[str, str]]) -> AIArchitecture:
    """Query the model and coerce its JSON into an AIArchitecture (one retry).

    Small local models are stochastic and can emit invalid JSON or an empty
    design; retrying once materially improves the success rate.
    """
    use_schema = _provider() != "ollama"
    last_error: Optional[Exception] = None
    for attempt in range(2):
        content = await _chat(messages, response_json=True, schema=_ARCH_SCHEMA if use_schema else None)
        try:
            arch = AIArchitecture.model_validate(_extract_json(content))
        except Exception as exc:  # noqa: BLE001 - ValueError or pydantic ValidationError
            logger.warning(
                "AI attempt %d returned unparseable output (%d chars): %.400s",
                attempt + 1, len(content or ""), content,
            )
            last_error = exc
            continue
        if arch.nodes:
            return arch
        logger.warning("AI attempt %d returned no resources", attempt + 1)
        last_error = ValueError("The AI returned no resources")
    raise last_error or ValueError("The AI did not return a usable design")


async def recommend_architecture(prompt: str) -> AIArchitecture:
    return await _design_from_messages([
        {"role": "system", "content": _SYSTEM_ARCHITECT},
        {"role": "user", "content": prompt},
    ])


_SYSTEM_FIX = (
    _SYSTEM_ARCHITECT
    + " You are given an existing design and the exact validation problems with it. "
    "Make the MINIMAL change that resolves each listed problem — prefer adding or removing "
    "edges over altering resources. Keep every existing node's id. Do NOT invent resource "
    "types: use only the allowed values. Return the corrected design in the same JSON format."
)


def _slim_node(node: Dict) -> Dict:
    data = node.get("data", {}) or {}
    return {
        "id": node.get("id"),
        "resourceType": data.get("resourceType") or node.get("type"),
        "properties": data.get("properties", {}) or {},
    }


async def fix_architecture(nodes, edges, issues) -> AIArchitecture:
    """Ask the model to repair a design given the validator's findings."""
    design = _design_json(nodes, edges)
    problems = "\n".join(
        f"- [{i.get('level')}] {i.get('message')}" for i in issues[:40]
    ) or "(none)"
    messages = [
        {"role": "system", "content": _SYSTEM_FIX},
        {
            "role": "user",
            "content": f"Current design:\n{design}\n\nValidation problems:\n{problems}\n\nReturn the corrected design.",
        },
    ]
    return await _design_from_messages(messages)


def _design_json(nodes, edges) -> str:
    return json.dumps({
        "nodes": [_slim_node(n) for n in nodes],
        "edges": [{"source": e.get("source"), "target": e.get("target")} for e in edges],
    })


async def analyze_security(nodes, edges, findings) -> str:
    """Higher-level security review layered on the deterministic findings."""
    problems = "\n".join(
        f"- [{f.get('severity')}] {f.get('title')} — {f.get('recommendation')}"
        for f in (findings or [])[:40]
    ) or "(none)"
    messages = [
        {
            "role": "system",
            "content": (
                "You are an AWS security reviewer. Given an architecture and the deterministic "
                "findings already detected, give a concise, prioritised security review and flag any "
                "additional higher-level concerns the fixed rules may have missed (e.g. missing private "
                "subnets, over-broad exposure, missing encryption/monitoring). Advisory only."
            ),
        },
        {
            "role": "user",
            "content": f"Design:\n{_design_json(nodes, edges)}\n\nDetected findings:\n{problems}\n\nGive a short prioritised review.",
        },
    ]
    return await _chat(messages, response_json=False)


async def optimize_cost(estimate, nodes) -> str:
    """Cost-optimization advice grounded in the deterministic estimate."""
    items = "\n".join(
        f"- {i.get('resource_type')} '{i.get('label')}': ${i.get('monthly_cost')}/mo ({i.get('note')})"
        for i in (estimate or {}).get("items", [])
    ) or "(none)"
    messages = [
        {
            "role": "system",
            "content": (
                "You are an AWS cost-optimization assistant. Using ONLY the provided deterministic "
                "estimate, suggest concrete optimizations (right-sizing, alternatives, removing idle "
                "resources) with rough monthly savings. Do not invent prices beyond the estimate. Concise."
            ),
        },
        {
            "role": "user",
            "content": f"Monthly total: ${(estimate or {}).get('monthly_total')} USD\nLine items:\n{items}\n\nSuggest optimizations.",
        },
    ]
    return await _chat(messages, response_json=False)


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
