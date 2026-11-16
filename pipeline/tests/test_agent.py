import io
import json
import sys

import pytest

from lapse.agent import guard, harness, mcp_server, models, planner, tools
from lapse.agent.models import Call, ModelError, Reply, Scripted
from lapse.backend.actions import verify


@pytest.fixture(scope="module")
def data(site):
    return tools.Site(site)


def texts(numbers):
    return [n.text for n in numbers]


# --- the number guard -----------------------------------------------------------------

def test_guard_reads_numbers_and_ignores_names():
    found = guard.numbers_in("MERRA-2 and AIRS3STM v7.0 show CO2 and O3 moving by −0.59 °C, +0.24 near 8 km, "
                             "from 2002-09 to 2026, in 3,713 cells (version 5.12.4). 1st of 24.")
    assert texts(found) == ["-0.59", "+0.24", "8", "2002", "09", "2026", "3713", "24"]
    assert found[0].sign == -1 and found[0].decimals == 2 and found[2].sign == 0
    assert texts(guard.numbers_in("1. First point\n2) Second point, per 10 years, a 10-year record")) == []
    assert texts(guard.numbers_in("between 5-10 km and (-1.13 to -0.25)")) == ["5", "10", "-1.13", "-0.25"]


def test_guard_allows_copies_and_careful_rounding_only():
    results = [{"rate": -0.5913, "range": [-0.7071, -0.4712], "height_km": 32, "years": 24.1,
                "summary": "about -1.4 °C in total, 3 of 3 methods, from 2002-09"}]
    ok = lambda text, q="": guard.check(text, q, results) == []              # noqa: E731
    assert ok("Cooling of 0.59 °C per ten years (−0.71 to −0.47) near 32 km, about -1.4 in total.")
    assert ok("-0.591 over 24 years since 2002, 3 of 3 methods")              # rounded, two digits kept
    assert not ok("about 0.6 °C per ten years")                           # one digit kept: too coarse
    assert not ok("+0.59 °C per ten years")                               # the sign is wrong
    assert not ok("cooling of 0.95 °C")                                   # invented
    assert not ok("since 1979")                                               # invented year
    assert not ok("about 2 °C in total")                                  # 1.4 is not 2
    assert ok("You asked about 45 km. Near 32 km it is -0.59.", q="what about 45 km?")
    problems = guard.check("It cooled 0.95 °C by 2030, and 0.95 again.", "", results)
    assert problems == ["The number 0.95 is not in any tool result.", "The number 2030 is not in any tool result."]


# --- the tools ----------------------------------------------------------------------------

CALLS = [("list_options", {}), ("trend_at", {"where": "global", "km": 5}), ("trend_at", {"where": "45N", "hpa": 10}),
         ("trend_at", {"where": "arctic"}), ("profile", {"where": "tropics"}), ("compare_methods", {"km": 45}),
         ("compare_datasets", {"km": 30}), ("compare_places", {"km": 5}), ("opposite_pairs", {}),
         ("effect_of_events", {"km": 30, "data": "merra2", "years": "full"}), ("yearly_history", {"km": 45}),
         ("yearly_history", {"where": "-60", "km": 5}), ("glossary", {"term": "anomaly"}), ("glossary", {})]


@pytest.mark.parametrize("name,args", CALLS)
def test_every_tool_answers_in_words_with_a_source_and_passes_its_own_guard(data, name, args):
    out = tools.call(data, name, args)
    assert out["ok"], out
    result = out["result"]
    assert result["summary"] and result["source"]["file"] and result["source"]["product"]
    json.dumps(result)                                                    # plain data only
    assert guard.check(result["summary"], "", [result]) == []


def test_tools_find_the_planted_signal(data):
    low = tools.call(data, "trend_at", {"km": 5})["result"]
    high = tools.call(data, "trend_at", {"km": 45, "method": "yearly"})["result"]
    assert low["rate"] > 0 > high["rate"] and low["direction"] == "warming" and high["direction"] == "cooling"
    assert low["tools_used"]["chosen_by_auto"] == ["dataset", "method", "period"]
    assert high["tools_used"]["method"] == "Year by year" and "yearly" in high["source"]["file"]
    assert abs(low["total_change"]["value"] - low["rate"] * low["total_change"]["over_years"] / 10) < 0.06
    column = tools.call(data, "profile", {})["result"]
    assert column["heights"][0]["height_km"] < column["heights"][-1]["height_km"]      # ground first
    assert sum(column["labels_count"].values()) == column["heights_checked"] == len(column["heights"])
    assert "warming low down and cooling higher up" in column["summary"]
    both = tools.call(data, "compare_datasets", {"km": 30})["result"]
    assert both["second"]["data"] != both["first"]["data"] and len(both["other_sources"]) == 1
    methods = tools.call(data, "compare_methods", {"km": 45})["result"]
    assert [m["role"] for m in methods["methods"]] == ["recommended", "sound", "sound", "comparison only"]


def test_tools_refuse_bad_input_without_raising(data):
    for name, args, word in [("trend_at", {"where": "narnia"}, "Unknown place"), ("trend_at", {"city": "x"}, "does not take"),
                             ("run_shell", {"cmd": "ls"}, "no tool called"), ("trend_at", {"what": "gold"}, "Unknown measure"),
                             ("trend_at", {"km": "high"}, "must be a number"), ("trend_at", {"where": "120N"}, "between -90 and 90"),
                             ("trend_at", {"km": -3}, "positive"), ("glossary", {"term": "love"}, "not a word"),
                             ("published_checks", {}, "has not been run"), ("trend_at", {"method": "magic"}, "Unknown method")]:
        out = tools.call(data, name, args)
        assert not out["ok"] and word in out["error"], (name, args, out)
    names = [s["name"] for s in tools.specs(data)]
    assert names == tools.NAMES and len(names) == 11
    assert all(s["parameters"]["additionalProperties"] is False for s in tools.specs(data))


# --- the harness --------------------------------------------------------------------------

def first_result(messages):
    return json.loads(next(m["text"] for m in messages if m["role"] == "tool" and not m["error"]))


def quote_rate(messages):
    r = first_result(messages)
    return Reply(text=f"Near {r['height_km']} km the air is {r['direction']} by {abs(r['rate']):.2f} {r['units']}. "
                      f"Label: {r['label']}.")


def test_harness_shows_an_answer_whose_numbers_all_come_from_the_tools(data):
    model = Scripted([Reply(calls=[Call("a", "trend_at", {"km": 45})]), quote_rate])
    out = harness.run("What is happening 45 km up?", model, data)
    assert out.answered and out.checked and out.notes == []
    assert out.sources and out.sources[0]["file"].startswith("web/data/trend/")
    assert [s.tool for s in out.steps] == ["trend_at"] and "Number check: passed" in out.text()
    json.dumps(out.to_dict())


def test_harness_rejects_an_invented_number_and_asks_for_a_rewrite(data):
    model = Scripted([Reply(calls=[Call("a", "trend_at", {"km": 45})]),
                      Reply(text="It is cooling by 9.87 degrees per ten years."), quote_rate])
    out = harness.run("What is happening 45 km up?", model, data)
    assert out.checked and "9.87" not in out.answer
    repair = model.seen[2][-1]
    assert repair["role"] == "user" and "9.87" in repair["text"] and "cannot be shown" in repair["text"]


def test_a_model_that_goes_quiet_after_reading_is_asked_once_more(data):
    model = Scripted([Reply(calls=[Call("a", "trend_at", {"km": 45})]), Reply(text=""), quote_rate])
    result = harness.run("How is the air changing 45 km up?", model, data)
    assert result.answered and result.checked and "tools' own wording" not in " ".join(result.notes)
    assert model.seen[-1][-1] == {"role": "user", "text": harness.PROD}

    silent = Scripted([Reply(calls=[Call("a", "trend_at", {"km": 45})]), Reply(text=""), Reply(text="")])
    result = harness.run("How is the air changing 45 km up?", silent, data)
    assert result.answered and result.checked                   # the tools' own sentences, still checked
    assert "wrote nothing" in " ".join(result.notes)


def test_harness_falls_back_to_the_tools_own_words_when_the_model_keeps_inventing(data):
    model = Scripted([Reply(calls=[Call("a", "trend_at", {"km": 45})])] + [Reply(text="Cooling by 9.87 degrees.")] * 3)
    out = harness.run("What is happening 45 km up?", model, data)
    assert out.checked and "9.87" not in out.answer
    assert out.answer == tools.call(data, "trend_at", {"km": 45})["result"]["summary"]
    assert any("failed the number check 3 times" in n for n in out.notes) and "9.87" in " ".join(out.notes)


def test_harness_never_runs_a_tool_that_is_not_on_the_list(data):
    model = Scripted([Reply(calls=[Call("a", "read_file", {"path": "/etc/passwd"}), Call("b", "trend_at", {"km": 5})]),
                      quote_rate])
    out = harness.run("How is the air near 5 km?", model, data)
    assert [(s.tool, s.ok) for s in out.steps] == [("read_file", False), ("trend_at", True)]
    refused = json.loads(model.seen[1][2]["text"])
    assert "no tool called" in refused["error"] and model.seen[1][2]["error"] is True
    assert out.checked


def test_harness_shows_nothing_that_has_no_data_behind_it(data):
    model = Scripted([Reply(text="Paris is the capital of France."), Reply(text="OUT_OF_SCOPE")])
    out = harness.run("What is the capital of France?", model, data)
    assert not out.answered and "Paris" not in out.answer and "I can only answer from NASA" in out.answer
    assert out.sources == [] and "Number check" not in out.text()
    assert "without reading any data" in model.seen[1][-1]["text"]                  # it was told why
    stubborn = Scripted([Reply(text="Paris."), Reply(text="Still Paris.")])
    assert not harness.run("Capital of France?", stubborn, data).answered
    direct = Scripted([Reply(text="OUT_OF_SCOPE")])
    assert harness.run("Tell me a joke", direct, data).answer == harness.out_of_scope(data)


def test_harness_limits_steps_and_calls(data):
    endless = Scripted([Reply(calls=[Call(f"c{i}", "trend_at", {"km": 5})]) for i in range(20)])
    out = harness.run("How is the air near 5 km?", endless, data, max_steps=3)
    assert len(out.steps) == 3 and out.answered and out.checked and "tools' own wording" in " ".join(out.notes)
    greedy = Scripted([Reply(calls=[Call(f"c{i}", "trend_at", {"km": 5}) for i in range(8)]), quote_rate])
    out = harness.run("How is the air near 5 km?", greedy, data)
    assert [s.ok for s in out.steps] == [True] * harness.MAX_CALLS + [False, False]
    assert "Too many calls" in out.steps[-1].error


def test_harness_survives_a_broken_model(data, monkeypatch):
    class Broken:
        name = label = "broken"

        def step(self, *a):
            raise ModelError("The Claude API answered 401")

    out = harness.run("Is the Arctic warming?", Broken(), data)
    assert out.answered and out.checked and out.model.startswith("rules")
    assert "answered 401" in out.notes[0] and "written by rule" in out.notes[0]

    class Busy(Broken):
        def step(self, *a):
            raise ModelError("The gemini server answered 429")

    out = harness.run("Is the Arctic warming?", Busy(), data)
    assert out.answered and out.checked and "usage limit" in out.notes[0] and "429" not in out.notes[0]
    for env in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY", "LAPSE_BASE_URL", "LAPSE_AGENT"):
        monkeypatch.delenv(env, raising=False)
    assert harness.run("Is the Arctic warming?", None, data).model.startswith("rules")   # no key: rules
    out = harness.run("Is the Arctic warming?", "openrouter", data)                       # asked for, but no key
    assert out.answered and "OPENROUTER_API_KEY is not set" in out.notes[0]


# --- the rule-based planner ----------------------------------------------------------------

def test_planner_picks_the_right_tool():
    plan = lambda q: planner.plan(q, lambda w: w in ("anomaly", "stratosphere"))     # noqa: E731
    assert plan("Is the Arctic warming?") == [("profile", {"what": "t", "where": "arctic"})]
    assert plan("What is happening 30 km up?") == [("trend_at", {"km": 30.0})]
    assert plan("Is ozone falling over the Antarctic at 20 km?") == [("trend_at", {"what": "o3", "where": "antarctic", "km": 20.0})]
    assert plan("temperature at 45 N, 10 hPa in MERRA-2") == [("trend_at", {"what": "t", "where": "45N", "hpa": 10.0, "data": "merra2"})]
    assert plan("Do the methods agree at 21 km?") == [("compare_methods", {"km": 21.0})]
    assert plan("Do both datasets agree at 41 km?") == [("compare_datasets", {"km": 41.0})]
    assert plan("Did the Hunga volcano change the trend at 32 km?")[0][0] == "effect_of_events"
    assert plan("How did the tropics change year by year near the ground?") == [("yearly_history", {"where": "tropics", "km": 0.0})]
    assert plan("Which region is warming fastest at 5 km?") == [("compare_places", {"what": "t", "km": 5.0})]
    assert plan("Where does the air change in opposite directions?") == [("opposite_pairs", {})]
    assert plan("Can I trust this?") == [("published_checks", {})]
    assert plan("What does anomaly mean?") == [("glossary", {"term": "anomaly"})]
    assert plan("What is the stratosphere?") == [("glossary", {"term": "stratosphere"})]
    assert plan("What data do you have?") == [("list_options", {})]
    assert plan("How warm is it where airliners cruise?") == [("trend_at", {"what": "t", "km": 11.0})]
    for off_topic in ("What is the capital of France?", "Write me a poem", "What does love mean?", "hello"):
        assert plan(off_topic) == [], off_topic


QUESTIONS = ["Is the Arctic warming?", "What is happening 30 km up?", "Do the methods agree at 45 km?",
             "Do both datasets agree at 30 km?", "Did the volcano change the trend at 30 km?",
             "How did the air change year by year at 45 km?", "Which region is warming fastest at 5 km?",
             "Where does the air change in opposite directions?", "What does anomaly mean?",
             "What data do you have?", "temperature at 60 S near the ground", "Is the tropics cooling at 10 hPa?"]


@pytest.mark.parametrize("question", QUESTIONS)
def test_with_no_model_every_answer_is_grounded_and_checked(data, question):
    out = harness.run(question, "rules", data)
    assert out.answered and out.checked and out.sources, out.to_dict()
    assert all(s.ok for s in out.steps)


def test_with_no_model_off_topic_and_unreadable_questions_get_no_invented_answer(data):
    assert not harness.run("What is the capital of France?", "rules", data).answered
    out = harness.run("Can I trust these numbers?", "rules", data)           # the synthetic site has no validation file
    assert not out.answered and "could not look that up" in out.answer and "has not been run" in out.answer


# --- model adapters (no network: the HTTP call is replaced) -----------------------------------

class FakeResponse:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


HISTORY = [{"role": "user", "text": "hi"},
           {"role": "assistant", "text": "", "calls": [Call("t1", "trend_at", {"km": 5}), Call("t2", "profile", {})]},
           {"role": "tool", "id": "t1", "name": "trend_at", "text": "{\"rate\": 1}", "error": False},
           {"role": "tool", "id": "t2", "name": "profile", "text": "{\"error\": \"x\"}", "error": True},
           {"role": "assistant", "text": "draft"}, {"role": "user", "text": "rewrite"}]


def test_claude_adapter_speaks_the_messages_api_and_keeps_the_key_private(data):
    sent = {}

    def post(url, headers, json, timeout):
        sent.update(url=url, headers=headers, body=json)
        return FakeResponse(200, {"content": [{"type": "text", "text": "Let me look."},
                                              {"type": "tool_use", "id": "toolu_1", "name": "trend_at", "input": {"km": 5}}]})

    model = models.Anthropic(model="some-model", key="sk-secret", post=post)
    reply = model.step("system text", HISTORY, tools.specs(data))
    assert reply.text == "Let me look." and reply.calls == [Call("toolu_1", "trend_at", {"km": 5})]
    assert sent["url"].endswith("/v1/messages") and sent["headers"]["authorization"] == "Bearer sk-secret"
    assert sent["body"]["system"] == "system text" and sent["body"]["model"] == "some-model"
    assert {t["name"] for t in sent["body"]["tools"]} == set(tools.NAMES) and "input_schema" in sent["body"]["tools"][0]
    roles = [m["role"] for m in sent["body"]["messages"]]
    assert roles == ["user", "assistant", "user", "assistant", "user"]              # both tool results in one message
    results = sent["body"]["messages"][2]["content"]
    assert [b["tool_use_id"] for b in results] == ["t1", "t2"] and results[1]["is_error"] is True
    assert sent["body"]["messages"][1]["content"][0] == {"type": "tool_use", "id": "t1", "name": "trend_at", "input": {"km": 5}}
    kept = models.to_anthropic([{"role": "assistant", "text": "x", "calls": [], "raw": reply.raw}])
    assert kept[0]["content"] is reply.raw                                          # the model's own blocks go back intact

    tried = []

    def picky(url, headers, json, timeout):                 # refuses the bearer header, accepts x-api-key
        tried.append(sorted(h for h in headers if h in ("authorization", "x-api-key")))
        return FakeResponse(200, {"content": [{"type": "text", "text": "ok"}]}) if "x-api-key" in headers \
            else FakeResponse(401, {"error": {"message": "Invalid bearer token"}})

    assert models.Anthropic(key="sk-secret", post=picky).step("s", HISTORY[:1], []).text == "ok"
    assert tried == [["authorization"], ["x-api-key"]]

    for bad in (lambda *a, **k: FakeResponse(401, {"error": {"message": "invalid key"}}),
                lambda *a, **k: (_ for _ in ()).throw(ConnectionError("sk-secret leaked?"))):
        with pytest.raises(ModelError) as err:
            models.Anthropic(key="sk-secret", post=bad).step("s", HISTORY[:1], [])
        assert "sk-secret" not in str(err.value)
    with pytest.raises(ModelError):
        models.Anthropic(key="")


def test_openai_style_adapter_translates_tool_calls(data, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-secret")
    monkeypatch.setenv("LAPSE_MODEL", "vendor/model")
    monkeypatch.delenv("LAPSE_BASE_URL", raising=False)
    sent = {}

    def post(url, headers, json, timeout):
        sent.update(url=url, headers=headers, body=json)
        return FakeResponse(200, {"choices": [{"message": {"content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "profile", "arguments": "{\"where\": \"arctic\"}"}},
            {"id": "c2", "type": "function", "function": {"name": "trend_at", "arguments": "not json"}}]}}]})

    reply = models.OpenAICompatible("openrouter", post=post).step("system text", HISTORY, tools.specs(data))
    assert reply.calls[0] == Call("c1", "profile", {"where": "arctic"}) and "_unreadable" in reply.calls[1].args
    assert sent["url"] == "https://openrouter.ai/api/v1/chat/completions"
    msgs = sent["body"]["messages"]
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "tool", "tool", "assistant", "user"]
    assert msgs[2]["tool_calls"][0]["function"] == {"name": "trend_at", "arguments": "{\"km\": 5}"}
    assert msgs[3] == {"role": "tool", "tool_call_id": "t1", "content": "{\"rate\": 1}"}
    assert sent["body"]["tools"][0]["type"] == "function"
    assert not tools.call(data, "trend_at", reply.calls[1].args)["ok"]              # unreadable arguments are refused
    monkeypatch.delenv("LAPSE_MODEL")
    with pytest.raises(ModelError, match="LAPSE_MODEL"):
        models.OpenAICompatible("openrouter")


# --- the MCP server --------------------------------------------------------------------------

def rpc(method, params=None, mid=1):
    return {"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}}


def test_mcp_server_handshake_tools_and_errors(data):
    server = mcp_server.Server(data)
    init = server.handle(rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}}))["result"]
    assert init["protocolVersion"] == "2025-06-18" and "tools" in init["capabilities"]
    assert init["serverInfo"]["name"] == "lapse" and "check_answer" in init["instructions"]
    newer = server.handle(rpc("initialize", {"protocolVersion": "2099-01-01"}))["result"]
    assert newer["protocolVersion"] == mcp_server.VERSIONS[-1]                      # offer the newest we speak
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert server.handle(rpc("ping"))["result"] == {}
    listed = server.handle(rpc("tools/list"))["result"]["tools"]
    assert [t["name"] for t in listed] == tools.NAMES + ["check_answer"]
    assert all(t["inputSchema"]["type"] == "object" and t["annotations"]["readOnlyHint"] for t in listed)
    assert server.handle(rpc("server/discover"))["error"]["code"] == -32601         # older-style server: clients fall back
    assert server.handle(rpc("tools/call", {"name": 5}))["error"]["code"] == -32602

    good = server.handle(rpc("tools/call", {"name": "trend_at", "arguments": {"km": 45}}))["result"]
    result = json.loads(good["content"][0]["text"])
    assert good["isError"] is False and result["rate"] < 0
    bad = server.handle(rpc("tools/call", {"name": "delete_everything", "arguments": {}}))["result"]
    assert bad["isError"] is True and "no tool called" in bad["content"][0]["text"]

    def check(text):
        out = server.handle(rpc("tools/call", {"name": "check_answer", "arguments": {"text": text}}))["result"]
        return json.loads(out["content"][0]["text"])

    assert check(f"It is cooling by {abs(result['rate']):.2f} near {result['height_km']} km.")["passed"] is True
    flagged = check("It is cooling by 9.87 degrees.")
    assert flagged["passed"] is False and "9.87" in flagged["problems"][0]


def test_mcp_server_talks_json_lines_and_survives_garbage(data):
    lines = [json.dumps(rpc("initialize", {"protocolVersion": "2024-11-05"})), "this is not json", "",
             json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}), "[1, 2]",
             json.dumps(rpc("tools/call", {"name": "profile", "arguments": {"where": "arctic"}}, mid=7))]
    out = io.StringIO()
    mcp_server.serve(io.StringIO("\n".join(lines) + "\n"), out, data)
    replies = [json.loads(line) for line in out.getvalue().splitlines()]
    assert [r.get("id") for r in replies] == [1, None, None, 7]
    assert replies[1]["error"]["code"] == -32700 and replies[2]["error"]["code"] == -32600
    assert "Arctic" in json.loads(replies[3]["result"]["content"][0]["text"])["summary"]


def test_mcp_server_works_with_the_official_client(site):
    """A real conformance check, run only where the official MCP library is installed."""
    mcp = pytest.importorskip("mcp")
    import asyncio

    async def session(mode):
        params = mcp.StdioServerParameters(command=sys.executable, args=["-m", "lapse", "mcp"],
                                           env={"LAPSE_DATA_DIR": str(site)})
        async with mcp.Client(params, mode=mode) as client:
            listed = await client.list_tools()
            called = await client.call_tool("trend_at", {"km": 45})
            refused = await client.call_tool("nope", {})
            return [t.name for t in listed.tools], called, refused

    for mode in ("auto", "legacy"):
        names, called, refused = asyncio.run(session(mode))
        assert names == tools.NAMES + ["check_answer"]
        assert json.loads(called.content[0].text)["rate"] < 0 and not called.is_error
        assert refused.is_error


# --- verify: are the published files what the code produces? -----------------------------------

def test_verify_spots_a_changed_number(site, tmp_path):
    import shutil
    copy = tmp_path / "web"
    shutil.copytree(site, copy)
    same = verify.compare(site, copy)
    assert same["ok"] and same["numbers"] > 10000 and same["labels"] > 1000
    path = copy / "trend/airs/t/full__none__robust.json"
    trend = json.loads(path.read_text())
    trend["regions"]["global"]["slope"][3] += 0.05
    path.write_text(json.dumps(trend))
    changed = verify.compare(site, copy)
    assert not changed["ok"] and len(changed["off"]) == 1 and "regions/global/slope[3]" in changed["off"][0][1]
    (copy / "trend/airs/t/full__none__classic.json").unlink()
    assert any("only in published" in line for line in verify.compare(site, copy)["shape"])


def test_the_whole_loop_over_real_http_with_a_stand_in_model_server(data, monkeypatch):
    """A tiny local server plays the model, so the real HTTP path is exercised without any provider."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            seen.append((self.path, self.headers.get("authorization"), body))
            tool_msgs = [m for m in body["messages"] if m["role"] == "tool"]
            if not tool_msgs:
                msg = {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "call_1", "type": "function", "function": {"name": "trend_at", "arguments": "{\"km\": 45}"}}]}
            else:
                r = json.loads(tool_msgs[0]["content"])
                msg = {"role": "assistant", "content": f"About {r['height_km']} km up the air is {r['direction']}: "
                                                       f"{r['rate']:+.2f} {r['units']} ({r['label']})."}
            out = json.dumps({"choices": [{"message": msg}]}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        monkeypatch.setenv("LAPSE_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
        monkeypatch.setenv("LAPSE_MODEL", "stand-in")
        monkeypatch.setenv("LAPSE_API_KEY", "local-key")
        monkeypatch.setenv("NO_PROXY", "127.0.0.1")
        out = harness.run("What is happening 45 km up?", "custom", data)
    finally:
        server.shutdown()
    assert out.answered and out.checked and out.notes == [] and out.model == "custom (stand-in)"
    assert "cooling" in out.answer and len(seen) == 2
    assert seen[0][0] == "/v1/chat/completions" and seen[0][1] == "Bearer local-key"
    assert seen[1][2]["messages"][-1]["role"] == "tool" and len(seen[0][2]["tools"]) == 11


# --- the website's ask endpoint and the Gemini preset ---------------------------------------------

def test_ask_endpoint_answers_checks_input_and_limits_visitors(data):
    from lapse.agent import web
    code, out = web.answer(json.dumps({"question": "Is the Arctic warming?"}).encode(), data, model="rules")
    assert code == 200 and out["answered"] and out["checked"] and out["sources"]
    code, out = web.answer(json.dumps({"question": "Capital of France?"}).encode(), data, model="rules")
    assert code == 200 and not out["answered"]
    assert web.answer(b"not json", data)[0] == 400 and web.answer(b"{}", data)[0] == 400
    assert web.answer(json.dumps({"question": "x" * 400}).encode(), data)[0] == 413
    assert web.answer(b"x" * 5000, data)[0] == 413
    web._seen.clear()
    codes = [web.answer(json.dumps({"question": "hello"}).encode(), data, who="1.2.3.4", model="rules")[0]
             for _ in range(web.PER_MINUTE + 2)]
    assert codes == [200] * web.PER_MINUTE + [429, 429]
    assert web.status(data)["ok"] and "key" not in json.dumps(web.status(data)).lower()


def test_gemini_preset_sends_a_schema_gemini_accepts_and_returns_its_message_unchanged(data, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g-secret")
    monkeypatch.delenv("LAPSE_MODEL", raising=False)
    monkeypatch.setenv("LAPSE_BASE_URL", "http://should-be-ignored")
    sent = []
    raw = {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "extra_content": {
        "google": {"thought_signature": "abc"}}, "function": {"name": "profile", "arguments": "{}"}}]}

    def post(url, headers, json, timeout):
        sent.append((url, headers, json))
        return FakeResponse(200, {"choices": [{"message": raw if len(sent) == 1 else {"content": "done"}}]})

    model = models.OpenAICompatible("gemini", post=post)
    assert model.model == "gemini-2.5-flash" and model.base.startswith("https://generativelanguage.googleapis.com")
    first = model.step("sys", [{"role": "user", "text": "q"}], tools.specs(data))
    assert first.raw is raw and sent[0][1]["authorization"] == "Bearer g-secret"
    fns = [t["function"] for t in sent[0][2]["tools"]]
    assert "parameters" not in next(f for f in fns if f["name"] == "list_options")      # no empty object
    assert all("additionalProperties" not in f.get("parameters", {}) for f in fns)
    history = [{"role": "user", "text": "q"}, {"role": "assistant", "text": "", "calls": first.calls, "raw": first.raw},
               {"role": "tool", "id": "c1", "name": "profile", "text": "{}", "error": False}]
    assert model.step("sys", history, tools.specs(data)).text == "done"
    assert sent[1][2]["messages"][2] is raw                                               # signature goes back intact
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert models.pick(None).name == "gemini"
