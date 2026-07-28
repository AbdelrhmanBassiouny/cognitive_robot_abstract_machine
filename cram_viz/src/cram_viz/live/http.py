"""HTTP endpoints of the live bridge (default port 8765).

    GET /info    {running, robot, objects, plan, chart, seq}
    GET /state   {seq, frames: {prefixed_joint: pos}, base: pose7,
                  objects: {mesh_key: pose7}}
    GET /objects geometry catalog (mesh served via /mesh?key=)
    GET /plan    {sig, nodes: [{id, parent, kind, label, status, derived}]}
    GET /chart   {sig, title, nodes: [{id, parent, name, cls, life, obs}],
                  edges: [{from, to, kind}]}
    POST /move   queue an object move (applied on the simulation thread)

Handlers only ever read finished snapshot dicts — never the world (see
hooks.py).
"""

import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cram_viz.live.bridge import BRIDGE

PORT = int(os.environ.get("LIVE_VIZ_PORT", "8765"))


class Handler(BaseHTTPRequestHandler):
    def _json(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/state"):
            return self._json(BRIDGE.get_state())
        if self.path.startswith("/plan"):
            return self._json(BRIDGE.get_plan())
        if self.path.startswith("/chart"):
            return self._json(BRIDGE.get_chart())
        if self.path.startswith("/objects"):
            with BRIDGE._lock:
                return self._json({"objects": list(BRIDGE.object_meta)})
        if self.path.startswith("/mesh"):
            return self._mesh()
        if self.path.startswith("/info"):
            return self._json({
                "running": BRIDGE.world is not None,
                "robot": type(BRIDGE.robot).__name__ if BRIDGE.robot else None,
                "objects": [k for k in BRIDGE._bodies if k != "__base__"],
                "movable": True,
                "plan": bool(BRIDGE.plan_state.get("nodes")),
                "chart": bool(BRIDGE.chart_state.get("nodes")),
                "seq": BRIDGE.seq,
            })
        self.send_response(404)
        self.end_headers()

    def _mesh(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        key = (q.get("key") or [""])[0]
        path = BRIDGE._mesh_serve.get(key)      # plain dict read; file IO only, no world access
        if not path or not os.path.isfile(path):
            self.send_response(404)
            self.end_headers()
            return
        data = open(path, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path.startswith("/move"):
            try:
                length = int(self.headers.get("Content-Length") or 0)
                req = json.loads(self.rfile.read(length) or b"{}")
                BRIDGE.queue_move(req)
                return self._json({"ok": True})
            except Exception as ex:
                return self._json({"ok": False, "error": str(ex)})
        self.send_response(404)
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.end_headers()

    def log_message(self, *a):
        pass


def serve(port=PORT):
    """Start the bridge's HTTP server on a daemon thread; returns the server."""
    import threading

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
