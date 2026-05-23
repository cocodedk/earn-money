---
tier: FAST
depends_on: []
files:
  creates: []
  modifies: [backend/apps/events/views.py, backend/apps/events/test_streaming.py]
  deletes: []
  renames: []
  generated: []
exports: []
imports: []
allow_extra_files: false
---

# Task 2: SSE Generic Frames — Drop event: Line

**Files:**
- Modify: `backend/apps/events/views.py`
- Modify: `backend/apps/events/test_streaming.py`

---

- [ ] **Step 1: Update SSE test to assert NO event: line**

In `backend/apps/events/test_streaming.py`, change `SSEStreamTests.test_streams_all_events_then_closes`:

```python
def test_streams_all_events_then_closes(self) -> None:
    url = reverse("scanrun-event-stream", args=[self.run.id])
    body = b"".join(self.client.get(url).streaming_content).decode()
    # Generic SSE frames — no event: line, type is in data payload
    assert "event:" not in body
    assert '"type": "system.test"' in body
    assert '"message": "first"' in body
    assert '"message": "second"' in body
    assert ": stream-closed" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/events/test_streaming.py::SSEStreamTests::test_streams_all_events_then_closes -v`
Expected: FAIL — `"event:" in body` because `_format()` still emits `event:` lines

- [ ] **Step 3: Remove event: line from _format()**

In `backend/apps/events/views.py`, replace the `_format` function:

```python
def _format(event: Event) -> bytes:
    payload = EventSerializer(event).data
    frame = (
        f"id: {event.id}\n"
        f"data: {json.dumps(payload, default=str)}\n\n"
    )
    return frame.encode("utf-8")
```

- [ ] **Step 4: Run full SSE test suite**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/events/test_streaming.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/events/views.py backend/apps/events/test_streaming.py
git commit -m "feat(sse): drop named event: line — use generic SSE frames"
```
