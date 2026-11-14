"""Command line: lapse synth | fetch | assemble | inspect | export | demo"""

from __future__ import annotations

import argparse

from . import config


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="lapse", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("synth", help="write synthetic zonal cubes (no NASA login needed)")
    sub.add_parser("export", help="compute trends and write web/data")
    sub.add_parser("demo", help="synth + export in one go")

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
        from . import synthetic
        for path in synthetic.generate():
            print(f"  wrote {path.name} (synthetic)")
    if args.cmd in ("export", "demo"):
        from . import export
        export.run()
    if args.cmd == "inspect":
        from . import fetch
        fetch.inspect(args.dataset)
    if args.cmd == "fetch":
        from . import fetch
        fetch.fetch(args.dataset, args.start, args.end, args.stride, args.workers)
    if args.cmd == "assemble":
        from . import fetch
        fetch.assemble(args.dataset)


if __name__ == "__main__":
    main()
