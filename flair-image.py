#!/usr/bin/env python3
"""Helper for the gpt-image-2.5-flare path: upload an edit source, print the workflow payload
for MCP submit_workflow, download a finished output, and publish it to the JIMSKY stage.

Submission itself is deliberately not done here: the flare node is a paid partner node and only
the OAuth-backed MCP session may call it (a workspace API key gets "Please login first"). So this
script does the parts a script legitimately can, and prints the exact JSON to submit.

    flair-image.py t2i "prompt text"                        # prints workflow for text to image
    flair-image.py edit <source image> "edit instruction"   # uploads, prints workflow for an edit
    flair-image.py fetch <prompt_id>                        # waits, downloads, publishes
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

API = "https://cloud.comfy.org/api"
MEDIA_PUBLISHER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "publish-media.py")
OUTDIR = os.environ.get("JIMSKY_IMAGE_OUT", "/tmp/jimsky_gen")

NO_TEXT = "No text, no lettering, no watermark, no signature."


def api_key() -> str:
    key = os.environ.get("COMFY_API_KEY") or os.environ.get("COMFY_CLOUD_API_KEY")
    if key:
        return key
    for path in ("/home/ubuntu/.hermes/.env", "/home/ubuntu/.hermes/profiles/jimsky/.env"):
        try:
            for line in open(path):
                if line.startswith(("COMFY_CLOUD_API_KEY=", "COMFY_API_KEY=")):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            continue
    sys.exit("no Comfy API key found (COMFY_API_KEY / COMFY_CLOUD_API_KEY)")


def node_inputs(prompt: str, size: str, quality: str, image_name: str | None, seed: int) -> dict:
    """custom_width/height/background are required by the node even when inert."""
    inp = {
        "prompt": prompt,
        "model": "gpt-image-2.5-flare",
        "model.size": size,
        "model.quality": quality,
        "model.background": "opaque",
        "model.custom_width": 1024,
        "model.custom_height": 1024,
        "n": 1,
        "seed": seed,
    }
    if image_name:
        inp["model.images.image_1"] = ["1", 0]
    return inp


def workflow(prompt: str, size: str, quality: str, image_name: str | None, seed: int, prefix: str) -> dict:
    wf = {"2": {"class_type": "OpenAIGPTImageNodeV2",
                "inputs": node_inputs(prompt, size, quality, image_name, seed)},
          "3": {"class_type": "SaveImage",
                "inputs": {"filename_prefix": prefix, "images": ["2", 0]}}}
    if image_name:
        wf["1"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
    return wf


def upload(path: str) -> str:
    out = subprocess.run(
        ["curl", "-s", "-m", "300", "-X", "POST",
         "-H", "Authorization: Bearer %s" % api_key(),
         "-F", "image=@%s" % path, "-F", "type=input", "-F", "overwrite=true",
         "%s/upload/image" % API],
        capture_output=True, text=True).stdout
    try:
        name = json.loads(out).get("name", "")
    except Exception:
        name = ""
    if not name:
        sys.exit("upload failed: %s" % out[:200])
    return name


def job(prompt_id: str) -> dict:
    req = urllib.request.Request("%s/jobs/%s" % (API, prompt_id),
                                headers={"Authorization": "Bearer %s" % api_key()})
    return json.load(urllib.request.urlopen(req, timeout=60))


def download(name: str, dest: str) -> int:
    # -L matters: /api/view 302s, and without it curl saves a 0-byte file.
    subprocess.run(["curl", "-sL", "-m", "300", "-H", "Authorization: Bearer %s" % api_key(),
                    "-o", dest, "%s/view?filename=%s&type=output" % (API, name)], check=False)
    return os.path.getsize(dest) if os.path.exists(dest) else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("t2i")
    t.add_argument("prompt")
    t.add_argument("--size", default="1024x1024")
    t.add_argument("--quality", default="high")
    t.add_argument("--seed", type=int, default=0)

    e = sub.add_parser("edit")
    e.add_argument("source")
    e.add_argument("instruction")
    e.add_argument("--size", default="1024x1536")
    e.add_argument("--quality", default="high")
    e.add_argument("--seed", type=int, default=0)

    f = sub.add_parser("fetch")
    f.add_argument("prompt_id")
    f.add_argument("--caption", default="")
    f.add_argument("--no-publish", action="store_true")
    f.add_argument("--timeout", type=int, default=900)

    a = ap.parse_args()

    if a.cmd in ("t2i", "edit"):
        if a.cmd == "t2i":
            wf = workflow(a.prompt if a.prompt.rstrip().endswith(".") else a.prompt + " " + NO_TEXT,
                          a.size, a.quality, None, a.seed, "jimsky_t2i")
            print("Submit this with the comfy-cloud MCP tool submit_workflow (confirm: true):")
        else:
            name = upload(a.source)
            print("uploaded source as: %s" % name)
            prompt = ("Edit this image. Keep the subject, pose and framing exactly as they are. %s %s"
                      % (a.instruction, NO_TEXT))
            wf = workflow(prompt, a.size, a.quality, name, a.seed, "jimsky_edit")
            print("Submit this with the comfy-cloud MCP tool submit_workflow (confirm: true):")
        print(json.dumps({"workflow": wf, "confirm": True}, indent=2))
        return 0

    # fetch
    os.makedirs(OUTDIR, exist_ok=True)
    start = time.time()
    while time.time() - start < a.timeout:
        state = job(a.prompt_id)
        status = state.get("status")
        if status in ("completed", "error", "cancelled"):
            break
        time.sleep(10)
    else:
        sys.exit("timed out waiting for %s" % a.prompt_id)

    if status != "completed":
        sys.exit("job %s finished as %s" % (a.prompt_id, status))

    files = [im["filename"] for o in (state.get("outputs") or {}).values()
             for im in (o.get("images") or [])]
    if not files:
        sys.exit("job completed but reported no images")
    rc = 0
    for name in files:
        dest = os.path.join(OUTDIR, "flare_%s" % name[:12])
        size = download(name, dest)
        print("downloaded %s -> %s (%d bytes)" % (name[:16], dest, size))
        if size < 10_000:
            print("  refusing to publish: file too small to be an image")
            rc = 1
            continue
        if not a.no_publish:
            subprocess.run([sys.executable, MEDIA_PUBLISHER, dest,
                            "--caption", a.caption or "gpt-image-2.5-flare output",
                            "--kind", "image"], check=False)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
