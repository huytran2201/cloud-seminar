"""Tiny local webhook receiver for the Prometheus Alertmanager demo."""

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading


HOST = "0.0.0.0"
PORT = 8081
MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_EVENTS = 200
events = []
events_lock = threading.Lock()


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="30">
  <title>Local Alert Receiver</title>
  <style>
    body { font: 15px system-ui, sans-serif; margin: 2rem auto; max-width: 1100px; padding: 0 1rem; background: #10151c; color: #e8edf2; }
    h1 { margin-bottom: .3rem; } .muted { color: #aab6c2; }
    table { border-collapse: collapse; width: 100%; margin-top: 1.5rem; }
    th, td { border-bottom: 1px solid #34404d; text-align: left; padding: .75rem; vertical-align: top; }
    th { color: #aab6c2; } .firing { color: #ff7b72; font-weight: 700; }
    .resolved { color: #7ee787; font-weight: 700; } code { color: #a5d6ff; }
  </style>
</head>
<body>
  <h1>Alertmanager Webhook Receiver</h1>
  <div class="muted">Local demo inbox. This page refreshes automatically every 5 seconds.</div>
  <div id="count" class="muted">Loading alerts…</div>
  <table>
    <thead><tr><th>Received</th><th>State</th><th>Alert</th><th>Severity</th><th>Details</th></tr></thead>
    <tbody id="rows"></tbody>
  </table>
  <script>
    async function refreshAlerts() {
      const response = await fetch('/alerts');
      const alerts = await response.json();
      const rows = document.getElementById('rows');
      rows.replaceChildren();
      document.getElementById('count').textContent = `${alerts.length} alert event(s) received`;
      for (const alert of alerts) {
        const row = document.createElement('tr');
        const values = [alert.receivedAt, alert.status, alert.alertname,
          alert.severity, alert.summary || alert.description || ''];
        values.forEach((value, index) => {
          const cell = document.createElement('td');
          cell.textContent = value || '—';
          if (index === 1) cell.className = alert.status === 'firing' ? 'firing' : 'resolved';
          row.appendChild(cell);
        });
        rows.appendChild(row);
      }
    }
    refreshAlerts();
    setInterval(refreshAlerts, 5000);
  </script>
</body>
</html>"""


class ReceiverHandler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {"status": "healthy"})
            return

        if self.path == "/alerts":
            with events_lock:
                snapshot = list(reversed(events))
            self.send_json(200, snapshot)
            return

        if self.path == "/":
            encoded = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return

        self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/webhook":
            self.send_json(404, {"error": "not found"})
            return

        try:
            body_size = int(self.headers.get("Content-Length", "0"))
            if body_size <= 0 or body_size > MAX_BODY_BYTES:
                self.send_json(413, {"error": "invalid payload size"})
                return
            payload = json.loads(self.rfile.read(body_size))
        except (ValueError, json.JSONDecodeError):
            self.send_json(400, {"error": "invalid JSON payload"})
            return

        incoming = payload.get("alerts", [])
        received_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        new_events = []
        for alert in incoming:
            labels = alert.get("labels", {})
            annotations = alert.get("annotations", {})
            new_events.append({
                "receivedAt": received_at,
                "status": alert.get("status", payload.get("status", "unknown")),
                "alertname": labels.get("alertname", "unknown"),
                "severity": labels.get("severity", "unknown"),
                "summary": annotations.get("summary", ""),
                "description": annotations.get("description", ""),
                "labels": labels,
                "startsAt": alert.get("startsAt", ""),
                "endsAt": alert.get("endsAt", ""),
            })

        with events_lock:
            events.extend(new_events)
            del events[:-MAX_EVENTS]

        print(json.dumps({"received": len(new_events), "status": payload.get("status")}), flush=True)
        self.send_json(200, {"status": "received", "alerts": len(new_events)})

    def log_message(self, format_string, *args):
        print(f"{self.address_string()} - {format_string % args}", flush=True)


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), ReceiverHandler)
    print(f"Alert receiver listening on http://{HOST}:{PORT}", flush=True)
    server.serve_forever()
