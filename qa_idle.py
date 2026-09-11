"""Prove the idle failsafe: connect, say nothing, and confirm the call hangs itself up.

Agent side and client side both enforce a timeout; either one ending the session must return the
UI to the connect gate. Run against the deployed app with ?idle= to shorten the client timer.
"""
import re
import sys
import time
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://jimsky-voice.netlify.app/?idle=45"
DEADLINE = 110  # seconds to wait for the auto-hangup

with sync_playwright() as pw:
    browser = pw.chromium.launch(args=[
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
        "--autoplay-policy=no-user-gesture-required",
        "--no-sandbox",
    ])
    ctx = browser.new_context(permissions=["microphone"], viewport={"width": 1500, "height": 900})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.goto(URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(1200)
    page.locator("button.cta").click()
    print("[1] connected, now staying quiet on purpose")

    # let it connect and settle (the greeting counts as activity)
    page.wait_for_timeout(9000)
    in_room = page.locator("header.hud").count() == 1
    print("    in room:", in_room)

    saw_countdown, countdown_text = False, None
    hung_up_at, gate_back = None, False
    start = time.time()

    while time.time() - start < DEADLINE:
        # countdown chip?
        chip = page.locator(".chip.idle-warn")
        if chip.count() and not saw_countdown:
            saw_countdown = True
            countdown_text = chip.first.inner_text()
            print(f"    [t+{int(time.time()-start)}s] countdown visible: {countdown_text}")
            page.screenshot(path="/tmp/idle_1_countdown.png")
        # back at the gate?
        if page.locator("button.cta").count() and page.locator("header.hud").count() == 0:
            gate_back = True
            hung_up_at = time.time() - start
            print(f"    [t+{int(hung_up_at)}s] disconnected - back at the connect gate")
            break
        page.wait_for_timeout(1000)

    page.screenshot(path="/tmp/idle_2_after.png")

    # read the control log from the last session if it is still rendered anywhere
    print("[2] result:")
    print("    countdown shown:", saw_countdown, "|", countdown_text)
    print("    auto-hung up:", gate_back, "| after", round(hung_up_at, 1) if hung_up_at else "-", "s")
    print("    page errors:", errors[:3] or "none")

    # confirm the gate is functional again (a real disconnect, not a wedged UI)
    if gate_back:
        print("    gate still usable:", page.locator("button.cta").inner_text().strip())

    ctx.close()
    browser.close()

sys.exit(0 if gate_back else 1)
