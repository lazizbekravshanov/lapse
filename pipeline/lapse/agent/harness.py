"""The loop that lets a model answer questions, and the rules that bind it.

What the model can do:    call the read-only tools in tools.py. Nothing else exists.
What it cannot do:        reach the internet, read other files, run code, or show a
                          number that no tool produced (guard.py).
What happens when it fails: the tools' own sentences are shown instead.

    from lapse.agent import harness
    result = harness.run("Is the Arctic warming?")
    print(result.text())
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import guard, tools
from .models import ModelError, pick
from .planner import Planner

MAX_STEPS = 8            # model turns per question
MAX_CALLS = 6            # tool calls per model turn
MAX_REPAIRS = 2          # rewrites allowed after a failed number check

SYSTEM = """You are Lapse, a guide to how Earth's atmosphere is changing at different heights. \
The person you are talking to may have no science background.

Everything you know comes from your tools. They read trends computed from two NASA records: AIRS \
(a satellite instrument, 2002 onward) and MERRA-2 (a NASA reanalysis, 1980 onward). You have no other source.

Rules:
1. Call a tool before you answer. Never answer from memory.
2. Use only numbers that appear in tool results. Copy them as written. You may round, but keep at \
least two significant digits (write 0.59, not 0.6). A number written with a plus or minus sign must keep \
the tool's sign. Do not add, subtract, multiply or convert numbers yourself. Your answer is checked by a \
program, and any number that is not in a tool result is rejected.
3. Always give the label the tool gave (Clear change, Likely change, Not proven yet, Disputed), never \
a stronger one. "Not proven yet" does not mean nothing changed.
4. A trend says what changed. It does not say why, and it does not predict. Give a cause or a forecast \
only if a tool result states it.
5. If a tool reports a limit or says there are no measurements, say so plainly.
6. If the question has nothing to do with these records (what they show, how they were measured and \
checked, or the words used to describe them), reply with exactly: OUT_OF_SCOPE
7. To compare two places, compare them at the same height: call compare_places, or give the same km in \
every call. If the question names no height, choose one (0 for near the ground, 30 for the upper air) and \
state the height the tool reports. Never set a rate at one height against a rate at another as if they \
were the same thing.

Style: the direct answer first. Short sentences and everyday words, as if to a curious 14-year-old. \
Heights in km. Every rate with its units and its range. Shorten long numbers to two decimals (write \
-0.72 for -0.7177), unless that would leave fewer than two significant digits (keep 0.0074). Write a range \
in words: between -0.92 and -0.52. Two to five sentences unless asked for more. No headings, no brackets."""

PROD = ("You have read the data. Now answer the question in two to five short sentences, using only numbers "
        "that appear in the tool results.")

NUDGE = ("You answered without reading any data. If this is about how the atmosphere is changing, call a "
         "tool now. If it is not, reply with exactly: OUT_OF_SCOPE")


@dataclass
class Step:
    tool: str
    args: dict
    ok: bool
    result: dict | None = None
    error: str | None = None


@dataclass
class Result:
    question: str
    answer: str
    answered: bool                    # False when the question was out of scope or nothing could be read
    checked: bool                     # True when every number in the answer was traced to a tool result
    model: str
    steps: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def text(self, show_steps: bool = False) -> str:
        lines = [self.answer]
        if self.sources:
            lines += ["", "Read from:"] + [f"  {s['product']}  {s['file']}" for s in self.sources]
        if self.answered:
            lines.append("Number check: " + ("passed. Every number above is in the files listed."
                                             if self.checked else "not passed."))
        lines += [f"Note: {n}" for n in self.notes]
        if show_steps:
            lines += ["", f"Model: {self.model}"]
            lines += [f"  {s.tool}({json.dumps(s.args)}) -> " + ("ok" if s.ok else f"refused: {s.error}")
                      for s in self.steps]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {"question": self.question, "answer": self.answer, "answered": self.answered,
                "checked": self.checked, "model": self.model, "sources": self.sources, "notes": self.notes,
                "steps": [{"tool": s.tool, "args": s.args, "ok": s.ok, "error": s.error} for s in self.steps]}


def out_of_scope(site: tools.Site) -> str:
    measures = sorted({v["label"].lower() for d in site.manifest["datasets"] for v in d["variables"]})
    return ("I can only answer from NASA's AIRS and MERRA-2 records: how " + ", ".join(measures[:-1])
            + f" and {measures[-1]} are changing at different heights. "
            "Try: \"Is the Arctic warming?\", \"What is happening 30 km up?\" or \"Do the methods agree at 21 km?\"")


def _sources(steps: list) -> list:
    seen, out = set(), []
    for s in steps:
        if not s.ok:
            continue
        for src in [s.result.get("source")] + s.result.get("other_sources", []):
            if src and src["file"] not in seen:
                seen.add(src["file"])
                out.append({"product": src["product"], "file": src["file"]})
    return out


def _loop(question: str, model, site: tools.Site, max_steps: int, max_repairs: int) -> Result:
    specs = tools.specs(site)
    messages = [{"role": "user", "text": question}]
    steps, notes, repairs, nudged, prodded = [], [], 0, False, False
    label = getattr(model, "label", model.name)

    def done(answer, answered, checked):
        good = [s for s in steps if s.ok]
        return Result(question, answer, answered, checked, label, steps, _sources(good) if answered else [], notes)

    def nothing_read():
        failed = [s for s in steps if not s.ok]
        if failed:
            return done(f"I could not look that up. {failed[-1].error} " + out_of_scope(site), False, False)
        return done(out_of_scope(site), False, False)

    for _ in range(max_steps):
        reply = model.step(SYSTEM, messages, specs)
        if reply.calls:
            messages.append({"role": "assistant", "text": reply.text, "calls": reply.calls, "raw": reply.raw})
            for n, c in enumerate(reply.calls):
                out = (tools.call(site, c.name, c.args) if n < MAX_CALLS
                       else {"ok": False, "error": f"Too many calls at once. The limit is {MAX_CALLS}."})
                steps.append(Step(c.name, c.args, out["ok"], out.get("result"), out.get("error")))
                messages.append({"role": "tool", "id": c.id, "name": c.name, "error": not out["ok"],
                                 "text": json.dumps(out["result"] if out["ok"] else {"error": out["error"]})})
            continue

        draft = (reply.text or "").strip()
        good = [s for s in steps if s.ok]
        if "OUT_OF_SCOPE" in draft:
            return nothing_read() if not good else done(out_of_scope(site), False, False)
        if not good:                                    # an answer with no data behind it is never shown
            if nudged or not draft:
                return nothing_read()
            nudged = True
            messages += [{"role": "assistant", "text": draft, "raw": reply.raw}, {"role": "user", "text": NUDGE}]
            continue
        if not draft:                                   # some models go quiet after reading: ask once more
            if prodded:
                notes.append("The model read the data but wrote nothing.")
                break
            prodded = True
            messages.append({"role": "user", "text": PROD})
            continue
        problems = guard.check(draft, question, [s.result for s in good])
        if not problems:
            return done(draft, True, True)
        if repairs >= max_repairs:
            notes.append(f"The model's own wording failed the number check {repairs + 1} times "
                         f"({' '.join(problems[:3])}) It was discarded.")
            break
        repairs += 1
        messages += [{"role": "assistant", "text": draft, "raw": reply.raw},
                     {"role": "user", "text": "Your draft cannot be shown. " + " ".join(problems) + " Rewrite it "
                      "using only numbers that appear in the tool results, copied as written. Do not calculate."}]

    good = [s for s in steps if s.ok]
    if not good:
        return nothing_read()
    seen, parts = set(), []                             # fall back to the tools' own sentences
    for s in good:
        summary = s.result.get("summary", "")
        if summary and summary not in seen:
            seen.add(summary)
            parts.append(summary)
    answer = "\n\n".join(parts)
    notes.append("This answer uses the tools' own wording.")
    return done(answer, True, not guard.check(answer, question, [s.result for s in good]))


def run(question: str, model=None, site: tools.Site | None = None,
        max_steps: int = MAX_STEPS, max_repairs: int = MAX_REPAIRS) -> Result:
    """Answer one question. Never raises because of the model: it falls back to the rules."""
    site = site or tools.Site()
    question = str(question).strip()
    if isinstance(model, str) or model is None:
        try:
            model = pick(model, site)
        except ModelError as exc:
            result = _loop(question, Planner(site), site, max_steps, max_repairs)
            result.notes.insert(0, f"No language model was used: {exc}. This answer was written by rule.")
            return result
    try:
        return _loop(question, model, site, max_steps, max_repairs)
    except ModelError as exc:
        result = _loop(question, Planner(site), site, max_steps, max_repairs)
        result.notes.insert(0, f"The language model failed ({exc}). This answer was written by rule instead.")
        return result
