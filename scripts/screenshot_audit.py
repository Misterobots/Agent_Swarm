"""
Screenshot audit of Hive Mind UI pages.
Uses Playwright to capture each section.
"""
import os
import sys
from playwright.sync_api import sync_playwright

SITE = os.environ.get("HIVE_URL", "https://hive.shivelymedia.com")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "screenshots")
os.makedirs(OUT_DIR, exist_ok=True)

PAGES = [
    ("home", "/"),
    ("chat", "/chat"),
    ("media", "/media"),
    ("developer", "/developer"),
    ("settings", "/settings"),
    ("monitoring", "/monitoring"),
    ("training", "/training"),
    ("operations", "/operations"),
    ("governance", "/governance"),
]

def authentik_login(page, username, password):
    """Handle Authentik multi-step login flow."""
    print("  Logging in to Authentik...")
    # Step 1: Enter username
    page.fill('input[name="uidField"], input[placeholder*="Email or Username"]', username)
    page.click('button:has-text("Log in"), button[type="submit"]')
    import time; time.sleep(2)

    # Step 2: Enter password (Authentik shows password on second step)
    try:
        page.fill('input[name="password"], input[type="password"]', password, timeout=5000)
        page.click('button:has-text("Continue"), button:has-text("Log in"), button[type="submit"]')
        import time; time.sleep(3)
    except Exception as e:
        print(f"  Password step: {e}")

    # Wait for redirect back to Hive
    page.wait_for_url(f"{SITE}/**", timeout=15000)
    print(f"  Logged in! Now at: {page.url}")

def run():
    username = os.environ.get("AUTH_USER", "")
    password = os.environ.get("AUTH_PASS", "")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
        )
        page = context.new_page()

        # First load — may redirect to Authentik login
        print(f"Loading {SITE} ...")
        page.goto(SITE, wait_until="networkidle", timeout=30000)
        current = page.url
        print(f"  Landed on: {current}")

        # If redirected to Authentik, log in
        if "auth." in current or "authentik" in current.lower():
            path = os.path.join(OUT_DIR, "00_authentik_login.png")
            page.screenshot(path=path, full_page=True)
            print(f"  Saved: {path}")

            if username and password:
                authentik_login(page, username, password)
            else:
                print("\n⚠️  Authentik login required. Set AUTH_USER and AUTH_PASS env vars.")
                browser.close()
                return

        # Take screenshots of each page
        for name, route in PAGES:
            url = f"{SITE}{route}"
            print(f"\n[{name}] {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                print(f"  ⚠️  Navigation error: {e}")
            
            # Wait for client-side rendering
            import time
            time.sleep(3)

            path = os.path.join(OUT_DIR, f"{name}.png")
            try:
                page.screenshot(path=path, full_page=False)
                print(f"  Saved: {path}")
            except Exception as e:
                print(f"  ⚠️  Screenshot error: {e}")

            final_url = page.url
            if final_url != url:
                print(f"  Redirected to: {final_url}")

        # Sidebar-specific screenshot (narrow crop)
        print("\n[sidebar] Capturing sidebar...")
        try:
            page.goto(f"{SITE}/chat", wait_until="domcontentloaded", timeout=30000)
            import time; time.sleep(3)
            sidebar = page.query_selector('[class*="sidebar"]')
            if sidebar:
                path = os.path.join(OUT_DIR, "sidebar.png")
                sidebar.screenshot(path=path)
                print(f"  Saved: {path}")
            else:
                print("  ⚠️  Sidebar element not found")
        except Exception as e:
            print(f"  ⚠️  Sidebar error: {e}")

        browser.close()
        print(f"\n✅ Screenshots saved to {OUT_DIR}")

if __name__ == "__main__":
    run()
