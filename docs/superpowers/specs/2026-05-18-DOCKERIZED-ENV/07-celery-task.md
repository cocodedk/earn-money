# 7. Celery task shape

Create a task like:

```python
run_scan(scan_run_id: str) -> None
```

For now it should simulate a scan.

It should:

* load the scan run
* mark it running
* iterate targets
* create events
* sleep briefly between steps
* respect pause
* respect stop
* mark target runs done
* mark scan run done

Do not implement real HTTP scanning yet.

This task proves the control system works.
