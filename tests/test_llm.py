"""GroqLLM error handling with a mocked OpenAI client (no network)."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx2
import openai
import pytest

from recurrence.llm import GroqLLM, LLMUnavailable, parse_tool_args, safe_execute, strip_reasoning

REQ = httpx2.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


def bad_request(code="tool_use_failed"):
    body = {"error": {"message": "Failed to call a function.", "code": code}}
    return openai.BadRequestError("Error code: 400", response=httpx2.Response(400, request=REQ), body=body)


def msg(content=None, calls=None):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=calls))])


def call(name, args, id_="c1"):
    return SimpleNamespace(id=id_, function=SimpleNamespace(name=name, arguments=args))


def llm(side_effect):
    client = MagicMock()
    client.chat.completions.create.side_effect = side_effect
    return GroqLLM("k", "u", "openai/gpt-oss-120b", "qwen/qwen3-32b", client=client), client


MSGS = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
TOOLS = [{"type": "function", "function": {"name": "recall_memory", "parameters": {}}}]


def test_plain_answer_strips_think():
    g, _ = llm([msg("<think>secret</think>Roll back ledger-svc.")])
    text, trace = g.run(MSGS, TOOLS, lambda n, a: "{}")
    assert text == "Roll back ledger-svc." and trace == []


def test_tool_loop_executes_and_returns():
    g, client = llm([msg(None, [call("recall_memory", '{"query":"hikari"}')]), msg("Repeat of INC-2087.")])
    seen = []
    text, trace = g.run(MSGS, TOOLS, lambda n, a: seen.append((n, a)) or '["m"]')
    assert text == "Repeat of INC-2087." and seen == [("recall_memory", {"query": "hikari"})]
    second = client.chat.completions.create.call_args_list[1].kwargs["messages"]
    assert second[-1]["role"] == "tool" and second[-2]["tool_calls"][0]["id"] == "c1"


def test_tool_use_failed_falls_back_to_second_model():
    g, client = llm([bad_request(), msg("answer from qwen")])
    text, trace = g.run(MSGS, TOOLS, lambda n, a: "{}")
    assert text == "answer from qwen"
    assert trace[0]["event"] == "tool_use_failed"
    models = [c.kwargs["model"] for c in client.chat.completions.create.call_args_list]
    assert models == ["openai/gpt-oss-120b", "qwen/qwen3-32b"]


def test_both_models_fail_tools_then_no_tools_answer():
    g, client = llm([bad_request(), bad_request(), msg("no-tool answer")])
    text, trace = g.run(MSGS, TOOLS, lambda n, a: "{}")
    assert text == "no-tool answer" and trace[-1]["event"] == "fallback_no_tools"
    assert "tools" not in client.chat.completions.create.call_args_list[-1].kwargs


def test_other_bad_request_is_raised():
    g, _ = llm([bad_request(code="context_length_exceeded")])
    with pytest.raises(openai.BadRequestError):
        g.run(MSGS, None, lambda n, a: "{}")


def test_everything_down_raises_unavailable(monkeypatch):
    monkeypatch.setattr("recurrence.llm.time.sleep", lambda s: None)
    err = openai.APIConnectionError(request=REQ)
    g, _ = llm([err] * 10)
    with pytest.raises(LLMUnavailable):
        g.run(MSGS, TOOLS, lambda n, a: "{}")


def test_bad_args_and_tool_errors_go_back_to_model():
    trace = []
    out = json.loads(safe_execute(lambda n, a: "{}", "recall_memory", "not json at all", trace))
    assert "invalid arguments" in out["error"] and trace[-1]["event"] == "bad_tool_args"

    def boom(n, a):
        raise ConnectionError("memory down")
    out = json.loads(safe_execute(boom, "recall_memory", "{}", trace))
    assert "failed" in out["error"] and trace[-1]["event"] == "tool_error"

    def unknown(n, a):
        raise KeyError(n)
    out = json.loads(safe_execute(unknown, "nope", "{}", trace))
    assert "unknown tool" in out["error"]


def test_max_rounds_forces_final_answer():
    loop = [msg(None, [call("recall_memory", '{"query":"x"}', f"c{i}")]) for i in range(2)]
    g, client = llm(loop + [msg("final")])
    text, trace = g.run(MSGS, TOOLS, lambda n, a: "[]", max_rounds=2)
    assert text == "final" and trace[-1]["event"] == "max_tool_rounds"


def test_parse_tool_args_variants():
    assert parse_tool_args('```json\n{"query": "a"}\n```') == {"query": "a"}
    assert parse_tool_args('{"query": "a"} trailing') == {"query": "a"}
    assert parse_tool_args("") == {} and parse_tool_args(None) == {}
    with pytest.raises(ValueError):
        parse_tool_args("[1,2]")
    assert strip_reasoning(None) == ""
