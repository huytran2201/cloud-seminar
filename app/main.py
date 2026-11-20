"""
app/main.py - Target Microservice (FastAPI + Prometheus)
=========================================================
Service giả lập một microservice thực tế với các chế độ:
  - normal     : xử lý nhanh (~30-60ms), CPU thấp (~15-25%), RAM ổn định
  - anomaly    : độ trễ giật cục (1.5-3s), CPU trung bình (~40-45%)
                 --> Dưới ngưỡng tĩnh 80% nhưng vẫn là bất thường hành vi (Gray Failure)!
  - memory_leak: rò rỉ bộ nhớ RAM tăng dần
  - jitter     : micro-burst độ trễ ngẫu nhiên
  - error_burst: sinh mã lỗi HTTP 500
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
# Định nghĩa các Prometheus Metrics (OpenMetrics Format)
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

# Gauge: mức RAM giả lập (MB)
MEMORY_GAUGE = Gauge(
    "app_simulated_memory_mb",
    "Mức RAM giả lập hiện tại của service (MB)"
)

# Counter: số lần tự phục hồi thành công (Self-healing)
REMEDIATION_COUNTER = Counter(
    "app_remediation_total",
    "Tổng số lần tự phục hồi hệ thống thành công (Self-Healing / Auto-Remediation)"
)

# Biến trạng thái nội bộ
_simulated_memory_mb = 128.0
_force_anomaly_override = False


def simulate_normal_processing() -> float:
    """
    Chế độ bình thường:
    - Độ trễ: 30-60ms (xử lý nhanh)
    - CPU: 15-25% (tải nhẹ)
    - RAM: ổn định quanh 128MB
    """
    global _simulated_memory_mb
    cpu_pct = random.uniform(15, 25)
    CPU_GAUGE.set(cpu_pct)
    _simulated_memory_mb = max(128.0, _simulated_memory_mb * 0.98)
    MEMORY_GAUGE.set(_simulated_memory_mb)

    delay = random.uniform(0.030, 0.060)
    time.sleep(delay)
    return delay


def simulate_anomaly_processing() -> float:
    """
    Chế độ bất thường (Gray Failure - Dưới ngưỡng tĩnh 80% nhưng hành vi bất thường):
    - Độ trễ: 1.5-3.0s (giật cục, không ổn định)
    - CPU: 40-45% (trung bình - KHÔNG vượt ngưỡng tĩnh 80%)
    """
    cpu_pct = random.uniform(40, 45)
    CPU_GAUGE.set(cpu_pct)
    MEMORY_GAUGE.set(_simulated_memory_mb)

    delay = random.uniform(1.5, 3.0)
    time.sleep(delay)
    return delay


def simulate_memory_leak_processing() -> float:
    """
    Kịch bản rò rỉ bộ nhớ (Memory Leak):
    - RAM tăng dần không giải phóng
    - CPU vừa phải ~25-35%
    """
    global _simulated_memory_mb
    _simulated_memory_mb += random.uniform(15.0, 30.0)
    MEMORY_GAUGE.set(_simulated_memory_mb)
    cpu_pct = random.uniform(25, 35)
    CPU_GAUGE.set(cpu_pct)

    delay = random.uniform(0.1, 0.3)
    time.sleep(delay)
    return delay


def simulate_jitter_processing() -> float:
    """
    Kịch bản micro-burst / jitter:
    - Thỉnh thoảng xuất hiện request chậm xen kẽ request nhanh
    """
    cpu_pct = random.uniform(20, 30)
    CPU_GAUGE.set(cpu_pct)
    MEMORY_GAUGE.set(_simulated_memory_mb)

    if random.random() < 0.3:
        delay = random.uniform(1.2, 2.2)
    else:
        delay = random.uniform(0.04, 0.08)
    time.sleep(delay)
    return delay


@app.get("/api/process")
def process(mode: str = Query("normal", enum=["normal", "anomaly", "memory_leak", "jitter", "error_burst"])):
    """
    Endpoint chính để xử lý tải:
    - mode=normal     : hành vi bình thường
    - mode=anomaly    : Gray Failure (độ trễ cao, CPU ~42% < 80%)
    - mode=memory_leak: rò rỉ bộ nhớ RAM tăng dần
    - mode=jitter     : giật cục vi mô (micro-burst)
    - mode=error_burst: sinh mã lỗi 500
    """
    global _simulated_memory_mb
    if _force_anomaly_override:
        mode = "anomaly"

    if mode == "error_burst" and random.random() < 0.4:
        REQUEST_COUNTER.labels(mode=mode).inc()
        return Response(content='{"error": "Internal Server Error (Simulated Chaos)"}', status_code=500, media_type="application/json")

    start_time = time.time()
    if mode == "normal":
        elapsed = simulate_normal_processing()
    elif mode == "anomaly":
        elapsed = simulate_anomaly_processing()
    elif mode == "memory_leak":
        elapsed = simulate_memory_leak_processing()
    elif mode == "jitter":
        elapsed = simulate_jitter_processing()
    else:
        elapsed = simulate_normal_processing()

    # Ghi nhận metrics vào Prometheus
    REQUEST_COUNTER.labels(mode=mode).inc()
    REQUEST_LATENCY.labels(mode=mode).observe(elapsed)

    return {
        "status": "ok",
        "mode": mode,
        "latency_ms": round(elapsed * 1000, 2),
        "cpu_percent": round(CPU_GAUGE._value.get(), 2),
        "memory_mb": round(_simulated_memory_mb, 2)
    }


@app.post("/api/remediate")
@app.get("/api/remediate")
def remediate():
    """
    Endpoint Auto-Remediation (Self-Healing):
    - Đặt lại mức RAM về baseline (128MB)
    - Tắt cờ anomaly override
    - Tăng counter số lần tự phục hồi thành công
    """
    global _simulated_memory_mb, _force_anomaly_override
    _simulated_memory_mb = 128.0
    _force_anomaly_override = False
    MEMORY_GAUGE.set(_simulated_memory_mb)
    CPU_GAUGE.set(20.0)
    REMEDIATION_COUNTER.inc()
    return {
        "status": "remediated",
        "message": "Self-healing triggered: Memory & states restored to healthy baseline",
        "simulated_memory_mb": _simulated_memory_mb
    }


@app.get("/metrics")
def metrics():
    """Endpoint Pull-based cho Prometheus scrape."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
def health():
    return {"status": "healthy"}
