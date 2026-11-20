"""
start_demo.py - 1-Click Master Runner for AIOps Cloud Demo
===========================================================
Automates:
  1. Docker Engine verification
  2. docker-compose up -d --build
  3. Application, monitoring and alerting healthcheck polling
  4. Auto-launch Grafana and local Alert Receiver in browser
  5. Interactive 5-phase SRE demonstration (run_demo.py --interactive)
"""

import sys
import time
import subprocess
import webbrowser
import requests

CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def main():
    print(f"""
{CYAN}{BOLD}========================================================================
AIOps & Cloud Monitoring Demo - 1-Click Master Runner
Workflow: Docker Services -> Open Grafana Browser -> Interactive Demo
========================================================================{RESET}
""")

    # 1. Verify Docker
    print(f"{YELLOW}[1/4] Checking Docker daemon status...{RESET}")
    try:
        res = subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode != 0:
            raise FileNotFoundError()
        print(f"  {GREEN}[OK] Docker engine is running.{RESET}\n")
    except Exception:
        print(f"  {RED}[ERROR] Docker is not running or not installed!{RESET}")
        print(f"  {YELLOW}Please launch Docker Desktop, wait for it to start, then re-run.{RESET}\n")
        input("Press [Enter] to exit...")
        sys.exit(1)

    # 2. Launch docker-compose
    print(f"{YELLOW}[2/4] Starting 6 services (App, AI Detector, Prometheus, Alertmanager, Receiver, Grafana)...{RESET}")
    compose_res = subprocess.run(["docker-compose", "up", "-d", "--build"])
    if compose_res.returncode != 0:
        print(f"  {RED}[ERROR] Failed to start docker-compose!{RESET}")
        input("Press [Enter] to exit...")
        sys.exit(1)

    try:
        port_res = subprocess.run(
            ["docker-compose", "port", "alert-receiver", "8081"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        port_binding = next(line.strip() for line in port_res.stdout.splitlines() if line.strip())
        receiver_port = port_binding.rsplit(":", 1)[-1]
        if not receiver_port.isdigit():
            raise ValueError(f"Unexpected docker-compose port output: {port_binding}")
        receiver_url = f"http://127.0.0.1:{receiver_port}"
        print(f"  {CYAN}[INFO] Alert Receiver: {receiver_url}{RESET}")
    except Exception as e:
        print(f"  {RED}[ERROR] Cannot determine Alert Receiver port: {e}{RESET}")
        sys.exit(1)

    # 3. Wait for services healthy
    print(f"\n{YELLOW}[3/4] Waiting for all services to become healthy...{RESET}")
    ready = False
    for _ in range(25):
        try:
            r1 = requests.get("http://localhost:8000/health", timeout=2)
            r2 = requests.get("http://localhost:9090/-/healthy", timeout=2)
            r3 = requests.get("http://localhost:8001/health", timeout=2)
            r4 = requests.get("http://localhost:9093/-/healthy", timeout=2)
            r5 = requests.get(f"{receiver_url}/health", timeout=2)
            if all(r.status_code == 200 for r in (r1, r2, r3, r4, r5)):
                ready = True
                break
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(2)
    print()

    if ready:
        print(f"  {GREEN}[OK] Application, monitoring and alerting services are healthy.{RESET}\n")
    else:
        print(f"  {YELLOW}[WARN] Services taking longer to respond, proceeding with connection...{RESET}\n")

    # 4. Open Grafana
    print(f"{GREEN}[4/4] Opening Grafana Dashboard in default browser (http://localhost:3000)...{RESET}\n")
    webbrowser.open("http://localhost:3000")
    webbrowser.open(receiver_url)
    time.sleep(2)

    # 5. Execute interactive demo
    subprocess.run([sys.executable, "run_demo.py", "--interactive"])

    # 6. Cleanup prompt
    print()
    choice = input("Do you want to stop the Docker containers now? (y/n, default: n): ").strip().lower()
    if choice == "y":
        print(f"{YELLOW}Stopping containers...{RESET}")
        subprocess.run(["docker-compose", "down"])
        print(f"{GREEN}[OK] All services stopped safely.{RESET}")
    else:
        print(f"{CYAN}Containers remain running in background. Explore Grafana at http://localhost:3000{RESET}")
        print("To stop them later, run: docker-compose down")


if __name__ == "__main__":
    main()
