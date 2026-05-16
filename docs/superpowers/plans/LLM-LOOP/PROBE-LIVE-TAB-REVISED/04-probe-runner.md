### File 4: `pentest_tools/dashboard/probe_runner.py` (NEW — live monitoring backend)

```python
"""ProbeRunner — runs HackerLoop in background thread with live event streaming."""

import threading
import queue
import uuid
import json
import logging
from typing import Iterator, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProbeRun:
    """Tracks a single probe execution."""
    run_id: str
    base_url: str
    roe_profile: str
    status: str  # "running" | "done" | "error"
    events: queue.Queue
    thread: Optional[threading.Thread] = None
    error: Optional[str] = None


class ProbeRunner:
    """Manages probe loop execution with event streaming."""
    
    def __init__(self):
        self._active_run: Optional[ProbeRun] = None
        self._lock = threading.Lock()
    
    def start(
        self,
        base_url: str,
        roe_profile_path: str,
        llm_provider,
        max_turns: int = 10,
    ) -> str:
        """Start a probe run. Returns run_id. Raises if already running."""
        with self._lock:
            if self._active_run and self._active_run.status == "running":
                raise ProbeAlreadyRunning(
                    f"Probe {self._active_run.run_id} is still running"
                )
            
            run_id = str(uuid.uuid4())[:8]
            run = ProbeRun(
                run_id=run_id,
                base_url=base_url,
                roe_profile=roe_profile_path,
                status="running",
                events=queue.Queue(),
            )
            
            # Load RoE profile
            roe = self._load_roe(roe_profile_path)
            
            # Create HackerLoop with event callback
            from ..hacker_loop import HackerLoop
            
            loop = HackerLoop(
                llm=llm_provider,
                target_url=base_url,
                roe_profile=roe,
                max_turns=max_turns,
                event_callback=lambda event_type, data: run.events.put(
                    self._format_sse(event_type, data)
                ),
            )
            
            # Run in daemon thread
            thread = threading.Thread(
                target=self._run_loop,
                args=(loop, run),
                daemon=True,
            )
            run.thread = thread
            self._active_run = run
            thread.start()
            
            logger.info(f"Probe started: {run_id} → {base_url}")
            return run_id
    
    def events(self) -> Iterator[str]:
        """Generator that yields SSE-formatted events from the active run."""
        if not self._active_run:
            yield self._format_sse("error", {"message": "No active probe"})
            return
        
        run = self._active_run
        while True:
            try:
                # Block for 1 second, then check if done
                event = run.events.get(timeout=1.0)
                yield event
                
                # Check if this was a done/error event
                if '"event":"done"' in event or '"event":"error"' in event:
                    break
                    
            except queue.Empty:
                # Check if thread died
                if run.thread and not run.thread.is_alive():
                    if run.status == "running":
                        run.status = "error"
                        run.error = "Probe thread died unexpectedly"
                        yield self._format_sse("error", {"message": run.error})
                    break
                continue
        
        # Cleanup
        with self._lock:
            self._active_run = None
    
    def _run_loop(self, loop, run: ProbeRun):
        """Run the HackerLoop in a thread, capturing all exceptions."""
        try:
            loop.run()
            run.status = "done"
        except Exception as e:
            logger.exception("Probe loop failed")
            run.status = "error"
            run.error = str(e)
            run.events.put(
                self._format_sse("error", {"message": str(e)})
            )
    
    def _format_sse(self, event_type: str, data: dict) -> str:
        """Format a Server-Sent Event."""
        payload = json.dumps({"event": event_type, "data": data})
        return f"event: {event_type}\ndata: {payload}\n\n"
    
    def _load_roe(self, path: str) -> dict:
        """Load Rules of Engagement from YAML file."""
        import yaml
        with open(path) as f:
            return yaml.safe_load(f)
    
    @property
    def is_running(self) -> bool:
        return self._active_run is not None and self._active_run.status == "running"


class ProbeAlreadyRunning(Exception):
    pass


# Global instance
probe_runner = ProbeRunner()
```

