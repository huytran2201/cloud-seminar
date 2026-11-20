"""
ai_detector/detector.py - AIOps Worker (Isolation Forest + XAI + Self-Healing)
=============================================================================
Vòng lặp chính của AI Detector:
  1. Mỗi 5 giây: gọi Prometheus API lấy dữ liệu chuỗi thời gian (Sliding Window 5 phút)
  2. Chống nhiễm độc Baseline (Drift/Poisoning Prevention) khi xảy ra sự cố kéo dài
  3. Huấn luyện lại Isolation Forest trên cửa sổ trượt
  4. Chấm điểm dữ liệu mới nhất → ai_anomaly_score [0.0, 1.0]
  5. Tính toán XAI Feature Attribution (Root Cause Analysis - RCA)
  6. Tự động kích hoạt Closed-Loop Remediation (Self-Healing) khi anomaly kéo dài
  7. Publish kết quả qua /metrics để Prometheus thu thập
"""

import time
import math
import logging
import threading
import numpy as np
import requests

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from prometheus_client import Gauge, Counter, generate_latest, CONTENT_TYPE_LATEST
from flask import Flask, Response

# ---------------------------------------------------------------------------
# Cấu hình logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [AI-Detector] %(levelname)s: %(message)s"
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cấu hình hệ thống
# ---------------------------------------------------------------------------
PROMETHEUS_URL           = "http://prometheus:9090"
APP_REMEDIATION_URL      = "http://app:8000/api/remediate"
SCRAPE_INTERVAL          = 5          # giây giữa các lần phân tích
WINDOW_MINUTES           = 5          # cửa sổ trượt lấy dữ liệu (phút)
MIN_POINTS               = 20         # số điểm tối thiểu để huấn luyện mô hình
ANOMALY_THRESHOLD        = 0.7        # ngưỡng: score > 0.7 → bất thường
AUTO_REMEDIATION_ENABLED = True       # tự kích hoạt phục hồi khi bất thường kéo dài
AUTO_REMEDIATION_STREAK  = 20         # 20 cycles (100s) > threshold -> safety trigger

# ---------------------------------------------------------------------------
# Định nghĩa Prometheus Metrics (AI tự báo cáo kết quả phân tích)
# ---------------------------------------------------------------------------
ANOMALY_SCORE = Gauge(
    "ai_anomaly_score",
    "Điểm bất thường từ Isolation Forest [0.0=bình thường, 1.0=rất bất thường]"
)
IS_ANOMALY = Gauge(
    "ai_is_anomaly",
    "Nhị phân: 1 nếu ai_anomaly_score > 0.7, ngược lại là 0"
)
DETECTOR_HEALTH = Gauge(
    "ai_detector_healthy",
    "1 nếu detector đang hoạt động bình thường, 0 nếu lỗi"
)
FEATURE_ATTRIBUTION = Gauge(
    "ai_feature_attribution",
    "XAI Root Cause: Tỷ lệ phần trăm đóng góp của đặc trưng vào điểm bất thường (0.0 - 1.0)",
    ["feature"]
)
REMEDIATION_TRIGGER_COUNTER = Counter(
    "ai_remediation_triggers_total",
    "Tổng số lần AIOps Detector tự động gửi lệnh Self-Healing đến microservice"
)

# ---------------------------------------------------------------------------
# Flask app để expose /metrics
# ---------------------------------------------------------------------------
flask_app = Flask(__name__)

@flask_app.route("/metrics")
def metrics():
    """Endpoint để Prometheus scrape kết quả AI."""
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

@flask_app.route("/health")
def health():
    return {"status": "healthy"}


# ---------------------------------------------------------------------------
# Hàm lấy dữ liệu từ Prometheus (Sliding Window)
# ---------------------------------------------------------------------------

def query_prometheus_range(metric_expr: str, minutes: int = WINDOW_MINUTES) -> list[float]:
    """
    Gọi Prometheus API /api/v1/query_range để lấy chuỗi thời gian.
    """
    end   = time.time()
    start = end - (minutes * 60)
    
    try:
        resp = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query_range",
            params={
                "query": metric_expr,
                "start": start,
                "end"  : end,
                "step" : "5s"   # khớp với scrape_interval
            },
            timeout=5
        )
        resp.raise_for_status()
        data = resp.json()
        
        results = data.get("data", {}).get("result", [])
        if not results:
            return []
        
        values = [float(v[1]) for v in results[0]["values"] if v[1] != "NaN"]
        return values
    
    except Exception as e:
        log.warning(f"Lỗi query Prometheus [{metric_expr}]: {e}")
        return []


def generate_baseline_data(n: int = MIN_POINTS) -> np.ndarray:
    """
    Sinh dữ liệu nền (baseline) khi Prometheus chưa đủ dữ liệu.
    """
    np.random.seed(42)
    request_rate = np.random.normal(loc=0.5,  scale=0.05, size=n).clip(0.1, 2.0)
    avg_latency  = np.random.normal(loc=0.05, scale=0.01, size=n).clip(0.01, 0.2)
    cpu_percent  = np.random.normal(loc=20.0, scale=3.0,  size=n).clip(5.0, 40.0)
    return np.column_stack([request_rate, avg_latency, cpu_percent])


# ---------------------------------------------------------------------------
# ISOLATION FOREST - Thuật toán phát hiện bất thường & XAI RCA
# ---------------------------------------------------------------------------

def build_feature_matrix(
    request_rates: list[float],
    latencies    : list[float],
    cpu_percents : list[float]
) -> np.ndarray | None:
    """
    Xây dựng ma trận đặc trưng từ 3 chuỗi thời gian:
      [request_rate, avg_latency, cpu_percent]
    """
    min_len = min(len(request_rates), len(latencies), len(cpu_percents))
    if min_len < 2:
        return None
    
    X = np.column_stack([
        request_rates[-min_len:],
        latencies[-min_len:],
        cpu_percents[-min_len:]
    ])
    X = X[np.isfinite(X).all(axis=1)]
    return X if len(X) >= 2 else None


def train_and_score(X: np.ndarray) -> tuple[float, dict[str, float]]:
    """
    Huấn luyện Isolation Forest và tính toán XAI Feature Attribution.
    """
    # === BƯỚC 1: Chuẩn hóa dữ liệu ===
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # === BƯỚC 2: Huấn luyện Isolation Forest ===
    model = IsolationForest(
        contamination=0.1,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_scaled)
    
    # === BƯỚC 3: Chấm điểm cho điểm dữ liệu MỚI NHẤT ===
    latest_point = X_scaled[[-1]]
    raw_score = model.decision_function(latest_point)[0]
    normalized_score = 1.0 / (1.0 + math.exp(5.0 * raw_score))
    score = float(np.clip(normalized_score, 0.0, 1.0))
    
    # === BƯỚC 4: XAI Feature Attribution (Root Cause Analysis - RCA) ===
    abs_deviations = np.abs(latest_point[0])
    total_dev = float(np.sum(abs_deviations))
    if total_dev > 1e-6:
        attr_weights = abs_deviations / total_dev
    else:
        attr_weights = np.array([0.333, 0.333, 0.334])
        
    attribution = {
        "request_rate": float(attr_weights[0]),
        "latency": float(attr_weights[1]),
        "cpu": float(attr_weights[2])
    }
    
    return score, attribution


# ---------------------------------------------------------------------------
# Vòng lặp phát hiện bất thường chính
# ---------------------------------------------------------------------------

def detection_loop():
    """
    Vòng lặp chạy vô hạn, mỗi SCRAPE_INTERVAL giây:
      1. Lấy dữ liệu Sliding Window từ Prometheus
      2. Chống nhiễm độc Baseline khi có sự cố kéo dài
      3. Huấn luyện Isolation Forest + tính điểm + XAI RCA
      4. Closed-loop Remediation (Self-healing) khi lỗi kéo dài
      5. Expose metrics ngược lại cho Prometheus
    """
    log.info("AI Detector bắt đầu vòng lặp phát hiện bất thường...")
    golden_baseline = generate_baseline_data(MIN_POINTS)
    consecutive_anomalies = 0
    
    while True:
        try:
            request_rates = query_prometheus_range(
                'rate(app_requests_total[30s])'
            )
            latencies = query_prometheus_range(
                'rate(app_request_latency_seconds_sum[30s]) / rate(app_request_latency_seconds_count[30s])'
            )
            cpu_percents = query_prometheus_range(
                'app_simulated_cpu_percent'
            )
            
            min_len = min(len(request_rates), len(latencies), len(cpu_percents))
            log.info(f"Dữ liệu thu thập: {min_len} điểm thời gian")
            
            if min_len < MIN_POINTS:
                log.info(f"Chưa đủ dữ liệu ({min_len}/{MIN_POINTS} điểm). Dùng baseline tổng hợp...")
                if min_len >= 2:
                    real_data = build_feature_matrix(request_rates, latencies, cpu_percents)
                    X = np.vstack([golden_baseline, real_data]) if real_data is not None else golden_baseline
                else:
                    X = golden_baseline
            else:
                real_data = build_feature_matrix(request_rates, latencies, cpu_percents)
                if real_data is None:
                    log.warning("Không thể xây dựng feature matrix. Bỏ qua lần này.")
                    DETECTOR_HEALTH.set(0)
                    time.sleep(SCRAPE_INTERVAL)
                    continue
                
                # Chống nhiễm độc baseline khi có anomaly
                if consecutive_anomalies > 0:
                    X = np.vstack([golden_baseline, real_data])
                else:
                    X = real_data
            
            score, attribution = train_and_score(X)
            is_anomaly = 1 if score > ANOMALY_THRESHOLD else 0
            
            ANOMALY_SCORE.set(score)
            IS_ANOMALY.set(is_anomaly)
            DETECTOR_HEALTH.set(1)
            
            FEATURE_ATTRIBUTION.labels(feature="request_rate").set(attribution["request_rate"])
            FEATURE_ATTRIBUTION.labels(feature="latency").set(attribution["latency"])
            FEATURE_ATTRIBUTION.labels(feature="cpu").set(attribution["cpu"])
            
            status_str = "ANOMALY" if is_anomaly else "NORMAL"
            rca_summary = f"RCA [Latency: {attribution['latency']*100:.1f}%, CPU: {attribution['cpu']*100:.1f}%, RPS: {attribution['request_rate']*100:.1f}%]"
            log.info(f"AI Score: {score:.3f} | {status_str} (Threshold: {ANOMALY_THRESHOLD}) | {rca_summary}")
            
            # Closed-Loop Remediation
            if is_anomaly:
                consecutive_anomalies += 1
                if AUTO_REMEDIATION_ENABLED and consecutive_anomalies >= AUTO_REMEDIATION_STREAK:
                    log.warning(f"[Self-Healing] Persistent anomaly detected for {consecutive_anomalies} cycles. Triggering Auto-Remediation...")
                    try:
                        resp = requests.post(APP_REMEDIATION_URL, timeout=3)
                        if resp.status_code == 200:
                            REMEDIATION_TRIGGER_COUNTER.inc()
                            log.info("[Self-Healing] Microservice successfully restored to healthy baseline!")
                    except Exception as err:
                        log.error(f"[Self-Healing] Failed to trigger remediation: {err}")
                    consecutive_anomalies = 0
            else:
                consecutive_anomalies = 0
        
        except Exception as e:
            log.error(f"Lỗi trong detection loop: {e}", exc_info=True)
            DETECTOR_HEALTH.set(0)
        
        time.sleep(SCRAPE_INTERVAL)


# ---------------------------------------------------------------------------
# Điểm khởi động
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    detector_thread = threading.Thread(target=detection_loop, daemon=True)
    detector_thread.start()
    
    log.info("AI Detector HTTP server khởi động trên port 8001...")
    flask_app.run(host="0.0.0.0", port=8001, debug=False)
