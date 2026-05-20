### File 5: `pentest_tools/dashboard/server.py` (MODIFIED — add probe routes)

```python
"""Dashboard server — add PROBE routes."""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from .probe_runner import probe_runner, ProbeAlreadyRunning
from ..llm.providers import OpenRouterProvider
import os


class DashboardHandler(BaseHTTPRequestHandler):
    
    def do_POST(self):
        if self.path == "/api/probe/start":
            self._handle_probe_start()
        else:
            self.send_error(404)
    
    def do_GET(self):
        if self.path == "/api/probe/stream":
            self._handle_probe_stream()
        elif self.path.startswith("/static/"):
            self._handle_static()
        else:
            super().do_GET()
    
    def _handle_probe_start(self):
        """Start a new probe run."""
        # Check RECON_ENABLED
        if not os.getenv("RECON_ENABLED"):
            self.send_json(403, {"error": "RECON_ENABLED not set"})
            return
        
        # Parse request
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length))
        
        base_url = body.get("base_url")
        roe_profile = body.get("roe_profile", "roe/local-lab.yaml")
        
        if not base_url:
            self.send_json(400, {"error": "base_url required"})
            return
        
        # Create LLM provider
        provider = OpenRouterProvider(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            default_model=os.getenv("OPENROUTER_DEFAULT_MODEL", ""),
        )
        
        try:
            run_id = probe_runner.start(
                base_url=base_url,
                roe_profile_path=roe_profile,
                llm_provider=provider,
                max_turns=int(os.getenv("PROBE_MAX_TURNS", "10")),
            )
            self.send_json(200, {"run_id": run_id})
        except ProbeAlreadyRunning:
            self.send_json(409, {"error": "A probe is already running"})
        except FileNotFoundError:
            self.send_json(400, {"error": f"RoE profile not found: {roe_profile}"})
        except Exception as e:
            self.send_json(500, {"error": str(e)})
    
    def _handle_probe_stream(self):
        """SSE stream for live probe events."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        
        try:
            for event in probe_runner.events():
                self.wfile.write(event.encode())
                self.wfile.flush()
        except Exception as e:
            error_event = f"event: error\ndata: {{\"error\": \"{str(e)}\"}}\n\n"
            self.wfile.write(error_event.encode())
            self.wfile.flush()
    
    def send_json(self, status: int, data: dict):
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
```

