"""Live front-end check: load the deployed app, connect with a fake mic, and prove the stage
renders media that Hermes published. Run with the venv that has playwright installed."""
import sys
from playwright.sync_api import sync_playwright

URL = "https://jimsky-voice.netlify.app"
SHOTS = []

with sync_playwright() as pw:
    browser = pw.chromium.launch(args=[
        "--use-fake-ui-for-media-stream",      # auto-grant mic
        "--use-fake-device-for-media-stream",  # synthetic audio input
        "--autoplay-policy=no-user-gesture-required",
        "--no-sandbox",
    ])
    ctx = browser.new_context(permissions=["microphone"], viewport={"width": 1600, "height": 950})
    page = ctx.new_page()

    errors, requests = [], []
    page.on("console", lambda m: errors.append(f"{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("response", lambda r: requests.append((r.status, r.url)) if "/api/token" in r.url or "index.json" in r.url else None)

    page.goto(URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(1500)
    page.screenshot(path="/tmp/jv_1_gate.png")
    SHOTS.append("/tmp/jv_1_gate.png")
    print("[1] gate loaded — title:", page.title())
    print("    wordmark present:", page.locator("h1", has_text="JIMSKY").count() > 0)
    print("    cta:", page.locator("button.cta").inner_text().strip())

    # connect
    page.locator("button.cta").click()
    page.wait_for_timeout(9000)
    page.screenshot(path="/tmp/jv_2_room.png")
    SHOTS.append("/tmp/jv_2_room.png")

    hud = page.locator("header.hud")
    print("[2] in room:", hud.count() > 0)
    if hud.count():
        print("    hud text:", " | ".join(hud.inner_text().split("\n"))[:150])
    chips = page.locator(".chip")
    print("    chips:", [chips.nth(i).inner_text() for i in range(chips.count())])
    print("    mic pill:", page.locator("button.pill").inner_text().strip())
    print("    peers readout:", page.locator(".peers").inner_text().strip() if page.locator(".peers").count() else "n/a")

    # the published media should have arrived via the poll
    page.wait_for_timeout(5000)
    hero = page.locator(".hero img")
    thumbs = page.locator(".thumb")
    print("[3] stage: hero images =", hero.count(), "| thumbs =", thumbs.count())
    if hero.count():
        src = hero.first.get_attribute("src")
        print("    hero src:", (src or "")[:78])
        print("    from media host:", "jimsky-media" in (src or ""))
    cap = page.locator(".hero-cap")
    print("    caption line:", cap.inner_text().replace("\n", " ")[:110] if cap.count() else "n/a")

    # log lines prove the client did real work
    logs = page.locator(".logline")
    print("[4] control log:")
    for i in range(min(logs.count(), 8)):
        print("      ", logs.nth(i).inner_text())

    print("[5] errors:", errors[:6] if errors else "none")
    print("[6] network:", requests[:5])
    page.screenshot(path="/tmp/jv_3_final.png", full_page=True)
    SHOTS.append("/tmp/jv_3_final.png")

    # prove the type-to-send path wires up (no agent needed for the UI path itself)
    box = page.locator(".typebox input")
    if box.count():
        box.fill("stage test from playwright")
        page.locator(".typebox button").click()
        page.wait_for_timeout(1500)
        logs2 = [page.locator(".logline").nth(i).inner_text() for i in range(page.locator(".logline").count())]
        print("[7] text send logged:", any("text sent" in l or "text send failed" in l for l in logs2))

    ctx.close()
    browser.close()

print("shots:", SHOTS)
