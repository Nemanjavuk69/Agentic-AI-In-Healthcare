from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import uuid
import os

BOOKING_API_KEY = os.environ.get("BOOKING_API_KEY", "")

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/book":
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "not found"}).encode())
            return

        # ── Mitigation: authenticate caller ─────────────────────────────────
        auth = self.headers.get("Authorization", "")
        expected = f"Bearer {BOOKING_API_KEY}" if BOOKING_API_KEY else ""
        if BOOKING_API_KEY and auth != expected:
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "unauthorized"}).encode())
            return

        try:
            length = int(self.headers["Content-Length"])
            data = json.loads(self.rfile.read(length))

            # ── Mitigation: validate required fields ─────────────────────────
            required_fields = {"hospital", "specialty", "time", "patient_id"}
            if not required_fields.issubset(data.keys()):
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "missing required fields"}).encode())
                return

            response = {
                "status": "confirmed",
                "booking_ref": str(uuid.uuid4())[:8],
                "hospital": data["hospital"],
                "specialty": data["specialty"],
                "time": data["time"]
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        except Exception:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "bad request"}).encode())

server = HTTPServer(("localhost", 8000), Handler)
print("Fake API running on port 8000")
server.serve_forever()