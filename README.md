# AIOps & Cloud Monitoring Demo
## Phát hiện bất thường động bằng Isolation Forest trong hệ thống Microservices

> **Môn học:** Điện toán đám mây (Cloud Computing - CO3059) | **Nhóm:** Nhóm 08 - L01  
> **Mục tiêu:** Minh họa AIOps phát hiện Gray Failure mà giám sát chỉ dựa trên ngưỡng CPU có thể bỏ sót, tích hợp giải thích nguyên nhân gốc rễ (XAI) và cơ chế tự phục hồi (Self-Healing).

> **Nếu bạn vừa clone repo:** bắt đầu ở mục [Chạy dự án trên Windows](#-chạy-dự-án-trên-windows). `INSTRUCTION.md` là phần giải thích kỹ thuật sâu hơn.

---

## 🧠 Kiến thức Áp dụng trong Dự án & Vị trí Hiện thực

Bảng dưới đây tổng hợp toàn bộ các khối kiến thức lý thuyết cốt lõi của môn học **Điện toán đám mây & SRE/DevOps** được áp dụng trong dự án, cùng vị trí file và module mã nguồn cụ thể:

| STT | Khối Kiến thức Áp dụng | Nội dung Lý thuyết Cốt lõi | Vị trí Áp dụng trong Mã nguồn |
|:---:|:---|:---|:---|
| **1** | **Ảo hóa & Đóng gói Container (Containerization)** | • Ảo hóa tầng HĐH (OS-level Virtualization) qua Docker.<br>• Đóng gói ứng dụng trong image Python slim; một số service dùng nền tảng linux/amd64.<br>• Cô lập tài nguyên tiến trình bằng Linux Cgroups & Namespaces. | • [app/Dockerfile](./app/Dockerfile)<br>• [ai_detector/Dockerfile](./ai_detector/Dockerfile)<br>• [docker-compose.yml](./docker-compose.yml) |
| **2** | **Kiến trúc Microservices (Stateless vs Stateful)** | • Tách biệt nhiệm vụ độc lập (Decoupling).<br>• **Stateless**: Dễ dàng scale-out ngang phía sau Load Balancer.<br>• **Stateful**: Bảo toàn dữ liệu qua Named Volumes (*Ephemeral Containers vs Persistent Storage*). | • **Stateless**: [app/main.py](./app/main.py), [ai_detector/detector.py](./ai_detector/detector.py)<br>• **Stateful Volumes**: `prometheus-data`, `grafana-data` trong [docker-compose.yml](./docker-compose.yml) |
| **3** | **Mạng Đám mây & Khám phá Dịch vụ (SDN & Service Discovery)** | • Docker Bridge Network (`aiops-net`) đóng vai trò như một mạng ảo VPC thu nhỏ.<br>• Docker DNS phân giải tên service; danh sách target scrape của Prometheus vẫn khai báo tĩnh bằng `static_configs`. | • Mạng `aiops-net` trong [docker-compose.yml](./docker-compose.yml)<br>• DNS targets `app:8000`, `ai-detector:8001` trong [prometheus/prometheus.yml](./prometheus/prometheus.yml)<br>• URL `http://prometheus:9090` trong [ai_detector/detector.py](./ai_detector/detector.py) |
| **4** | **Giám sát Đám mây & Viễn trắc (Observability & OpenMetrics)** | • 3 kiểu dữ liệu metric chuẩn OpenMetrics:<br>  - `Counter`: Lưu lượng request (RPS).<br>  - `Histogram`: Ghi nhận phân bố latency, có thể dùng để tính phân vị như $p_{50}$/$p_{90}$/$p_{99}$.<br>  - `Gauge`: CPU/RAM giả lập do app báo cáo.<br>• Thu thập dữ liệu theo mô hình Kéo (Pull-based Scrape). | • [app/main.py](./app/main.py) (khai báo `REQUEST_COUNTER`, `REQUEST_LATENCY`, `CPU_GAUGE`, endpoint `/metrics`)<br>• [prometheus/prometheus.yml](./prometheus/prometheus.yml) (`scrape_interval: 5s`) |
| **5** | **Cơ sở dữ liệu Chuỗi thời gian (TSDB) & Alerting Engine** | • Lưu trữ chuỗi thời gian Append-only tối ưu nén Gorilla.<br>• Ghi nhật ký Write-Ahead Log (WAL) chống mất mát dữ liệu.<br>• Prometheus đánh giá alert rules; Alertmanager nhóm và định tuyến thông báo qua webhook cục bộ. | • [prometheus/prometheus.yml](./prometheus/prometheus.yml)<br>• [prometheus/alert.rules.yml](./prometheus/alert.rules.yml)<br>• [alertmanager/alertmanager.yml](./alertmanager/alertmanager.yml) |
| **6** | **Hạ tầng dưới dạng mã (IaC) & Observability-as-Code** | • Khai báo trạng thái mong muốn (Desired State) qua file cấu hình.<br>• Tự động nạp Datasource và Dashboard Grafana qua YAML, không cần cấu hình thủ công bằng tay (GitOps-ready). | • [docker-compose.yml](./docker-compose.yml)<br>• [grafana/provisioning/datasources/prometheus.yml](./grafana/provisioning/datasources/prometheus.yml)<br>• [grafana/provisioning/dashboards/dashboard.yml](./grafana/provisioning/dashboards/dashboard.yml)<br>• [grafana/dashboards/aiops_dashboard.json](./grafana/dashboards/aiops_dashboard.json) |
| **7** | **Học máy Vận hành Đám mây (AIOps & Dynamic Detection)** | • Nhận diện sự cố ngầm định (**Gray Failure**): CPU ~42% (dưới ngưỡng 80%) nhưng Latency vọt x30 lần.<br>• Thuật toán **Isolation Forest** trên cửa sổ trượt (Sliding Window 5 phút) phân tích tương quan phi tuyến đa biến $(RPS, Latency, CPU)$. | • [ai_detector/detector.py](./ai_detector/detector.py) (hàm `build_feature_matrix()`, `train_and_score()`, model `IsolationForest`) |
| **8** | **Tính Giải thích được của AI (XAI - Root Cause Analysis)** | • Xóa bỏ định kiến AI là "hộp đen".<br>• Phân rã độ lệch chuẩn $z_i = \frac{\|x_i - \mu_i\|}{\sigma_i}$ để định lượng % đóng góp nguyên nhân sự cố (chỉ ra Latency chiếm ~78%, CPU chiếm ~16%). | • [ai_detector/detector.py](./ai_detector/detector.py) (tính toán `attribution` gán vào metric `ai_feature_attribution`)<br>• Panel 5 (Bar Gauge) trong [grafana/dashboards/aiops_dashboard.json](./grafana/dashboards/aiops_dashboard.json) |
| **9** | **Chống Nhiễm độc Dữ liệu (Drift & Poisoning Prevention)** | • Xử lý khởi động lạnh (**Cold Start**) bằng dữ liệu Gaussian nhân tạo.<br>• Khi sự cố kéo dài, tự động hòa trộn **Golden Baseline** để ngăn AI tự "bình thường hóa" trạng thái lỗi. | • [ai_detector/detector.py](./ai_detector/detector.py) (hàm `generate_baseline_data()`, cơ chế ghép `golden_baseline` khi `consecutive_anomalies > 0`) |
| **10** | **Tự Chữa lành Đám mây (Closed-Loop Remediation / Self-Healing)** | • Hiện thực hóa chu trình tự trị **OODA / MAPE-K** (Monitor $\rightarrow$ Analyze $\rightarrow$ Decide $\rightarrow$ Remediate).<br>• Có auto-remediation demo sau anomaly kéo dài; Phase 4 cũng gọi endpoint trực tiếp. Endpoint chỉ reset trạng thái mô phỏng, không điều khiển Docker. | • Endpoint `/api/remediate` trong [app/main.py](./app/main.py)<br>• Auto-remediation sau 20 chu kỳ anomaly liên tiếp (~100 giây); Phase 4 gọi endpoint trực tiếp trong [run_demo.py](./run_demo.py)<br>• Panel 6 trong [grafana/dashboards/aiops_dashboard.json](./grafana/dashboards/aiops_dashboard.json) |
| **11** | **Kỹ nghệ Sự cố & Chịu lỗi (Chaos Engineering & Fault Injection)** | • Chủ động tiêm tải lỗi vi mô (Gray Failure, Memory Leak, Jitter, HTTP 500 Spike) để kiểm thử độ nhạy và tính kiên cường (Resilience) của hệ thống giám sát. | • [traffic_sim.py](./traffic_sim.py) (các chế độ `anomaly`, `memory_leak`, `jitter`, `error_burst`)<br>• [run_demo.py](./run_demo.py) (Phase 2 Fault Injection) |
| **12** | **Kỹ nghệ Độ tin cậy Đám mây (SRE Metrics & SLO Protection)** | • Tối ưu hóa các chỉ số vận hành chuẩn mực:<br>  - MTTD/MTTR ở Phase 5 là chỉ số minh họa cho kịch bản.<br>  - Các giá trị này không phải benchmark production.<br>  - Dự án chưa tính error budget hoặc xác minh SLA 99.9%. | • Thể hiện qua kết quả thực nghiệm trong [run_demo.py](./run_demo.py) (Phase 5 SRE Comparison Table)<br>• Chi tiết phân tích tại [INSTRUCTION.md](./INSTRUCTION.md) |

> **Phạm vi demo:** CPU/RAM là metric giả lập, Prometheus dùng danh sách scrape target tĩnh, và remediation chỉ reset trạng thái mô phỏng của app. Bảng Phase 5 là minh họa cho kịch bản, không phải phép đo SLA/error budget của production.

---

## 🚀 Chạy dự án trên Windows

### Yêu cầu

- Docker Desktop đã cài và đang chạy.
- Python 3.10 trở lên và Windows Python Launcher (`py`).
- Lệnh `docker-compose` nhận diện được trong terminal.
- Trình duyệt mặc định để mở trang giám sát.

### 1. Clone và chuẩn bị Python

Clone repository, mở PowerShell tại thư mục `cloud-seminar`, rồi tạo môi trường riêng cho script demo:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install requests
```

Nếu máy có nhiều bản Python và `py -3` không chọn bản mong muốn, thay `-3` bằng phiên bản đã cài, ví dụ `py -3.13`. Môi trường `.venv` bị Git bỏ qua; mỗi người clone cần tự tạo môi trường này.

### 2. Khởi động và chạy demo

Từ thư mục gốc của repository, chạy một lối khởi động chính:

```powershell
.\start_demo.bat
```

`start_demo.bat` gọi bước build/khởi động và mở trang trong `build.bat`/`build.ps1`, rồi chạy demo tương tác. Nếu chỉ muốn build, mở các trang giám sát và không chạy demo, dùng:

```powershell
.\build.bat
```

Build sẽ chạy sáu service, chờ health check tối đa 60 giây rồi mở Grafana, Prometheus Alerts, Alertmanager Alerts và Alert Receiver. Receiver dùng một cổng host ngẫu nhiên do Docker cấp; địa chỉ chính xác được in trong terminal. Khi chạy `start_demo.bat`, nhấn Enter để chuyển phase demo. Ở cuối, chọn `n` để giữ container chạy hoặc `y` để dừng chúng.

Lần build đầu cần tải image Docker và cài thư viện bên trong image, nên có thể mất vài phút. Những lần sau thường nhanh hơn.

### 3. Các trang và cổng

| Thành phần | Địa chỉ |
|---|---|
| Grafana dashboard | http://localhost:3000 — đăng nhập `admin` / `admin123` |
| Prometheus Alerts | http://localhost:9090/alerts |
| Alertmanager Alerts | http://localhost:9093/#/alerts |
| Alert Receiver | Cổng động; dùng URL được in bởi `start_demo.bat` |

Grafana nạp dashboard tự động. Prometheus và Alertmanager xem các alert đang hoạt động; Receiver là hộp thư webhook lưu sự kiện firing/resolved trong bộ nhớ của container.

### 4. Bật đo CPU thật của máy Windows

Dashboard tách CPU thành ba nguồn: **CPU Demo (Simulated)** lấy từ app, **Windows Host CPU (Real)** lấy từ máy Windows chạy Docker, và **Windows Client CPU (Real)** lấy từ máy bạn bè qua VPN. Host vẫn có thêm anomaly score, scrape latency và trạng thái exporter. Panel CPU client sử dụng recording rule `windows_client_cpu_percent`.

1. Tải và cài MSI `windows_exporter` phù hợp với máy từ [GitHub Releases](https://github.com/prometheus-community/windows_exporter/releases). Cài với thiết lập mặc định; exporter chạy như Windows service và mặc định xuất metrics ở cổng `9182`, đường dẫn `/metrics`.
2. Trên máy Windows, mở `http://localhost:9182/metrics` để xác nhận endpoint trả về metrics.
3. Khởi động lại Prometheus để nạp scrape target và recording rules:

   ```powershell
   docker-compose restart prometheus
   ```

4. Khởi động lại Grafana để nạp dashboard mới:

   ```powershell
   docker-compose restart grafana
   ```

5. Mở `http://localhost:9090/targets` và xác nhận job `windows-host` có trạng thái **UP**. Sau đó mở Grafana; hai panel CPU host sẽ hiển thị sau khi Prometheus thu thập được dữ liệu.

Prometheus truy cập exporter qua `host.docker.internal`, tên host Docker Desktop dùng để container kết nối về máy Windows. Scrape target và PromQL của panel đã được khai báo trong repo.

Để bật CPU máy khách, cài `windows_exporter` trên máy bạn bè, đảm bảo máy Prometheus truy cập được IP VPN của họ ở TCP `9182`, rồi thay `YOUR_FRIEND_VPN_IP` trong `prometheus/prometheus.yml` bằng IP VPN thật. Kiểm tra `http://<IP-VPN>:9182/metrics` từ máy chạy stack, sau đó áp dụng cấu hình bằng `docker-compose restart prometheus`. Khi target `windows-client` hiện **UP** tại `http://localhost:9090/targets`, panel **Windows Client CPU (Real)** sẽ có dữ liệu. Windows Firewall trên máy khách cần cho phép kết nối tới cổng `9182` từ máy chạy Prometheus.

### Dừng hoặc làm sạch dữ liệu

```powershell
docker-compose down
```

Lệnh trên dừng container nhưng giữ volume dữ liệu Prometheus, Grafana và Alertmanager. Muốn xóa các volume dữ liệu đó:

```powershell
docker-compose down -v
```

Lưu ý: receiver giữ lịch sử trong bộ nhớ; nếu container receiver bị tạo lại hoặc khởi động lại, danh sách sự kiện sẽ mất.

### Giới hạn mô phỏng cần biết

- CPU/RAM của app vẫn là **metric giả lập**; panel CPU host và CPU client dùng `windows_exporter` để đo CPU thật từ từng máy Windows. Latency được tạo từ thời gian xử lý mô phỏng.
- Docker DNS phân giải tên service như `app` và `ai-detector`, nhưng Prometheus vẫn có `static_configs`; thêm target mới vẫn cần sửa cấu hình scrape.
- `/api/remediate` đặt lại các metric/trạng thái mô phỏng của app. Đây chưa phải thao tác khởi động lại container, sửa máy thật hay chạy remediation trên hạ tầng production.
- Alertmanager hiện gửi webhook tới receiver cục bộ; chưa gửi Telegram, Slack hay email.

### Khắc phục nhanh

| Tình huống | Cách kiểm tra/xử lý |
|---|---|
| Launcher báo port đang được dùng | Các cổng host `3000`, `8000`, `8001`, `9090`, `9093` là cố định. Dừng stack cũ bằng `docker-compose down`, rồi chạy lại. Receiver có cổng động nên không cần tự chọn cổng. |
| Health check hết 45 giây và in `[WARN]` | Dòng cảnh báo liệt kê service chưa phản hồi. Kiểm tra `docker-compose ps` và xem log tương ứng bằng `docker-compose logs --tail=100 <service>`. Script vẫn sẽ thử mở trang và chạy demo. |
| `ModuleNotFoundError: requests` | Tạo `.venv` và cài package theo bước 1; launcher dùng Python của `.venv` nếu có `requests`. |
| Alert có trong Prometheus/Alertmanager nhưng receiver trống | Mở URL receiver mới nhất được in ở terminal; xem log bằng `docker-compose logs --tail=100 alertmanager alert-receiver`. Receiver lưu lịch sử trong RAM, nên restart sẽ xóa sự kiện; alert còn firing có thể không được gửi lại trước `repeat_interval` 1 giờ. |

---

## 🎬 Kịch bản demo 5 phase

Mở dashboard Grafana trước hoặc để `start_demo.bat` mở tự động. Dùng các panel CPU, Latency, AI Score, System Health, RCA và Self-Healing để đối chiếu với trạng thái trong terminal.

Các giá trị bên dưới là kết quả mô phỏng dự kiến, có thể thay đổi theo thời điểm và dữ liệu metrics.

**Bảng Kịch bản Demo 5 Giai đoạn & Trạng thái 6 Panels trên Grafana:**

| Giai đoạn | Hành động & Nhịp nói với Giảng viên | Trạng thái hiển thị Chi tiết trên 6 Panels Grafana |
|:---|:---|:---|
| **Giai đoạn 1: Baseline** *(0:00 - 0:45)* | Gửi tải bình thường (2 req/s).<br>👉 *Nói:* "Hệ thống đang chạy ổn định, CPU ~20%, Latency ~40ms. Isolation Forest đang học phân bố hành vi bình thường của hệ thống." | • **Panel 1 (CPU):** Ổn định ở mức thấp ~20% (dưới xa vạch đỏ 80%).<br>• **Panel 2 (Latency):** Cực nhanh ~30-50ms (đáp ứng tốt).<br>• **Panel 3 (AI Score):** Rất thấp ~0.15 - 0.20 (vùng an toàn xanh).<br>• **Panel 4 (Status):** Xanh `✅ BÌNH THƯỜNG`.<br>• **Panel 5 (XAI RCA):** Các thanh cân bằng, không có độ lệch.<br>• **Panel 6 (Self-Healing):** `0` (hệ thống lành mạnh, chưa kích hoạt). |
| **Giai đoạn 2: Gray Failure** *(0:45 - 1:30)* | Bấm **[Enter]** để tiêm lỗi Gray Failure.<br>👉 *Nói:* "Sự cố xảy ra! Latency giật cục lên 2.5s khiến người dùng kêu ca, nhưng CPU chỉ ~42% (vẫn dưới ngưỡng 80%). Ngưỡng CPU tĩnh không báo vì CPU dưới 80%; rule latency riêng vẫn có thể cảnh báo." | • **Panel 1 (CPU):** Nhích lên ~42% $\rightarrow$ **VẪN DƯỚI vạch đỏ 80% (không báo động)**.<br>• **Panel 2 (Latency):** Vọt giật cục x30 lần (1.5 - 3.0s).<br>• **Panel 3 (AI Score):** Bắt đầu dốc đứng từ 0.2 $\rightarrow$ 0.6.<br>• **Panel 4 (Status):** Đang trong chu kỳ đánh giá cửa sổ trượt.<br>• **Panel 5 (XAI RCA):** Cột Latency bắt đầu tách nhóm vọt lên.<br>• **Panel 6 (Self-Healing):** Vẫn là `0`. |
| **Giai đoạn 3: AI Phát hiện & XAI** *(1:30 - 2:00)* | Bấm **[Enter]** để đo đạc và bóc tách XAI.<br>👉 *Nói:* "Chỉ sau 10s, AI phát hiện tương quan đa biến bị lệch chuẩn. Score vọt qua 0.7 báo động đỏ! Panel 5 chỉ rõ Latency đóng góp tới ~78% nguyên nhân sự cố." | • **Panel 1 (CPU):** Vẫn giữ nguyên ~42% (chứng minh tính chất ngầm định).<br>• **Panel 2 (Latency):** Duy trì ở đỉnh cao 2.0 - 2.8s.<br>• **Panel 3 (AI Score):** **VƯỢT VẠCH ĐỎ 0.70**, chạm mức 0.85 - 0.92.<br>• **Panel 4 (Status):** Chuyển đỏ rực: **`🚨 BẤT THƯỜNG`**.<br>• **Panel 5 (XAI RCA):** Cột **Latency chiếm ~78%** (đỏ), CPU ~16%, RPS ~6%.<br>• **Panel 6 (Self-Healing):** Tích lũy chuỗi cảnh báo chuẩn bị tự xử lý. |
| **Giai đoạn 4: Remediation mô phỏng** *(2:00 - 2:30)* | Bấm **[Enter]**; `run_demo.py` gửi POST tới `/api/remediate`, rồi chuyển traffic generator về chế độ bình thường.<br>👉 *Nói:* "Demo gửi yêu cầu reset trạng thái mô phỏng của app để minh họa bước remediation." | • Counter remediation tăng.<br>• CPU/RAM giả lập được đặt lại về baseline; latency giảm khi traffic chuyển về `normal`.<br>• Đây không phải thao tác restart container hay sửa máy thật. |
| **Giai đoạn 5: Tổng kết** | Terminal in bảng so sánh minh họa Static Threshold và AIOps. | Dùng để tổng kết kịch bản; các số liệu MTTD/MTTR trong bảng không phải benchmark production. |

---

### Kịch bản thủ công từng bước (Traffic Simulator & Chaos Engine)

Sử dụng script `traffic_sim.py` để chủ động điều khiển từng kịch bản tải theo ý muốn:

#### 1. Tạo dữ liệu baseline bình thường:
```powershell
.\.venv\Scripts\python.exe traffic_sim.py --mode normal
```
- Gửi đều đặn 2 req/s, CPU ~20%, latency ~30-50ms.
- Quan sát trên Grafana: AI Anomaly Score ở mức thấp ~0.2 (màu xanh).

#### 2. Kích hoạt sự cố Gray Failure:
Nhấn `Ctrl+C` dừng lệnh trên, sau đó chạy:
```powershell
.\.venv\Scripts\python.exe traffic_sim.py --mode anomaly
```
- CPU giả lập ~42%, dưới ngưỡng CPU 80%; alert latency của Prometheus là rule riêng.
- Latency giật cục 1.5 - 3.0s $\rightarrow$ Isolation Forest phát hiện tương quan đa biến, điểm AI Score vọt lên > 0.7 (cảnh báo đỏ).
- Panel 5 trên Grafana phân tích chi tiết nguyên nhân gốc rễ (XAI RCA).

#### 3. Các kịch bản Chaos Engineering mở rộng:
```powershell
# Kịch bản rò rỉ bộ nhớ (RAM tăng dần theo thời gian):
.\.venv\Scripts\python.exe traffic_sim.py --mode memory_leak

# Kịch bản vi nghẽn độ trễ (Micro-burst jitter):
.\.venv\Scripts\python.exe traffic_sim.py --mode jitter

# Kịch bản bão mã lỗi HTTP 500:
.\.venv\Scripts\python.exe traffic_sim.py --mode error_burst
```

#### 4. Kích hoạt Self-Healing (Tự chữa lành):
Mở một cửa sổ terminal mới và chạy:
```powershell
.\.venv\Scripts\python.exe traffic_sim.py --remediate
```
- Hệ thống gọi `/api/remediate` để đặt lại các metric giả lập về baseline; không giải phóng RAM hệ thống hoặc khởi động lại container. Panel 6 ghi nhận số lần phục hồi thành công.

### 🚨 Demo Prometheus Alertmanager

Luồng cảnh báo được hiện thực riêng với luồng remediation:

```text
App / AI Detector → Prometheus scrape metrics → Prometheus đánh giá alert rules
                                                   ↓ alert firing/resolved
                                         Alertmanager nhóm và định tuyến
                                                   ↓ webhook
                                      Local Alert Receiver (trang nhận alert)
```

Khi chạy `start_demo.bat`, các trang Prometheus, Alertmanager và receiver sẽ tự mở. Các trang này có vai trò khác nhau:

Mở các trang sau:

- `http://localhost:9090/alerts`: trạng thái alert của Prometheus, gồm `pending` và `firing`.
- `http://localhost:9093/#/alerts`: alert đang hoạt động trong Alertmanager; không cần nhập custom matcher để xem danh sách.
- Hộp thư webhook cục bộ: `start_demo.bat` sẽ in và mở URL. Nếu đã chạy Compose thủ công, lấy cổng bằng `docker-compose port alert-receiver 8081` rồi mở URL tương ứng, ví dụ `http://127.0.0.1:49154`.

Prometheus đánh giá các luật trong `prometheus/alert.rules.yml` mỗi 5 giây. Có rule cho app/AI Detector không scrape được, latency trung bình trên 1 giây, CPU giả lập trên 80%, và AI anomaly score trên 0.70. Rule `HighRequestLatency` độc lập với AI: nó dựa trên latency trung bình. Rule `AIOpsAnomalyDetected` dựa trên score của AI. Các điều kiện cần giữ liên tục 10 giây (`for: 10s`); sau đó Alertmanager đợi `group_wait: 3s` trước lần gửi đầu. Thời gian hiển thị có thể dài hơn do chu kỳ scrape/evaluation.

| Nơi xem | Ý nghĩa |
|---|---|
| Prometheus Alerts | Trạng thái rule (`inactive`, `pending`, `firing`) và điều kiện đang được đánh giá |
| Alertmanager Alerts | Alert đang hoạt động, nhóm, silence và receiver được chọn |
| Alert Receiver | Các webhook event `firing`/`resolved` mà receiver đã nhận; đây là lịch sử trong RAM, không phải danh sách alert hiện tại |

Nếu Alertmanager đang có alert nhưng receiver trống, xem log bằng `docker-compose logs --tail=100 alertmanager alert-receiver`. Receiver mất lịch sử khi container khởi động lại; trong khi alert còn firing, `repeat_interval` hiện là 1 giờ nên có thể chưa nhận lại thông báo firing. Để demo lại, đợi alert resolve rồi kích hoạt lại điều kiện.

Để trình diễn một alert chắc chắn, dừng app:

```powershell
docker-compose stop app
```

Sau khoảng 20 giây, `AppTargetDown` sẽ chuyển từ `pending` sang `firing`; Prometheus gửi alert đến Alertmanager, rồi webhook sẽ xuất hiện tại hộp thư receiver. `start_demo.bat` tự mở trang này; nếu chạy Docker Compose thủ công, dùng `docker-compose port alert-receiver 8081` để xem cổng host. Khởi động lại app để xem alert được gửi trạng thái resolved:

```powershell
docker-compose start app
```

Có thể xem log của hai thành phần xử lý thông báo bằng:

```powershell
docker-compose logs -f alertmanager alert-receiver
```

Trong demo này, Alertmanager gửi webhook đến receiver cục bộ, không gửi tin nhắn ra Telegram/Slack/email. Receiver giữ tối đa 200 sự kiện trong bộ nhớ; khởi động lại receiver sẽ xóa lịch sử hiển thị. Alerting chỉ báo sự cố; nó không tự sửa app và tách biệt với remediation mô phỏng ở `run_demo.py`/AI Detector.

---

## 📁 Cấu trúc Thư mục Dự án

```
cloud-seminar/
├── start_demo.bat              # Entry point chính trên Windows; chạy toàn bộ stack và demo
├── start_demo.ps1              # Luồng PowerShell được start_demo.bat gọi
├── start_demo.py               # Runner Python thay thế; không cần dùng khi chạy file .bat
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

> 📖 **Xem giải thích chi tiết về thuật toán, mô hình toán học và bối cảnh SRE tại:** [INSTRUCTION.md](./INSTRUCTION.md)
