# AIOps & Cloud Monitoring Demo
## Phát hiện bất thường động bằng Isolation Forest trong hệ thống Microservices

> **Môn học:** Điện toán đám mây (Cloud Computing - CO3059) | **Nhóm:** Nhóm 08 - L01  
> **Mục tiêu:** Minh họa AIOps phát hiện sự cố ngầm định (Gray Failure) mà giám sát ngưỡng tĩnh truyền thống bỏ sót, tích hợp giải thích nguyên nhân gốc rễ (XAI) và cơ chế tự phục hồi (Self-Healing).

---

## 🧠 Kiến thức Áp dụng trong Dự án & Vị trí Hiện thực

Bảng dưới đây tổng hợp toàn bộ các khối kiến thức lý thuyết cốt lõi của môn học **Điện toán đám mây & SRE/DevOps** được áp dụng trong dự án, cùng vị trí file và module mã nguồn cụ thể:

| STT | Khối Kiến thức Áp dụng | Nội dung Lý thuyết Cốt lõi | Vị trí Áp dụng trong Mã nguồn |
|:---:|:---|:---|:---|
| **1** | **Ảo hóa & Đóng gói Container (Containerization)** | • Ảo hóa tầng HĐH (OS-level Virtualization) qua Docker.<br>• Tối ưu kích thước Image (Multi-stage, Linux AMD64).<br>• Cô lập tài nguyên tiến trình bằng Linux Cgroups & Namespaces. | • [app/Dockerfile](file:///c:/261/CloudComputing/cloud-seminar/app/Dockerfile)<br>• [ai_detector/Dockerfile](file:///c:/261/CloudComputing/cloud-seminar/ai_detector/Dockerfile)<br>• [docker-compose.yml](file:///c:/261/CloudComputing/cloud-seminar/docker-compose.yml) |
| **2** | **Kiến trúc Microservices (Stateless vs Stateful)** | • Tách biệt nhiệm vụ độc lập (Decoupling).<br>• **Stateless**: Dễ dàng scale-out ngang phía sau Load Balancer.<br>• **Stateful**: Bảo toàn dữ liệu qua Named Volumes (*Ephemeral Containers vs Persistent Storage*). | • **Stateless**: [app/main.py](file:///c:/261/CloudComputing/cloud-seminar/app/main.py), [ai_detector/detector.py](file:///c:/261/CloudComputing/cloud-seminar/ai_detector/detector.py)<br>• **Stateful Volumes**: `prometheus-data`, `grafana-data` trong [docker-compose.yml](file:///c:/261/CloudComputing/cloud-seminar/docker-compose.yml) |
| **3** | **Mạng Đám mây & Khám phá Dịch vụ (SDN & Service Discovery)** | • Docker Bridge Network (`aiops-net`) đóng vai trò như một mạng ảo VPC thu nhỏ.<br>• Khám phá dịch vụ tự động qua Docker Embedded DNS (`127.0.0.11`) bằng tên service thay cho IP tĩnh. | • Mạng `aiops-net` trong [docker-compose.yml](file:///c:/261/CloudComputing/cloud-seminar/docker-compose.yml)<br>• DNS targets `app:8000`, `ai-detector:8001` trong [prometheus/prometheus.yml](file:///c:/261/CloudComputing/cloud-seminar/prometheus/prometheus.yml)<br>• URL `http://prometheus:9090` trong [ai_detector/detector.py](file:///c:/261/CloudComputing/cloud-seminar/ai_detector/detector.py) |
| **4** | **Giám sát Đám mây & Viễn trắc (Observability & OpenMetrics)** | • 3 kiểu dữ liệu metric chuẩn OpenMetrics:<br>  - `Counter`: Lưu lượng request (RPS).<br>  - `Histogram`: Phân vị độ trễ $p_{50}, p_{90}, p_{99}$ đo lường **SLO/SLA**.<br>  - `Gauge`: Mức CPU, RAM tức thời.<br>• Thu thập dữ liệu theo mô hình Kéo (Pull-based Scrape). | • [app/main.py](file:///c:/261/CloudComputing/cloud-seminar/app/main.py) (khai báo `REQUEST_COUNTER`, `REQUEST_LATENCY`, `CPU_GAUGE`, endpoint `/metrics`)<br>• [prometheus/prometheus.yml](file:///c:/261/CloudComputing/cloud-seminar/prometheus/prometheus.yml) (`scrape_interval: 5s`) |
| **5** | **Cơ sở dữ liệu Chuỗi thời gian (TSDB) & Alerting Engine** | • Lưu trữ chuỗi thời gian Append-only tối ưu nén Gorilla.<br>• Ghi nhật ký Write-Ahead Log (WAL) chống mất mát dữ liệu.<br>• Prometheus đánh giá alert rules; Alertmanager nhóm và định tuyến thông báo qua webhook cục bộ. | • [prometheus/prometheus.yml](file:///c:/261/CloudComputing/cloud-seminar/prometheus/prometheus.yml)<br>• [prometheus/alert.rules.yml](file:///c:/261/CloudComputing/cloud-seminar/prometheus/alert.rules.yml)<br>• [alertmanager/alertmanager.yml](file:///c:/261/CloudComputing/cloud-seminar/alertmanager/alertmanager.yml) |
| **6** | **Hạ tầng dưới dạng mã (IaC) & Observability-as-Code** | • Khai báo trạng thái mong muốn (Desired State) qua file cấu hình.<br>• Tự động nạp Datasource và Dashboard Grafana qua YAML, không cần cấu hình thủ công bằng tay (GitOps-ready). | • [docker-compose.yml](file:///c:/261/CloudComputing/cloud-seminar/docker-compose.yml)<br>• [grafana/provisioning/datasources/prometheus.yml](file:///c:/261/CloudComputing/cloud-seminar/grafana/provisioning/datasources/prometheus.yml)<br>• [grafana/provisioning/dashboards/dashboard.yml](file:///c:/261/CloudComputing/cloud-seminar/grafana/provisioning/dashboards/dashboard.yml)<br>• [grafana/dashboards/aiops_dashboard.json](file:///c:/261/CloudComputing/cloud-seminar/grafana/dashboards/aiops_dashboard.json) |
| **7** | **Học máy Vận hành Đám mây (AIOps & Dynamic Detection)** | • Nhận diện sự cố ngầm định (**Gray Failure**): CPU ~42% (dưới ngưỡng 80%) nhưng Latency vọt x30 lần.<br>• Thuật toán **Isolation Forest** trên cửa sổ trượt (Sliding Window 5 phút) phân tích tương quan phi tuyến đa biến $(RPS, Latency, CPU)$. | • [ai_detector/detector.py](file:///c:/261/CloudComputing/cloud-seminar/ai_detector/detector.py) (hàm `build_feature_matrix()`, `train_and_score()`, model `IsolationForest`) |
| **8** | **Tính Giải thích được của AI (XAI - Root Cause Analysis)** | • Xóa bỏ định kiến AI là "hộp đen".<br>• Phân rã độ lệch chuẩn $z_i = \frac{\|x_i - \mu_i\|}{\sigma_i}$ để định lượng % đóng góp nguyên nhân sự cố (chỉ ra Latency chiếm ~78%, CPU chiếm ~16%). | • [ai_detector/detector.py](file:///c:/261/CloudComputing/cloud-seminar/ai_detector/detector.py) (tính toán `attribution` gán vào metric `ai_feature_attribution`)<br>• Panel 5 (Bar Gauge) trong [grafana/dashboards/aiops_dashboard.json](file:///c:/261/CloudComputing/cloud-seminar/grafana/dashboards/aiops_dashboard.json) |
| **9** | **Chống Nhiễm độc Dữ liệu (Drift & Poisoning Prevention)** | • Xử lý khởi động lạnh (**Cold Start**) bằng dữ liệu Gaussian nhân tạo.<br>• Khi sự cố kéo dài, tự động hòa trộn **Golden Baseline** để ngăn AI tự "bình thường hóa" trạng thái lỗi. | • [ai_detector/detector.py](file:///c:/261/CloudComputing/cloud-seminar/ai_detector/detector.py) (hàm `generate_baseline_data()`, cơ chế ghép `golden_baseline` khi `consecutive_anomalies > 0`) |
| **10** | **Tự Chữa lành Đám mây (Closed-Loop Remediation / Self-Healing)** | • Hiện thực hóa chu trình tự trị **OODA / MAPE-K** (Monitor $\rightarrow$ Analyze $\rightarrow$ Decide $\rightarrow$ Remediate).<br>• Tự động kích hoạt webhook phục hồi microservice khi phát hiện sự cố kéo dài mà không cần con người can thiệp. | • Endpoint `/api/remediate` trong [app/main.py](file:///c:/261/CloudComputing/cloud-seminar/app/main.py)<br>• Logic kích hoạt webhook khi streak $\ge 3$ trong [ai_detector/detector.py](file:///c:/261/CloudComputing/cloud-seminar/ai_detector/detector.py)<br>• Panel 6 trong [grafana/dashboards/aiops_dashboard.json](file:///c:/261/CloudComputing/cloud-seminar/grafana/dashboards/aiops_dashboard.json) |
| **11** | **Kỹ nghệ Sự cố & Chịu lỗi (Chaos Engineering & Fault Injection)** | • Chủ động tiêm tải lỗi vi mô (Gray Failure, Memory Leak, Jitter, HTTP 500 Spike) để kiểm thử độ nhạy và tính kiên cường (Resilience) của hệ thống giám sát. | • [traffic_sim.py](file:///c:/261/CloudComputing/cloud-seminar/traffic_sim.py) (các chế độ `anomaly`, `memory_leak`, `jitter`, `error_burst`)<br>• [run_demo.py](file:///c:/261/CloudComputing/cloud-seminar/run_demo.py) (Phase 2 Fault Injection) |
| **12** | **Kỹ nghệ Độ tin cậy Đám mây (SRE Metrics & SLO Protection)** | • Tối ưu hóa các chỉ số vận hành chuẩn mực:<br>  - Rút ngắn **MTTD** từ vô hạn xuống **10–15 giây**.<br>  - Rút ngắn **MTTR** từ 15–30 phút xuống **1–2 giây**.<br>  - Bảo vệ ngân sách lỗi (**Error Budget**) để đạt cam kết **SLA 99.9%**. | • Thể hiện qua kết quả thực nghiệm trong [run_demo.py](file:///c:/261/CloudComputing/cloud-seminar/run_demo.py) (Phase 5 SRE Comparison Table)<br>• Chi tiết phân tích tại [INSTRUCTION.md](file:///c:/261/CloudComputing/cloud-seminar/INSTRUCTION.md) |

---

## 🚀 Hướng dẫn Triển khai & Vận hành (Deployment Guide)

### Bước 0: Yêu cầu môi trường
1. **Docker Desktop:** Đảm bảo Docker Desktop đang chạy (biểu tượng cá voi chuyển sang màu xanh, hỗ trợ WSL2 backend trên Windows).
2. **Python:** Phiên bản Python 3.10+ trên máy host (dùng để chạy script điều phối và giả lập tải).

### Bước 1: Build và khởi động toàn bộ hệ thống
Mở terminal tại thư mục gốc của dự án (`cloud-seminar`) và chạy lệnh:

```powershell
docker-compose up -d --build
```

> **Lưu ý:** Lần build đầu tiên mất ~2-3 phút để tải image và cài đặt thư viện (`FastAPI`, `Scikit-Learn`, `Prometheus-Client`). Các lần khởi động sau chỉ mất khoảng 10-20 giây.

### Bước 2: Kiểm tra tất cả services đang chạy
Xác nhận trạng thái các container bằng lệnh:

```powershell
docker-compose ps
```

**Kết quả mong đợi:** Cả 4 services đều hiển thị trạng thái `Up` (hoặc `healthy`):
- `aiops-app`: Target Microservice (FastAPI - cổng `8000`)
- `aiops-ai-detector`: AI Worker Isolation Forest (Flask - cổng `8001`)
- `aiops-prometheus`: Time-Series Database & Scraper (cổng `9090`)
- `aiops-grafana`: Visualization Dashboard (cổng `3000`)

### Bước 3: Mở Grafana Dashboard
Truy cập trình duyệt tại địa chỉ: **http://localhost:3000**
- **Username:** `admin`
- **Password:** `admin123`
- Bảng điều khiển **AIOps - Dynamic Anomaly Detection** gồm 6 Panels trực quan đã được tự động nạp sẵn (Auto-Provisioned).

### Bước 4: Cài đặt thư viện phát sinh tải (trên máy host)
```powershell
pip install requests
```

### Dừng hệ thống khi kết thúc
```powershell
# Dừng các container:
docker-compose down

# Dừng và xóa dữ liệu volumes nếu muốn làm sạch:
docker-compose down -v
```

---

## 🎬 Hướng dẫn cách chạy dự án này

---

### ⚡ CÁCH NHANH NHẤT: 1-CLICK MASTER RUNNER (KHÔNG CẦN GÕ NHIỀU LỆNH)

Để tự động hóa toàn bộ quy trình: **Kiểm tra Docker $\rightarrow$ Khởi động 4 Container $\rightarrow$ Chờ Healthcheck $\rightarrow$ Tự động mở Grafana trên trình duyệt $\rightarrow$ Chạy Kịch bản Demo 5 giai đoạn**, MemBau chỉ cần chọn **1 trong 3 cách** sau:

- **Cách 1 (Chuột):** Nhấp đúp chuột (**Double-click**) trực tiếp vào file **`start_demo.bat`** trong Windows Explorer.
- **Cách 2 (PowerShell):** Mở PowerShell tại thư mục dự án và gõ:
  ```powershell
  .\start_demo.ps1
  ```
- **Cách 3 (Python):** Chạy lệnh:
  ```powershell
  python start_demo.py
  ```

> 💡 *Toàn bộ quy trình từ khởi động đến mở web đều tự động 100%, MemBau chỉ cần nhấn `[Enter]` để chuyển qua từng giai đoạn thuyết trình!*

---

### 🌟 Cách 2: Chạy Riêng Kịch bản Điều phối (Nếu Đã Bật Docker Trước)

Nếu 4 container Docker đã được bật từ trước (`docker-compose up -d`), MemBau có thể chạy trực tiếp script điều phối:

```powershell
# Chế độ tương tác từng bước (Khuyên dùng khi thuyết trình - bấm Enter để chuyển giai đoạn):
python run_demo.py --interactive

# Hoặc chế độ tự động hoàn toàn theo timeline (Tốc độ 1.5x):
python run_demo.py --speed 1.5
```

**Bảng Kịch bản Demo 5 Giai đoạn & Trạng thái 6 Panels trên Grafana:**

| Giai đoạn | Hành động & Nhịp nói với Giảng viên | Trạng thái hiển thị Chi tiết trên 6 Panels Grafana |
|:---|:---|:---|
| **Giai đoạn 1: Baseline** *(0:00 - 0:45)* | Gửi tải bình thường (2 req/s).<br>👉 *Nói:* "Hệ thống đang chạy ổn định, CPU ~20%, Latency ~40ms. Isolation Forest đang học phân bố hành vi bình thường của hệ thống." | • **Panel 1 (CPU):** Ổn định ở mức thấp ~20% (dưới xa vạch đỏ 80%).<br>• **Panel 2 (Latency):** Cực nhanh ~30-50ms (đáp ứng tốt).<br>• **Panel 3 (AI Score):** Rất thấp ~0.15 - 0.20 (vùng an toàn xanh).<br>• **Panel 4 (Status):** Xanh `✅ BÌNH THƯỜNG`.<br>• **Panel 5 (XAI RCA):** Các thanh cân bằng, không có độ lệch.<br>• **Panel 6 (Self-Healing):** `0` (hệ thống lành mạnh, chưa kích hoạt). |
| **Giai đoạn 2: Gray Failure** *(0:45 - 1:30)* | Bấm **[Enter]** để tiêm lỗi Gray Failure.<br>👉 *Nói:* "Sự cố xảy ra! Latency giật cục lên 2.5s khiến người dùng kêu ca, nhưng CPU chỉ ~42% (vẫn dưới ngưỡng 80%). Giám sát ngưỡng tĩnh hoàn toàn bị mù và bỏ sót!" | • **Panel 1 (CPU):** Nhích lên ~42% $\rightarrow$ **VẪN DƯỚI vạch đỏ 80% (không báo động)**.<br>• **Panel 2 (Latency):** Vọt giật cục x30 lần (1.5 - 3.0s).<br>• **Panel 3 (AI Score):** Bắt đầu dốc đứng từ 0.2 $\rightarrow$ 0.6.<br>• **Panel 4 (Status):** Đang trong chu kỳ đánh giá cửa sổ trượt.<br>• **Panel 5 (XAI RCA):** Cột Latency bắt đầu tách nhóm vọt lên.<br>• **Panel 6 (Self-Healing):** Vẫn là `0`. |
| **Giai đoạn 3: AI Phát hiện & XAI** *(1:30 - 2:00)* | Bấm **[Enter]** để đo đạc và bóc tách XAI.<br>👉 *Nói:* "Chỉ sau 10s, AI phát hiện tương quan đa biến bị lệch chuẩn. Score vọt qua 0.7 báo động đỏ! Panel 5 chỉ rõ Latency đóng góp tới ~78% nguyên nhân sự cố." | • **Panel 1 (CPU):** Vẫn giữ nguyên ~42% (chứng minh tính chất ngầm định).<br>• **Panel 2 (Latency):** Duy trì ở đỉnh cao 2.0 - 2.8s.<br>• **Panel 3 (AI Score):** **VƯỢT VẠCH ĐỎ 0.70**, chạm mức 0.85 - 0.92.<br>• **Panel 4 (Status):** Chuyển đỏ rực: **`🚨 BẤT THƯỜNG`**.<br>• **Panel 5 (XAI RCA):** Cột **Latency chiếm ~78%** (đỏ), CPU ~16%, RPS ~6%.<br>• **Panel 6 (Self-Healing):** Tích lũy chuỗi cảnh báo chuẩn bị tự xử lý. |
| **Giai đoạn 4: Self-Healing** *(2:00 - 2:30)* | Bấm **[Enter]** để kích hoạt tự chữa lành.<br>👉 *Nói:* "AI tự động hoàn tất vòng lặp khép kín, bắn webhook `/api/remediate` để phục hồi container về trạng thái an toàn." | • **Panel 6 (Self-Healing):** **TĂNG LÊN 1 (MÀU XANH)** $\rightarrow$ Ghi nhận phục hồi.<br>• **Panel 1 (CPU):** Tụt dốc từ 42% về lại 20%.<br>• **Panel 2 (Latency):** Rơi thẳng đứng từ 2.5s về 40ms.<br>• **Panel 3 (AI Score):** Hạ nhiệt nhanh chóng từ 0.88 về 0.18.<br>• **Panel 4 (Status):** Lập tức đảo chiều về **`✅ BÌNH THƯỜNG`**.<br>• **Panel 5 (XAI RCA):** Các thanh đo hạ nhiệt và tái cân bằng. |
| **Giai đoạn 5: Tổng kết** | Terminal tự động in Bảng so sánh SRE định lượng giữa Static Threshold vs AIOps để MemBau chốt bài thuyết trình. | Cả 6 Panels đồng nhất ở trạng thái màu xanh an toàn, chứng minh trọn vẹn chu trình tự trị Cloud-Native (OODA / MAPE-K) trước Hội đồng. |

---

### 🛠️ Cách 2: Kịch bản Thủ công từng bước (Traffic Simulator & Chaos Engine)

Sử dụng script `traffic_sim.py` để chủ động điều khiển từng kịch bản tải theo ý muốn:

#### 1. Tạo dữ liệu baseline bình thường:
```powershell
python traffic_sim.py --mode normal
```
- Gửi đều đặn 2 req/s, CPU ~20%, latency ~30-50ms.
- Quan sát trên Grafana: AI Anomaly Score ở mức thấp ~0.2 (màu xanh).

#### 2. Kích hoạt sự cố Gray Failure:
Nhấn `Ctrl+C` dừng lệnh trên, sau đó chạy:
```powershell
python traffic_sim.py --mode anomaly
```
- CPU chỉ ~42% (hoàn toàn **dưới** ngưỡng tĩnh 80% $\rightarrow$ Giám sát truyền thống bỏ sót).
- Latency giật cục 1.5 - 3.0s $\rightarrow$ Isolation Forest phát hiện tương quan đa biến, điểm AI Score vọt lên > 0.7 (cảnh báo đỏ).
- Panel 5 trên Grafana phân tích chi tiết nguyên nhân gốc rễ (XAI RCA).

#### 3. Các kịch bản Chaos Engineering mở rộng:
```powershell
# Kịch bản rò rỉ bộ nhớ (RAM tăng dần theo thời gian):
python traffic_sim.py --mode memory_leak

# Kịch bản vi nghẽn độ trễ (Micro-burst jitter):
python traffic_sim.py --mode jitter

# Kịch bản bão mã lỗi HTTP 500:
python traffic_sim.py --mode error_burst
```

#### 4. Kích hoạt Self-Healing (Tự chữa lành):
Mở một cửa sổ terminal mới và chạy:
```powershell
python traffic_sim.py --remediate
```
- Hệ thống gửi tín hiệu đến `/api/remediate`, giải phóng bộ nhớ và khôi phục baseline an toàn. Panel 6 ghi nhận số lần phục hồi thành công.

### 🚨 Demo Prometheus Alertmanager

Luồng cảnh báo được hiện thực riêng với luồng remediation:

```text
App / AI Detector → Prometheus scrape metrics → Prometheus đánh giá alert rules
                                                   ↓ alert firing/resolved
                                         Alertmanager nhóm và định tuyến
                                                   ↓ webhook
                                      Local Alert Receiver (trang nhận alert)
```

Khởi động toàn bộ stack (receiver, Alertmanager, Prometheus, app, AI Detector và Grafana):

```powershell
docker-compose up -d --build
```

Mở các trang sau:

- `http://localhost:9090/alerts`: trạng thái alert của Prometheus, gồm `pending` và `firing`.
- `http://localhost:9093`: Alertmanager, nơi xem alert đã nhận, nhóm và silence.
- `http://localhost:8081`: hộp thư webhook cục bộ, hiển thị alert đang firing và resolved.

Prometheus đánh giá các luật trong `prometheus/alert.rules.yml` mỗi 5 giây. Hiện có các rule: app không scrape được, AI Detector không scrape được, latency trung bình trên 1 giây, CPU trên 80%, và AI anomaly score trên 0.70. Mỗi rule yêu cầu điều kiện kéo dài 10 giây (`for: 10s`) để tránh gửi cảnh báo vì một mẫu lỗi thoáng qua. Thời gian thực tế có thể lâu hơn do còn phụ thuộc lúc scrape/evaluate và `group_wait` của Alertmanager.

Để trình diễn một alert chắc chắn, dừng app:

```powershell
docker-compose stop app
```

Sau khoảng 20 giây, `AppTargetDown` sẽ chuyển từ `pending` sang `firing`; Prometheus gửi alert đến Alertmanager, rồi webhook sẽ xuất hiện tại trang `localhost:8081`. Khởi động lại app để xem alert được gửi trạng thái resolved:

```powershell
docker-compose start app
```

Có thể xem log của hai thành phần xử lý thông báo bằng:

```powershell
docker-compose logs -f alertmanager alert-receiver
```

Trong demo này, Alertmanager gửi webhook đến receiver cục bộ, không gửi tin nhắn ra Telegram/Slack/email. Trang receiver giữ tối đa 200 sự kiện trong bộ nhớ của container; khởi động lại receiver sẽ xóa lịch sử hiển thị. Alertmanager nhận, nhóm và chuyển thông báo; nó không tự sửa app và không thay thế lệnh remediation của `run_demo.py`.

---

## 📁 Cấu trúc Thư mục Dự án

```
cloud-seminar/
├── start_demo.bat              # ⚡ [1-Click] Nhấp đúp chuột để chạy toàn bộ hệ thống
├── start_demo.ps1              # ⚡ [PowerShell Master] Tự bật container, mở web & chạy demo
├── start_demo.py               # ⚡ [Python Master] Tự động hóa đa nền tảng
├── run_demo.py                 # [Demo Runner] Điều phối kịch bản 5 giai đoạn
├── traffic_sim.py              # [Chaos Engine] Bơm tải normal, anomaly, chaos
├── docker-compose.yml          # Orchestration cho app, AI, monitoring và alert receiver
├── README.md                   # Tài liệu triển khai & hướng dẫn vận hành dự án
├── INSTRUCTION.md              # Tài liệu kỹ thuật chi tiết & lý thuyết giải thích sâu
├── app/
│   ├── Dockerfile              # Container đóng gói microservice FastAPI
│   ├── main.py                 # Microservice FastAPI: xử lý tải, phơi OpenMetrics, hỗ trợ /remediate
│   └── requirements.txt        # fastapi, uvicorn, prometheus-client
├── ai_detector/
│   ├── Dockerfile              # Container đóng gói AIOps Worker (Scikit-Learn)
│   ├── detector.py             # Isolation Forest: Sliding Window, XAI RCA, Drift Shield, Auto-Heal
│   └── requirements.txt        # flask, scikit-learn, numpy, requests, prometheus-client
├── alertmanager/
│   └── alertmanager.yml        # Gom nhóm và route alert tới webhook receiver
├── alert_receiver/
│   ├── Dockerfile              # Image nhỏ cho webhook receiver cục bộ
│   └── receiver.py             # Nhận và hiển thị alert/resolved trong trang demo
├── prometheus/
│   ├── prometheus.yml          # Cấu hình scrape targets (chu kỳ 5s) & nạp rules
│   └── alert.rules.yml         # Luật cảnh báo cho target down, latency, CPU và AI score
└── grafana/
    ├── provisioning/
    │   ├── datasources/
    │   │   └── prometheus.yml  # Tự động nạp Prometheus Datasource
    │   └── dashboards/
    │       └── dashboard.yml   # Tự động nạp Dashboards
    └── dashboards/
        └── aiops_dashboard.json # 6 Panels: CPU, Latency, AI Score, Status, XAI RCA, Self-Healing
```

> 📖 **Xem giải thích chi tiết về thuật toán, mô hình toán học và bối cảnh SRE tại:** [INSTRUCTION.md](file:///c:/261/CloudComputing/cloud-seminar/INSTRUCTION.md)
