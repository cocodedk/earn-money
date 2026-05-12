# Security Policy

This is a private operational repository for authorised security testing under bug-bounty programs. It is not a published product.

## Reporting a vulnerability in this code

Do **not** open a public GitHub issue.

- Use the **"Report a vulnerability"** button on the Security tab of this repository (GitHub private advisory), or
- Email: babak@cocode.dk

Acknowledgement within 5 business days; fix targeted within 30 days of confirmation.

## Reporting an operational concern

If you believe a recon runner has scanned an out-of-scope asset, that a submission has been queued for a program with `policy: manual-only`, or that any operational invariant from [`CLAUDE.md`](CLAUDE.md) has been broken, halt the pipeline immediately:

```bash
rm RECON_ENABLED
```

Then email babak@cocode.dk before re-enabling.

## Supported versions

| Version | Supported |
|---------|-----------|
| `main`  | ✅ |
| older   | ❌ |
