"""
GA Session Keeper - Keep GA active user sessions alive
Sends hits via GA Measurement Protocol (GA4 + Universal Analytics)
"""

import requests
import time
import random
import json
import os
import sys
import io
import logging
from datetime import datetime

# Force UTF-8 output on Windows (fixes CP1252 encoding errors)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# CONFIG
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("ga_keeper.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("ga_keeper")

# ─────────────────── USER AGENTS ngẫu nhiên ─────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.71 Mobile Safari/537.36",
]

# ─────────────────── PAGES mô phỏng browse ──────────────────────────────────
PAGES = [
    "/",
    "/about",
    "/products",
    "/products/detail",
    "/blog",
    "/blog/post-1",
    "/contact",
    "/pricing",
    "/faq",
    "/news",
]


def load_config() -> dict:
    """Load cấu hình từ biến môi trường hoặc config.json"""
    cfg = {
        # GA4
        "ga4_measurement_id": os.environ.get("GA4_MEASUREMENT_ID", ""),
        "ga4_api_secret": os.environ.get("GA4_API_SECRET", ""),
        # Universal Analytics (nếu vẫn dùng UA)
        "ua_tracking_id": os.environ.get("UA_TRACKING_ID", ""),
        # Cài đặt chạy
        "target_url": os.environ.get("TARGET_URL", "https://example.com"),
        "hit_interval_min": int(os.environ.get("HIT_INTERVAL_MIN", "25")),  # giây
        "hit_interval_max": int(os.environ.get("HIT_INTERVAL_MAX", "40")),  # giây
        "num_virtual_users": int(os.environ.get("NUM_VIRTUAL_USERS", "5")),
        "run_forever": os.environ.get("RUN_FOREVER", "true").lower() == "true",
        "run_duration_hours": float(os.environ.get("RUN_DURATION_HOURS", "5.5")),
    }

    # Merge từ file config nếu có
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            file_cfg = json.load(f)
        for k, v in file_cfg.items():
            if not cfg.get(k):  # env override file
                cfg[k] = v

    return cfg


def rand_client_id() -> str:
    """Tạo client_id ngẫu nhiên (GA format)"""
    return f"{random.randint(100000000, 999999999)}.{int(time.time())}"


def rand_session_id() -> str:
    return str(random.randint(1000000000, 9999999999))


def rand_page(base_url: str) -> tuple[str, str]:
    """Trả về (location, title) ngẫu nhiên"""
    path = random.choice(PAGES)
    location = base_url.rstrip("/") + path
    title = path.strip("/").replace("-", " ").replace("/", " | ").title() or "Home"
    return location, title


# ─────────────────── GA4 Measurement Protocol ───────────────────────────────
def send_ga4_event(
    measurement_id: str,
    api_secret: str,
    client_id: str,
    session_id: str,
    event_name: str,
    params: dict,
    ua: str,
) -> bool:
    """Gửi 1 event GA4 qua Measurement Protocol"""
    url = (
        f"https://www.google-analytics.com/mp/collect"
        f"?measurement_id={measurement_id}&api_secret={api_secret}"
    )
    payload = {
        "client_id": client_id,
        "timestamp_micros": str(int(time.time() * 1_000_000)),
        "user_properties": {
            "browser": {"value": ua.split("(")[0].strip()},
        },
        "events": [
            {
                "name": event_name,
                "params": {
                    "session_id": session_id,
                    "engagement_time_msec": str(random.randint(15000, 45000)),
                    **params,
                },
            }
        ],
    }
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={"User-Agent": ua, "Content-Type": "application/json"},
            timeout=15,
        )
        return resp.status_code in (200, 204)
    except Exception as e:
        log.warning(f"GA4 send error: {e}")
        return False


def send_ga4_pageview(
    measurement_id: str,
    api_secret: str,
    client_id: str,
    session_id: str,
    location: str,
    title: str,
    ua: str,
) -> bool:
    return send_ga4_event(
        measurement_id,
        api_secret,
        client_id,
        session_id,
        "page_view",
        {"page_location": location, "page_title": title},
        ua,
    )


def send_ga4_engagement(
    measurement_id: str,
    api_secret: str,
    client_id: str,
    session_id: str,
    location: str,
    ua: str,
) -> bool:
    """user_engagement = signal người dùng đang active trên trang"""
    return send_ga4_event(
        measurement_id,
        api_secret,
        client_id,
        session_id,
        "user_engagement",
        {"page_location": location, "engagement_time_msec": str(random.randint(20000, 60000))},
        ua,
    )


# ─────────────────── Universal Analytics (UA) ───────────────────────────────
def send_ua_pageview(
    tracking_id: str,
    client_id: str,
    location: str,
    title: str,
    ua: str,
) -> bool:
    """Gửi pageview qua UA Measurement Protocol"""
    data = {
        "v": "1",
        "tid": tracking_id,
        "cid": client_id,
        "t": "pageview",
        "dl": location,
        "dt": title,
        "ua": ua,
        "sr": random.choice(["1920x1080", "1366x768", "1440x900", "2560x1440"]),
        "ul": random.choice(["vi-vn", "en-us", "en-gb"]),
        "sd": "24-bit",
        "je": "0",
        "fl": "0.0",
    }
    try:
        resp = requests.post(
            "https://www.google-analytics.com/collect",
            data=data,
            headers={"User-Agent": ua},
            timeout=15,
        )
        return resp.status_code == 200
    except Exception as e:
        log.warning(f"UA send error: {e}")
        return False


def send_ua_event(
    tracking_id: str,
    client_id: str,
    location: str,
    ua: str,
    category: str = "engagement",
    action: str = "active",
) -> bool:
    """Gửi event UA để báo hiệu active"""
    data = {
        "v": "1",
        "tid": tracking_id,
        "cid": client_id,
        "t": "event",
        "ec": category,
        "ea": action,
        "dl": location,
        "ua": ua,
    }
    try:
        resp = requests.post(
            "https://www.google-analytics.com/collect",
            data=data,
            headers={"User-Agent": ua},
            timeout=15,
        )
        return resp.status_code == 200
    except Exception as e:
        log.warning(f"UA event error: {e}")
        return False


# ─────────────────── VIRTUAL USER ───────────────────────────────────────────
class VirtualUser:
    def __init__(self, uid: int, cfg: dict):
        self.uid = uid
        self.cfg = cfg
        self.client_id = rand_client_id()
        self.session_id = rand_session_id()
        self.ua = random.choice(USER_AGENTS)
        self.current_page, self.current_title = rand_page(cfg["target_url"])
        self.page_time = 0
        self.total_hits = 0
        self.session_hits = 0
        log.info(f"[User-{uid}] INIT | cid={self.client_id} | ua={self.ua[:40]}...")

    def rotate_session(self):
        """New session after ~30 mins to avoid detection"""
        self.session_id = rand_session_id()
        self.ua = random.choice(USER_AGENTS)
        self.session_hits = 0
        log.info(f"[User-{self.uid}] NEW SESSION: {self.session_id}")

    def navigate(self):
        """Navigate to random page"""
        self.current_page, self.current_title = rand_page(self.cfg["target_url"])
        self.page_time = 0
        log.info(f"[User-{self.uid}] NAVIGATE -> {self.current_page}")

    def tick(self) -> dict:
        """Gửi 1 vòng hit, trả về stats"""
        ok_ga4 = ok_ua = None
        m_id = self.cfg.get("ga4_measurement_id", "")
        api_sec = self.cfg.get("ga4_api_secret", "")
        ua_tid = self.cfg.get("ua_tracking_id", "")

        # ── GA4 ──
        if m_id and api_sec:
            if self.session_hits == 0 or self.page_time == 0:
                ok_ga4 = send_ga4_pageview(
                    m_id, api_sec, self.client_id, self.session_id,
                    self.current_page, self.current_title, self.ua,
                )
            else:
                ok_ga4 = send_ga4_engagement(
                    m_id, api_sec, self.client_id, self.session_id,
                    self.current_page, self.ua,
                )

        # ── UA ──
        if ua_tid:
            if self.session_hits == 0 or self.page_time == 0:
                ok_ua = send_ua_pageview(ua_tid, self.client_id, self.current_page, self.current_title, self.ua)
            else:
                ok_ua = send_ua_event(ua_tid, self.client_id, self.current_page, self.ua)

        self.page_time += 1
        self.session_hits += 1
        self.total_hits += 1

        # Sau ~6 hit trên 1 trang → chuyển trang
        if self.page_time >= random.randint(4, 8):
            self.navigate()

        # Sau ~20 hit → rotate session
        if self.session_hits >= random.randint(15, 25):
            self.rotate_session()

        return {"uid": self.uid, "ok_ga4": ok_ga4, "ok_ua": ok_ua, "hits": self.total_hits}


# ─────────────────── MAIN LOOP ───────────────────────────────────────────────
def main():
    log.info("=" * 60)
    log.info("  GA SESSION KEEPER - STARTING")
    log.info("=" * 60)

    cfg = load_config()

    if not cfg.get("ga4_measurement_id") and not cfg.get("ua_tracking_id"):
        log.error("[ERROR] No GA Measurement ID or UA Tracking ID configured!")
        log.error("        See README.md for setup instructions.")
        sys.exit(1)

    log.info(f"Target URL    : {cfg['target_url']}")
    log.info(f"GA4 ID        : {cfg.get('ga4_measurement_id') or '(disabled)'}")
    log.info(f"UA Tracking   : {cfg.get('ua_tracking_id') or '(disabled)'}")
    log.info(f"Virtual Users : {cfg['num_virtual_users']}")
    log.info(f"Hit Interval  : {cfg['hit_interval_min']}-{cfg['hit_interval_max']}s")
    log.info(f"Run Forever   : {cfg['run_forever']}")
    if not cfg["run_forever"]:
        log.info(f"Duration      : {cfg['run_duration_hours']} hours")

    users = [VirtualUser(i + 1, cfg) for i in range(cfg["num_virtual_users"])]

    start_time = time.time()
    end_time = start_time + cfg["run_duration_hours"] * 3600

    cycle = 0
    try:
        while True:
            cycle += 1
            now = time.time()

            if not cfg["run_forever"] and now >= end_time:
                log.info("[STOP] Time limit reached.")
                break

            log.info(f"\n-- Cycle {cycle} | {datetime.now().strftime('%H:%M:%S')} --")
            for user in users:
                result = user.tick()
                status = []
                if result["ok_ga4"] is not None:
                    status.append(f"GA4={'OK' if result['ok_ga4'] else 'FAIL'}")
                if result["ok_ua"] is not None:
                    status.append(f"UA={'OK' if result['ok_ua'] else 'FAIL'}")
                log.info(
                    f"  User-{result['uid']:02d} | {' '.join(status)} | total_hits={result['hits']}"
                )
                # Small delay between users to avoid burst
                time.sleep(random.uniform(0.5, 2.0))

            interval = random.randint(cfg["hit_interval_min"], cfg["hit_interval_max"])
            log.info(f"  -> Waiting {interval}s before next cycle...")
            time.sleep(interval)

    except KeyboardInterrupt:
        log.info("\n[STOP] Interrupted by user.")

    total_time = (time.time() - start_time) / 60
    log.info(f"\n[DONE] {cycle} cycles | {total_time:.1f} minutes running")


if __name__ == "__main__":
    main()
