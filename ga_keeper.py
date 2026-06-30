"""
GA Session Keeper - Browser mode with crash recovery
Runs 16 virtual users via Playwright headless Chromium
"""

import asyncio
import random
import os
import sys
import logging
import json
import time
from datetime import datetime

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("ga_keeper")

PAGES = [
    "/", "/about", "/blog", "/contact", "/pricing",
    "/faq", "/news", "/products", "/services", "/team",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.71 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1280, "height": 800},
    {"width": 390,  "height": 844},
    {"width": 412,  "height": 915},
    {"width": 768,  "height": 1024},
]


def load_config() -> dict:
    cfg = {
        "target_url":           os.environ.get("TARGET_URL", "https://coinsight.click"),
        "num_virtual_users":    int(os.environ.get("NUM_VIRTUAL_USERS", "4")),   # giảm users để bớt views/events
        "session_duration_min": int(os.environ.get("SESSION_DURATION_MIN", "120")),
        "session_duration_max": int(os.environ.get("SESSION_DURATION_MAX", "300")),
        "page_stay_min":        int(os.environ.get("PAGE_STAY_MIN", "20")),
        "page_stay_max":        int(os.environ.get("PAGE_STAY_MAX", "60")),
        "run_duration_hours":   float(os.environ.get("RUN_DURATION_HOURS", "5.5")),
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            for k, v in json.load(f).items():
                if k in cfg and not os.environ.get(k.upper()):
                    cfg[k] = v
    return cfg


async def one_session(playwright, uid: int, cfg: dict):
    """Run a single browser session for one virtual user."""
    ua       = random.choice(USER_AGENTS)
    viewport = random.choice(VIEWPORTS)
    base_url = cfg["target_url"].rstrip("/")

    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--disable-extensions",
        ],
    )
    try:
        ctx = await browser.new_context(
            user_agent=ua,
            viewport=viewport,
            locale=random.choice(["vi-VN", "en-US", "en-GB", "ja-JP", "ko-KR"]),
            timezone_id=random.choice([
                "Asia/Ho_Chi_Minh", "America/New_York",
                "Europe/London", "Asia/Tokyo", "Asia/Seoul",
            ]),
        )
        await ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins',   { get: () => [1,2,3,4,5] });
            window.chrome = { runtime: {} };
        """)

        page = await ctx.new_page()
        session_duration = random.randint(cfg["session_duration_min"], cfg["session_duration_max"])
        session_end = time.time() + session_duration

        # Chỉ load 1 trang duy nhất — không navigate sang trang khác
        # để tránh phát sinh thêm pageview / event
        landing = base_url + "/"
        try:
            await page.goto(landing, wait_until="domcontentloaded", timeout=30000)
            log.info(f"[U{uid:02d}] Loaded {landing} | will stay {session_duration}s")
        except Exception as e:
            log.warning(f"[U{uid:02d}] Load failed: {e}")

        # Scroll + mouse liên tục suốt session để duy trì engagement
        while time.time() < session_end:
            try:
                # Scroll lên/xuống tự nhiên
                scroll_dir = random.choice([1, -1])
                await page.evaluate(f"window.scrollBy(0, {scroll_dir * random.randint(80, 300)})")
                # Di chuột ngẫu nhiên
                await page.mouse.move(
                    random.randint(50, viewport["width"]  - 50),
                    random.randint(50, viewport["height"] - 50),
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            await asyncio.sleep(random.uniform(4.0, 8.0))

        remaining = max(0, session_end - time.time())
        log.info(f"[U{uid:02d}] SESSION DONE | stayed {session_duration}s on {landing}")
    finally:
        try:
            await browser.close()
        except Exception:
            pass


async def user_loop(uid: int, cfg: dict, end_time: float):
    """Keep running sessions until end_time; auto-restart on ANY crash."""
    from playwright.async_api import async_playwright

    session = 0
    while time.time() < end_time:
        session += 1
        log.info(f"[U{uid:02d}] === Session {session} start ===")
        try:
            async with async_playwright() as pw:
                await one_session(pw, uid, cfg)
        except asyncio.CancelledError:
            log.info(f"[U{uid:02d}] Cancelled.")
            break
        except Exception as e:
            log.error(f"[U{uid:02d}] Crash: {e} — restarting in 10s")
            await asyncio.sleep(10)
        else:
            # Short cooldown between sessions
            await asyncio.sleep(random.uniform(5, 15))


async def main():
    log.info("=" * 60)
    log.info("  GA SESSION KEEPER  v2  (Browser Mode)")
    log.info("=" * 60)

    cfg = load_config()

    log.info(f"Target        : {cfg['target_url']}")
    log.info(f"Virtual users : {cfg['num_virtual_users']}")
    log.info(f"Session time  : {cfg['session_duration_min']}-{cfg['session_duration_max']}s")
    log.info(f"Page stay     : {cfg['page_stay_min']}-{cfg['page_stay_max']}s")
    log.info(f"Run duration  : {cfg['run_duration_hours']} hours")
    log.info("=" * 60)

    end_time = time.time() + cfg["run_duration_hours"] * 3600

    tasks = [
        asyncio.create_task(user_loop(uid + 1, cfg, end_time))
        for uid in range(cfg["num_virtual_users"])
    ]

    # Status ticker every 5 minutes
    async def status_ticker():
        while time.time() < end_time:
            remaining = (end_time - time.time()) / 60
            alive = sum(1 for t in tasks if not t.done())
            log.info(f"[STATUS] {alive}/{len(tasks)} users alive | {remaining:.0f}min remaining")
            await asyncio.sleep(300)

    tasks.append(asyncio.create_task(status_ticker()))

    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except KeyboardInterrupt:
        log.info("[STOP] Interrupted.")
        for t in tasks:
            t.cancel()

    elapsed = (time.time() - (end_time - cfg["run_duration_hours"] * 3600)) / 60
    log.info(f"[DONE] {elapsed:.1f} minutes total")


if __name__ == "__main__":
    asyncio.run(main())
