# AIOps & Cloud Monitoring Demo
## Phát hiện bất thường động bằng Isolation Forest

> **Môn:** Điện toán đám mây | **Mục tiêu:** Minh họa AIOps phát hiện bất thường hành vi mà threshold tĩnh bỏ sót

---

## 🏗️ Kiến trúc hệ thống

```
traffic_sim.py (host)
       │  HTTP requests
       ▼
┌─────────────────────┐     scrape/5s    ┌───────────────────┐
│  app:8000           │◄─────────────────│  prometheus:9090  │
│  FastAPI + prom     │                  │  TSDB & Scraper   │
│  /api/process       │                  │                   │
│  /metrics           │◄─────────────────│                   │
└─────────────────────┘     scrape/5s    │                   │
                                         │                   │
┌─────────────────────┐     scrape/5s    │                   │
│  ai-detector:8001   │◄─────────────────│                   │
│  Isolation Forest   │                  └───────────────────┘
│  /metrics           │  query_range API         │
│  ai_anomaly_score   │──────────────────────────┘
└─────────────────────┘                           │
                                                  │ datasource
                                         ┌────────▼──────────┐
                                         │  grafana:3000      │
                                         │  Auto-provisioned  │
                                         │  Dashboard         │
                                         └───────────────────┘
```

---

## 🚀 Hướng dẫn chạy

### Bước 0: Đảm bảo Docker Desktop đang chạy

Mở **Docker Desktop** từ Start Menu → đợi biểu tượng cá voi ở taskbar chuyển sang **xanh** (WSL2 engine sẵn sàng).

Xác nhận bằng lệnh:

```powershell
docker info   # Phải thấy "Server Version: ..."
```

### Bước 1: Build và khởi động toàn bộ hệ thống

```powershell
cd "d:\BACHKHOA\YEAR3\HK1\Cloud\SEMINAR\DEMO"
docker-compose up -d --build
```

> Build lần đầu mất ~3-5 phút (tải scikit-learn). Các lần sau chỉ ~30 giây.
>
> **Lưu ý WSL2:** Docker Desktop dùng Ubuntu WSL2 làm backend — tất cả image chạy dưới Linux kernel, không cần thêm cấu hình gì.

### Bước 2: Kiểm tra tất cả services đang chạy

```powershell
docker-compose ps
```

Kết quả mong đợi: tất cả 4 services đều `Up` (Prometheus và Grafana sẽ có thêm `(healthy)`).

### Bước 3: Mở Grafana Dashboard

Truy cập: **http://localhost:3000**
- Username: `admin`
- Password: `admin123`
- Dashboard `AIOps - Dynamic Anomaly Detection` đã được import sẵn.

### Bước 4: Cài thư viện cho traffic simulator (máy host)

```bash
pip install requests
```

---

## 🎬 Kịch bản Demo 3 phút

### ⏱️ Phút 0:00 - 1:00 | Tạo baseline bình thường

Mở terminal 1, chạy traffic simulator chế độ normal:

```bash
python traffic_sim.py --mode normal
```

**Nói với khán giả:**
> "Hệ thống đang hoạt động bình thường. Trên Grafana, ta thấy CPU ~20%, latency ~50ms, AI score thấp ~0.2. Isolation Forest đang học pattern bình thường này."

### ⏱️ Phút 1:00 - 2:30 | Kích hoạt bất thường

Nhấn `Ctrl+C`, sau đó:

```bash
python traffic_sim.py --mode anomaly
```

**Nói với khán giả:**
> "Bây giờ tôi kích hoạt bất thường. Nhìn vào **Panel 1 (CPU)**: CPU chỉ lên ~45% — VẪN DƯỚI ngưỡng 80% — hệ thống truyền thống KHÔNG cảnh báo gì cả.
>
> Nhưng nhìn **Panel 3 (AI Score)**: chỉ sau vài chu kỳ, Isolation Forest nhận ra rằng **combination** (CPU 45% + latency 2s + request rate thay đổi) là bất thường trong context lịch sử → Score vọt lên > 0.7 → Cảnh báo đỏ!"

### ⏱️ Phút 2:30 - 3:00 | Tóm tắt

**Nói với khán giả:**
> "Đây là giá trị cốt lõi của AIOps: thay vì dùng ngưỡng cứng cho từng metric đơn lẻ, Isolation Forest phân tích **đa chiều** và phát hiện bất thường **hành vi** (behavior anomaly) mà con người khó thiết lập rule thủ công."

---

## 🛑 Dừng hệ thống

```powershell
docker-compose down
```

Nếu muốn xóa cả dữ liệu (volumes):

```powershell
docker-compose down -v
```

---

## 📊 Giải thích thuật toán Isolation Forest

| Khái niệm | Giải thích |
|-----------|-----------|
| **Isolation Tree** | Cây quyết định ngẫu nhiên chia không gian đặc trưng |
| **Isolation** | Điểm bất thường bị "cô lập" gần gốc cây (ít bước chia hơn) |
| **contamination=0.1** | Giả định 10% dữ liệu trong cửa sổ là bất thường |
| **Sliding Window** | Chỉ dùng 5 phút gần nhất → thích nghi với pattern thay đổi |
| **Score [0,1]** | Chuẩn hóa qua sigmoid, > 0.7 → kích cảnh báo |

---

## 📁 Cấu trúc thư mục

```
DEMO/
├── docker-compose.yml          # Orchestration
├── traffic_sim.py              # Script giả lập tải (chạy trên host)
├── README.md                   # File này
├── app/
│   ├── Dockerfile
│   ├── main.py                 # FastAPI microservice
│   └── requirements.txt
├── ai_detector/
│   ├── Dockerfile
│   ├── detector.py             # Isolation Forest worker
│   └── requirements.txt
├── prometheus/
│   └── prometheus.yml          # Scrape config
└── grafana/
    ├── provisioning/
    │   ├── datasources/
    │   │   └── prometheus.yml  # Auto-connect Prometheus
    │   └── dashboards/
    │       └── dashboard.yml   # Auto-import dashboard
    └── dashboards/
        └── aiops_dashboard.json # Dashboard definition
```
