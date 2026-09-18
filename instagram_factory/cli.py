from __future__ import annotations

import argparse
import json

from .config import Settings, load_env
from .pipeline import Pipeline


def main() -> None:
    parser = argparse.ArgumentParser(prog="ig-factory")
    parser.add_argument("command", choices=("render", "status", "publish-due", "test-publish"))
    args = parser.parse_args()
    load_env()
    pipeline = Pipeline(Settings())
    if args.command == "render":
        result = pipeline.render_ready()
    elif args.command == "status":
        result = pipeline.status()
    elif args.command == "test-publish":
        result = pipeline.publish_due(force=True)
    else:
        result = pipeline.publish_due()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
