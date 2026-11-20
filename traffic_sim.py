"""
traffic_sim.py - Script gia lap tai & Chaos Engine cho Demo AIOps Cloud
========================================================================
Chay tren may host (khong can Docker), gui HTTP request den FastAPI app.

Su dung:
  python traffic_sim.py --mode normal       # Tai binh thuong (2 req/s)
  python traffic_sim.py --mode anomaly      # Gray Failure (Latency giat cuc 2s, CPU ~42% < 80%)
  python traffic_sim.py --mode memory_leak  # Ro ri bo nho RAM mo phong
  python traffic_sim.py --mode jitter       # Micro-burst latency ngau nhien
  python traffic_sim.py --mode error_burst  # Bao loi HTTP 500
  python traffic_sim.py --remediate         # Kich hoat Self-Healing thu cong
"""

import argparse
import time
import sys
import random
import requests
from datetime import datetime

# ---------------------------------------------------------------------------
# Cau hinh
# ---------------------------------------------------------------------------
APP_URL       = "http://localhost:8000/api/process"
REMEDIATE_URL = "http://localhost:8000/api/remediate"
NORMAL_RPS    = 2      # requests per second khi mode=normal
ANOMALY_RATIO = 0.4    # 40% request la anomaly khi mode=anomaly


def log(msg: str):
    """In log co timestamp."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def send_request(mode: str) -> dict:
    """Gui mot request den FastAPI va tra ve ket qua."""
    try:
        resp = requests.get(APP_URL, params={"mode": mode}, timeout=10)
        return resp.json()
    except requests.exceptions.ConnectionError:
        log("[ERROR] Khong ket noi duoc toi app! Dam bao Docker Compose dang chay.")
        sys.exit(1)
    except Exception as e:
        log(f"[WARN] Loi request: {e}")
        return {}


def run_normal_mode():
    """
    Che do binh thuong: gui deu dan 2 req/s
    -> Tao vung du lieu on dinh cho Isolation Forest hoc baseline
    """
    log("[START] Bat dau che do BINH THUONG (2 req/s)")
    log("   -> CPU: ~15-25% | Latency: ~30-60ms | RAM: ~128MB")
    log("   -> Dung de tao baseline cho Isolation Forest")
    log("   Nhan Ctrl+C de dung.\n")

    count = 0
    interval = 1.0 / NORMAL_RPS

    while True:
        result = send_request("normal")
        count += 1
        if result:
            log(f"[OK] [#{count}] normal | latency={result.get('latency_ms', '?')}ms | cpu={result.get('cpu_percent', '?'):.1f}%")
        time.sleep(interval)


def run_anomaly_mode():
    """
    Che do bat thuong (Gray Failure): xen ke normal va anomaly request
    -> CPU van ~40-45% (KHONG vuot nguong tinh 80%)
    -> Nhung latency giat cuc 1.5-3s -> Isolation Forest phat hien
    """
    log("[START] Bat dau che do BAT THUONG (xen ke anomaly requests - Gray Failure)")
    log("   -> CPU anomaly: ~40-45% (DUOI nguong tinh 80% !!)")
    log("   -> Latency anomaly: 1.5-3.0s (giat cuc bat thuong)")
    log("   -> Muc tieu: AI phat hien duoc, threshold tinh KHONG phat hien")
    log("   Nhan Ctrl+C de dung.\n")

    count = 0
    while True:
        mode = "anomaly" if random.random() < ANOMALY_RATIO else "normal"
        result = send_request(mode)
        count += 1

        if result:
            tag = "[ANOMALY]" if mode == "anomaly" else "[NORMAL] "
            log(
                f"{tag} [#{count}] {mode:7s} | "
                f"latency={result.get('latency_ms', '?')}ms | "
                f"cpu={result.get('cpu_percent', '?'):.1f}%"
            )

        if mode == "normal":
            time.sleep(0.5)


def run_chaos_mode(scenario: str):
    """
    Chay cac kich ban Chaos Engineering:
    - memory_leak : ro ri bo nho mo phong
    - error_burst : bao loi HTTP 500
    - jitter      : giat cuc vi mo (micro-burst)
    """
    log(f"[CHAOS] Kich hoat kich ban Chaos: {scenario.upper()}")
    log("   Nhan Ctrl+C de dung.\n")

    count = 0
    while True:
        result = send_request(scenario)
        count += 1
        if result:
            mem = f" | mem={result.get('memory_mb', '?')}MB" if 'memory_mb' in result else ""
            log(f"[TEST] [#{count}] {scenario} | latency={result.get('latency_ms', '?')}ms | cpu={result.get('cpu_percent', '?'):.1f}%{mem}")
        time.sleep(0.5)


def trigger_remediate():
    """Gui yeu cau self-healing phuc hoi he thong."""
    try:
        resp = requests.post(REMEDIATE_URL, timeout=5)
        log(f"[REMEDIATE] Phuc hoi he thong: {resp.json().get('message')}")
    except Exception as e:
        log(f"[ERROR] Loi khi gui lenh phuc hoi: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="AIOps Demo - Traffic Simulator & Chaos Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--mode",
        choices=["normal", "anomaly", "memory_leak", "jitter", "error_burst"],
        default="normal",
        help="Che do gia lap tai (mac dinh: normal)"
    )
    parser.add_argument(
        "--remediate",
        action="store_true",
        help="Gui tin hieu Self-Healing phuc hoi service ve trang thai binh thuong"
    )

    args = parser.parse_args()

    if args.remediate:
        trigger_remediate()
        return

    try:
        if args.mode == "normal":
            run_normal_mode()
        elif args.mode == "anomaly":
            run_anomaly_mode()
        else:
            run_chaos_mode(args.mode)
    except KeyboardInterrupt:
        log("\nDung gia lap tai.")
        sys.exit(0)


if __name__ == "__main__":
    main()
