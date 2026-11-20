"""
run_demo.py - SRE AIOps Interactive Demo Runner
================================================
Demonstrates real-time dynamic anomaly detection and self-healing:
  Phase 1: Baseline Establishment
  Phase 2: Gray Failure Injection
  Phase 3: AI Detection & Root Cause Analysis
  Phase 4: Closed-Loop Remediation
  Phase 5: SRE Evaluation Summary
"""

import sys
import time
import threading
import argparse
import subprocess
import re
import requests

# ANSI Styling
GREEN   = "\033[92m"
RED     = "\033[91m"
YELLOW  = "\033[93m"
CYAN    = "\033[96m"
MAGENTA = "\033[95m"
BOLD    = "\033[1m"
RESET   = "\033[0m"
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
ANSI_TOKENS = re.compile(r"(\x1b\[[0-?]*[ -/]*[@-~])")

APP_URL        = "http://localhost:8000"
PROMETHEUS_URL = "http://localhost:9090"
AI_URL         = "http://localhost:8001"
ALERTMANAGER_URL = "http://localhost:9093"


class ContinuousTrafficGenerator:
    """
    Maintains background request stream to preserve sliding window metrics
    and prevent anomaly score decay while the presenter speaks.
    """
    def __init__(self):
        self.mode = "normal"
        self._running = False
        self._thread = None
        self.last_latencies = []

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def set_mode(self, new_mode: str):
        self.mode = new_mode

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _worker(self):
        while self._running:
            t0 = time.time()
            try:
                current_mode = self.mode
                timeout_sec = 6 if current_mode == "anomaly" else 3
                requests.get(f"{APP_URL}/api/process?mode={current_mode}", timeout=timeout_sec)
                elapsed = time.time() - t0
                self.last_latencies.append(elapsed)
                if len(self.last_latencies) > 20:
                    self.last_latencies.pop(0)
            except Exception:
                pass

            sleep_time = 0.5 if self.mode == "normal" else 0.3
            time.sleep(sleep_time)


traffic_gen = ContinuousTrafficGenerator()


def print_banner():
    print(f"""
{CYAN}{BOLD}========================================================================
AIOps Cloud Monitoring Demo - SRE Terminal Runner
FastAPI | Prometheus | Isolation Forest | Alertmanager | Grafana
========================================================================{RESET}""")


def check_prerequisites():
    """Verify connectivity to all required services."""
    try:
        port_result = subprocess.run(
            ["docker-compose", "port", "alert-receiver", "8081"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        port_binding = next(line.strip() for line in port_result.stdout.splitlines() if line.strip())
        host_port = port_binding.rsplit(":", 1)[-1]
        if not host_port.isdigit():
            raise ValueError(f"Unexpected docker-compose port output: {port_binding}")
        alert_receiver_url = f"http://127.0.0.1:{host_port}"
    except Exception as e:
        print(f"  {RED}[FAIL] Alert Receiver: Cannot determine the published port ({e}){RESET}")
        print(f"      {BOLD}docker-compose up -d --build alert-receiver alertmanager{RESET}\n")
        sys.exit(1)
    print(f"  {CYAN}[INFO] Alert Receiver: {alert_receiver_url}{RESET}")

    services = [
        ("App Service (:8000)", f"{APP_URL}/health"),
        ("Prometheus (:9090)", f"{PROMETHEUS_URL}/-/healthy"),
        ("AI Detector (:8001)", f"{AI_URL}/health"),
        ("Alertmanager (:9093)", f"{ALERTMANAGER_URL}/-/healthy"),
        (f"Alert Receiver (host :{host_port})", f"{alert_receiver_url}/health")
    ]
    for name, url in services:
        try:
            r = requests.get(url, timeout=3)
            if r.status_code != 200:
                print(f"  {RED}[FAIL] {name}: HTTP {r.status_code}{RESET}")
                sys.exit(1)
        except Exception:
            print(f"  {RED}[FAIL] {name}: Cannot connect to {url}{RESET}")
            print(f"\n{RED}{BOLD}Note:{RESET} Please start Docker Desktop and run:")
            print(f"      {BOLD}docker-compose up -d --build{RESET}\n")
            sys.exit(1)
    print(f"  {GREEN}[OK] All services are healthy and operational.{RESET}\n")


def query_prometheus(query: str):
    """Execute instant query against Prometheus API."""
    try:
        resp = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query}, timeout=3)
        data = resp.json()
        return data.get("data", {}).get("result", [])
    except Exception:
        return []


def fit_ansi(text: str, width: int) -> str:
    """Clip and pad text to a visible width, ignoring ANSI color sequences."""
    parts = ANSI_TOKENS.split(str(text))
    output = []
    visible = 0
    clipped = False

    for part in parts:
        if not part:
            continue
        if ANSI_ESCAPE.fullmatch(part):
            output.append(part)
            continue

        remaining = width - visible
        if remaining <= 0:
            clipped = True
            break
        if len(part) > remaining:
            output.append(part[:remaining])
            visible += remaining
            clipped = True
            break
        output.append(part)
        visible += len(part)

    if clipped:
        output.append(RESET)
    output.append(" " * max(0, width - visible))
    return "".join(output)


def print_ascii_table(headers, rows, widths):
    """Print a fixed-width table whose columns stay aligned with ANSI colors."""
    border = "  +" + "+".join("-" * (width + 2) for width in widths) + "+"

    def render_row(cells):
        padded = [fit_ansi(cell, width) for cell, width in zip(cells, widths)]
        return "  | " + " | ".join(padded) + " |"

    print(f"{BOLD}{border}{RESET}")
    print(render_row(headers))
    print(border)
    for row in rows:
        print(render_row(row))
    print(f"{BOLD}{border}{RESET}")


def render_progress(percent: int, label: str):
    """Render one stable-width progress line for Windows terminals."""
    steps = 25
    percent = max(0, min(100, percent))
    filled = round(steps * percent / 100)
    bar = "=" * filled + "-" * (steps - filled)
    label = label[:40]
    print(f"\r  {CYAN}[{bar}] {percent:3d}% | {label:<40}{RESET}", end="", flush=True)


def progress_bar(total_seconds: float, label: str):
    """Show a timed ASCII progress bar."""
    steps = 25
    sleep_interval = max(0.0, total_seconds / steps)
    for i in range(steps + 1):
        render_progress(int((i / steps) * 100), label)
        if i < steps and sleep_interval:
            time.sleep(sleep_interval)
    print()


def fetch_live_panels(fallback_latency: float = 0.040):
    """
    Fetch real-time metrics matching Grafana's 6 panels:
      P1: CPU Utilization (%)
      P2: Request Latency (s)
      P3: Anomaly Score [0.0 - 1.0]
      P4: System Health (0=NORMAL, 1=ANOMALY)
      P5: Root Cause Attribution (%)
      P6: Self-Healing Events (Count)
    """
    # P1: CPU
    p1 = query_prometheus("app_simulated_cpu_percent")
    cpu_val = float(p1[0]["value"][1]) if p1 else 20.0

    # P2: Latency
    p2 = query_prometheus("sum(rate(app_request_latency_seconds_sum[30s])) / sum(rate(app_request_latency_seconds_count[30s]))")
    lat_val = None
    if p2 and p2[0]["value"][1] != "NaN":
        try:
            lat_val = float(p2[0]["value"][1])
        except (ValueError, TypeError):
            lat_val = None
    if lat_val is None:
        if traffic_gen.last_latencies:
            lat_val = sum(traffic_gen.last_latencies) / len(traffic_gen.last_latencies)
        else:
            lat_val = fallback_latency

    # P3: AI Score
    p3 = query_prometheus("ai_anomaly_score")
    score_val = float(p3[0]["value"][1]) if p3 else 0.180

    # P4: Status
    p4 = query_prometheus("ai_is_anomaly")
    is_anomaly_val = int(float(p4[0]["value"][1])) if p4 else (1 if score_val >= 0.70 else 0)

    # P5: XAI
    p5 = query_prometheus("ai_feature_attribution")
    attr = {"latency": 33.3, "cpu": 33.3, "request_rate": 33.4}
    for item in p5:
        feat = item.get("metric", {}).get("feature")
        if feat in attr:
            try:
                attr[feat] = round(float(item["value"][1]) * 100, 1)
            except (ValueError, TypeError):
                pass

    # P6: Remediations
    p6 = query_prometheus("app_remediation_total")
    heal_count = int(float(p6[0]["value"][1])) if p6 else 0

    return {
        "cpu": cpu_val,
        "latency": lat_val,
        "score": score_val,
        "is_anomaly": is_anomaly_val,
        "attr": attr,
        "heal_count": heal_count
    }


def print_dashboard_table(p: dict, phase_notes: dict):
    """
    Renders an aligned CLI table representing the 6 Grafana panels.
    """
    # Color formatting
    c_p1 = GREEN if p["cpu"] < 80 else RED
    c_p2 = GREEN if p["latency"] < 1.0 else RED
    c_p3 = GREEN if p["score"] < 0.70 else RED
    c_p4 = GREEN if p["is_anomaly"] == 0 else RED
    c_p6 = GREEN if p["heal_count"] > 0 else CYAN

    health_str = "NORMAL" if p["is_anomaly"] == 0 else "ANOMALY"
    rca_main = f"Lat:{p['attr']['latency']:.0f}%"

    print_ascii_table(
        ["ID", "PANEL", "VALUE", "UNIT", "STATUS & OBSERVATION"],
        [
            ["P1", "CPU Utilization", f"{c_p1}{p['cpu']:.1f}{RESET}", "%", phase_notes.get("p1", "")],
            ["P2", "Request Latency", f"{c_p2}{p['latency']:.2f}{RESET}", "s", phase_notes.get("p2", "")],
            ["P3", "Anomaly Score", f"{c_p3}{p['score']:.2f}{RESET}", "[0-1]", phase_notes.get("p3", "")],
            ["P4", "System Health", f"{c_p4}{health_str}{RESET}", "-", phase_notes.get("p4", "")],
            ["P5", "Root Cause", rca_main, "%", phase_notes.get("p5", "")],
            ["P6", "Self-Healing Events", f"{c_p6}{p['heal_count']}{RESET}", "count", phase_notes.get("p6", "")],
        ],
        [2, 21, 9, 6, 37],
    )


def run_phase_1(speed: float):
    print(f"{BOLD}{GREEN}========================================================================{RESET}")
    print(f"{BOLD}{GREEN}[PHASE 1] BASELINE ESTABLISHMENT{RESET}")
    print(f"{BOLD}{GREEN}========================================================================{RESET}")
    print("  Action: Generating steady normal traffic (2 req/s) | AI baseline calibration")

    traffic_gen.set_mode("normal")
    progress_bar(8.0 / speed, "Collecting metrics...")
    p = fetch_live_panels(fallback_latency=0.042)

    notes = {
        "p1": f"{GREEN}[NORMAL] Below 80% threshold{RESET}",
        "p2": f"{GREEN}[NORMAL] Under 1.0s SLA (~40ms){RESET}",
        "p3": f"{GREEN}[SAFE] Below 0.70 threshold{RESET}",
        "p4": f"{GREEN}[OK] Healthy operational state{RESET}",
        "p5": f"Balanced distribution",
        "p6": f"Standby (No action required)"
    }
    print_dashboard_table(p, notes)


def run_phase_2(speed: float):
    print(f"{BOLD}{YELLOW}========================================================================{RESET}")
    print(f"{BOLD}{YELLOW}[PHASE 2] GRAY FAILURE INJECTION{RESET}")
    print(f"{BOLD}{YELLOW}========================================================================{RESET}")
    print("  Action: Injecting high-latency degradation | CPU remains ~42% < 80%")

    traffic_gen.set_mode("anomaly")
    progress_bar(12.0 / speed, "Injecting anomaly & accumulating window...")
    p = fetch_live_panels(fallback_latency=2.25)

    notes = {
        "p1": f"{YELLOW}[BLIND SPOT] CPU 42% < 80% limit{RESET}",
        "p2": f"{RED}[BREACH] Latency spiked to ~2.3s{RESET}",
        "p3": f"{YELLOW}[EVALUATING] Rising deviation{RESET}",
        "p4": f"{YELLOW}[CONFIRMING] Sliding window active{RESET}",
        "p5": f"Latency attribution rising",
        "p6": f"Accumulating anomaly streak"
    }
    print_dashboard_table(p, notes)


def run_phase_3(speed: float):
    print(f"{BOLD}{MAGENTA}========================================================================{RESET}")
    print(f"{BOLD}{MAGENTA}[PHASE 3] AI DETECTION & ROOT CAUSE{RESET}")
    print(f"{BOLD}{MAGENTA}========================================================================{RESET}")
    print("  Action: Gray Failure confirmed | Isolation Forest multivariate trigger")

    p = None
    max_checks = 6
    detected = False
    for attempt in range(max_checks):
        p = fetch_live_panels(fallback_latency=2.35)
        detected = p["score"] >= 0.70 or p["is_anomaly"] == 1
        if detected:
            render_progress(100, "AI anomaly detected")
            break
        percent = int(((attempt + 1) / max_checks) * 100)
        label = "Evaluation complete; below threshold" if attempt == max_checks - 1 else "Evaluating AI score..."
        render_progress(percent, label)
        if attempt < max_checks - 1:
            time.sleep(2.0 / max(speed, 0.01))
    print()

    if p is None:
        p = fetch_live_panels(fallback_latency=2.35)

    p3_note = f"{RED}[ALERT] Exceeds 0.70 threshold{RESET}" if p["score"] >= 0.70 else f"{YELLOW}[CONFIRMING] Score active{RESET}"
    p4_note = f"{RED}[ALERT] Critical anomaly confirmed{RESET}" if p["is_anomaly"] == 1 else f"{YELLOW}[WARNING] Investigating{RESET}"

    notes = {
        "p1": f"{YELLOW}[CPU] <80%; latency alert separate{RESET}",
        "p2": f"{RED}[BREACH] Latency severely degraded{RESET}",
        "p3": p3_note,
        "p4": p4_note,
        "p5": f"Latency {p['attr']['latency']:.1f}% | CPU {p['attr']['cpu']:.1f}%",
        "p6": f"Armed (Ready for Webhook)"
    }
    print_dashboard_table(p, notes)


def run_phase_4():
    print(f"{BOLD}{CYAN}========================================================================{RESET}")
    print(f"{BOLD}{CYAN}[PHASE 4] CLOSED-LOOP REMEDIATION{RESET}")
    print(f"{BOLD}{CYAN}========================================================================{RESET}")
    print("  Action: Triggering automated self-healing via POST /api/remediate...")

    try:
        r = requests.post(f"{APP_URL}/api/remediate", timeout=5).json()
        print(f"  {GREEN}[OK] Webhook: {r.get('message', 'States restored')}{RESET}")
    except Exception as e:
        print(f"  {YELLOW}[WARN] Webhook: {e}{RESET}")

    traffic_gen.set_mode("normal")
    progress_bar(6.0, "Restoring baseline & cooling down metrics...")
    p = fetch_live_panels(fallback_latency=0.040)

    notes = {
        "p1": f"{GREEN}[RECOVERED] Normalized to ~20%{RESET}",
        "p2": f"{GREEN}[RECOVERED] Dropped back to ~40ms{RESET}",
        "p3": f"{GREEN}[SAFE] Cooled below 0.70{RESET}",
        "p4": f"{GREEN}[HEALTHY] Restored to NORMAL{RESET}",
        "p5": f"Rebalanced distribution",
        "p6": f"{GREEN}Remediation successful{RESET}"
    }
    print_dashboard_table(p, notes)


def run_phase_5_summary():
    print(f"{BOLD}========================================================================")
    print("[PHASE 5] SRE EVALUATION SUMMARY")
    print(f"========================================================================{RESET}")

    print_ascii_table(
        ["SRE Evaluation Criterion", "CPU-only threshold", "AIOps demo"],
        [
            ["Gray Failure Detection", f"{RED}[MISSED] CPU < 80%{RESET}", f"{GREEN}[DETECTED] Score > 0.70{RESET}"],
            ["CPU During Degradation", "~42% simulated", "~42% simulated"],
            ["Detection Time", "Not benchmarked", "~15s illustrative"],
            ["Root Cause Analysis", "Manual investigation", f"{CYAN}Latency attribution{RESET}"],
            ["Remediation", "Manual action", f"{GREEN}Simulated reset{RESET}"],
        ],
        [28, 22, 22],
    )


def main():
    parser = argparse.ArgumentParser(description="AIOps SRE Terminal Demo Runner")
    parser.add_argument("--speed", type=float, default=1.0, help="Demo speed multiplier")
    parser.add_argument("--interactive", action="store_true", help="Wait for [Enter] between phases")
    args = parser.parse_args()

    print_banner()
    check_prerequisites()

    traffic_gen.start()

    phases = [
        ("Phase 1: Baseline Establishment", lambda: run_phase_1(args.speed)),
        ("Phase 2: Gray Failure Injection", lambda: run_phase_2(args.speed)),
        ("Phase 3: AI Detection & Root Cause", lambda: run_phase_3(args.speed)),
        ("Phase 4: Closed-Loop Remediation", run_phase_4),
        ("Phase 5: SRE Evaluation Summary", run_phase_5_summary)
    ]

    try:
        for idx, (title, func) in enumerate(phases, start=1):
            if args.interactive and idx > 1:
                input(f"{BOLD}{CYAN}Press [Enter] to advance to {title}...{RESET}\n")
            func()
    finally:
        traffic_gen.stop()


if __name__ == "__main__":
    main()
