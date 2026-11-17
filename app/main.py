"""
app/main.py - Target Microservice (FastAPI + Prometheus)
=========================================================
Service giả lập một microservice thực tế với 2 chế độ:
  - normal : xử lý nhanh (~30-60ms), CPU thấp (~15-25%)
  - anomaly: độ trễ giật cục (1.5-3s), CPU trung bình (~40-45%)
              --> Dưới ngưỡng tĩnh 80% nhưng vẫn là bất thường hành vi!
"""

import time
import random
import math
import os

from fastapi import FastAPI, Query
from prometheus_client import (
    Counter, Histogram, Gauge,
    generate_latest, CONTENT_TYPE_LATEST
)
from starlette.responses import Response

app = FastAPI(title="Target Microservice")

# ---------------------------------------------------------------------------
# Định nghĩa các Prometheus Metrics
# ---------------------------------------------------------------------------

# Counter: tổng số request (nhãn: mode)
REQUEST_COUNTER = Counter(
    "app_requests_total",
    "Tổng số request đã xử lý",
    ["mode"]
)

# Histogram: phân bố độ trễ xử lý request (nhãn: mode)
REQUEST_LATENCY = Histogram(
    "app_request_latency_seconds",
    "Độ trễ xử lý request tính bằng giây",
    ["mode"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0]
)

# Gauge: mức CPU hiện tại của service (do chính service tự báo cáo)
CPU_GAUGE = Gauge(
    "app_simulated_cpu_percent",
    "Mức CPU giả lập hiện tại của service (%)"
)


def simulate_normal_processing() -> float:
    """
    Chế độ bình thường:
    - Độ trễ: 30-60ms (xử lý nhanh)
    - CPU: 15-25% (tải nhẹ)
    Trả về thời gian thực thi thực tế (giây).
    """
    # Giả lập tải CPU nhẹ bằng vòng lặp tính toán nhỏ
    cpu_pct = random.uniform(15, 25)
    CPU_GAUGE.set(cpu_pct)

    # Độ trễ ngẫu nhiên trong khoảng bình thường
    delay = random.uniform(0.030, 0.060)
    time.sleep(delay)
    return delay


def simulate_anomaly_processing() -> float:
    """
    Chế độ bất thường (Dưới ngưỡng tĩnh 80% nhưng hành vi bất thường):
    - Độ trễ: 1.5-3.0s (giật cục, không ổn định)
    - CPU: 40-45% (trung bình - KHÔNG vượt ngưỡng tĩnh 80%)

    Đây chính là điểm mấu chốt của demo:
    - Hệ thống giám sát truyền thống (threshold tĩnh) sẽ KHÔNG phát hiện ra
    - Nhưng Isolation Forest sẽ nhận ra pattern bất thường trong chuỗi thời gian
    """
    # CPU ở mức trung bình (cố ý KHÔNG vượt 80% để minh họa hạn chế threshold tĩnh)
    cpu_pct = random.uniform(40, 45)
    CPU_GAUGE.set(cpu_pct)

    # Độ trễ bất thường: giật cục ngẫu nhiên trong khoảng [1.5s, 3.0s]
    delay = random.uniform(1.5, 3.0)
    time.sleep(delay)
    return delay


@app.get("/api/process")
def process(mode: str = Query("normal", enum=["normal", "anomaly"])):
    """
    Endpoint chính để giả lập tải.
    - mode=normal : hành vi bình thường
    - mode=anomaly: hành vi bất thường (nhưng CPU vẫn dưới ngưỡng tĩnh 80%)
    """
    start_time = time.time()

    if mode == "normal":
        elapsed = simulate_normal_processing()
    else:
        elapsed = simulate_anomaly_processing()

    # Ghi nhận metrics vào Prometheus
    REQUEST_COUNTER.labels(mode=mode).inc()
    REQUEST_LATENCY.labels(mode=mode).observe(elapsed)

    return {
        "status": "ok",
        "mode": mode,
        "latency_ms": round(elapsed * 1000, 2),
        "cpu_percent": CPU_GAUGE._value.get()
    }


@app.get("/metrics")
def metrics():
    """Endpoint Pull-based cho Prometheus scrape."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
def health():
    return {"status": "healthy"}
