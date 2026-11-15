"""Command line: lapse fetch | assemble | inspect | export | verify | validate | tools | ask | agent | serve | mcp | synth | demo"""

from __future__ import annotations

import argparse

from . import config


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="lapse", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("synth", help="write synthetic zonal cubes (no NASA login needed)")
    p.add_argument("--force", action="store_true", help="overwrite real NASA cubes")
    sub.add_parser("export", help="compute trends and write web/data")
    sub.add_parser("verify", help="recompute every published number from data/zonal and compare (no login needed)")
    sub.add_parser("validate", help="compare our numbers with published results")
    sub.add_parser("tools", help="list every tool in the hub catalog")
    p = sub.add_parser("ask", help="ask the hub a question; anything left out is chosen for you")
    p.add_argument("--what", default="t", help="measure: t, qv, o3")
    p.add_argument("--where", default="global", help="a region id (global, arctic, tropics, ...) or a latitude")
    p.add_argument("--km", type=float, help="height in km (default: the strongest labelled change)")
    p.add_argument("--data", default="auto", help="airs, merra2 or auto")
    p.add_argument("--method", default="auto", help="robust, classic, yearly, textbook or auto")
    p.add_argument("--years", default="auto", help="full, airs_era or auto")
    p.add_argument("--months", default="none", help="none, no_hunga or no_volcano")
    p = sub.add_parser("agent", help="ask in your own words; answers come only from the NASA data")
    p.add_argument("question", nargs="*", help="leave empty for a conversation")
    p.add_argument("--model", help="auto (default), rules, anthropic, gemini, openrouter, openai, ollama or custom")
    p.add_argument("--steps", action="store_true", help="show every tool call")
    p.add_argument("--json", action="store_true", help="print the full result as JSON")
    sub.add_parser("mcp", help="serve the tools to an MCP client (Claude Desktop, Claude Code) over stdio")
    p = sub.add_parser("serve", help="the website with its ask box, on http://localhost:8000")
    p.add_argument("--port", type=int, default=8000)
    p = sub.add_parser("demo", help="synth + export in one go")
    p.add_argument("--force", action="store_true", help="overwrite real NASA cubes")

    names = list(config.DATASETS)
    p = sub.add_parser("inspect", help="print one real file's variables and dimensions")
    p.add_argument("dataset", choices=names)

    p = sub.add_parser("fetch", help="download real NASA data into zonal cubes")
    p.add_argument("dataset", choices=names)
    p.add_argument("--start", help="YYYY-MM (default: start of record)")
    p.add_argument("--end", help="YYYY-MM (default: two months ago)")
    p.add_argument("--stride", type=int, help="keep every Nth grid point (default: per dataset)")
    p.add_argument("--workers", type=int, default=4, help="downloads at the same time")

    p = sub.add_parser("assemble", help="rebuild cubes from the month cache")
    p.add_argument("dataset", choices=names)

    args = ap.parse_args(argv)

    if args.cmd in ("synth", "demo"):
        from .backend.data import cubes, synthetic
        real = [f.name for f in config.ZONAL_DIR.glob("*.nc")
                if cubes.read_cube(f).attrs.get("synthetic") != "true"]
        if real and not args.force:
            raise SystemExit("Real NASA data is in data/zonal (" + ", ".join(sorted(real)) + ").\n"
                             "Synthetic data would replace it and the site. Add --force if you mean it.")
        for path in synthetic.generate():
            print(f"  wrote {path.name} (synthetic)")
    if args.cmd in ("export", "demo"):
        from .backend.actions import export
        export.run()
    if args.cmd == "verify":
        from .backend.actions import verify
        if not verify.run()["ok"]:
            raise SystemExit(1)
    if args.cmd == "validate":
        from .backend.actions import validate
        validate.run()
    if args.cmd == "tools":
        from .hub import registry
        cat = registry.catalog()
        print("Data sources")
        for d in config.DATASETS.values():
            print(f"  {d.id:10s} {d.label}: {', '.join(v.id for v in d.variables)}")
        print("Methods")
        for m in cat["methods"]:
            tag = " (recommended)" if m["recommended"] else "" if m["sound"] else " (comparison only)"
            print(f"  {m['id']:10s} {m['label']}{tag}: {m['science']}")
        print("Checks, always on")
        for c in cat["checks"]:
            print(f"  {c['id']:10s} {c['label']}: {c['science']}")
    if args.cmd == "ask":
        from .hub import router
        try:
            out = router.answer({"what": args.what, "where": args.where, "km": args.km, "dataset": args.data,
                                 "method": args.method, "period": args.years, "mask": args.months})
        except ValueError as exc:
            raise SystemExit(str(exc))
        r = out["request"]
        print(out["sentence"])
        print(f"  tools: data={r['dataset']} method={r['method']} years={r['period']} months={r['mask']}"
              + (f"  (auto chose: {', '.join(r['chosen_by_auto'])})" if r["chosen_by_auto"] else ""))
        print(f"  file:  web/data/{out['route']}")
    if args.cmd == "agent":
        import json

        from .agent import harness, tools
        site = tools.Site()

        def ask(question):
            result = harness.run(question, args.model, site)
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False) if args.json else result.text(args.steps))

        if args.question:
            ask(" ".join(args.question))
        else:
            print("Ask about air temperature, water vapor or ozone at any height. Empty line to stop.")
            while True:
                try:
                    question = input("\n> ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if not question:
                    break
                ask(question)
    if args.cmd == "serve":
        from .agent import web
        web.serve(args.port)
    if args.cmd == "mcp":
        from .agent import mcp_server
        mcp_server.serve()
    if args.cmd == "inspect":
        from .backend.data import fetch
        fetch.inspect(args.dataset)
    if args.cmd == "fetch":
        from .backend.data import fetch
        fetch.fetch(args.dataset, args.start, args.end, args.stride, args.workers)
    if args.cmd == "assemble":
        from .backend.data import fetch
        fetch.assemble(args.dataset)


if __name__ == "__main__":
    main()
