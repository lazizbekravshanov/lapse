"""Answering without any language model.

The planner reads the question with plain keyword rules, picks tools, and answers
with the tools' own sentences. It has the same shape as a model adapter, so it runs
through the same harness and the same checks. It is what you get with no API key,
and what the harness falls back to when a model fails or is unreachable.

It is deliberately simple. It will not understand a subtle question; it will never
invent an answer either.
"""

from __future__ import annotations

import json
import re

from .models import Call, Reply

SCOPE = re.compile(
    r"atmospher|\bair\b|\bsky\b|climate|warm|cool|\bhot|\bcold|heat|temperature|ozone|vapou?r|humid|moist|"
    r"stratospher|tropospher|altitude|height|\bhigh\b|\bkm\b|kilomet|hpa|arctic|antarctic|tropic|equator|\bpoles?\b|"
    r"latitude|glob|\bearth\b|planet|\bworld|trend|chang|nasa|\bairs\b|merra|satellite|volcan|hunga|pinatubo|"
    r"method|dataset|\bdata\b|published|trust|accura|reliab", re.I)

LANDMARKS = [(r"near the ground|ground level|\bsurface\b|sea level|where we live|down here", 0.0),
             (r"everest", 9.0), (r"airliner|planes? (fly|cruise)|jets? (fly|cruise)|cruising", 11.0),
             (r"ozone layer", 25.0), (r"weather balloon", 33.0), (r"skydiv", 41.0),
             (r"upper stratosphere", 40.0), (r"lower stratosphere", 20.0)]


def parse(question: str) -> dict:
    """Pull the measure, place, height and tool choices out of a question."""
    q = " " + question.lower().replace("°", " ") + " "
    args = {}

    if re.search(r"ozone", q):
        args["what"] = "o3"
    elif re.search(r"vapou?r|humid|moist|\bwater\b", q):
        args["what"] = "qv"
    elif re.search(r"temperature|warm|cool|\bhot|\bcold|heat", q):
        args["what"] = "t"

    lat = re.search(r"(?<![\d.])(\d{1,2}(?:\.\d+)?)\s*(?:deg(?:rees?)?)?\s*(n|s|north|south)\b", q)
    if re.search(r"antarctic|south pole", q):
        args["where"] = "antarctic"
    elif re.search(r"arctic|north pole", q):
        args["where"] = "arctic"
    elif re.search(r"tropic|equator", q):
        args["where"] = "tropics"
    elif re.search(r"north(ern)? mid", q):
        args["where"] = "north_mid"
    elif re.search(r"south(ern)? mid", q):
        args["where"] = "south_mid"
    elif lat:
        args["where"] = lat.group(1) + ("S" if lat.group(2).startswith("s") else "N")
    elif re.search(r"glob|whole (earth|planet|world)|worldwide", q):
        args["where"] = "global"

    km = re.search(r"(\d+(?:\.\d+)?)\s*(?:km|kilomet)", q)
    hpa = re.search(r"(\d+(?:\.\d+)?)\s*(?:hpa|millibar|mb\b)", q)
    if km:
        args["km"] = float(km.group(1))
    elif hpa:
        args["hpa"] = float(hpa.group(1))
    else:
        for pattern, height in LANDMARKS:
            if re.search(pattern, q):
                args["km"] = height
                break

    if re.search(r"merra|reanalysis", q) and not re.search(r"\bairs\b|satellite", q):
        args["data"] = "merra2"
    elif re.search(r"\bairs\b|satellite", q) and not re.search(r"merra|reanalysis", q):
        args["data"] = "airs"
    if re.search(r"since 1980|full record|whole record|longest record|46 years", q):
        args.update(data="merra2", years="full")
    for word, method in (("robust", "robust"), ("classic|straight line", "classic"),
                         ("yearly method|year by year method|annual means", "yearly"), ("textbook", "textbook")):
        if re.search(word, q) and not re.search(r"methods|compare|agree|differ", q):
            args["method"] = method
    return args


MEANING = re.compile(r"what (?:does|do) (?:an? |the )?[\"']?([a-z\- ]+?)[\"']? mean|"
                     r"(?:define|meaning of|explain the (?:word|term)) (?:an? |the )?[\"']?([a-z\- ]+)|"
                     r"^\s*what(?: is|'s| are) (?:an? |the )?[\"']?([a-z\- ]{3,30}?)[\"']?\s*\??\s*$")


def plan(question: str, known_term=None) -> list:
    """The tool calls for a question: a list of (tool name, arguments). Empty means out of scope.

    known_term(word) -> bool says whether a word is in the glossary.
    """
    q = question.lower()
    meaning = MEANING.search(q)
    if meaning and known_term:
        word = next(g for g in meaning.groups() if g).strip()
        if known_term(word):
            return [("glossary", {"term": word})]
    if not SCOPE.search(q):
        return []
    args = parse(question)
    pick = lambda *keys: {k: args[k] for k in keys if k in args}            # noqa: E731
    calls = []

    if re.search(r"what can (i|you|we) ask|what (data|datasets|measures|options)|which (data|datasets|measures)|"
                 r"how does this work|what do you (know|have)", q):
        return [("list_options", {})]
    if re.search(r"publish|literature|\bpapers?\b|other scientists|trust|accura|reliab|validat|verif|"
                 r"how do (you|we) know|is this (right|correct|true)", q):
        calls.append(("published_checks", {}))
        if not any(k in args for k in ("km", "hpa", "where")):
            return calls

    if re.search(r"opposite|contrast|both directions|fingerprint|one cause", q):
        calls.append(("opposite_pairs", pick("what", "data", "method", "years")))
    elif re.search(r"methods?\b.*(agree|differ|compare|same)|(agree|differ|compare).*methods?\b|which method|"
                   r"every method|all (the )?methods|textbook", q):
        calls.append(("compare_methods", pick("what", "where", "km", "hpa", "data", "years")))
    elif re.search(r"both datasets|two datasets|second dataset|datasets? agree|airs.*merra|merra.*airs|"
                   r"satellite.*reanalysis|confirm", q):
        calls.append(("compare_datasets", pick("what", "where", "km", "hpa", "method")))
    elif re.search(r"volcan|hunga|pinatubo|erupt|jump|data.source|instrument change", q):
        calls.append(("effect_of_events", pick("what", "where", "km", "hpa", "data", "method", "years")))
    elif re.search(r"year by year|each year|every year|yearly|history|over time|timeline|record (high|low|year)|"
                   r"(warmest|coldest|hottest|highest|lowest) year", q):
        calls.append(("yearly_history", pick("what", "where", "km", "hpa", "data")))
    elif re.search(r"where .*(fastest|most|strongest|quickest)|which (region|place|part)|compare (the )?(regions|places)|"
                   r"(regions|places) compare|region by region", q) and "where" not in args:
        calls.append(("compare_places", pick("what", "km", "hpa", "data", "method", "years")))
    elif "km" in args or "hpa" in args:
        calls.append(("trend_at", pick("what", "where", "km", "hpa", "data", "method", "years")))
    else:
        calls.append(("profile", pick("what", "where", "data", "method", "years")))
    return calls


class Planner:
    """The rule-based stand-in for a model."""
    name = "rules"
    label = "rules (no language model)"

    def __init__(self, site=None):
        self.site = site

    def known_term(self, word: str) -> bool:
        from . import tools
        self.site = self.site or tools.Site()
        return bool(tools.find_terms(self.site, word))

    def step(self, system: str, messages: list, specs: list) -> Reply:
        results = [m for m in messages if m["role"] == "tool"]
        if not results:
            if len(messages) > 1:                       # already asked once and nothing could be planned
                return Reply(text="OUT_OF_SCOPE")
            calls = plan(messages[0]["text"], self.known_term)
            if not calls:
                return Reply(text="OUT_OF_SCOPE")
            return Reply(calls=[Call(f"plan_{i}", name, args) for i, (name, args) in enumerate(calls)])
        seen, parts = set(), []
        for m in results:
            if m.get("error"):
                continue
            summary = json.loads(m["text"]).get("summary", "")
            if summary and summary not in seen:
                seen.add(summary)
                parts.append(summary)
        return Reply(text="\n\n".join(parts) if parts else "OUT_OF_SCOPE")
