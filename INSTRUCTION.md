
> **Đọc nhanh:** README.md dành cho người clone muốn cài và chạy demo. Tài liệu này giải thích sâu kiến trúc và thuật toán. Implementation hiện tại dùng metric CPU/RAM giả lập, target scrape tĩnh và remediation mô phỏng; kết quả kịch bản không phải benchmark production.

## MỤC LỤC TỔNG QUAN
1. [Bối cảnh SRE, Cloud-Native và Bài toán Gray Failure](#1-bối-cảnh-sre-cloud-native-và-bài-toán-gray-failure)
2. [Kiến trúc Cloud-Native Microservices Phân tán](#2-kiến-trúc-cloud-native-microservices-phân-tán)
3. [Phân tích Chi tiết Từng Thành phần Kỹ thuật](#3-phân-tích-chi-tiết-từng-thành-phần-kỹ-thuật)
4. [Cơ sở Lý thuyết Toán học và Thuật toán AIOps](#4-cơ-sở-lý-thuyết-toán-học-và-thuật-toán-aiops)
5. [Đánh giá Định lượng Chỉ số SRE (MTTD, MTTR, SLA/SLO)](#5-đánh-giá-định-lượng-chỉ-số-sre-mttd-mttr-slaslo)
6. [Runbook Vận hành và Kịch bản Thuyết trình Mẫu (Demo Playbook)](#6-runbook-vận-hành-và-kịch-bản-thuyết-trình-mẫu-demo-playbook)
7. [Định hướng Nâng cấp Production-Ready Cloud Architecture](#7-định-hướng-nâng-cấp-production-ready-cloud-architecture)

---

## 1. Bối cảnh SRE, Cloud-Native và Bài toán Gray Failure

### 1.1. Thách thức Giám sát trong Kỷ nguyên Đám mây
Trong các hệ thống phân tán Cloud-Native hiện đại (Kubernetes, Microservices, Serverless), việc bảo đảm tính sẵn sàng cao (High Availability) và độ tin cậy dịch vụ (Service Reliability) đối mặt với hai đặc tính hạ tầng then chốt:
- **Tính co giãn động (Elasticity / Autoscaling):** Tải của hệ thống biến động liên tục theo thời gian thực.
- **Tính tạm thời của Container (Ephemeral Nature):** Các Pod/Container liên tục được sinh ra, tiêu hủy, hoặc tái điều phối qua các node vật lý khác nhau.

### 1.2. Khái niệm "Gray Failure" (Sự cố ngầm định)
Trong kỹ nghệ độ tin cậy hệ thống (SRE), các sự cố được chia làm hai nhóm chính:
1. **Crash Failure / Hard Failure (Sập cứng):** Tiến trình chết (Exit code 1, OOMKilled, CrashLoopBackOff), port bị đóng hoặc trả về mã lỗi `HTTP 500`. Dạng sự cố này cực kỳ dễ phát hiện thông qua Healthcheck probe đơn giản.
2. **Gray Failure (Lỗi xám / Suy thoái ngầm):**
   - Tiến trình vẫn sống bình thường, endpoint trả về mã `HTTP 200 OK`.
   - Metric CPU giả lập chỉ ở mức trung bình $\sim 40 - 45\%$ (hoàn toàn không chạm ngưỡng cảnh báo tĩnh $80\%$).
   - Tuy nhiên, **Độ trễ xử lý (Latency)** bị giật cục từ $30\text{ms}$ vọt lên $1.5 - 3.0\text{s}$ do nghẽn hàng đợi nội bộ, tranh chấp luồng (Thread Contention), rò rỉ bộ nhớ vi mô hoặc nghẽn Database Connection Pool.

```
Mức độ tiêu thụ tài nguyên
      ▲
 100% ┼───────────────────────────────────────────────────────────── (Ngưỡng tĩnh 80% CPU)
      │
  42% ┼──────────────● VÙNG SỰ CỐ GRAY FAILURE:
      │              │ - CPU chỉ 42% (Ngưỡng tĩnh KHÔNG BÁO ĐỘNG!)
      │              │ - Latency vọt x30 lần (30ms -> 2.5s)
  20% ┼─── Normal ───┘ - Trải nghiệm người dùng sụp đổ!
      └─────────────────────────────────────────────────────────────► Thời gian
```

### 1.3. Sự thất bại của Giám sát Ngưỡng tĩnh (Static Thresholds)
Hầu hết các hệ thống giám sát truyền thống chỉ đặt các luật ngưỡng cứng (ví dụ: `CPU > 80%` hoặc `RAM > 85%`). Trên môi trường Cloud, tiếp cận này gây ra 2 thảm họa vận hành:
- **False Negatives (Chết ngầm - Silent Outages):** Khi xảy ra Gray Failure, CPU không chạm $80\%$, hệ thống giám sát im lặng hoàn toàn trong khi khách hàng rời bỏ dịch vụ.
- **Alert Fatigue (Báo động giả tràn lan):** Khi có đợt truy cập tăng đột biến tạm thời (Flash Crowd), CPU có thể chạm $85\%$ trong vài giây trước khi hệ thống kịp scale-out, kích hoạt hàng loạt chuông báo giả khiến kỹ sư trực ca bị quá tải và tê liệt phản ứng.

$\implies$ **Giải pháp:** Áp dụng **AIOps (Artificial Intelligence for IT Operations)** với thuật toán Machine Learning không giám sát (**Isolation Forest**) để giám sát **mối tương quan hành vi đa biến** giữa lưu lượng truy cập (Traffic Rate), độ trễ (Latency) và tài nguyên (CPU/RAM).

---

## 2. Kiến trúc Cloud-Native Microservices Phân tán

Hệ thống được thiết kế theo kiến trúc Microservices phân tán độc lập, đóng gói hoàn toàn trong Docker Containers thông qua [docker-compose.yml](./docker-compose.yml):

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ MÁY CHỦ HOST / CLIENT                                                          │
│ • run_demo.py (Interactive 1-Click Runner)                                     │
│ • traffic_sim.py (Traffic Generator & Chaos Engine)                            │
└──────────────────────────────────────┬─────────────────────────────────────────┘
                                       │ HTTP Requests (:8000)
                                       ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│ DOCKER BRIDGE NETWORK: aiops-net (Cơ chế mạng ảo VPC thu nhỏ)                  │
│                                                                                │
│  ┌───────────────────────┐   Scrape HTTP GET /metrics    ┌──────────────────┐  │
│  │ app:8000 (Stateless)  │◄──────────────────────────────│ prometheus:9090  │  │
│  │ FastAPI Microservice  │                               │ (Stateful TSDB)  │  │
│  │ - /api/process (Load) │                               │ - Scraper chu kỳ │  │
│  │ - /api/remediate (Heal│                               │   mỗi 5 giây     │  │
│  │ - /metrics (Prom)     │                               │ - Evaluates Rules│  │
│  └───────────▲───────────┘                               └─────────┬────────┘  │
│              │                                                     │           │
│              │ Self-Healing Webhook                                │ Query     │
│              │ POST /api/remediate (khi score > 0.7 trong 15s)     │ Range API │
│              │                                                     │           │
│  ┌───────────┴───────────┐   Scrape HTTP GET /metrics              │           │
│  │ ai-detector:8001      │◄────────────────────────────────────────┘           │
│  │ (Stateless Worker)    │                                                     │
│  │ - Isolation Forest ML │                                                     │
│  │ - XAI RCA Attribution │                                                     │
│  │ - Drift Shield        │                                                     │
│  └───────────────────────┘                                                     │
│                                                          ┌──────────────────┐  │
│                                      Datasource Query    │ grafana:3000     │  │
│                                      (Auto-Provisioned)  │ (Stateful UI)    │  │
│                                                          │ - 6 Live Panels  │  │
│                                                          └──────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────┘
       ▲                                                           ▲
       │                                                           │
┌──────┴──────────────┐                                     ┌──────┴───────────┐
│ prometheus-data     │                                     │ grafana-data     │
│ (Persistent Volume) │                                     │ (Persistent Vol) │
└─────────────────────┘                                     └──────────────────┘
```

### 2.1. Phân định Stateless vs Stateful
- **Stateless Services (`app`, `ai-detector`):**
  - Không lưu trữ trạng thái người dùng trên ổ đĩa cục bộ của container.
  - Có thể khởi động, hủy bỏ, hoặc mở rộng quy mô (Scale-out) thành nhiều bản sao phía sau một Load Balancer (Reverse Proxy như Nginx/Envoy) một cách dễ dàng.
- **Stateful Services (`prometheus`, `grafana`):**
  - Cơ sở dữ liệu chuỗi thời gian TSDB của Prometheus và cấu hình Dashboard/Preferences của Grafana được gắn kết qua **Docker Named Volumes** (`prometheus-data`, `grafana-data`).
  - Dữ liệu lịch sử sống sót an toàn qua các chu kỳ tái khởi động hoặc nâng cấp image container (*Ephemeral Container vs Persistent Storage*).

### 2.2. Mạng Overlay và Cơ chế Khám phá Dịch vụ (Service Discovery)
- **Container Network Model (CNM):** Mạng bridge `aiops-net` đóng vai trò như một mạng nội bộ ảo VPC, cô lập hoàn toàn các container với môi trường mạng bên ngoài máy host.
- **Docker Embedded DNS Server (`127.0.0.11`):** Các service giao tiếp với nhau qua tên container thay vì địa chỉ IP tĩnh:
  - Prometheus scrape `http://app:8000/metrics` và `http://ai-detector:8001/metrics`.
  - AI Detector query chuỗi thời gian từ `http://prometheus:9090/api/v1/query_range`.
  - AI Detector gửi webhook phục hồi tới `http://app:8000/api/remediate`.
  - Docker DNS phân giải các tên này tự động, nhưng danh sách scrape target Prometheus nằm tĩnh trong `prometheus/prometheus.yml`; thêm target vẫn cần sửa `static_configs`.

### 2.3. Ràng buộc Khởi động (Healthcheck Chains)
Để tránh tình trạng "Race Condition" lúc khởi động (AI Detector gọi Prometheus khi server TSDB chưa sẵn sàng), [docker-compose.yml](./docker-compose.yml) thiết lập cấu hình:
```yaml
depends_on:
  prometheus:
    condition: service_healthy
```
Prometheus phải vượt qua kiểm tra sức khỏe HTTP probe (`wget --spider http://localhost:9090/-/healthy`) thì container AI Detector mới được cấp phép khởi động.

---

## 3. Phân tích Chi tiết Từng Thành phần Kỹ thuật

### 3.1. Target Microservice (`app/main.py`)
Microservice nghiệp vụ xây dựng trên nền tảng **FastAPI**, mô phỏng môi trường vi dịch vụ thực tế:
- **Endpoints:**
  - `GET /api/process?mode=normal|anomaly|memory_leak|jitter|error_burst`: Xử lý yêu cầu với các hành vi tải khác nhau.
  - `POST /api/remediate`: Endpoint remediation mô phỏng: đặt lại RAM giả lập về $128\text{MB}$, CPU giả lập về $20\%$ và tắt cờ anomaly override.
  - `GET /metrics`: Endpoint phơi dữ liệu chuẩn OpenMetrics cho Prometheus cào dữ liệu.
  - `GET /health`: Healthcheck probe xác nhận container hoạt động.
- **Các loại Metrics phơi ra (OpenMetrics Standard):**
  - `app_requests_total` (**Counter**): Đếm tổng số lượng request theo nhãn `mode`.
  - `app_request_latency_seconds` (**Histogram**): Đo độ trễ với 9 buckets: `[0.05, 0.1, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0]`. Là cơ sở tính toán phân vị độ trễ $p_{50}, p_{90}, p_{99}$ trong SRE.
  - `app_simulated_cpu_percent` (**Gauge**): Giá trị CPU giả lập do app tự đặt, không phải CPU thật của host/container.
  - `app_simulated_memory_mb` (**Gauge**): Giá trị RAM giả lập do app tự đặt.
  - `app_remediation_total` (**Counter**): Đếm tổng số lần hệ thống tự phục hồi thành công qua Self-Healing.

### 3.2. AIOps Worker (`ai_detector/detector.py`)
Là tiến trình phân tích thông minh hoạt động ở chế độ nền (Background Daemon Worker):
- **Sliding Window:** Mỗi $5\text{s}$, truy vấn Prometheus lấy dữ liệu 5 phút gần nhất ($60$ điểm mẫu) của 3 chuỗi thời gian:
  1. `rate(app_requests_total[1m])` (Lưu lượng RPS)
  2. `rate(app_request_latency_seconds_sum[1m]) / rate(app_request_latency_seconds_count[1m])` (Độ trễ trung bình)
  3. `app_simulated_cpu_percent` (Mức sử dụng CPU)
- **Cơ chế Cold-Start (Khởi động lạnh):** Khi hệ thống vừa bật, Prometheus chưa đủ $20$ điểm thời gian (`MIN_POINTS = 20`), hàm `generate_baseline_data()` tự sinh tập dữ liệu chuẩn Gaussian $(\mu_{\text{rps}}=0.5, \mu_{\text{lat}}=0.05\text{s}, \mu_{\text{cpu}}=20\%)$ để mô hình có dữ liệu tham chiếu ngay lập tức, không gây treo hệ thống.
- **Chống nhiễm độc Baseline (Drift / Poisoning Prevention):** Nếu xảy ra sự cố kéo dài (ví dụ chạy anomaly liên tục 5 phút), các điểm lỗi sẽ chiếm đa số trong cửa sổ trượt khiến mô hình tự "bình thường hóa" cái sai. Hệ thống tự động kích hoạt **Golden Baseline Injection** (`np.vstack([golden_baseline, real_data])`), bảo toàn ký ức lành mạnh của hệ thống.
- **XAI Feature Attribution (Root Cause Analysis - RCA):** Bóc tách độ lệch chuẩn $z_i$ để tính toán tỷ lệ đóng góp của từng đặc trưng vào sự cố, phơi ra qua metric `ai_feature_attribution{feature="latency|cpu|request_rate"}`.
- **Auto-remediation demo:** Khi `is_anomaly == 1` liên tục trong 20 chu kỳ ($100\text{s}$), AI Detector POST tới `http://app:8000/api/remediate`. Endpoint chỉ đặt lại metric/trạng thái mô phỏng; không restart container hoặc sửa hạ tầng thật. Phase 4 của `run_demo.py` cũng gọi endpoint này trực tiếp.

### 3.3. Prometheus Engine (`prometheus/`)
- **Mô hình Thu thập (Pull-based Model):** Định kỳ $5\text{s}$, Prometheus chủ động gửi HTTP GET tới cổng `/metrics` của từng container.
  - *Ưu thế trong Cloud:* Tránh tình trạng nghẽn đường truyền khi hàng ngàn container ồ ạt push dữ liệu; dễ dàng kiểm soát tốc độ ghi; phát hiện ngay container bị chết nếu request timeout.
- **Cơ sở dữ liệu chuỗi thời gian (TSDB):**
  - Dữ liệu được nén theo thuật toán Gorilla (Delta-of-delta timestamp và XOR floating-point values), tối ưu hóa dung lượng lưu trữ trên disk.
  - Sử dụng Write-Ahead Log (WAL) để chống mất mát dữ liệu khi container bị tắt đột ngột.
- **Hệ thống Alerting Rules ([alert.rules.yml](./prometheus/alert.rules.yml)):** gồm target down, latency trung bình trên 1 giây, CPU giả lập trên 80% và AI anomaly score trên 0.70; mỗi rule yêu cầu điều kiện tồn tại 10 giây.
  - `HighRequestLatency` là cảnh báo ngưỡng latency, độc lập với AI. Vì vậy Gray Failure có thể làm cảnh báo latency firing dù CPU dưới 80%.
  - `AIOpsAnomalyDetected` là cảnh báo riêng dựa trên score AI > 0.70.

### 3.4. Grafana Visualization ([grafana/dashboards/aiops_dashboard.json](./grafana/dashboards/aiops_dashboard.json))
Tự động nạp cấu hình qua YAML (Observability-as-Code), trực quan hóa 6 Panels chuyên nghiệp:
- **Panel 1 (CPU Usage vs 80% Threshold):** Thể hiện sự bất lực của giám sát truyền thống khi CPU chỉ ở mức $\sim 42\%$.
- **Panel 2 (Request Latency Time-Series):** Hiển thị rõ độ trễ giật cục từ $40\text{ms}$ vọt lên $2.5\text{s}$.
- **Panel 3 (AI Anomaly Score):** Đường cong điểm bất thường của Isolation Forest vọt qua ngưỡng đỏ $0.7$.
- **Panel 4 (AI Detection Status):** Stat badge màu chuyển từ Xanh (`✅ BÌNH THƯỜNG`) sang Đỏ (`🚨 BẤT THƯỜNG`).
- **Panel 5 (XAI Root Cause Analysis):** Bar Gauge hiển thị % đóng góp nguyên nhân (Latency $\sim 78\%$, CPU $\sim 16\%$, RPS $\sim 6\%$).
- **Panel 6 (Self-Healing Remediation Events):** Đếm số lần hệ thống tự động phục hồi thành công.

---

## 4. Cơ sở Lý thuyết Toán học và Thuật toán AIOps

### 4.1. Bản chất Toán học của Isolation Forest
Được đề xuất bởi Liu, Ting và Zhou (2008), Isolation Forest khai thác hai đặc tính cơ bản của dữ liệu bất thường:
1. Số lượng rất ít (Minority).
2. Giá trị các đặc trưng sai lệch đáng kể so với phân bố chung (Attribute-value difference).

Thay vì tính toán khoảng cách hình học hay mật độ lân cận tốn kém độ phức tạp $O(N^2)$, Isolation Forest xây dựng một tập hợp gồm $T$ cây cô lập nhị phân ngẫu nhiên (**Isolation Trees - iTree**).

```
          [Root Node: Không gian đa biến toàn thể]
                         /          \
               (x_latency < 0.5s)   (x_latency >= 0.5s)
                     /                    \
              [Điểm bình thường]       [ĐIỂM BẤT THƯỜNG]
              (Cần nhiều lần cắt)     (Bị cô lập ngay tại độ sâu h = 1!)
```

#### Chiều dài đường đi trung bình trong cây nhị phân không thành công:
Đối với một tập dữ liệu gồm $n$ mẫu, chiều dài đường đi trung bình $c(n)$ của cây tìm kiếm nhị phân được tính bằng công thức:
$$c(n) = 2 \left( \ln(n - 1) + 0.5772156649 \right) - \frac{2(n - 1)}{n}$$
*(trong đó $0.5772156649$ là hằng số Euler-Mascheroni).*

#### Điểm số bất thường lý thuyết (Anomaly Score):
Điểm số bất thường $s(x, n)$ của một điểm dữ liệu $x$ trên tập hợp các cây iTree được định nghĩa:
$$s(x, n) = 2^{-\frac{\mathbb{E}(h(x))}{c(n)}}$$
- Nếu kỳ vọng độ sâu $\mathbb{E}(h(x)) \to 0 \implies s \to 1$: Điểm $x$ bị cô lập cực nhanh ở gần gốc $\rightarrow$ **Chắc chắn là bất thường**.
- Nếu $\mathbb{E}(h(x)) \to n - 1 \implies s \to 0$: Điểm $x$ nằm sâu trong tán cây $\rightarrow$ **Hoàn toàn bình thường**.
- Nếu $\mathbb{E}(h(x)) \to c(n) \implies s \to 0.5$: Phân bố đồng nhất, không phát hiện dấu hiệu bất thường.

### 4.2. Chuẩn hóa Sigmoid trong Source Code
Trong Scikit-Learn, hàm `decision_function()` trả về giá trị thô:
$$\text{raw\_score} \in (-\infty, +\infty)$$
*(Giá trị âm biểu thị bất thường, giá trị dương biểu thị bình thường).*

Trong [ai_detector/detector.py](./ai_detector/detector.py), thuật toán áp dụng ánh xạ hàm Sigmoid nghịch đảo có trọng số để đưa về thang điểm chuẩn hóa $[0.0, 1.0]$ (không phải xác suất đã hiệu chỉnh):
$$\text{ai\_anomaly\_score} = \frac{1}{1 + e^{5.0 \times \text{raw\_score}}}$$
- Khi $\text{raw\_score} \ll 0$ (rất bất thường) $\implies e^{5.0 \times \text{raw\_score}} \to 0 \implies \text{score} \to 1.0$.
- Khi $\text{raw\_score} \gg 0$ (rất bình thường) $\implies e^{5.0 \times \text{raw\_score}} \to \infty \implies \text{score} \to 0.0$.
- Ngưỡng quyết định tối ưu được chọn là: $\text{Threshold} = 0.70$.

### 4.3. Toán học của XAI Feature Attribution (Giải thích Nguyên nhân Gốc rễ)
Sau khi dữ liệu được đưa qua bộ chuẩn hóa `StandardScaler`:
$$z_{i} = \frac{x_{\text{latest}, i} - \mu_{i}}{\sigma_{i}}$$
Độ lệch tuyệt đối $|z_i|$ phản ánh mức độ "rời xa" giá trị trung bình lịch sử của đặc trưng thứ $i$. Tỷ lệ đóng góp $w_i$ được chuẩn hóa theo công thức:
$$w_{i} = \frac{|z_{i}|}{\sum_{j=1}^{M} |z_{j}| + \epsilon}$$
Kết quả định lượng được phơi ra Dashboard:
$$\text{Latency Attribution} \approx 78\%, \quad \text{CPU Attribution} \approx 16\%, \quad \text{RPS Attribution} \approx 6\%$$
Điều này chứng minh cho kỹ sư SRE thấy: **Sự cố bắt nguồn từ độ trễ phản hồi của ứng dụng chứ không phải do quá tải năng lực tính toán của CPU**.

---

## 5. Đánh giá Định lượng Chỉ số SRE (MTTD, MTTR, SLA/SLO)

| Chỉ số SRE | Giám sát Ngưỡng tĩnh (Cũ) | Hệ thống AIOps Dynamic (Mới) | Lợi ích Đạt được |
|:---|:---:|:---:|:---|
| **MTTD (Mean Time to Detect)** | Chưa đo trong dự án | Rule cần giữ điều kiện 10 giây, cộng chu kỳ scrape/evaluation và group wait | Cấu hình minh họa luồng alert, chưa phải benchmark |
| **MTTR (Mean Time to Recover)** | Chưa đo trong dự án | Phase 4 gọi endpoint reset trạng thái mô phỏng | Không phải thời gian khôi phục production |
| **False Positives / False Negatives** | Chưa đánh giá thống kê | Có ví dụ kịch bản CPU threshold và AI score | Cần tập dữ liệu lớn hơn để kết luận tỷ lệ |
| **Error Budget / SLA** | Chưa triển khai | Chưa tính error budget hoặc xác minh SLA 99.9% | Có thể phát triển thêm sau demo |

---

## 6. Runbook Vận hành và Kịch bản Thuyết trình Mẫu (Demo Playbook)

### 6.1. Hướng dẫn Khởi động Hạ tầng
1. Làm theo phần Quick Start trong README để tạo `.venv` và cài `requests`.
2. Mở **Docker Desktop**, vào thư mục `cloud-seminar` rồi chạy `start_demo.bat`. Lệnh này build stack, chờ các endpoint health, mở Grafana/Prometheus/Alertmanager/receiver và chạy demo tương tác.
3. Có 6 services: app, AI Detector, Prometheus, Alertmanager, receiver và Grafana. Kiểm tra bằng `docker-compose ps`.
4. Grafana ở `http://localhost:3000` (tài khoản `admin` / `admin123`). Receiver dùng cổng host động; lấy URL từ dòng in trong terminal.

---

### 6.2. Kịch bản Thuyết trình Mẫu 3 Phút (Dành cho Sinh viên Báo cáo Hội đồng)

`start_demo.bat` tự khởi động stack và gọi runner ở chế độ tương tác. Nếu stack đã chạy và chỉ muốn chạy lại kịch bản, dùng:
```powershell
.\.venv\Scripts\python.exe run_demo.py --interactive
```

#### ⏱️ Phút 0:00 - 0:45 | Giai đoạn 1: Thiết lập Golden Baseline
- **Hành động trên terminal:** Script tự động gửi traffic bình thường `mode=normal` (2 req/s).
- **Lời thoại thuyết trình trước Hội đồng:**
  > *"Kính thưa Thầy và các bạn, hệ thống microservice của nhóm đang xử lý các tác vụ thông thường. Quan sát trên Panel 1 và Panel 2 của Grafana, CPU chỉ tiêu thụ khoảng 20%, độ trễ xử lý rất nhanh và ổn định ở mức 40ms. Ở Panel 3, điểm số AI Anomaly Score duy trì ở mức an toàn dưới 0.2. Thuật toán Isolation Forest đang liên tục cập nhật và học phân bố hành vi bình thường của hệ thống trên cửa sổ trượt."*

#### ⏱️ Phút 0:45 - 1:30 | Giai đoạn 2: Tiêm lỗi Gray Failure
- **Hành động trên terminal:** Nhấn `[Enter]` để kích hoạt Phase 2 (`mode=anomaly`).
- **Lời thoại thuyết trình trước Hội đồng:**
  > *"Bây giờ nhóm tiêm Gray Failure. Panel 1 cho thấy CPU giả lập khoảng 42%, dưới ngưỡng CPU 80%, nên rule CPU không cảnh báo. Panel 2 cho thấy latency tăng; rule `HighRequestLatency` của Prometheus có thể cảnh báo độc lập với AI. Khi dữ liệu lệch khỏi baseline, AI score có thể vượt 0.70 và Panel 4 chuyển sang trạng thái bất thường. Giá trị và thời điểm cụ thể có thể thay đổi giữa các lần chạy."*

#### ⏱️ Phút 1:30 - 2:00 | Giai đoạn 3: Phân tích Nguyên nhân Gốc rễ (XAI RCA)
- **Hành động trên terminal:** Nhấn `[Enter]` để truy vấn metrics XAI từ Prometheus.
- **Lời thoại thuyết trình trước Hội đồng:**
  > *"Để chứng minh AI không phải là một hộp đen khó hiểu, xin mời Hội đồng nhìn vào Panel 5 (XAI Root Cause Analysis). Dựa trên độ lệch chuẩn đa biến, hệ thống đã chỉ ra chính xác: Độ trễ đóng góp tới gần 80% nguyên nhân sự cố, trong khi CPU chỉ đóng góp 16%. Điều này giúp đội ngũ SRE không bị định hướng sai lầm sang việc nâng cấp CPU mà tập trung ngay vào việc điều tra nghẽn luồng xử lý của ứng dụng."*

#### ⏱️ Phút 2:00 - 2:30 | Giai đoạn 4: Closed-Loop Remediation (Self-Healing)
- **Hành động trên terminal:** Nhấn `[Enter]` để kích hoạt Webhook tự chữa lành.
- **Lời thoại thuyết trình trước Hội đồng:**
  > *"Hệ thống không chỉ dừng lại ở mức phát hiện mà còn hoàn thiện chu trình tự trị khép kín (Closed-Loop). Phase 4 của demo runner chủ động POST tới `/api/remediate` để reset trạng thái metric mô phỏng. AI Detector có một nhánh auto-remediation riêng sau 20 chu kỳ anomaly liên tiếp (~100 giây); đây không phải hành động sửa hoặc restart hạ tầng thật. Ngay lập tức, Panel 6 ghi nhận hành động Self-Healing thành công và toàn bộ đồ thị trên Grafana đã hạ nhiệt về dải màu xanh an toàn!"*

#### ⏱️ Phút 2:30 - 3:00 | Giai đoạn 5: Tổng kết
- **Lời thoại thuyết trình trước Hội đồng:**
  > *"Tóm lại, demo cho thấy giám sát AI có thể bổ sung góc nhìn đa biến bên cạnh các rule ngưỡng như CPU và latency. Đây là prototype mô phỏng để minh họa phát hiện và remediation; muốn dùng production cần đánh giá dữ liệu, SLO và hành động phục hồi thực tế. Nhóm xin cảm ơn Thầy và các bạn đã lắng nghe!"*

---

## 7. Định hướng Nâng cấp Production-Ready Cloud Architecture

Để chuyển giao đồ án từ môi trường Docker Compose cục bộ sang môi trường Production quy mô lớn trên nền tảng Cloud công cộng (GCP / AWS / Azure), kiến trúc có thể mở rộng theo các hướng sau:

1. **Triển khai trên Kubernetes (K8s Cluster):**
   - Đóng gói ứng dụng thành các `Deployments` với `HorizontalPodAutoscaler` (HPA).
   - Triển khai Prometheus và Grafana qua **kube-prometheus-stack** Helm Chart (sử dụng Prometheus Operator và Custom Resource Definitions - CRDs).
2. **KEDA (Kubernetes Event-driven Autoscaling):**
   - Thay vì chỉ scale Pod dựa trên CPU/RAM thô của node, cấu hình KEDA autoscaler kích hoạt scale-out số lượng bản sao Pod dựa trên chính metric `ai_anomaly_score` lấy từ Prometheus TSDB.
3. **Tích hợp Service Mesh (Istio / Linkerd):**
   - Sử dụng Sidecar Envoy Proxy để thu thập dữ liệu viễn trắc tầng mạng L7 (mTLS, HTTP request status, latency) tự động 100% mà không cần sửa đổi bất kỳ dòng code nào trong ứng dụng gốc.
   - Khi AI phát hiện anomaly score vọt cao, tự động điều khiển Envoy Proxy áp dụng cơ chế **Circuit Breaking** (Ngắt mạch) hoặc **Rate Limiting** để bảo vệ hạ tầng backend.
4. **Hệ thống Thông báo Thời gian thực (Alertmanager Webhook):**
   - Đồ án hiện đã có Prometheus alert rules, Alertmanager routing và webhook receiver cục bộ để mô phỏng việc nhận cảnh báo; xem `prometheus/alert.rules.yml`, `alertmanager/alertmanager.yml` và `alert_receiver/`.
   - Hướng nâng cấp production là thay receiver demo bằng kênh vận hành thực tế như Telegram Bot, Slack Webhook hoặc PagerDuty, đồng thời quản lý token/URL bí mật ngoài file cấu hình được commit.

---
*Tài liệu này được biên soạn bởi Nhóm 08 - Bộ môn Điện toán đám mây (CO3059) - Trường Đại học Bách Khoa - ĐHQG TP. Hồ Chí Minh.*
