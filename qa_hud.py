"""Drive the JIMSKY HUD in a real browser: three screen sizes, a real generation, a real browse.

The HUD key is injected into localStorage before any script runs, which is exactly how a human
would supply it once - it never needs to appear in the page source.
"""
import sys
import time
from playwright.sync_api import sync_playwright

URL = "https://jimsky-voice.netlify.app"
KEY = None
for line in open("/home/ubuntu/.hermes/profiles/jimsky/.env"):
    if line.startswith("JIMSKY_HUD_KEY="):
        KEY = line.split("=", 1)[1].strip()
if not KEY:
    sys.exit("no HUD key in the profile env")

VIEWPORTS = [
    ("desktop", 1440, 900),
    ("ipad", 834, 1112),
    ("phone", 390, 844),
]

with sync_playwright() as pw:
    browser = pw.chromium.launch(args=["--no-sandbox"])
    failures = []

    for name, w, h in VIEWPORTS:
        ctx = browser.new_context(viewport={"width": w, "height": h})
        ctx.add_init_script(f"window.localStorage.setItem('jimsky.hud.key', {KEY!r})")
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1200)
        page.locator("nav.tabs button", has_text="STUDIO").click()
        page.wait_for_timeout(3500)

        models = page.locator(".chipmodel").count()
        templates = page.locator(".tchip").count()
        credits = page.locator(".credits b").inner_text() if page.locator(".credits b").count() else "?"
        create_visible = page.locator("button.cta.grow").count() > 0
        print(f"[{name} {w}x{h}] models={models} templates={templates} credits={credits} "
              f"create_button={create_visible} errors={len(errors)}")
        page.screenshot(path=f"/tmp/hud_{name}.png", full_page=False)
        if models < 40:
            failures.append(f"{name}: only {models} models rendered")
        if not create_visible:
            failures.append(f"{name}: create button missing")
        ctx.close()

    # --- real generation through the UI, at phone size (the tightest layout) ---
    ctx = browser.new_context(viewport={"width": 390, "height": 844})
    ctx.add_init_script(f"window.localStorage.setItem('jimsky.hud.key', {KEY!r})")
    page = ctx.new_page()
    page.goto(URL, wait_until="networkidle", timeout=60000)
    page.locator("nav.tabs button", has_text="STUDIO").click()
    page.wait_for_timeout(3000)

    page.locator(".tchip", has_text="Neon portrait").click()
    page.wait_for_timeout(400)
    ta = page.locator("textarea").first
    ta.fill("JIMSKY leaning on a rain-soaked neon sign, teal and magenta, cinematic, no text")
    print("[phone] prompt filled from template:", ta.input_value()[:48], "...")
    page.locator("button.cta.grow").click()
    print("[phone] CREATE clicked - waiting for the job to finish")

    done = False
    start = time.time()
    while time.time() - start < 200:
        page.wait_for_timeout(4000)
        states = [page.locator(".job").nth(i).get_attribute("class") for i in range(page.locator(".job").count())]
        if any("done" in (s or "") for s in states):
            done = True
            break
        if any("error" in (s or "") for s in states):
            err = page.locator(".jerr").first.inner_text() if page.locator(".jerr").count() else "?"
            failures.append(f"generation errored: {err[:120]}")
            break
    print(f"[phone] generation done={done} after {round(time.time()-start)}s")
    page.screenshot(path="/tmp/hud_created.png")

    if done:
        page.locator(".jlink").first.click()
        page.wait_for_timeout(2500)
        shown = page.locator(".preview img").count() > 0
        print("[phone] 'show on stage' opened preview:", shown)
        if not shown:
            failures.append("preview did not open")
        page.screenshot(path="/tmp/hud_preview.png")

    # --- browse a real page (dismiss the preview first, as a human would) ---
    page.keyboard.press("Escape")
    page.wait_for_timeout(600)
    page.locator(".browsebox input").first.fill("https://huggingface.co/datasets/TheMindExpansionNetwork")
    page.locator(".browsebox button").first.click()
    print("[phone] opened a real browser page via the HUD")
    page.wait_for_timeout(20000)
    page.screenshot(path="/tmp/hud_browse.png")
    jobs = page.locator(".job").count()
    print("[phone] jobs listed after browse:", jobs)

    ctx.close()
    browser.close()

print("FAILURES:", failures or "none")
sys.exit(1 if failures else 0)
