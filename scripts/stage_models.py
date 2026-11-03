#!/usr/bin/env python3
"""Stage ONNX face models onto the findme network volume.

Uses the volume's S3-compatible API (US-IL-1). Requires console-created S3
credentials:
  AWS_ACCESS_KEY_ID=<runpod user id>  AWS_SECRET_ACCESS_KEY=<rps_... key>
  python scripts/stage_models.py --volume <NETWORK_VOLUME_ID>

Fallback without S3 keys: attach the volume to a temporary pod and
`runpodctl send` the two files into /workspace/models/.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "plans" / "reference" / "assets"
ENDPOINT = "https://s3api-us-il-1.runpod.io/"
REGION = "US-IL-1"
FILES = ["det_10g.onnx", "w600k_r50.onnx"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--volume", required=True)
    ap.add_argument("--endpoint", default=ENDPOINT)
    ap.add_argument("--region", default=REGION)
    args = ap.parse_args()

    if not os.environ.get("AWS_ACCESS_KEY_ID") or not os.environ.get("AWS_SECRET_ACCESS_KEY"):
        print("S3 credentials missing. Create an S3 API key in the Runpod console (Settings > S3 API keys).")
        return 1

    import boto3

    s3 = boto3.client("s3", endpoint_url=args.endpoint, region_name=args.region)
    for name in FILES:
        src = ASSETS / name
        if not src.exists():
            print(f"missing asset {src}")
            return 1
        key = f"models/{name}"
        print(f"uploading {name} ({src.stat().st_size / 1e6:.1f} MB) -> s3://{args.volume}/{key}")
        s3.upload_file(str(src), args.volume, key)
    print("staged. workers read FINDME_MODELS_DIR=/runpod-volume/models")
    return 0


if __name__ == "__main__":
    sys.exit(main())
