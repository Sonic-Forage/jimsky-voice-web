#!/usr/bin/env python3
"""Publish a generated file to the JIMSKY stage.

Hermes calls this after it produces an image, video, or audio file. It copies the file into the
media root and appends a record to index.json, which the front end polls. The browser renders
whatever shows up here, and that is the entire contract.

    publish-media.py <file> --caption "WOOZLE at the drive-in" [--kind image|video|audio]

Prints a JSON result on success, exits non-zero with a reason on failure.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import shutil
import sys
import time
import uuid

MEDIA_ROOT = os.environ.get("JIMSKY_MEDIA_ROOT", '/mnt/forge/jimsky-media')
INDEX = os.path.join(MEDIA_ROOT, "index.json")
PUBLIC_BASE = os.environ.get("JIMSKY_MEDIA_BASE", "")
MAX_BYTES = int(os.environ.get("JIMSKY_MEDIA_MAX_BYTES", 200 * 1024 * 1024))


def kind_for(path, explicit):
    if explicit:
        return explicit
    guess, _ = mimetypes.guess_type(path)
    if guess is None:
        return "image"
    if guess.startswith("video/"):
        return "video"
    if guess.startswith("audio/"):
        return "audio"
    return "image"


def load_index():
    try:
        with open(INDEX, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or "items" not in data:
            raise ValueError("malformed index")
        return data
    except FileNotFoundError:
        return {"items": []}
    except Exception as exc:          # never lose the new item to a corrupt index
        sys.stderr.write("warning: rebuilding unreadable index\n")
        return {"items": []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--caption", default="")
    ap.add_argument("--kind", choices=["image", "video", "audio"], default=None)
    ap.add_argument("--agent", default="jimsky")
    ap.add_argument("--keep-name", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(args.file):
        sys.stderr.write("error: no such file: %s\n" % args.file)
        return 2
    size = os.path.getsize(args.file)
    if size == 0:
        sys.stderr.write("error: file is empty\n")
        return 2
    if size > MAX_BYTES:
        sys.stderr.write("error: %d bytes exceeds limit %d\n" % (size, MAX_BYTES))
        return 2

    os.makedirs(MEDIA_ROOT, exist_ok=True)
    ext = os.path.splitext(args.file)[1].lower() or ".bin"
    item_id = uuid.uuid4().hex[:12]
    name = os.path.basename(args.file) if args.keep_name else "%d-%s%s" % (int(time.time()), item_id, ext)
    dest = os.path.join(MEDIA_ROOT, name)
    shutil.copy2(args.file, dest)

    mime = mimetypes.guess_type(dest)[0] or "application/octet-stream"
    record = {
        "id": item_id, "kind": kind_for(dest, args.kind), "mime": mime, "file": name,
        "caption": args.caption, "agent": args.agent, "bytes": size, "at": int(time.time() * 1000),
    }
    index = load_index()
    index["items"] = ([record] + index["items"])[:120]
    index["updated"] = record["at"]
    tmp = INDEX + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=1)
    os.replace(tmp, INDEX)            # atomic: the front end never reads a half-written index

    url = (PUBLIC_BASE.rstrip("/") + "/" + name) if PUBLIC_BASE else name
    print(json.dumps({"ok": True, "file": dest, "url": url, "kind": record["kind"], "bytes": size}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
