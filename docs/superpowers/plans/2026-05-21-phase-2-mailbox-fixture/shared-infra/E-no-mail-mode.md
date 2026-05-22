# Slice E — `no_mailbox_mode` for targets that don't email

> No code lives in `mailbox.py` for this — it's a CONVENTION
> stubs follow when `load_mailbox_backend()` returns None.

## The case

Some targets don't send a verification email at registration.
DVWA is the textbook example. Juice Shop's signup-by-default
behaviour is also unverified. Operator runs `FIXTURE_MAILBOX_BACKEND=none`
to declare "this target doesn't email; don't wait for one".

## What stubs do in `no_mailbox_mode`

Each stub that needs a reset token / verification link / OAuth
callback decides for itself:

| Stub | `no_mailbox_mode` behaviour |
|------|-----------------------------|
| 2.5 predictable-reset-token | Refuse — no token to analyse without an email. Emit `AUTH_FIXTURE_REQUIRED` `data.detail=mailbox_required_for_reset`. |
| 2.6 reset-token-reuse | Same — `AUTH_FIXTURE_REQUIRED`. |
| 2.7 weak-reset-expiry | Same. |
| 2.8 reset-poisoning | Same. |
| 2.9 email-change-takeover | Same. |
| 2.20 email-verification-bypass | **Run.** This stub specifically tests the "no email verification" case: register, attempt login immediately, observe whether the account works. `no_mailbox_mode` means the target is the exact thing the stub is trying to detect; the runner posts a sensitive request right after registration and looks at whether it succeeds. The fact that no mailbox is configured IS the finding signal. |

## Code shape

In each stub's runner:

```python
mailbox = load_mailbox_backend()
if mailbox is None:
    # Stub-specific decision per the table above.
    if stub_supports_no_mail_mode:
        return _run_no_mail_branch(...)
    record_refusal(
        scan_run=scan_run, target_run=target_run, stub_id="2.X",
        reason=RefusalReason.FIXTURE_REQUIRED,
        details={"detail": "mailbox_required_for_reset"},
    )
    return
# else: normal mailbox-using branch
```

## Why the operator declares this explicitly

Inferring "does this target email?" by probing is hostile (you'd
have to register-and-wait, then guess "no email arrived in 60 s
→ probably none"). Worse, the inference fails when emails are
delayed (Gmail can take minutes to deliver). The explicit
`none` declaration is operator action: register manually once,
observe the target's behaviour, set the env var, move on.

## Test surface

* Stubs that refuse in `no_mailbox_mode` get one gate test
  asserting the right `AUTH_FIXTURE_REQUIRED` event fires when
  the backend returns None.
* Stub 2.20 (which DOES run in no-mail mode) gets two test
  paths: one with a real mailbox, one with `none` mode, and
  asserts the finding shape differs accordingly.
