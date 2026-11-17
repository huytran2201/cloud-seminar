"""
traffic_sim.py - Script giả lập tải cho demo AIOps
====================================================
Chạy trên máy host (không cần Docker), gửi request đến FastAPI app.

Sử dụng:
  python traffic_sim.py --mode normal   # Tải bình thường (2 req/s)
  python traffic_sim.py --mode anomaly  # Tải bất thường xen kẽ

Cài đặt: pip install requests
"""

import argparse
import time
import sys
import requests
from datetime import datetime

# ---------------------------------------------------------------------------
# Cấu hình
# ---------------------------------------------------------------------------
APP_URL       = "http://localhost:8000/api/process"
NORMAL_RPS    = 2      # requests per second khi mode=normal
ANOMALY_RATIO = 0.4    # 40% request là anomaly khi mode=anomaly


def log(msg: str):
    """In log có timestamp."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def send_request(mode: str) -> dict:
    """Gửi một request đến FastAPI và trả về kết quả."""
    try:
        resp = requests.get(APP_URL, params={"mode": mode}, timeout=10)
        return resp.json()
    except requests.exceptions.ConnectionError:
        log("❌ Không kết nối được tới app! Đảm bảo Docker Compose đang chạy.")
        sys.exit(1)
    except Exception as e:
        log(f"⚠️ Lỗi request: {e}")
        return {}


def run_normal_mode():
    """
    Chế độ bình thường: gửi đều đặn 2 req/s
    → Tạo vùng dữ liệu ổn định cho Isolation Forest học baseline
    """
    log("🟢 Bắt đầu chế độ BÌNH THƯỜNG (2 req/s)")
    log("   → CPU: ~15-25% | Latency: ~30-60ms")
    log("   → Dùng để tạo baseline cho Isolation Forest")
    log("   Nhấn Ctrl+C để dừng.\n")

    count = 0
    interval = 1.0 / NORMAL_RPS  # 0.5 giây giữa 2 request

    while True:
        result = send_request("normal")
        count += 1
        if result:
            log(f"✅ [#{count}] normal | latency={result.get('latency_ms', '?')}ms | cpu={result.get('cpu_percent', '?'):.1f}%")
        time.sleep(interval)


def run_anomaly_mode():
    """
    Chế độ bất thường: xen kẽ normal và anomaly request
    → CPU vẫn ~40-45% (KHÔNG vượt ngưỡng tĩnh 80%)
    → Nhưng latency giật cục 1.5-3s → Isolation Forest phát hiện
    """
    log("🔴 Bắt đầu chế độ BẤT THƯỜNG (xen kẽ anomaly requests)")
    log("   → CPU anomaly: ~40-45% (DƯỚI ngưỡng tĩnh 80% !!)")
    log("   → Latency anomaly: 1.5-3.0s (giật cục bất thường)")
    log("   → Mục tiêu: AI phát hiện được, threshold tĩnh KHÔNG phát hiện")
    log("   Nhấn Ctrl+C để dừng.\n")

    count = 0
    import random

    while True:
        # 40% chance gửi request anomaly, 60% normal
        mode = "anomaly" if random.random() < ANOMALY_RATIO else "normal"
        result = send_request(mode)
        count += 1

        if result:
            emoji = "🚨" if mode == "anomaly" else "✅"
            log(
                f"{emoji} [#{count}] {mode:7s} | "
                f"latency={result.get('latency_ms', '?')}ms | "
                f"cpu={result.get('cpu_percent', '?'):.1f}%"
            )

        # Không delay cứng: anomaly request tự delay 1.5-3s bên trong
        # Normal request delay thêm 0.5s để không bắn quá nhanh
        if mode == "normal":
            time.sleep(0.5)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="🚀 AIOps Demo - Traffic Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python traffic_sim.py --mode normal    # Tạo baseline (chạy ~2 phút đầu)
  python traffic_sim.py --mode anomaly   # Trigger bất thường để AI phát hiện

Quy trình demo khuyến nghị:
  1. Chạy normal 60-90 giây để AI học baseline
  2. Chuyển sang anomaly để xem AI score tăng vọt trên Grafana
        """
    )
    parser.add_argument(
        "--mode",
        choices=["normal", "anomaly"],
        default="normal",
        help="Chế độ giả lập tải (default: normal)"
    )
    args = parser.parse_args()

    try:
        if args.mode == "normal":
            run_normal_mode()
        else:
            run_anomaly_mode()
    except KeyboardInterrupt:
        log("\n⏹️  Dừng giả lập tải.")
        sys.exit(0)


if __name__ == "__main__":
    main()
