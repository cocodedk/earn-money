# 6. Scan control rules

Start:

```text
queued -> running
enqueue Celery task
create scan event
```

Pause:

```text
running -> paused
worker must stop between safe steps
worker must not kill itself mid-request
```

Resume:

```text
paused -> running
worker continues when it sees running again
```

Stop:

```text
running/paused -> stopping
worker exits cleanly
then status becomes stopped
```

Failure:

```text
any unexpected worker error -> failed
write ScanEvent with error
```

Done:

```text
all targets processed -> done
```
