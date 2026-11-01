import asyncio
import os
from playwright.async_api import async_playwright

ARTIFACT_DIR = "/Users/arnavbansal/.gemini/antigravity/brain/e36f816b-4f83-4473-bafe-eaf910d709c8"

async def run_audit():
    print("=== Starting Playwright End-to-End Browser Audit ===")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        page.on("console", lambda msg: print(f"BROWSER LOG: [{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: print(f"BROWSER ERROR: {err}"))

        # 1. Login Page
        print("1. Navigating to http://127.0.0.1:8005/login...")
        await page.goto("http://127.0.0.1:8005/login", wait_until="networkidle")
        await page.screenshot(path=os.path.join(ARTIFACT_DIR, "pw_1_login.png"))

        # Fill credentials
        print("   Filling credentials: username=admin, password=password123")
        await page.fill('input[type="text"]', "admin")
        await page.fill('input[type="password"]', "password123")
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(2500)
        print(f"   Current URL after login: {page.url}")
        await page.screenshot(path=os.path.join(ARTIFACT_DIR, "pw_after_login.png"))

        # 2. Check Dashboard
        if "/dashboard" not in page.url:
            print("   Navigating explicitly to /dashboard...")
            await page.goto("http://127.0.0.1:8005/dashboard", wait_until="networkidle")
            await page.wait_for_timeout(1500)

        await page.screenshot(path=os.path.join(ARTIFACT_DIR, "pw_2_dashboard.png"))
        print(f"   Dashboard URL: {page.url}")

        # 3. Ring Explorer
        print("3. Navigating to Ring Explorer...")
        await page.goto("http://127.0.0.1:8005/rings?account=1&hops=1", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        await page.screenshot(path=os.path.join(ARTIFACT_DIR, "pw_3_ring_explorer.png"))
        print("   Saved Ring Explorer screenshot.")

        # Test Zoom & Center View
        print("   Testing Ring Explorer controls...")
        zoom_in_btn = page.locator('button[title="Zoom In"]')
        if await zoom_in_btn.count() > 0:
            await zoom_in_btn.click()
            await page.wait_for_timeout(400)
            await zoom_in_btn.click()
            await page.wait_for_timeout(400)

        center_btn = page.locator('button[title*="Center View"]')
        if await center_btn.count() > 0:
            await center_btn.click()
            await page.wait_for_timeout(600)
        await page.screenshot(path=os.path.join(ARTIFACT_DIR, "pw_3_ring_centered.png"))
        print("   Saved Ring Explorer centered screenshot.")

        # 4. Alert Queue
        print("4. Navigating to Alert Queue...")
        await page.goto("http://127.0.0.1:8005/alerts", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        await page.screenshot(path=os.path.join(ARTIFACT_DIR, "pw_4_alert_queue.png"))
        print("   Saved Alert Queue screenshot.")

        # 5. Add & Upload CSV (Score Transaction)
        print("5. Navigating to Score Transaction...")
        await page.goto("http://127.0.0.1:8005/score?tab=single", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=os.path.join(ARTIFACT_DIR, "pw_5_score_single.png"))

        print("   Testing Upload CSV tab...")
        await page.goto("http://127.0.0.1:8005/score?tab=batch", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=os.path.join(ARTIFACT_DIR, "pw_5_score_batch.png"))

        print("   Testing Company Ledger History tab...")
        await page.goto("http://127.0.0.1:8005/score?tab=history", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=os.path.join(ARTIFACT_DIR, "pw_5_score_history.png"))
        print("   Saved Score Transaction tabs screenshots.")

        print("=== Playwright Audit Completed Successfully! ===")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_audit())
