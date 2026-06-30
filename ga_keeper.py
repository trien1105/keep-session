"""
GA Engagement Time Keeper — Measurement Protocol Mode
Chỉ gửi user_engagement, KHÔNG gửi page_view
→ Tăng Average engagement time, KHÔNG tăng Views/Events
"""

import asyncio
import random
import os
import sys
import json
import time
import uuid
import logging
import aiohttp
from datetime import datetime

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("ga_keeper")

# ──────────────────────────────────────────────
# GA4 Measurement Protocol endpoint
# Điền MEASUREMENT_ID và API_SECRET vào GitHub Secrets
# ──────────────────────────────────────────────
GA4_ENDPOINT = "https://www.google-analytics.com/mp/collect"


def load_config() -> dict:
    cfg = {
        "measurement_id":       os.environ.get("GA4_MEASUREMENT_ID", ""),
        "api_secret":           os.environ.get("GA4_API_SECRET", ""),
        "num_virtual_users":    int(os.environ.get("NUM_VIRTUAL_USERS", "16")),
        "session_duration_min": int(os.environ.get("SESSION_DURATION_MIN", "480")),
        "session_duration_max": int(os.environ.get("SESSION_DURATION_MAX", "900")),
        "run_duration_hours":   float(os.environ.get("RUN_DURATION_HOURS", "5.5")),
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            for k, v in json.load(f).items():
                if k in cfg and not os.environ.get(k.upper()):
                    cfg[k] = v
    return cfg


def make_client_id() -> str:
    """Tạo client_id ngẫu nhiên, giống GA4 browser."""
    return f"{random.randint(100000000, 999999999)}.{int(time.time())}"


def make_session_id() -> str:
    return str(int(time.time()) + random.randint(0, 9999))


async def send_engagement(
    session: aiohttp.ClientSession,
    measurement_id: str,
    api_secret: str,
    client_id: str,
    session_id: str,
    engagement_ms: int,
    uid: int,
):
    """
    Gửi DUY NHẤT event user_engagement.
    KHÔNG gửi page_view → Views không tăng.
    """
    payload = {
        "client_id": client_id,
        "non_personalized_ads": False,
        "events": [
            {
                "name": "user_engagement",
                "params": {
                    "session_id": session_id,
                    "engagement_time_msec": engagement_ms,
                    # KHÔNG có page_view, KHÔNG có event_count trigger
                },
            }
        ],
    }

    url = f"{GA4_ENDPOINT}?measurement_id={measurement_id}&api_secret={api_secret}"

    try:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 204:
                log.debug(f"[U{uid:02d}] ✓ sent engagement {engagement_ms}ms")
            else:
                body = await resp.text()
                log.warning(f"[U{uid:02d}] GA returned {resp.status}: {body[:200]}")
    except Exception as e:
        log.warning(f"[U{uid:02d}] send error: {e}")


async def virtual_user(uid: int, cfg: dict, end_time: float):
    """
    Mỗi virtual user:
    - Tạo client_id & session_id riêng
    - Cứ mỗi 30–60s gửi 1 user_engagement với engagement_time_msec = khoảng thời gian đó
    - Khi session hết hạn, tạo session mới
    """
    measurement_id = cfg["measurement_id"]
    api_secret     = cfg["api_secret"]

    if not measurement_id or not api_secret:
        log.error("Thiếu GA_MEASUREMENT_ID hoặc GA_API_SECRET! Kiểm tra GitHub Secrets.")
        return

    async with aiohttp.ClientSession() as http:
        session_count = 0
        while time.time() < end_time:
            session_count += 1
            client_id  = make_client_id()
            session_id = make_session_id()
            session_duration = random.randint(cfg["session_duration_min"], cfg["session_duration_max"])
            session_end = time.time() + session_duration

            log.info(f"[U{uid:02d}] Session {session_count} | duration={session_duration}s | cid={client_id}")

            while time.time() < session_end and time.time() < end_time:
                # Khoảng ping mỗi 30–60 giây — đây là "engagement period"
                ping_interval = random.randint(30, 60)
                await asyncio.sleep(ping_interval)

                # Gửi engagement_time_msec = thời gian vừa ở trên trang (ms)
                engagement_ms = ping_interval * 1000 + random.randint(-2000, 2000)
                engagement_ms = max(5000, engagement_ms)  # tối thiểu 5s

                await send_engagement(
                    http, measurement_id, api_secret,
                    client_id, session_id, engagement_ms, uid,
                )

            log.info(f"[U{uid:02d}] Session {session_count} done | sleeping 10s")
            await asyncio.sleep(random.uniform(5, 15))


async def main():
    log.info("=" * 60)
    log.info("  GA ENGAGEMENT KEEPER  v3  (Measurement Protocol)")
    log.info("  Chỉ gửi user_engagement — KHÔNG tăng Views/Events")
    log.info("=" * 60)

    cfg = load_config()

    log.info(f"Measurement ID : {cfg['measurement_id'] or '❌ CHƯA SET'}")
    log.info(f"API Secret     : {'✅ SET' if cfg['api_secret'] else '❌ CHƯA SET'}")
    log.info(f"Virtual users  : {cfg['num_virtual_users']}")
    log.info(f"Session time   : {cfg['session_duration_min']}–{cfg['session_duration_max']}s")
    log.info(f"Run duration   : {cfg['run_duration_hours']} hours")
    log.info("=" * 60)

    if not cfg["measurement_id"] or not cfg["api_secret"]:
        log.error("⛔ Thiếu GA4_MEASUREMENT_ID hoặc GA4_API_SECRET. Dừng.")
        log.error("   Thêm vào GitHub Secrets hoặc config.json.")
        return

    end_time = time.time() + cfg["run_duration_hours"] * 3600

    tasks = [
        asyncio.create_task(virtual_user(uid + 1, cfg, end_time))
        for uid in range(cfg["num_virtual_users"])
    ]

    async def status_ticker():
        while time.time() < end_time:
            remaining = (end_time - time.time()) / 60
            alive = sum(1 for t in tasks if not t.done())
            log.info(f"[STATUS] {alive}/{len(tasks)} users alive | {remaining:.0f}min left")
            await asyncio.sleep(300)

    tasks.append(asyncio.create_task(status_ticker()))

    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except KeyboardInterrupt:
        log.info("[STOP] Interrupted.")
        for t in tasks:
            t.cancel()

    log.info("[DONE] Finished.")


if __name__ == "__main__":
    asyncio.run(main())
