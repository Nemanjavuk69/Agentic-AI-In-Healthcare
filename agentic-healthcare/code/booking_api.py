from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import uuid

class Handler(BaseHTTPRequestHandler):

    def do_POST(self):
        if self.path == "/book":

            length = int(self.headers["Content-Length"])
            data = json.loads(self.rfile.read(length))

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

server = HTTPServer(("localhost", 8000), Handler)
print("Fake API running on port 8000")
server.serve_forever()
