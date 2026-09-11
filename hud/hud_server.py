#!/usr/bin/env python3
"""JIMSKY HUD backend.

The studio half of the front end: model catalog, templates, batches, image editing, web browsing
and a credit ledger. It exists because the front end needs to do things a browser cannot - run
generation jobs that take 30-90 seconds, drive a real Chromium, and publish results to the stage.

Why it lives on the VPS instead of Netlify: serverless functions time out long before a video or
upscale finishes. Why it needs a key: every call here can spend money, so an open endpoint would
be the wrong default. No key, no spend.

    python hud_server.py            # 127.0.0.1:8099, exposed by Caddy at jimsky-hud.<ip>.nip.io
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import Body, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

HOME = Path("/home/ubuntu")
WORK = Path("/home/ubuntu/sf-ops/jimsky-hud")
RUNS = WORK / "runs"
MEDIA_ROOT = Path("/mnt/forge/jimsky-media")
PUBLISHER = Path("/home/ubuntu/sf-ops/jimsky-voice/publish-media.py")
MEDIA_BASE = os.environ.get("JIMSKY_MEDIA_BASE", "https://jimsky-media.15-204-82-198.nip.io")
STATE = WORK / "state.json"
LEDGER = WORK / "credits.json"
PORT = int(os.environ.get("JIMSKY_HUD_PORT", "8099"))

# Spend guardrails: a batch larger than this is almost always a mistake, and the box has 6 cores.
MAX_BATCH = int(os.environ.get("JIMSKY_HUD_MAX_BATCH", "8"))
WORKERS = int(os.environ.get("JIMSKY_HUD_WORKERS", "2"))
VIDEO_TIMEOUT = int(os.environ.get("JIMSKY_HUD_VIDEO_TIMEOUT", "900"))

# Credit price per job, by category. Not a billing engine - a speed bump that makes a runaway
# batch visible before it runs.
PRICE = {"text-to-image": 1, "image-edit": 1, "image-to-image": 1, "controlnet": 1,
         "inpaint": 1, "outpaint": 1, "background": 1, "vectorize": 1, "upscale": 2,
         "text-to-video": 5, "image-to-video": 5, "video-extend": 5, "lipsync": 5}

# Cheat codes: the point is to make testing pleasant, not to be security.
CHEAT_CODES = {
    "SUNBURST": 100, "HYPERBLOOM": 100, "JIMSKY": 250, "RASCALVEX": 50, "ENFOREST": 500,
}

app = FastAPI(title="JIMSKY HUD", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://jimsky-voice.netlify.app", "http://localhost:5199",
                   "http://127.0.0.1:5199"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_lock = threading.Lock()
_jobs: dict[str, dict] = {}
_pool = ThreadPoolExecutor(max_workers=WORKERS)


# --------------------------------------------------------------------------- auth

def hud_key() -> str:
    """The key the front end must present. Generated once into the profile env."""
    env = HOME / ".hermes/profiles/jimsky/.env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("JIMSKY_HUD_KEY="):
                return line.split("=", 1)[1].strip()
    key = secrets.token_urlsafe(24)
    with env.open("a") as fh:
        fh.write(f"\nJIMSKY_HUD_KEY={key}\n")
    return key


HUD_KEY = hud_key()


def require_key(x_hud_key: str | None) -> None:
    if not x_hud_key or not secrets.compare_digest(x_hud_key, HUD_KEY):
        raise HTTPException(status_code=401, detail="missing or wrong X-HUD-Key")


# --------------------------------------------------------------------------- credits

def load_credits() -> dict:
    if LEDGER.exists():
        try:
            return json.loads(LEDGER.read_text())
        except Exception:
            pass
    return {"balance": 25, "spent": 0, "history": [], "redeemed": []}


def save_credits(data: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    tmp = LEDGER.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(LEDGER)


def charge(n: int) -> None:
    with _lock:
        data = load_credits()
        data["balance"] -= n
        data["spent"] += n
        data["history"].append({"at": int(time.time() * 1000), "delta": -n})
        data["history"] = data["history"][-200:]
        save_credits(data)


# --------------------------------------------------------------------------- catalog

_TEMPLATES = [
    {"id": "neon-portrait", "name": "Neon portrait", "category": "text-to-image",
     "prompt": "{subject}, cinematic cyberpunk portrait, teal and magenta key light, wet "
               "reflections, volumetric haze, dramatic rim light, 35mm film grain, extreme detail",
     "hint": "One character, hero lighting."},
    {"id": "crew-sheet", "name": "Crew reference sheet", "category": "text-to-image",
     "prompt": "Character reference sheet: {subject} shown as a full-body turnaround with front, "
               "side and back views, four expression studies and three action poses on a neutral "
               "grey ground, clean studio lighting, flat even exposure, production art",
     "hint": "This is the sheet the 3D pipeline eats."},
    {"id": "turnaround-strip", "name": "Turnaround strip", "category": "text-to-image",
     "prompt": "Orthographic turnaround strip, the SAME character four times: front, left profile, "
               "back, right profile, evenly spaced on a plain background, neutral A-pose, empty "
               "hands, consistent proportions and costume across all four views",
     "hint": "Wide. Feed it to the mesh pipeline."},
    {"id": "psychedelic-plate", "name": "Psychedelic plate", "category": "text-to-image",
     "prompt": "{subject}, rendered as a {style} psychedelic art plate. Palette: {palette}. "
               "Museum-grade print quality, extreme micro-detail, rich deep blacks, one centred "
               "specimen on a dark neutral ground",
     "hint": "The HYPERBLOOM look."},
    {"id": "poster", "name": "Gig poster", "category": "text-to-image",
     "prompt": "Screen-printed gig poster for {subject}, high-contrast limited palette, bold "
               "silhouette, halftone texture, slight paper grain, three-colour overprint",
     "hint": "Silhouette-first, prints well."},
    {"id": "product", "name": "Product shot", "category": "text-to-image",
     "prompt": "Studio product photograph of {subject}, seamless background, softbox lighting, "
               "crisp shadows, catalogue grade, centred composition",
     "hint": "Clean, sellable."},
    {"id": "push-mood", "name": "Edit: push the mood", "category": "image-edit",
     "prompt": "Edit this image. Keep the subject, pose and framing exactly as they are. Push the "
               "atmosphere: heavier contrast, richer colour, dramatic volumetric light, deeper "
               "blacks, hotter highlights, cinematic grade",
     "hint": "Needs a source image."},
    {"id": "restyle", "name": "Edit: restyle", "category": "image-edit",
     "prompt": "Edit this image. Keep the subject and composition identical. Restyle it as "
               "{style}, preserving every identifiable feature of the subject",
     "hint": "Same subject, new look."},
    {"id": "cleanup", "name": "Edit: clean up", "category": "image-edit",
     "prompt": "Edit this image. Remove any text, lettering, labels, watermarks and stray marks. "
               "Keep everything else pixel-identical. Leave clean empty background where the text "
               "was",
     "hint": "Strips text before training."},
]

# --------------------------------------------------------------------------- mods
#
# A mod is a capability with a status you can read at a glance: what it needs, whether that is
# present, and where its guts live. Nothing here auto-installs anything - a mod that needs a paid
# third-party key stays "needs-key" until a human supplies it, which is the whole point.

MODS = [
    {"id": "voice", "name": "Voice link", "status": "built-in",
     "what": "Talk to the agent over LiveKit on the self-hosted server.",
     "console": "one-off: restart the agent gateway from a shell outside it",
     "docs": "jimsky-voice-web/README.md"},
    {"id": "studio", "name": "Studio / Comfy", "status": "built-in",
     "what": "Model catalog, batches, edits, credits. This panel.",
     "docs": "jimsky-voice-web/IMAGE-STACK.md"},
    {"id": "browse", "name": "Web browser", "status": "built-in",
     "what": "Real Chromium screenshots of any page onto the stage.", "docs": "hud_server.py"},
    {"id": "liveavatar", "name": "LiveAvatar face", "status": None,
     "what": "An animated talking avatar driven by GPT-Live, where tool calls land on screen as "
             "animated overlays. This is the seed for live interactive games.",
     "requires": ["LIVEAVATAR_API_KEY"],
     "path": "/home/ubuntu/sf-ops/mods/liveavatar",
     "run": "cd /home/ubuntu/sf-ops/mods/liveavatar && pnpm dev",
     "persona": "server/prompts/instructions.md + greeting.md",
     "overlays": "web/public/overlays/*.html",
     "docs": "docs/REPURPOSING.md + docs/ADDING_FRONTEND_COMPONENTS.md",
     "source": "github.com/heygen-com/liveavatar-gpt-live-demos (MIT)",
     "verified": "pnpm install + pnpm typecheck pass with no keys set"},
    {"id": "publisher", "name": "Publisher", "status": "stopped",
     "what": "Push finished work to a channel. The Kick station is stopped and disabled at your "
             "request.",
     "run": "systemctl --user enable --now sonic-forage-kick-broadcast"},
    {"id": "games", "name": "Games", "status": "planned",
     "what": "Interactive modes on the stage: the avatar calls a tool, the stage reacts."},
]


def env_present(name: str) -> bool:
    if os.environ.get(name):
        return True
    for path in (HOME / ".hermes/.env", HOME / ".hermes/profiles/jimsky/.env"):
        try:
            for line in path.read_text().splitlines():
                if line.startswith(f"{name}=") and len(line.split("=", 1)[1].strip()) > 8:
                    return True
        except OSError:
            continue
    return False


def mods_state() -> list[dict]:
    out = []
    for mod in MODS:
        m = dict(mod)
        need = m.get("requires") or []
        if need:
            missing = [k for k in need if not env_present(k)]
            m["missing"] = missing
            m["status"] = "ready" if not missing else "needs-key"
        out.append(m)
    return out


# --------------------------------------------------------------------------- workflows

def load_workflows() -> list[dict]:
    path = WORK / "workflows.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return [
        {"id": "wf-neon", "name": "Neon portrait", "model": "flux-2", "builtin": True,
         "prompt": "{subject}, cinematic cyberpunk portrait, teal and magenta key light, wet "
                   "reflections, volumetric haze, dramatic rim light, 35mm film grain",
         "notes": "Hero shot. Swap the model to gpt-image-2.5-flare for the newer stack."},
        {"id": "wf-sheet", "name": "Crew sheet to 3D", "model": "flux-2", "builtin": True,
         "prompt": "Character reference sheet: {subject} as a full-body turnaround, front, side and "
                   "back, four expression studies, three action poses, neutral grey ground, flat "
                   "even studio lighting, production art",
         "notes": "Feeds the mesh pipeline."},
        {"id": "wf-strip", "name": "Turnaround strip", "model": "flux-kontext-max", "builtin": True,
         "prompt": "Orthographic turnaround strip, the SAME character four times: front, left "
                   "profile, back, right profile, evenly spaced, plain background, neutral A-pose, "
                   "empty hands, identical costume in every view",
         "notes": "Needs a source sheet. Wide output."},
        {"id": "wf-clean", "name": "Strip text (training prep)", "model": "flux-kontext",
         "builtin": True,
         "prompt": "Edit this image. Remove all text, lettering, labels, watermarks and stray "
                   "marks. Keep everything else pixel-identical, leave clean background where the "
                   "text was",
         "notes": "Run before fine-tuning so the model never learns the furniture."},
    ]


def save_workflows(items: list[dict]) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    tmp = (WORK / "workflows.json").with_suffix(".tmp")
    tmp.write_text(json.dumps(items, indent=1))
    tmp.replace(WORK / "workflows.json")


# New stack first: models named below lead, and the older flux-1.x era is demoted so the default
# view is the current generation rather than the widest possible list.
NEW_STACK = ("flare", "nano-banana", "kontext-max", "kling-v3", "kling-v2-6", "seedance",
             "grok", "reve", "soul", "hidream", "qwen-image", "z-image", "wan-2")
LEGACY = ("flux-pro", "flux-1", "flux-canny", "flux-depth", "flux-fill", "flux-expand",
          "dalle-3", "ideogram-v2", "sd3", "sdxl")


def tier_of(alias: str, category: str) -> str:
    low = alias.lower()
    if any(k in low for k in NEW_STACK):
        return "new"
    if any(k in low for k in LEGACY):
        return "legacy"
    if category in ("text-to-video", "image-to-video", "video-extend", "lipsync"):
        return "new"
    return "current"


_catalog_cache: dict | None = None


def comfy_models() -> list[dict]:
    env = {**os.environ, "COMFY_API_KEY": comfy_key()}
    try:
        out = subprocess.run(["comfy", "generate", "list", "--json"], capture_output=True,
                             text=True, timeout=180, env=env).stdout
        data = json.loads(out)
        models = data.get("models") or []
        for m in models:
            m["price"] = PRICE.get(m.get("category", ""), 1)
            m["tier"] = tier_of(m.get("alias", ""), m.get("category", ""))
        # The flare node is not in the CLI catalog: it is reached through the agent (paid node,
        # OAuth only), so it is declared here and routed via /api/agent instead of the CLI.
        models.insert(0, {"alias": "gpt-image-2.5-flare", "id": "OpenAIGPTImageNodeV2",
                          "partner": "openai", "category": "text-to-image", "mode": "mcp",
                          "price": 2, "tier": "new",
                          "summary": "Newest OpenAI image model: text to image, highest fidelity. "
                                     "Routed through the agent (paid node)."})
        models.insert(1, {"alias": "gpt-image-2.5-flare-edit",
                          "id": "OpenAIGPTImageNodeV2+LoadImage",
                          "partner": "openai", "category": "image-edit", "mode": "mcp",
                          "price": 2, "tier": "new",
                          "summary": "Flare image edit: image in, image out. Needs a source image."})
        order = {"new": 0, "current": 1, "legacy": 2}
        models.sort(key=lambda m: (order.get(m.get("tier", "current"), 1), m.get("category", ""),
                                   m["alias"]))
        return models
    except Exception:
        return []


def comfy_key() -> str:
    key = os.environ.get("COMFY_API_KEY") or os.environ.get("COMFY_CLOUD_API_KEY")
    if key:
        return key
    for path in (HOME / ".hermes/.env", HOME / ".hermes/profiles/jimsky/.env"):
        try:
            for line in path.read_text().splitlines():
                if line.startswith(("COMFY_CLOUD_API_KEY=", "COMFY_API_KEY=")):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            continue
    return ""


def catalog(refresh: bool = False) -> dict:
    global _catalog_cache
    if _catalog_cache is None or refresh:
        models = comfy_models()
        _catalog_cache = {"models": models, "templates": _TEMPLATES,
                          "counts": {"models": len(models), "templates": len(_TEMPLATES)}}
    return _catalog_cache


# --------------------------------------------------------------------------- jobs

def load_jobs() -> None:
    if STATE.exists():
        try:
            _jobs.update(json.loads(STATE.read_text()).get("jobs", {}))
        except Exception:
            pass


def save_jobs() -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        recent = dict(sorted(_jobs.items(), key=lambda kv: kv[1]["at"], reverse=True)[:200])
        tmp = STATE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"jobs": recent}, indent=1))
        tmp.replace(STATE)


def publish(path: Path, caption: str) -> str | None:
    """Hand the file to the stage. This is the same entry point the agent uses."""
    try:
        out = subprocess.run([sys.executable, str(PUBLISHER), str(path), "--caption", caption,
                              "--kind", "image", "--agent", "hud"],
                             capture_output=True, text=True, timeout=180,
                             env={**os.environ, "JIMSKY_MEDIA_BASE": MEDIA_BASE}).stdout
        return json.loads(out).get("url")
    except Exception:
        return None


def run_generate(job_id: str) -> None:
    job = _jobs[job_id]
    job["state"] = "running"
    job["started"] = int(time.time() * 1000)
    save_jobs()

    RUNS.mkdir(parents=True, exist_ok=True)
    stamp = f"{int(time.time())}-{job_id[:6]}"
    out = RUNS / f"{stamp}.png"
    args = ["comfy", "generate", job["model"], "--prompt", job["prompt"],
            "--download", str(out), "--json"]
    if job.get("image"):
        args += ["--input_image", job["image"]]
    for k, v in (job.get("params") or {}).items():
        args += [f"--{k}", str(v)]

    env = {**os.environ, "COMFY_API_KEY": comfy_key()}
    try:
        proc = subprocess.run(args, capture_output=True, text=True,
                              timeout=VIDEO_TIMEOUT, env=env)
        job["exit"] = proc.returncode
        if proc.returncode != 0 or not out.exists():
            job["state"] = "error"
            job["error"] = (proc.stderr or proc.stdout or "no output")[-600:]
        else:
            size = out.stat().st_size
            if size < 5000:
                job["state"] = "error"
                job["error"] = f"output suspiciously small ({size} bytes)"
            else:
                job["state"] = "done"
                job["file"] = out.name
                job["bytes"] = size
                job["url"] = publish(out, job.get("caption") or job["prompt"][:80])
    except subprocess.TimeoutExpired:
        job["state"] = "error"
        job["error"] = f"timed out after {VIDEO_TIMEOUT}s"
    except Exception as exc:
        job["state"] = "error"
        job["error"] = repr(exc)
    job["finished"] = int(time.time() * 1000)
    save_jobs()


def submit(model: str, prompt: str, image: str | None, params: dict | None,
           caption: str | None) -> dict:
    model = (model or "").strip()
    prompt = (prompt or "").strip()
    if not model or not prompt:
        raise HTTPException(status_code=400, detail="model and prompt are required")
    if len(prompt) > 8000:
        raise HTTPException(status_code=400, detail="prompt too long")
    job_id = uuid.uuid4().hex[:12]
    info = next((m for m in catalog()["models"] if m["alias"] == model), None)
    if info is None:
        raise HTTPException(status_code=400, detail=f"unknown model: {model}")
    cat = info.get("category", "text-to-image")
    price = PRICE.get(cat, 1)
    with _lock:
        data = load_credits()
        if data["balance"] < price:
            raise HTTPException(status_code=402,
                                detail=f"not enough credits ({data['balance']} left, {price} needed)")
    charge(price)
    job = {"id": job_id, "model": model, "category": cat, "prompt": prompt, "image": image,
           "params": params or {}, "caption": caption, "price": price, "state": "queued",
           "at": int(time.time() * 1000)}
    _jobs[job_id] = job
    _pool.submit(run_generate, job_id)
    return job


# --------------------------------------------------------------------------- routes

# --------------------------------------------------------------------------- chat
#
# The full agent, text only: no LiveKit, no voice, no room. Each message runs a real agent turn
# with every tool it has, and anything it generates lands on the stage through the usual publish
# path. Session continuity is what makes this a conversation rather than a series of one-shots.

CHAT_SESSION = os.environ.get("JIMSKY_CHAT_SESSION", "jimsky-hud")
CHAT_LOG = WORK / "chat.json"


def load_chat() -> list[dict]:
    if CHAT_LOG.exists():
        try:
            return json.loads(CHAT_LOG.read_text())
        except Exception:
            pass
    return []


def save_chat(items: list[dict]) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    tmp = CHAT_LOG.with_suffix(".tmp")
    tmp.write_text(json.dumps(items[-120:], indent=1))
    tmp.replace(CHAT_LOG)


def _clean_reply(raw: str) -> str:
    """Strip CLI chrome so the panel shows the answer, not the plumbing."""
    keep = []
    for line in raw.splitlines():
        s = line.rstrip()
        if not s.strip():
            keep.append("")
            continue
        if s.startswith(("Warning:", "Query:", "Initializing agent", "Session ", "─", "┌", "└",
                         "│", "╰", "╭")) or "Unknown toolsets" in s:
            continue
        keep.append(s)
    text = "\n".join(keep).strip()
    # collapse runs of blank lines
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text


def run_chat(job_id: str, message: str) -> None:
    job = _jobs[job_id]
    log = WORK / "chat.log"
    started = time.time()
    reply, err = "", None
    # `hermes chat` owns --continue/--create-if-missing (the top-level oneshot does not), and
    # --query-file - reads the message from stdin with NOTHING shell-interpreted, so a message
    # containing quotes, $(...) or backticks cannot do anything but be a message.
    # -Q keeps the CLI's chrome (banner, warnings, reasoning panels) off stdout so the panel shows
    # the answer rather than a transcript of the agent thinking.
    base = ["hermes", "chat", "--query-file", "-", "--profile", "jimsky", "--oneshot", "-Q"]
    try:
        # Continue the named session, creating it on the first message. Without
        # --create-if-missing Hermes refuses an unknown title, which would have made every
        # message a fresh one-shot instead of a conversation.
        proc = subprocess.run(base + ["--continue", CHAT_SESSION, "--create-if-missing"],
                              input=message, capture_output=True, text=True, timeout=900,
                              cwd=str(HOME))
        reply = _clean_reply(proc.stdout or proc.stderr or "")
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "agent turn failed")[-500:]
    except subprocess.TimeoutExpired:
        err = "the agent turn timed out"
    except Exception as exc:
        err = repr(exc)[:400]

    entry_user = {"role": "user", "text": message, "at": int(started * 1000)}
    chat = load_chat() + [entry_user]
    if reply or err:
        chat.append({"role": "assistant", "text": reply or f"[error] {err}",
                     "at": int(time.time() * 1000), "seconds": round(time.time() - started, 1),
                     "error": bool(err)})
    save_chat(chat)
    with log.open("a") as fh:
        fh.write(f"\n=== {time.strftime('%H:%M:%S')} {job_id}\nQ: {message}\nA: {reply[:2000]}\n")
    job["state"] = "done" if not err else "error"
    job["reply"] = reply[:4000]
    if err:
        job["error"] = err
    job["finished"] = int(time.time() * 1000)
    save_jobs()


@app.get("/api/chat")
async def api_chat_history(x_hud_key: str | None = Header(default=None)) -> dict:
    require_key(x_hud_key)
    return {"messages": load_chat(), "session": CHAT_SESSION}


@app.post("/api/chat")
async def api_chat(payload: dict = Body(...), x_hud_key: str | None = Header(default=None)) -> dict:
    require_key(x_hud_key)
    message = (payload.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    if len(message) > 4000:
        raise HTTPException(status_code=400, detail="message too long")
    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {"id": job_id, "model": "hermes-chat", "category": "chat", "prompt": message,
                     "state": "running", "price": 0, "at": int(time.time() * 1000)}
    save_jobs()
    _pool.submit(run_chat, job_id, message)
    return {"job": _jobs[job_id]}


@app.post("/api/chat/clear")
async def api_chat_clear(x_hud_key: str | None = Header(default=None)) -> dict:
    require_key(x_hud_key)
    save_chat([])
    return {"messages": []}


# --------------------------------------------------------------------------- settings
#
# One place for "make it my machine": which ComfyUI to talk to, which endpoints, and how the
# panels behave. Persisted so a phone and a desktop see the same setup.

DEFAULTS = {
    "comfy_endpoint": "",            # e.g. http://100.84.222.44:8188 (the 4070 box) or a pod
    "comfy_endpoint_label": "",
    "livekit_url": "wss://vex.15-204-82-198.nip.io",
    "media_base": MEDIA_BASE,
    "default_model": "flux-2",
    "default_batch": 1,
    "new_stack_only": True,
    "auto_publish": True,
    "chat_dock": "float",            # float | column
    "accent": "teal",                # teal | magenta | amber
    "panels": {"queue": True, "workflows": True, "mods": True, "templates": True, "browse": True},
}

SETTINGS = WORK / "settings.json"


def load_settings() -> dict:
    data = dict(DEFAULTS)
    if SETTINGS.exists():
        try:
            saved = json.loads(SETTINGS.read_text())
            if isinstance(saved, dict):
                for k, v in saved.items():
                    if k in ("panels",) and isinstance(v, dict):
                        data["panels"] = {**DEFAULTS["panels"], **v}
                    else:
                        data[k] = v
        except Exception:
            pass
    return data


def save_settings(data: dict) -> dict:
    merged = load_settings()
    for k, v in (data or {}).items():
        if k == "panels" and isinstance(v, dict):
            merged["panels"] = {**merged.get("panels", {}), **v}
        elif k in DEFAULTS:
            merged[k] = v
    WORK.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS.with_suffix(".tmp")
    tmp.write_text(json.dumps(merged, indent=1))
    tmp.replace(SETTINGS)
    return merged


@app.get("/api/settings")
async def api_settings(x_hud_key: str | None = Header(default=None)) -> dict:
    require_key(x_hud_key)
    return {"settings": load_settings()}


@app.post("/api/settings")
async def api_save_settings(payload: dict = Body(...),
                            x_hud_key: str | None = Header(default=None)) -> dict:
    require_key(x_hud_key)
    return {"settings": save_settings(payload.get("settings") or payload)}


# --------------------------------------------------------------------------- comfy endpoints
#
# Our own ComfyUI, wherever it runs. The probe is deliberately shallow: /system_stats tells us the
# box is alive and what it is, and /object_info counts the nodes so a half-loaded instance is
# obvious rather than mysterious.

ENDPOINT_PRESETS = [
    {"id": "cloud", "label": "Comfy Cloud (default)", "url": "",
     "note": "The CLI path this HUD already uses. Paid partner nodes live here."},
    {"id": "rtx4070", "label": "Local 4070 (tailnet)", "url": "http://100.84.222.44:8188",
     "note": "Your desktop over Tailscale. Free to run, ~12 GB VRAM."},
    {"id": "localhost", "label": "This box", "url": "http://127.0.0.1:8188",
     "note": "Only if ComfyUI runs on the VPS itself."},
    {"id": "pod", "label": "Rented GB10 pod", "url": "",
     "note": "Boot one, then paste its proxy URL like https://<id>-8188.proxy.runpod.net."},
    {"id": "custom", "label": "Custom", "url": "", "note": "Any reachable ComfyUI."},
]


@app.get("/api/comfy/presets")
async def api_comfy_presets(x_hud_key: str | None = Header(default=None)) -> dict:
    require_key(x_hud_key)
    return {"presets": ENDPOINT_PRESETS, "current": load_settings().get("comfy_endpoint", "")}


@app.post("/api/comfy/test")
async def api_comfy_test(payload: dict = Body(...),
                         x_hud_key: str | None = Header(default=None)) -> dict:
    """Is that ComfyUI awake, and what is it?"""
    require_key(x_hud_key)
    url = (payload.get("url") or load_settings().get("comfy_endpoint") or "").rstrip("/")
    if not url:
        return {"ok": False, "detail": "no endpoint set - using Comfy Cloud via the CLI"}
    if not re.match(r"^https?://", url):
        raise HTTPException(status_code=400, detail="endpoint must start with http:// or https://")

    import urllib.error
    import urllib.request
    result = {"ok": False, "url": url, "checked": int(time.time() * 1000)}
    try:
        with urllib.request.urlopen(f"{url}/system_stats", timeout=12) as resp:
            stats = json.loads(resp.read())
        sysinfo = (stats.get("system") or {})
        devices = stats.get("devices") or [{}]
        result.update({
            "ok": True,
            "comfyui_version": sysinfo.get("comfyui_version") or sysinfo.get("os") or "unknown",
            "python": sysinfo.get("python_version", ""),
            "device": devices[0].get("name", "unknown"),
            "vram_total_gb": round((devices[0].get("vram_total") or 0) / 1e9, 1),
            "vram_free_gb": round((devices[0].get("vram_free") or 0) / 1e9, 1),
        })
        try:
            with urllib.request.urlopen(f"{url}/object_info", timeout=25) as resp:
                result["nodes"] = len(json.loads(resp.read()))
        except Exception:
            result["nodes"] = None
    except urllib.error.HTTPError as exc:
        result["detail"] = f"HTTP {exc.code} from {url}"
    except Exception as exc:
        result["detail"] = f"{type(exc).__name__}: {str(exc)[:140]}"
    return result


# --------------------------------------------------------------------------- run a template
#
# Convert an official template against the endpoint's own schema and run it. This is the piece that
# makes the template library more than a browser: any of the 629 can be executed on your own
# ComfyUI, or on Comfy Cloud, without a human rebuilding the graph by hand.

import comfy_runner  # local module: subgraph expansion + UI->API conversion + queue/poll


def endpoint_for_settings() -> tuple[str, str | None]:
    """(endpoint, api_key). Empty endpoint means Comfy Cloud via its API."""
    s = load_settings()
    url = (s.get("comfy_endpoint") or "").rstrip("/")
    if not url:
        return "https://cloud.comfy.org/api", comfy_key() or None
    return url, None


def run_template_job(job_id: str, template: str) -> None:
    job = _jobs[job_id]
    endpoint, api_key = endpoint_for_settings()
    log = WORK / "templates.log"
    try:
        import urllib.request
        with urllib.request.urlopen(comfy_runner_template_url(template), timeout=60) as resp:
            graph = json.loads(resp.read())
        job["stage"] = "converting"
        save_jobs()

        info = comfy_runner.object_info(endpoint, api_key)
        flat, expand_warnings = comfy_runner.expand_subgraphs(graph)
        api, warnings = comfy_runner.convert_ui_to_api(flat, info)
        problems = comfy_runner.missing_prompt_inputs(api, flat, info)
        if problems:
            job["state"] = "error"
            job["error"] = "conversion left required inputs unconnected: " + "; ".join(problems[:3])
            job["finished"] = int(time.time() * 1000)
            save_jobs()
            return

        job["nodes"] = len(api)
        job["warnings"] = (expand_warnings + warnings)[:6]
        job["stage"] = f"running {len(api)} nodes on {endpoint}"
        save_jobs()

        pid = comfy_runner.queue_prompt(endpoint, api, api_key=api_key)
        job["prompt_id"] = pid
        save_jobs()

        cloud = "cloud.comfy.org" in endpoint
        history = comfy_runner.wait_for_history(endpoint, pid, api_key=api_key,
                                                timeout=VIDEO_TIMEOUT, cloud_jobs=cloud)
        if history.get("status") not in (None, "completed"):
            job["state"] = "error"
            job["error"] = json.dumps(history)[:500]
        else:
            files = comfy_runner.output_files(history)
            if not files:
                job["state"] = "error"
                job["error"] = "the run completed but produced no files"
            else:
                RUNS.mkdir(parents=True, exist_ok=True)
                dest = RUNS / f"{int(time.time())}-{job_id[:6]}-{template}.png"
                size = comfy_runner.download(endpoint, files[0], str(dest), api_key=api_key)
                if size < 5000:
                    job["state"] = "error"
                    job["error"] = f"output was only {size} bytes"
                else:
                    job["state"] = "done"
                    job["file"] = dest.name
                    job["bytes"] = size
                    job["url"] = publish(dest, f"TEMPLATE · {template} ({len(api)} nodes)")
                    job.pop("stage", None)
        with log.open("a") as fh:
            fh.write(f"\n=== {time.strftime('%H:%M:%S')} {template} on {endpoint}\n"
                     f"nodes={len(api)} state={job['state']} pid={pid}\n")
    except Exception as exc:
        job["state"] = "error"
        job["error"] = f"{type(exc).__name__}: {str(exc)[:400]}"
    job.pop("stage", None)
    job["finished"] = int(time.time() * 1000)
    save_jobs()


def comfy_runner_template_url(name: str) -> str:
    return TEMPLATE_JSON.format(name=name)


@app.post("/api/comfy/run")
async def api_comfy_run(payload: dict = Body(...),
                        x_hud_key: str | None = Header(default=None)) -> dict:
    """Run one official template on the configured endpoint."""
    require_key(x_hud_key)
    name = (payload.get("template") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_\-]{1,80}", name):
        raise HTTPException(status_code=400, detail="bad template name")
    endpoint, _ = endpoint_for_settings()
    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {"id": job_id, "model": name, "category": "template", "prompt": f"{name} on {endpoint}",
                     "state": "running", "price": 0, "stage": "fetching template",
                     "at": int(time.time() * 1000)}
    save_jobs()
    _pool.submit(run_template_job, job_id, name)
    return {"job": _jobs[job_id], "endpoint": endpoint}


# --------------------------------------------------------------------------- template library
#
# The whole official Comfy template catalogue, straight from Comfy-Org/workflow_templates.
# Listing is cached; the per-template workflow JSON is fetched on demand so opening one is fresh.

TEMPLATES_URL = ("https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/"
                 "templates/index.json")
TEMPLATE_JSON = ("https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/"
                 "templates/{name}.json")
_tpl_cache: dict | None = None


@app.get("/api/templates")
async def api_templates(q: str = "", limit: int = 400, refresh: bool = False,
                        x_hud_key: str | None = Header(default=None)) -> dict:
    require_key(x_hud_key)
    global _tpl_cache
    if _tpl_cache is None or refresh:
        import urllib.request
        try:
            with urllib.request.urlopen(TEMPLATES_URL, timeout=60) as resp:
                raw = json.loads(resp.read())
        except Exception as exc:
            raise HTTPException(status_code=502,
                                detail=f"could not fetch the template index: {exc}"[:180])
        flat = []
        for group in raw if isinstance(raw, list) else []:
            cat = group.get("category") or group.get("title") or "Other"
            sub = group.get("title") or ""
            for t in group.get("templates") or []:
                name = t.get("name")
                if not name:
                    continue
                flat.append({
                    "name": name,
                    "title": t.get("title") or name,
                    "category": cat,
                    "group": sub,
                    "media": t.get("mediaType") or "",
                    "description": (t.get("description") or "")[:400],
                    "tags": (t.get("tags") or [])[:8],
                    "models": (t.get("models") or [])[:8],
                    "tutorial": t.get("tutorialUrl") or "",
                    "date": t.get("date") or "",
                    "json_url": TEMPLATE_JSON.format(name=name),
                })
        _tpl_cache = {"templates": flat, "count": len(flat),
                      "categories": sorted({t["category"] for t in flat})}
    items = _tpl_cache["templates"]
    if q:
        ql = q.lower()
        items = [t for t in items if ql in (t["name"] + t["title"] + t["description"]
                                            + " ".join(t["tags"])).lower()]
    return {**_tpl_cache, "templates": items[:limit], "shown": len(items[:limit])}


@app.get("/api/templates/json")
async def api_template_json(name: str, x_hud_key: str | None = Header(default=None)) -> dict:
    require_key(x_hud_key)
    if not re.fullmatch(r"[A-Za-z0-9_\-]{1,80}", name or ""):
        raise HTTPException(status_code=400, detail="bad template name")
    import urllib.request
    try:
        with urllib.request.urlopen(TEMPLATE_JSON.format(name=name), timeout=45) as resp:
            return {"name": name, "workflow": json.loads(resp.read())}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"could not fetch {name}: {exc}"[:160])


@app.get("/api/mods")
async def api_mods(x_hud_key: str | None = Header(default=None)) -> dict:
    require_key(x_hud_key)
    return {"mods": mods_state()}


@app.get("/api/workflows")
async def api_workflows(x_hud_key: str | None = Header(default=None)) -> dict:
    require_key(x_hud_key)
    return {"workflows": load_workflows()}


@app.post("/api/workflows")
async def api_save_workflow(payload: dict = Body(...),
                            x_hud_key: str | None = Header(default=None)) -> dict:
    require_key(x_hud_key)
    wf = payload.get("workflow") or payload
    if not (wf.get("name") and wf.get("model") and wf.get("prompt")):
        raise HTTPException(status_code=400, detail="name, model and prompt are required")
    items = load_workflows()
    wf["id"] = wf.get("id") or "wf-" + uuid.uuid4().hex[:8]
    wf["builtin"] = False
    items = [w for w in items if w["id"] != wf["id"]] + [wf]
    save_workflows(items)
    return {"workflow": wf, "workflows": items}


@app.post("/api/workflows/delete")
async def api_delete_workflow(payload: dict = Body(...),
                              x_hud_key: str | None = Header(default=None)) -> dict:
    require_key(x_hud_key)
    wid = payload.get("id")
    items = [w for w in load_workflows() if w["id"] != wid]
    save_workflows(items)
    return {"workflows": items}


@app.post("/api/workflows/run")
async def api_run_workflow(payload: dict = Body(...),
                           x_hud_key: str | None = Header(default=None)) -> dict:
    require_key(x_hud_key)
    wf = next((w for w in load_workflows() if w["id"] == payload.get("id")), None)
    if wf is None:
        raise HTTPException(status_code=404, detail="no such workflow")
    subject = (payload.get("subject") or "").strip()
    prompt = wf["prompt"].replace("{subject}", subject) if subject else wf["prompt"]
    n = max(1, min(int(payload.get("n") or 1), MAX_BATCH))
    if wf.get("model", "").startswith("gpt-image"):
        # flare is MCP-only, so hand it to the agent and let it publish
        job_id = uuid.uuid4().hex[:12]
        _jobs[job_id] = {"id": job_id, "model": wf["model"], "category": "agent",
                         "prompt": prompt, "state": "running", "price": 0,
                         "at": int(time.time() * 1000)}
        save_jobs()
        _pool.submit(run_agent, job_id,
                     f"Generate an image with the {wf['model']} node for this brief: {prompt}. "
                     f"Then publish it to the JIMSKY stage with publish-media.py, captioning it "
                     f"'{wf['name']}'. Reply with just the filename.")
        return {"jobs": [_jobs[job_id]], "credits": load_credits()["balance"]}
    jobs = [submit(wf["model"], prompt, payload.get("image"), wf.get("params"),
                   f"{wf['name']} · {subject or wf['model']}") for _ in range(n)]
    return {"jobs": jobs, "credits": load_credits()["balance"]}


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "jobs": len(_jobs), "port": PORT}


@app.get("/api/catalog")
async def api_catalog(refresh: bool = False, x_hud_key: str | None = Header(default=None)) -> dict:
    require_key(x_hud_key)
    cat = catalog(refresh)
    return {**cat, "credits": load_credits()["balance"], "max_batch": MAX_BATCH}


@app.post("/api/create")
async def api_create(payload: dict = Body(...), x_hud_key: str | None = Header(default=None)) -> dict:
    require_key(x_hud_key)
    n = max(1, min(int(payload.get("n") or 1), MAX_BATCH))
    jobs = [submit(payload.get("model"), payload.get("prompt"), payload.get("image"),
                   payload.get("params"), payload.get("caption")) for _ in range(n)]
    return {"jobs": jobs, "credits": load_credits()["balance"]}


@app.get("/api/jobs")
async def api_jobs(limit: int = 40, x_hud_key: str | None = Header(default=None)) -> dict:
    require_key(x_hud_key)
    items = sorted(_jobs.values(), key=lambda j: j["at"], reverse=True)[:max(1, min(limit, 200))]
    return {"jobs": items, "credits": load_credits()["balance"]}


@app.post("/api/browse")
async def api_browse(payload: dict = Body(...), x_hud_key: str | None = Header(default=None)) -> dict:
    """Open a URL in a real browser and put what it looks like on the stage."""
    require_key(x_hud_key)
    url = (payload.get("url") or "").strip()
    if not re.match(r"^https?://", url):
        raise HTTPException(status_code=400, detail="url must start with http:// or https://")
    full = bool(payload.get("full_page"))
    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {"id": job_id, "model": "browser", "category": "browse", "prompt": url,
                     "state": "running", "price": 0, "at": int(time.time() * 1000)}
    save_jobs()
    _pool.submit(run_browse, job_id, url, full)
    return {"job": _jobs[job_id], "credits": load_credits()["balance"]}


def run_browse(job_id: str, url: str, full: bool) -> None:
    job = _jobs[job_id]
    RUNS.mkdir(parents=True, exist_ok=True)
    png = RUNS / f"{int(time.time())}-{job_id[:6]}.png"
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(url, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            page.screenshot(path=str(png), full_page=full)
            job["title"] = page.title()
            browser.close()
        job["state"] = "done"
        job["file"] = png.name
        job["bytes"] = png.stat().st_size
        job["url"] = publish(png, f"BROWSE · {job.get('title') or url}")
    except Exception as exc:
        job["state"] = "error"
        job["error"] = repr(exc)[:400]
    job["finished"] = int(time.time() * 1000)
    save_jobs()


@app.post("/api/agent")
async def api_agent(payload: dict = Body(...), x_hud_key: str | None = Header(default=None)) -> dict:
    """Hand a request to Hermes itself, for work only the agent can do (MCP only, e.g. the
    gpt-image flare node, saved workflows, batch submission)."""
    require_key(x_hud_key)
    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {"id": job_id, "model": "hermes", "category": "agent", "prompt": prompt,
                     "state": "running", "price": 0, "at": int(time.time() * 1000)}
    save_jobs()
    _pool.submit(run_agent, job_id, prompt)
    return {"job": _jobs[job_id], "credits": load_credits()["balance"]}


def run_agent(job_id: str, prompt: str) -> None:
    import logging
    job = _jobs[job_id]
    log = WORK / "agent.log"
    try:
        with log.open("a") as fh:
            fh.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} {job_id}\n{prompt}\n")
            proc = subprocess.run(
                ["hermes", "-z", prompt, "--profile", "jimsky"],
                capture_output=True, text=True, timeout=900, cwd=str(HOME))
            fh.write(proc.stdout[-4000:] + "\n" + proc.stderr[-2000:] + "\n")
        job["state"] = "done" if proc.returncode == 0 else "error"
        job["reply"] = (proc.stdout or "")[-1200:]
        if proc.returncode != 0:
            job["error"] = (proc.stderr or "")[-400:]
    except Exception as exc:
        job["state"] = "error"
        job["error"] = repr(exc)[:400]
    job["finished"] = int(time.time() * 1000)
    save_jobs()


@app.get("/api/credits")
async def api_credits(x_hud_key: str | None = Header(default=None)) -> dict:
    require_key(x_hud_key)
    data = load_credits()
    return {"balance": data["balance"], "spent": data["spent"], "redeemed": data["redeemed"]}


@app.post("/api/credits/redeem")
async def api_redeem(payload: dict = Body(...), x_hud_key: str | None = Header(default=None)) -> dict:
    require_key(x_hud_key)
    code = (payload.get("code") or "").strip().upper()
    amount = CHEAT_CODES.get(code)
    if not amount:
        raise HTTPException(status_code=404, detail="unknown code")
    with _lock:
        data = load_credits()
        if code in data["redeemed"]:
            raise HTTPException(status_code=409, detail="code already used")
        data["balance"] += amount
        data["redeemed"].append(code)
        data["history"].append({"at": int(time.time() * 1000), "delta": amount, "code": code})
        save_credits(data)
        return {"balance": data["balance"], "added": amount, "code": code}


@app.post("/api/say")
async def api_say(payload: dict = Body(...), x_hud_key: str | None = Header(default=None)) -> dict:
    """Typed text handed to the room's agent over the LiveKit data channel."""
    require_key(x_hud_key)
    return {"ok": False, "detail": "text is delivered by the front end over the LiveKit channel"}


# ---------------------------------------------------------------------------
# Model router
#
# One prompt, several brains, measured side by side. This exists because "which
# model should run this?" is the question the whole studio turns on: luna is the
# voice agent's own backend, deepseek-flash is the default workhorse, and the
# open-weights shelf is what we fall back to when a bill has to stay at zero.
#
# Every number returned here is measured at call time (latency from the clock,
# tokens from the response's own usage block). Cost is only reported when a real
# price is known, and the source of that price travels with it - an invented
# price is worse than a blank one.
# ---------------------------------------------------------------------------

ROUTER_MODELS = [
    {"id": "gpt-5.6-luna", "provider": "openai", "label": "GPT-5.6 LUNA",
     "tier": "frontier", "role": "voice agent brain",
     "note": "the model Vex runs on in GPT-Live full-duplex. our reference point."},
    {"id": "gpt-5.6-sol", "provider": "openai", "label": "GPT-5.6 SOL",
     "tier": "frontier", "role": "deep reasoning", "note": "heavier sibling of luna."},
    {"id": "gpt-5.5", "provider": "openai", "label": "GPT-5.5",
     "tier": "frontier", "role": "general", "note": "previous generation, still strong."},
    {"id": "deepseek-v4-pro", "provider": "deepseek", "label": "DEEPSEEK V4 PRO",
     "tier": "frontier", "role": "reasoning, cheap frontier",
     "note": "near-frontier output at a fraction of the price."},
    {"id": "deepseek-flash", "provider": "deepseek", "label": "DEEPSEEK FLASH",
     "tier": "fast", "role": "default workhorse",
     "note": "Hermes' own default brain. fast, cheap, good enough for most turns."},
    {"id": "z-ai/glm-5.3-flash", "provider": "openrouter", "label": "GLM 5.3 FLASH",
     "tier": "fast", "role": "bulk tasks",
     "note": "1.3M context. the cron-pinned model - costs almost nothing per call."},
    {"id": "qwen/qwen3.8-flash", "provider": "openrouter", "label": "QWEN 3.8 FLASH",
     "tier": "fast", "role": "bulk + long context", "note": "1M context, very cheap."},
    {"id": "qwen/qwen3.8-max-0902", "provider": "openrouter", "label": "QWEN 3.8 MAX",
     "tier": "open", "role": "open weights, near-frontier",
     "note": "open-weights flagship. the honest test of 'do we still need closed models'."},
    {"id": "deepseek/deepseek-v4-flash-vision-exp", "provider": "openrouter", "label": "DEEPSEEK V4 FLASH VISION",
     "tier": "open", "role": "open weights + vision",
     "note": "sees images. useful for judging our own renders."},
    {"id": "~z-ai/glm-flash-latest", "provider": "openrouter", "label": "GLM FLASH (latest)",
     "tier": "open", "role": "open weights, cheapest", "note": "1.3M context for pennies."},
]

SELF_HOSTED = [
    {"id": "ollama:2nx1xa9cjnvx6i", "label": "OLLAMA pod A",
     "url": "https://2nx1xa9cjnvx6i-11434.proxy.runpod.net", "status": "offline",
     "note": "RunPod Ollama proxy answered 403 - pod down. this is where a fully private model runs."},
    {"id": "ollama:j3uippxqcaw6iy", "label": "OLLAMA pod B",
     "url": "https://j3uippxqcaw6iy-11434.proxy.runpod.net", "status": "offline",
     "note": "same - 403. reviving one pod puts open weights on our own silicon."},
]

_OR_PRICES: dict | None = None


def provider_key(name: str) -> str:
    """Read a provider key from the environment or the profile env files. Never returned to clients."""
    key = os.environ.get(name)
    if key:
        return key
    for path in (HOME / ".hermes/profiles/jimsky/.env", HOME / ".hermes/.env"):
        try:
            for line in path.read_text().splitlines():
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            continue
    return ""


def openrouter_prices() -> dict:
    """Live per-token prices from OpenRouter, used as the cost source of record."""
    global _OR_PRICES
    if _OR_PRICES is not None:
        return _OR_PRICES
    out: dict = {}
    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {provider_key('OPENROUTER_API_KEY')}"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            for m in json.loads(resp.read().decode()).get("data", []):
                p = m.get("pricing") or {}
                try:
                    out[m["id"]] = {"prompt": float(p.get("prompt") or 0),
                                    "completion": float(p.get("completion") or 0),
                                    "ctx": m.get("context_length")}
                except (TypeError, ValueError):
                    continue
    except Exception:
        out = {}
    _OR_PRICES = out
    return out


def price_for(model_id: str) -> tuple[dict | None, str]:
    """(price, source). Honest about where a number came from; no guess is published as fact."""
    prices = openrouter_prices()
    if model_id in prices:
        return prices[model_id], f"openrouter listing: {model_id}"
    if model_id.startswith("openrouter:"):
        return None, "unpublished"
    # cloud ids: use the closest listed variant and SAY it is an approximation
    for cand, note in ((f"openai/{model_id}", "exact listing"),
                       (f"openai/{model_id}-pro", "approximation: OpenRouter lists the -pro variant")):
        if cand in prices:
            return prices[cand], note
    return None, "unpublished"


def call_model(entry: dict, prompt: str, max_tokens: int = 400, temperature: float = 0.7) -> dict:
    """One real completion. Errors are returned as data, never raised at the caller."""
    provider = entry["provider"]
    model = entry["id"]
    if provider == "openai":
        url, key = "https://api.openai.com/v1/chat/completions", provider_key("OPENAI_API_KEY")
        body = {"model": model, "messages": [{"role": "user", "content": prompt}],
                "max_completion_tokens": max_tokens}
    elif provider == "deepseek":
        url, key = "https://api.deepseek.com/v1/chat/completions", provider_key("DEEPSEEK_API_KEY")
        body = {"model": model, "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens, "temperature": temperature}
    else:
        url, key = "https://openrouter.ai/api/v1/chat/completions", provider_key("OPENROUTER_API_KEY")
        body = {"model": model, "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens, "temperature": temperature}

    result = {"id": model, "provider": provider, "label": entry.get("label", model),
              "ok": False, "text": "", "latency_ms": None, "tokens_in": None,
              "tokens_out": None, "cost_usd": None, "price_source": "unpublished", "error": None}
    if not key:
        result["error"] = f"no {provider.upper()} key in this profile"
        return result

    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode())
        result["latency_ms"] = round((time.time() - t0) * 1000)
        choice = (payload.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        result["text"] = (msg.get("content") or "") or (choice.get("text") or "")
        # reasoning models fill the completion budget with thinking first, and some
        # return the visible answer in a separate field. Do not report that as empty.
        if not result["text"]:
            for alt in ("reasoning_content", "reasoning"):
                if msg.get(alt):
                    result["text"] = msg[alt]
                    result["from_reasoning"] = True
                    break
        usage = payload.get("usage") or {}
        result["tokens_in"] = usage.get("prompt_tokens")
        result["tokens_out"] = usage.get("completion_tokens")
        finish = choice.get("finish_reason")
        result["finish_reason"] = finish
        result["ok"] = bool(result["text"])
        if not result["ok"]:
            result["error"] = (f"empty text (finish_reason={finish}, "
                               f"{result['tokens_out']} completion tokens) — reasoning models "
                               f"spend the cap on thinking; raise max_tokens")
        elif finish == "length":
            result["truncated"] = True
        price, source = price_for(model)
        result["price_source"] = source
        if price and result["tokens_in"] is not None and result["tokens_out"] is not None:
            result["cost_usd"] = round(
                result["tokens_in"] * price["prompt"] + result["tokens_out"] * price["completion"], 8)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:220]
        result["error"] = f"HTTP {e.code}: {detail}"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {str(e)[:180]}"
    return result


@app.get("/api/router/models")
async def api_router_models(x_hud_key: str | None = Header(default=None)) -> dict:
    """Every brain the router can reach, with who it is and what it costs."""
    require_key(x_hud_key)
    prices = openrouter_prices()
    models = []
    for m in ROUTER_MODELS:
        price, source = price_for(m["id"])
        models.append({**m, "key_present": bool(provider_key(
            {"openai": "OPENAI_API_KEY", "deepseek": "DEEPSEEK_API_KEY",
             "openrouter": "OPENROUTER_API_KEY"}[m["provider"]])),
            "price_per_mtok_in": (round(price["prompt"] * 1_000_000, 4) if price else None),
            "price_per_mtok_out": (round(price["completion"] * 1_000_000, 4) if price else None),
            "price_source": source,
            "context": (price or {}).get("ctx")})
    free = [{"id": k, "label": k, "provider": "openrouter", "tier": "free",
             "role": "zero-cost testing", "note": "OpenRouter lists it at $0/token.",
             "price_per_mtok_in": 0.0, "price_per_mtok_out": 0.0,
             "price_source": f"openrouter listing: {k}", "context": v.get("ctx")}
            for k, v in prices.items()
            if v["prompt"] == 0 and v["completion"] == 0 and ":batch" not in k][:12]
    return {"ok": True, "models": models, "free": free, "self_hosted": SELF_HOSTED,
            "counts": {"cloud": len(models), "free": len(free), "self_hosted": len(SELF_HOSTED)}}


@app.post("/api/router/compare")
async def api_router_compare(payload: dict = Body(...),
                             x_hud_key: str | None = Header(default=None)) -> dict:
    """Run ONE prompt through several models at once and report what actually happened."""
    require_key(x_hud_key)
    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    wanted = [m for m in (payload.get("models") or []) if isinstance(m, str)][:4]
    if not wanted:
        raise HTTPException(status_code=400, detail="pick at least one model")
    by_id = {m["id"]: m for m in ROUTER_MODELS}
    if (prices := openrouter_prices()):
        for k in prices:
            by_id.setdefault(k, {"id": k, "provider": "openrouter", "label": k, "tier": "free",
                                 "role": "zero-cost testing", "note": "OpenRouter $0 model."})
    entries = [by_id[m] for m in wanted if m in by_id]
    if not entries:
        raise HTTPException(status_code=400, detail="no known model in that list")
    max_tokens = int(payload.get("max_tokens") or 900)
    temperature = float(payload.get("temperature") or 0.7)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=len(entries)) as pool:
        futures = [pool.submit(call_model, e, prompt, max_tokens, temperature) for e in entries]
        results = [f.result() for f in futures]
    return {"ok": True, "prompt": prompt, "results": results,
            "wall_ms": round((time.time() - t0) * 1000),
            "total_cost_usd": round(sum(r["cost_usd"] or 0 for r in results), 8),
            "cost_known": all(r["cost_usd"] is not None for r in results)}


if __name__ == "__main__":
    import uvicorn
    load_jobs()
    WORK.mkdir(parents=True, exist_ok=True)
    print(f"[hud] JIMSKY HUD on 127.0.0.1:{PORT} | {len(_jobs)} jobs loaded | "
          f"key from profile env", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
