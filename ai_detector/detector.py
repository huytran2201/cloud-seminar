"""
ai_detector/detector.py - AIOps Worker (Isolation Forest)
==========================================================
Vòng lặp chính của AI Detector:
  1. Mỗi 5 giây: gọi Prometheus API lấy dữ liệu chuỗi thời gian (Sliding Window 5 phút)
  2. Huấn luyện lại Isolation Forest trên cửa sổ dữ liệu hiện tại
  3. Chấm điểm điểm dữ liệu mới nhất → ai_anomaly_score [0.0, 1.0]
  4. Publish kết quả qua /metrics để Prometheus thu thập ngược lại
"""

import time
import math
import logging
import threading
import numpy as np
import requests

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST
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
PROMETHEUS_URL   = "http://prometheus:9090"
SCRAPE_INTERVAL  = 5          # giây giữa các lần phân tích
WINDOW_MINUTES   = 5          # cửa sổ trượt lấy dữ liệu (phút)
MIN_POINTS       = 20         # số điểm tối thiểu để huấn luyện mô hình
ANOMALY_THRESHOLD = 0.7       # ngưỡng: score > 0.7 → bất thường

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
    
    Args:
        metric_expr: PromQL expression (ví dụ: 'rate(app_requests_total[1m])')
        minutes    : độ rộng cửa sổ trượt (phút)
    
    Returns:
        Danh sách giá trị float theo thứ tự thời gian (cũ → mới)
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
        
        # Lấy series đầu tiên, trích xuất giá trị (bỏ timestamp)
        values = [float(v[1]) for v in results[0]["values"] if v[1] != "NaN"]
        return values
    
    except Exception as e:
        log.warning(f"Lỗi query Prometheus [{metric_expr}]: {e}")
        return []


def generate_baseline_data(n: int = MIN_POINTS) -> np.ndarray:
    """
    Sinh dữ liệu nền (baseline) khi Prometheus chưa đủ dữ liệu.
    
    Lý do cần thiết: Khi mới khởi động container, Prometheus chưa thu thập
    đủ MIN_POINTS mẫu. Thay vì chờ đợi (gây lỗi khi demo gấp), ta tự sinh
    dữ liệu giả lập trạng thái bình thường để mô hình có baseline để so sánh.
    
    Dữ liệu sinh ra phản ánh trạng thái "bình thường":
      - request_rate : ~0.5 req/s (ổn định)
      - avg_latency  : ~0.05s (nhanh)
      - cpu_percent  : ~20% (thấp)
    """
    np.random.seed(42)
    request_rate = np.random.normal(loc=0.5,  scale=0.05, size=n).clip(0.1, 2.0)
    avg_latency  = np.random.normal(loc=0.05, scale=0.01, size=n).clip(0.01, 0.2)
    cpu_percent  = np.random.normal(loc=20.0, scale=3.0,  size=n).clip(5.0, 40.0)
    return np.column_stack([request_rate, avg_latency, cpu_percent])


# ---------------------------------------------------------------------------
# ISOLATION FOREST - Thuật toán phát hiện bất thường
# ---------------------------------------------------------------------------

def build_feature_matrix(
    request_rates: list[float],
    latencies    : list[float],
    cpu_percents : list[float]
) -> np.ndarray | None:
    """
    Xây dựng ma trận đặc trưng (feature matrix) từ 3 chuỗi thời gian.
    
    Mỗi hàng = một điểm thời gian, 3 cột = 3 đặc trưng:
      [request_rate, avg_latency, cpu_percent]
    
    Chỉ lấy các dòng có đủ 3 giá trị hợp lệ.
    """
    min_len = min(len(request_rates), len(latencies), len(cpu_percents))
    if min_len < 2:
        return None
    
    X = np.column_stack([
        request_rates[-min_len:],
        latencies[-min_len:],
        cpu_percents[-min_len:]
    ])
    # Lọc bỏ các hàng chứa NaN hoặc Inf
    X = X[np.isfinite(X).all(axis=1)]
    return X if len(X) >= 2 else None


def train_and_score(X: np.ndarray) -> float:
    """
    THUẬT TOÁN ISOLATION FOREST - Giải thích từng bước:
    
    ┌─────────────────────────────────────────────────────────────────┐
    │ BƯỚC 1: CHUẨN HÓA DỮ LIỆU (StandardScaler)                    │
    │   Đưa tất cả đặc trưng về cùng thang đo (mean=0, std=1)        │
    │   → Tránh đặc trưng có giá trị lớn áp đảo đặc trưng nhỏ       │
    └─────────────────────────────────────────────────────────────────┘
    ┌─────────────────────────────────────────────────────────────────┐
    │ BƯỚC 2: HUẤN LUYỆN ISOLATION FOREST trên cửa sổ trượt         │
    │   - Xây dựng N cây quyết định ngẫu nhiên (Isolation Trees)     │
    │   - Mỗi cây: liên tục chia ngẫu nhiên không gian đặc trưng     │
    │   - Điểm BẤT THƯỜNG bị cô lập nhanh hơn (gần gốc cây)        │
    │   - Điểm BÌNH THƯỜNG cần nhiều bước phân chia hơn (sâu hơn)   │
    │                                                                 │
    │   Tham số:                                                      │
    │   - contamination=0.1 : giả định 10% dữ liệu là bất thường    │
    │   - n_estimators=100  : số cây (mặc định sklearn)              │
    │   - random_state=42   : đảm bảo kết quả tái tạo được          │
    └─────────────────────────────────────────────────────────────────┘
    ┌─────────────────────────────────────────────────────────────────┐
    │ BƯỚC 3: TÍNH ANOMALY SCORE cho điểm MỚI NHẤT                  │
    │   - decision_function() trả về score thô ∈ (-∞, +∞)           │
    │   - Score âm → bất thường | Score dương → bình thường          │
    │   - Chuẩn hóa về [0.0, 1.0] bằng sigmoid-like mapping         │
    └─────────────────────────────────────────────────────────────────┘
    
    Args:
        X: Ma trận đặc trưng [n_samples, 3], cột cuối là điểm mới nhất cần chấm
    
    Returns:
        score: float ∈ [0.0, 1.0], càng gần 1.0 càng bất thường
    """
    # === BƯỚC 1: Chuẩn hóa dữ liệu ===
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # === BƯỚC 2: Huấn luyện Isolation Forest trên toàn cửa sổ trượt ===
    model = IsolationForest(
        contamination=0.1,   # Giả định 10% dữ liệu trong cửa sổ là bất thường
        random_state=42,     # Seed cố định để kết quả ổn định khi demo
        n_jobs=-1            # Sử dụng tất cả CPU cores để huấn luyện nhanh
    )
    model.fit(X_scaled)
    
    # === BƯỚC 3: Chấm điểm cho điểm dữ liệu MỚI NHẤT (hàng cuối) ===
    latest_point = X_scaled[[-1]]            # Lấy hàng cuối (mới nhất)
    raw_score = model.decision_function(latest_point)[0]
    
    # Chuyển đổi raw_score → [0.0, 1.0]:
    # - decision_function ∈ (-∞, +∞)
    # - Dùng công thức: score = 1 / (1 + exp(5 * raw_score))
    # - raw_score rất âm (rất bất thường) → score gần 1.0
    # - raw_score rất dương (rất bình thường) → score gần 0.0
    normalized_score = 1.0 / (1.0 + math.exp(5.0 * raw_score))
    
    return float(np.clip(normalized_score, 0.0, 1.0))


# ---------------------------------------------------------------------------
# Vòng lặp phát hiện bất thường chính
# ---------------------------------------------------------------------------

def detection_loop():
    """
    Vòng lặp chạy vô hạn, mỗi SCRAPE_INTERVAL giây:
      1. Lấy dữ liệu Sliding Window từ Prometheus
      2. Nếu chưa đủ dữ liệu → dùng baseline tổng hợp
      3. Huấn luyện + chấm điểm Isolation Forest
      4. Cập nhật Gauge metrics để Prometheus thu thập
    """
    log.info("AI Detector bắt đầu vòng lặp phát hiện bất thường...")
    
    while True:
        try:
            # --- Thu thập dữ liệu Sliding Window (5 phút gần nhất) ---
            request_rates = query_prometheus_range(
                'rate(app_requests_total[1m])'
            )
            latencies = query_prometheus_range(
                'rate(app_request_latency_seconds_sum[1m]) / rate(app_request_latency_seconds_count[1m])'
            )
            cpu_percents = query_prometheus_range(
                'app_simulated_cpu_percent'
            )
            
            min_len = min(len(request_rates), len(latencies), len(cpu_percents))
            log.info(f"Dữ liệu thu thập: {min_len} điểm thời gian")
            
            # --- Kiểm tra đủ dữ liệu chưa ---
            if min_len < MIN_POINTS:
                log.info(
                    f"Chưa đủ dữ liệu ({min_len}/{MIN_POINTS} điểm). "
                    f"Dùng baseline tổng hợp để khởi động nhanh..."
                )
                # Sinh dữ liệu baseline, ghép với điểm thực có sẵn (nếu có)
                baseline = generate_baseline_data(MIN_POINTS)
                
                if min_len >= 2:
                    # Có một ít dữ liệu thực → thêm vào cuối baseline
                    real_data = build_feature_matrix(request_rates, latencies, cpu_percents)
                    if real_data is not None:
                        X = np.vstack([baseline, real_data])
                    else:
                        X = baseline
                else:
                    X = baseline
            else:
                # Đủ dữ liệu thực → xây dựng ma trận đặc trưng từ dữ liệu Prometheus
                X = build_feature_matrix(request_rates, latencies, cpu_percents)
                if X is None:
                    log.warning("Không thể xây dựng feature matrix. Bỏ qua lần này.")
                    DETECTOR_HEALTH.set(0)
                    time.sleep(SCRAPE_INTERVAL)
                    continue
            
            # --- Chạy Isolation Forest → lấy anomaly score ---
            score = train_and_score(X)
            is_anomaly = 1 if score > ANOMALY_THRESHOLD else 0
            
            # --- Cập nhật metrics để Prometheus thu thập ---
            ANOMALY_SCORE.set(score)
            IS_ANOMALY.set(is_anomaly)
            DETECTOR_HEALTH.set(1)
            
            status_emoji = "🚨 BẤT THƯỜNG" if is_anomaly else "✅ Bình thường"
            log.info(f"AI Score: {score:.3f} | {status_emoji} (ngưỡng: {ANOMALY_THRESHOLD})")
        
        except Exception as e:
            log.error(f"Lỗi trong detection loop: {e}", exc_info=True)
            DETECTOR_HEALTH.set(0)
        
        time.sleep(SCRAPE_INTERVAL)


# ---------------------------------------------------------------------------
# Điểm khởi động
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Chạy detection loop trong thread riêng (daemon)
    detector_thread = threading.Thread(target=detection_loop, daemon=True)
    detector_thread.start()
    
    # Chạy Flask server để expose /metrics trên port 8001
    log.info("AI Detector HTTP server khởi động trên port 8001...")
    flask_app.run(host="0.0.0.0", port=8001, debug=False)
