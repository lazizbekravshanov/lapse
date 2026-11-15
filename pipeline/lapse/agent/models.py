"""Model adapters. The harness speaks one neutral shape; each adapter translates.

    model.step(system, messages, specs) -> Reply(text, calls)

messages is a list of dicts:
    {"role": "user", "text": ...}
    {"role": "assistant", "text": ..., "calls": [Call], "raw": provider message or None}
    {"role": "tool", "id": ..., "name": ..., "text": json string, "error": bool}

Keys are read from the environment and never printed, logged or stored:
    ANTHROPIC_API_KEY      Claude, through the Messages API
    OPENROUTER_API_KEY     any model on OpenRouter
    OPENAI_API_KEY         OpenAI
    LAPSE_BASE_URL         any OpenAI-compatible server, e.g. a local one (LAPSE_API_KEY if it needs one)
    LAPSE_MODEL            the model id to use
With none of these set, the harness answers by rule and needs no model at all.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


class ModelError(RuntimeError):
    """The model could not be used. The message is safe to show: it never holds a key."""


@dataclass
class Call:
    id: str
    name: str
    args: dict


@dataclass
class Reply:
    text: str = ""
    calls: list = field(default_factory=list)
    raw: object = None           # the provider's own assistant message, sent back unchanged next turn


def _post(url: str, headers: dict, body: dict, who: str, post=None) -> dict:
    """One HTTP call. Every failure becomes a ModelError with a short, key-free message."""
    if post is None:
        import requests
        post = requests.post
    try:
        r = post(url, headers=headers, json=body, timeout=120)
    except Exception as exc:                                    # connection refused, timeout, DNS
        raise ModelError(f"{who} could not be reached ({type(exc).__name__})") from None
    if r.status_code != 200:
        try:
            err = r.json().get("error", {})
            detail = err.get("message", "") if isinstance(err, dict) else str(err)
        except Exception:
            detail = ""
        raise ModelError(f"{who} answered {r.status_code}" + (f": {detail[:200]}" if detail else ""))
    try:
        return r.json()
    except Exception:
        raise ModelError(f"{who} sent something that is not JSON") from None


# --- Claude, through the Messages API ---------------------------------------------

def to_anthropic(messages: list) -> list:
    out = []
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "content": [{"type": "text", "text": m["text"]}]})
        elif m["role"] == "assistant":
            if m.get("raw") is not None:                         # keep the model's own blocks intact
                out.append({"role": "assistant", "content": m["raw"]})
                continue
            blocks = [{"type": "text", "text": m["text"]}] if m.get("text") else []
            blocks += [{"type": "tool_use", "id": c.id, "name": c.name, "input": c.args} for c in m.get("calls", [])]
            out.append({"role": "assistant", "content": blocks})
        else:                                                    # tool results travel in one user message
            block = {"type": "tool_result", "tool_use_id": m["id"], "content": m["text"]}
            if m.get("error"):
                block["is_error"] = True
            last = out[-1] if out else None
            if last and last["role"] == "user" and last["content"] and last["content"][0]["type"] == "tool_result":
                last["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
    return out


class Anthropic:
    name = "anthropic"
    URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, model: str | None = None, key: str | None = None, post=None):
        self.key = key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.key:
            raise ModelError("ANTHROPIC_API_KEY is not set")
        self.model = model or os.environ.get("LAPSE_MODEL") or "claude-sonnet-5-5"
        self.version = os.environ.get("ANTHROPIC_VERSION", "2026-10-21")
        self.post = post
        self.label = f"Claude ({self.model})"

    def step(self, system: str, messages: list, specs: list) -> Reply:
        body = {
            "model": self.model, "max_tokens": 1500, "system": system, "messages": to_anthropic(messages),
            "tools": [{"name": s["name"], "description": s["description"], "input_schema": s["parameters"]}
                      for s in specs],
        }
        base = {"content-type": "application/json", "anthropic-version": self.version}
        # The current API reference sends the key as a bearer token; x-api-key is the older header.
        # Both exist, so if the first is refused the second is tried once.
        ways = ({"authorization": f"Bearer {self.key}"}, {"x-api-key": self.key})
        for n, auth in enumerate(ways):
            try:
                data = _post(self.URL, {**base, **auth}, body, "The Claude API", self.post)
                break
            except ModelError as exc:
                if "answered 401" not in str(exc) or n == len(ways) - 1:
                    raise
        blocks = data.get("content") or []
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        calls = [Call(b["id"], b["name"], b.get("input") or {}) for b in blocks if b.get("type") == "tool_use"]
        return Reply(text=text, calls=calls, raw=blocks)


# --- anything that speaks the OpenAI chat format ------------------------------------

def to_openai(system: str, messages: list) -> list:
    out = [{"role": "system", "content": system}]
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["text"]})
        elif m["role"] == "assistant":
            msg = {"role": "assistant", "content": m.get("text") or None}
            if m.get("calls"):
                msg["tool_calls"] = [{"id": c.id, "type": "function",
                                      "function": {"name": c.name, "arguments": json.dumps(c.args)}}
                                     for c in m["calls"]]
            out.append(msg)
        else:
            out.append({"role": "tool", "tool_call_id": m["id"], "content": m["text"]})
    return out


PRESETS = {
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
    "ollama": ("http://localhost:11434/v1", None),
    "custom": (None, "LAPSE_API_KEY"),
}


class OpenAICompatible:
    def __init__(self, preset: str = "custom", model: str | None = None, post=None):
        base, key_name = PRESETS[preset]
        self.name = preset
        self.base = (os.environ.get("LAPSE_BASE_URL") or base or "").rstrip("/")
        if not self.base:
            raise ModelError("LAPSE_BASE_URL is not set")
        self.key = os.environ.get(key_name, "") if key_name else ""
        if key_name and not self.key and preset != "custom":
            raise ModelError(f"{key_name} is not set")
        self.model = model or os.environ.get("LAPSE_MODEL", "")
        if not self.model:
            raise ModelError("LAPSE_MODEL is not set. Set it to the id of a model that can call tools")
        self.post = post
        self.label = f"{preset} ({self.model})"

    def step(self, system: str, messages: list, specs: list) -> Reply:
        body = {
            "model": self.model, "messages": to_openai(system, messages),
            "tools": [{"type": "function", "function": {"name": s["name"], "description": s["description"],
                                                        "parameters": s["parameters"]}} for s in specs],
        }
        headers = {"content-type": "application/json"}
        if self.key:
            headers["authorization"] = f"Bearer {self.key}"
        data = _post(f"{self.base}/chat/completions", headers, body, f"The {self.name} server", self.post)
        try:
            msg = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError):
            raise ModelError(f"The {self.name} server sent an answer in an unexpected shape") from None
        calls = []
        for i, c in enumerate(msg.get("tool_calls") or []):
            fn = c.get("function", {})
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {"_unreadable": fn.get("arguments")}      # the tool layer rejects it and says why
            calls.append(Call(c.get("id") or f"call_{i}", fn.get("name", ""), args if isinstance(args, dict) else {}))
        return Reply(text=msg.get("content") or "", calls=calls)


# --- a model that follows a script, for tests -----------------------------------------

class Scripted:
    """Plays back prepared replies. Each item is a Reply, or a function of the messages so far."""
    name = label = "scripted"

    def __init__(self, replies: list):
        self.replies = list(replies)
        self.seen = []

    def step(self, system: str, messages: list, specs: list) -> Reply:
        self.seen.append([dict(m) for m in messages])
        if not self.replies:
            raise ModelError("the script ran out")
        nxt = self.replies.pop(0)
        return nxt(messages) if callable(nxt) else nxt


def pick(name: str | None = None, site=None):
    """Choose a model from a name or from whichever key is set. No key means the rule-based planner."""
    from .planner import Planner

    name = (name or os.environ.get("LAPSE_AGENT") or "auto").lower()
    if name in ("rules", "none", "off"):
        return Planner(site)
    if name == "auto":
        for env, choice in (("ANTHROPIC_API_KEY", "anthropic"), ("OPENROUTER_API_KEY", "openrouter"),
                            ("OPENAI_API_KEY", "openai"), ("LAPSE_BASE_URL", "custom")):
            if os.environ.get(env):
                name = choice
                break
        else:
            return Planner(site)
    if name in ("anthropic", "claude"):
        return Anthropic()
    if name in PRESETS:
        return OpenAICompatible(name)
    raise ModelError(f"Unknown model choice {name!r}. Use auto, rules, anthropic, openrouter, openai, ollama or custom")
