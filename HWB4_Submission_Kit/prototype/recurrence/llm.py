"""LLM layer: Groq (OpenAI-compatible) with defensive tool-calling, plus an offline stand-in.

Groq's OpenAI-compatible endpoint is https://api.groq.com/openai/v1. Open models
sometimes emit malformed tool calls; Groq then answers HTTP 400 with error code
``tool_use_failed``. We handle that and every other tool-call failure mode here
so the on-call engineer still gets an answer.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Callable

log = logging.getLogger("recurrence.llm")

ToolExecutor = Callable[[str, dict[str, Any]], str]

_THINK = re.compile(r"<think>.*?</think>", re.S)


def strip_reasoning(text: str | None) -> str:
    """qwen3 models may wrap chain-of-thought in <think> tags; never show it to the user."""
    return _THINK.sub("", text or "").strip()


def parse_tool_args(raw: str | None) -> dict[str, Any]:
    """Parse tool-call arguments; tolerate ```json fences and trailing junk. Raise ValueError if hopeless."""
    if raw is None or raw == "":
        return {}
    txt = raw.strip()
    txt = re.sub(r"^```(?:json)?|```$", "", txt).strip()
    try:
        val = json.loads(txt)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", txt, re.S)
        if not m:
            raise ValueError(f"tool arguments are not JSON: {raw[:120]!r}")
        val = json.loads(m.group(0))
    if not isinstance(val, dict):
        raise ValueError("tool arguments must be a JSON object")
    return val


class LLMUnavailable(RuntimeError):
    pass


class GroqLLM:
    name = "groq"

    def __init__(self, api_key: str, base_url: str, model: str, fallback_model: str | None = None, client: Any = None):
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=api_key, base_url=base_url, timeout=45.0, max_retries=1)
        self.client = client
        self.model = model
        self.fallback_model = fallback_model

    def _create(self, model: str, messages: list[dict], tools: list[dict] | None, tool_choice: str | None):
        kwargs: dict[str, Any] = {"model": model, "messages": messages, "temperature": 0.2}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"
        return self.client.chat.completions.create(**kwargs)

    def _call(self, messages, tools, tool_choice, trace) -> Any:
        """One completion with error handling. Returns the message object."""
        import openai

        models = [self.model] + ([self.fallback_model] if self.fallback_model else [])
        last_exc: Exception | None = None
        for model in models:
            for attempt in range(2):
                try:
                    resp = self._create(model, messages, tools, tool_choice)
                    return resp.choices[0].message
                except openai.BadRequestError as exc:
                    body = str(getattr(exc, "body", "")) + str(exc)
                    if "tool_use_failed" in body or "tool call" in body.lower():
                        trace.append({"event": "tool_use_failed", "model": model, "detail": body[:300]})
                        last_exc = exc
                        break  # try the fallback model rather than resending the same prompt
                    raise
                except (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError) as exc:
                    trace.append({"event": "transient_error", "model": model, "attempt": attempt, "detail": str(exc)[:200]})
                    last_exc = exc
                    time.sleep(1.5 * (attempt + 1))
                except openai.APIStatusError as exc:  # 5xx etc.
                    trace.append({"event": "api_error", "model": model, "detail": str(exc)[:200]})
                    last_exc = exc
                    break
        # Last resort: answer without tools. Memory was already pre-recalled into the prompt.
        if tools:
            trace.append({"event": "fallback_no_tools"})
            try:
                resp = self._create(self.model, messages, None, None)
                return resp.choices[0].message
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
        raise LLMUnavailable(f"LLM unavailable: {last_exc}")

    def run(self, messages: list[dict], tools: list[dict] | None, execute: ToolExecutor, max_rounds: int = 4):
        trace: list[dict[str, Any]] = []
        messages = list(messages)
        for _ in range(max_rounds):
            msg = self._call(messages, tools, "auto", trace)
            calls = getattr(msg, "tool_calls", None) or []
            if not calls:
                return strip_reasoning(msg.content), trace
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
                        for c in calls
                    ],
                }
            )
            for c in calls:
                result = safe_execute(execute, c.function.name, c.function.arguments, trace)
                messages.append({"role": "tool", "tool_call_id": c.id, "content": result})
        # Out of rounds: force a final answer with no further tool use.
        trace.append({"event": "max_tool_rounds"})
        msg = self._call(messages, None, None, trace)
        return strip_reasoning(msg.content), trace


def safe_execute(execute: ToolExecutor, name: str, raw_args: str | None, trace: list) -> str:
    """Run a tool; never raise. Errors go back to the model as tool output so it can recover."""
    try:
        args = parse_tool_args(raw_args)
    except (ValueError, json.JSONDecodeError) as exc:
        trace.append({"event": "bad_tool_args", "tool": name, "detail": str(exc)})
        return json.dumps({"error": f"invalid arguments: {exc}. Call again with a JSON object."})
    try:
        out = execute(name, args)
        trace.append({"event": "tool_ok", "tool": name, "args": args})
        return out
    except KeyError:
        trace.append({"event": "unknown_tool", "tool": name})
        return json.dumps({"error": f"unknown tool '{name}'"})
    except Exception as exc:  # noqa: BLE001  - memory server down, timeout, etc.
        trace.append({"event": "tool_error", "tool": name, "detail": str(exc)[:200]})
        return json.dumps({"error": f"tool '{name}' failed: {exc}. Answer from the memories already in context."})


class OfflineLLM:
    """OFFLINE / TEST-ONLY. Deterministic template 'answers' so the UI and tests run with no API key.

    It is not a language model. It formats whatever memories it is given. Output
    is prefixed so nobody mistakes it for a Groq answer.
    """

    name = "offline-template"

    def run(self, messages, tools, execute, max_rounds: int = 4):
        trace: list[dict[str, Any]] = []
        system = messages[0]["content"]
        user = messages[-1]["content"]
        extra = ""
        if tools:
            extra = safe_execute(execute, "recall_memory", json.dumps({"query": user[:300]}), trace)
        if "PAST INCIDENT MEMORIES" not in system:
            return (
                "[offline template, no LLM]\nGeneric triage (no memory):\n"
                "1. Check recent deploys and roll back if one lines up with the alert.\n"
                "2. Check dashboards for error rate, latency and saturation.\n"
                "3. Restart unhealthy pods if errors persist.\n"
                "4. Scale out if CPU or connection usage is high.\n"
                "5. Escalate to the service owner."
            ), trace
        mem_block = system.split("PAST INCIDENT MEMORIES", 1)[1]
        # keep recall rank order (first mention wins), not sorted order
        ids = list(dict.fromkeys(re.findall(r"INC-(?:LIVE-)?\d+", mem_block + extra)))
        # only real dead-end memories, not earlier advice that quoted one
        dont = [
            l.split(") ", 1)[-1].strip()
            for l in mem_block.splitlines()
            if "did NOT work" in l and "Recurrence advised" not in l and not l.startswith("Do NOT repeat")
        ]
        lines = ["[offline template, no LLM]", f"This looks like a repeat of {', '.join(ids[:3]) or 'a past incident'}."]
        if "rollback-first" in system:
            lines.append("Rollback first: roll back the most recent ledger-svc / service deploy before investigating.")
        if "step-by-step" in system:
            lines.append("Step by step, with a check after each step (per your preference).")
        if dont:
            lines.append("Do NOT repeat: " + dont[0][:220])
        return "\n".join(lines), trace
