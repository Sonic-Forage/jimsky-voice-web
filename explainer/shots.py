#!/usr/bin/env python3
"""Screenshot pass for the JIMSKY front end.

Drives the DEPLOYED site (not a dev server) with the HUD key injected into localStorage,
walks every screen at desktop and phone widths, and runs one real model comparison so the
capture shows measured numbers rather than a mockup.

    HUDKEY=... python3 shots.py [outdir]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("SITE", "https://jimsky-voice.netlify.app")
KEY = os.environ.get("HUDKEY", "")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/home/ubuntu/sf-ops/jimsky-voice/shots")
OUT.mkdir(parents=True, exist_ok=True)

DESKTOP = {"width": 1440, "height": 940}
PHONE = {"width": 390, "height": 844}

errors: list[str] = []
shots: list[str] = []


def shot(page, name: str) -> None:
    p = OUT / f"{name}.png"
    page.screenshot(path=str(p), full_page=False)
    shots.append(name)
    print(f"  shot {name}.png  ({p.stat().st_size // 1024} KB)")


def tab(page, label: str) -> None:
    page.get_by_role("button", name=label, exact=True).first.click()
    page.wait_for_timeout(1200)
    if label == "MODELS":
        # the router list is fetched async: waiting a fixed 1.2s captured an empty screen
        page.wait_for_selector(".rt-card", timeout=45000)
        page.wait_for_timeout(700)


def walk(page, suffix: str) -> None:
    for label, name in (("VOICE", "01-voice"), ("STUDIO", "02-studio"),
                        ("MODELS", "03-models"), ("CONFIG", "05-config")):
        tab(page, label)
        shot(page, f"{name}{suffix}")


with sync_playwright() as pw:
    browser = pw.chromium.launch(args=["--no-sandbox"])
    ctx = browser.new_context(viewport=DESKTOP, device_scale_factor=2)
    ctx.add_init_script(f"try{{localStorage.setItem('jimsky.hud.key', {KEY!r});}}catch(e){{}}")
    page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text[:150]}")
            if m.type == "error" else None)

    print(f"  loading {BASE}")
    page.goto(BASE, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2500)

    print("  desktop walk")
    walk(page, "")

    # the real comparison, through the deployed HUD, in the browser
    print("  running a live comparison in the UI (this takes ~20s)")
    tab(page, "MODELS")
    page.wait_for_timeout(1500)
    cards = page.locator(".rt-card")
    print(f"    router cards rendered: {cards.count()}")
    picked = page.locator(".rt-card.on").count()
    print(f"    pre-selected: {picked}")
    # add the open-weights contender so the capture tells the real story: closed vs open
    try:
        page.locator('.rt-card[title="qwen/qwen3.8-max-0902"]').first.click()
        page.wait_for_timeout(400)
        print(f"    picked after adding open-weights: {page.locator('.rt-card.on').count()}")
    except Exception as e:
        print(f"    could not add open-weights card: {type(e).__name__}")
    page.get_by_role("button", name="RUN COMPARISON").click()
    try:
        page.wait_for_selector(".rt-ans", timeout=120000)
        print("    results arrived")
    except Exception as e:
        print(f"    !! no results: {type(e).__name__}")
    page.wait_for_timeout(2000)
    answers = page.locator(".rt-ans").count()
    print(f"    answer panels: {answers}")
    shot(page, "04-compare")

    # record exactly what the screen shows, so any document built from these
    # screenshots quotes measured numbers instead of retyped ones
    import json as _json
    verdict = page.locator(".rt-verdict").first.inner_text()
    panels = []
    for i in range(answers):
        card = page.locator(".rt-ans").nth(i)
        panels.append({
            "label": card.locator(".chipmodel").first.inner_text().strip(),
            "id": card.locator(".tiny.muted").first.inner_text().strip(),
            "stats": " | ".join(card.locator(".rt-stats span").all_inner_texts()),
            "text": card.locator(".rt-anstext").first.inner_text().strip() if card.locator(".rt-anstext").count() else "",
            "warning": card.locator(".rt-warn").first.inner_text().strip() if card.locator(".rt-warn").count() else "",
        })
    payload = {"prompt": page.locator(".rt-compose textarea").first.input_value(),
               "verdict": verdict, "panels": panels}
    (OUT / "compare.json").write_text(_json.dumps(payload, indent=1))
    print(f"    recorded {len(panels)} panels -> compare.json")
    # the verdict block, tightly cropped, for the explainer
    try:
        page.locator(".rt-verdict").first.screenshot(path=str(OUT / "04b-verdict.png"))
        print("  shot 04b-verdict.png")
    except Exception as e:
        print(f"    verdict crop failed: {type(e).__name__}")

    # does the LIVE VOICE half still work after the change?
    tab(page, "VOICE")
    has_mic = page.locator("text=/CONNECT|JOIN|TALK/i").count()
    print(f"    voice screen interactive elements: {has_mic}")

    print("  phone walk")
    pctx = browser.new_context(viewport=PHONE, device_scale_factor=3, is_mobile=True)
    pctx.add_init_script(f"try{{localStorage.setItem('jimsky.hud.key', {KEY!r});}}catch(e){{}}")
    pp = pctx.new_page()
    pp.on("pageerror", lambda e: errors.append(f"phone pageerror: {e}"))
    pp.goto(BASE, wait_until="networkidle", timeout=60000)
    pp.wait_for_timeout(2500)
    walk(pp, "-phone")
    tab(pp, "MODELS")
    pp.wait_for_timeout(1500)
    shot(pp, "06-models-scroll-phone")
    pp.mouse.wheel(0, 900)
    pp.wait_for_timeout(900)
    shot(pp, "07-models-lower-phone")

    browser.close()

print(f"\n  {len(shots)} screenshots -> {OUT}")
print(f"  page errors: {len(errors)}")
for e in errors[:10]:
    print(f"    {e}")
