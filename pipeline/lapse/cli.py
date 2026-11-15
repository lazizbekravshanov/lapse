"""Command line: lapse synth | fetch | assemble | inspect | export | validate | demo"""

from __future__ import annotations

import argparse

from . import config


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="lapse", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("synth", help="write synthetic zonal cubes (no NASA login needed)")
    p.add_argument("--force", action="store_true", help="overwrite real NASA cubes")
    sub.add_parser("export", help="compute trends and write web/data")
    sub.add_parser("validate", help="compare our numbers with published results")
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
    if args.cmd == "validate":
        from .backend.actions import validate
        validate.run()
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
