"""
GA Session Keeper - Keeps GA4 active users alive using real headless browsers
Uses Playwright to simulate real user browsing - shows up in GA4 Realtime
"""

import asyncio
import random
import os
import sys
import logging
import json
import time
from datetime import datetime

# CONFIG
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("ga_keeper")

# ── PAGES to browse ──────────────────────────────────────────────────────────
PAGES = [
    "/",
    "/about",
    "/blog",
    "/contact",
    "/pricing",
    "/faq",
]

# ── USER AGENTS ───────────────────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.71 Mobile Safari/537.36",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 390, "height": 844},   # iPhone
    {"width": 412, "height": 915},   # Android
]


def load_config() -> dict:
    cfg = {
        "target_url": os.environ.get("TARGET_URL", "https://coinsight.click"),
        "num_virtual_users": int(os.environ.get("NUM_VIRTUAL_USERS", "5")),
        "session_duration_min": int(os.environ.get("SESSION_DURATION_MIN", "120")),  # seconds per session
        "session_duration_max": int(os.environ.get("SESSION_DURATION_MAX", "300")),
        "page_stay_min": int(os.environ.get("PAGE_STAY_MIN", "20")),   # seconds per page
        "page_stay_max": int(os.environ.get("PAGE_STAY_MAX", "60")),
        "run_forever": os.environ.get("RUN_FOREVER", "false").lower() == "true",
        "run_duration_hours": float(os.environ.get("RUN_DURATION_HOURS", "5.5")),
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            file_cfg = json.load(f)
        for k, v in file_cfg.items():
            if k not in cfg or not cfg[k]:
                cfg[k] = v
    return cfg


async def simulate_user(browser_type, uid: int, cfg: dict):
    """One virtual user: browse the site for a session then restart"""
    from playwright.async_api import async_playwright

    ua = random.choice(USER_AGENTS)
    viewport = random.choice(VIEWPORTS)
    base_url = cfg["target_url"].rstrip("/")

    log.info(f"[User-{uid:02d}] START | {ua[:50]}...")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                ],
            )
            context = await browser.new_context(
                user_agent=ua,
                viewport=viewport,
                locale=random.choice(["vi-VN", "en-US", "en-GB"]),
                timezone_id=random.choice(["Asia/Ho_Chi_Minh", "America/New_York", "Europe/London"]),
                # Mask automation fingerprint
                java_script_enabled=True,
            )

            # Remove automation detection
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
                window.chrome = { runtime: {} };
            """)

            page = await context.new_page()
            session_end = time.time() + random.randint(
                cfg["session_duration_min"], cfg["session_duration_max"]
            )
            pages_visited = 0

            while time.time() < session_end:
                path = random.choice(PAGES)
                url = base_url + path
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    pages_visited += 1
                    log.info(f"[User-{uid:02d}] PAGE {pages_visited}: {url}")

                    stay = random.randint(cfg["page_stay_min"], cfg["page_stay_max"])

                    # Simulate reading: scroll slowly
                    for _ in range(stay // 5):
                        scroll_y = random.randint(100, 400)
                        await page.evaluate(f"window.scrollBy(0, {scroll_y})")
                        await asyncio.sleep(random.uniform(4, 7))

                    # Sometimes move mouse
                    try:
                        await page.mouse.move(
                            random.randint(100, viewport["width"] - 100),
                            random.randint(100, viewport["height"] - 100),
                        )
                    except Exception:
                        pass

                except Exception as e:
                    log.warning(f"[User-{uid:02d}] Page error: {e}")
                    await asyncio.sleep(5)

            await browser.close()
            log.info(f"[User-{uid:02d}] SESSION END | {pages_visited} pages visited")

    except Exception as e:
        log.error(f"[User-{uid:02d}] Fatal error: {e}")


async def run_user_loop(uid: int, cfg: dict, end_time: float):
    """Keep restarting sessions for one user until end_time"""
    session = 0
    while time.time() < end_time:
        session += 1
        log.info(f"[User-{uid:02d}] === Session {session} ===")
        await simulate_user(None, uid, cfg)
        # Short break between sessions
        await asyncio.sleep(random.uniform(5, 15))


async def main():
    log.info("=" * 60)
    log.info("  GA SESSION KEEPER - BROWSER MODE")
    log.info("=" * 60)

    cfg = load_config()

    log.info(f"Target URL     : {cfg['target_url']}")
    log.info(f"Virtual Users  : {cfg['num_virtual_users']}")
    log.info(f"Session time   : {cfg['session_duration_min']}-{cfg['session_duration_max']}s")
    log.info(f"Page stay      : {cfg['page_stay_min']}-{cfg['page_stay_max']}s")
    log.info(f"Run duration   : {cfg['run_duration_hours']} hours")

    end_time = time.time() + cfg["run_duration_hours"] * 3600

    # Run all virtual users concurrently
    tasks = [
        asyncio.create_task(run_user_loop(uid + 1, cfg, end_time))
        for uid in range(cfg["num_virtual_users"])
    ]

    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        log.info("[STOP] Interrupted by user.")
        for t in tasks:
            t.cancel()

    total = (time.time() - (end_time - cfg["run_duration_hours"] * 3600)) / 60
    log.info(f"[DONE] {total:.1f} minutes running")


if __name__ == "__main__":
    asyncio.run(main())
