"""Command-line interface: ``he-dapi translate ...`` / ``he-dapi info``."""
from __future__ import annotations

import argparse
import sys


def _cmd_translate(args) -> int:
    from .translate import translate_to_file

    out = translate_to_file(
        args.input,
        args.out,
        direction=args.direction,
        weights=args.weights,
        device=args.device,
    )
    print(f"[he-dapi] wrote {out}")
    return 0


def _cmd_info(_args) -> int:
    from . import __version__
    from .model import HF_REPO_ID, WEIGHT_FILES

    print(f"he-dapi {__version__}")
    print(f"weights repo: https://huggingface.co/{HF_REPO_ID}")
    for direction, filename in WEIGHT_FILES.items():
        print(f"  {direction:<8} -> {filename}")
    return 0


def main(argv=None) -> int:
    from . import __version__

    parser = argparse.ArgumentParser(prog="he-dapi", description="H&E <-> DAPI virtual staining")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("translate", help="translate an image")
    p.add_argument("--input", "-i", required=True, help="input image path")
    p.add_argument("--out", "-o", required=True, help="output image path")
    p.add_argument("--direction", "-d", default="he2dapi", choices=["he2dapi", "dapi2he"])
    p.add_argument("--weights", default=None, help="optional local weights file")
    p.add_argument("--device", default="cpu")
    p.set_defaults(func=_cmd_translate)

    sub.add_parser("info", help="show model/weight info").set_defaults(func=_cmd_info)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
