# Architecture decisions (locked in)

Four decisions taken before any code lands. Revisit only on operator instruction or codex consult.

* **One stub for 1.20–1.25, not six.** Codex consult verdict 2026-05-20: identical core loop, shared safety controls matter, precedent established by 1.10→1.18. Don't flatten the finding taxonomy — preserve per-family `Finding.category` and `Finding.data.family`.
* **Stub 1.19 stays standalone.** It's a body-signature classifier, not a path probe — different shape from `well_known_paths`. Sharing would couple unrelated concerns.
* **No new shared types.** Evidence + Finding shapes are unchanged from PR #29. Per-family additions land under `Finding.data` keys, which is additive and frontend-tolerant per [[project-merge-coordination]] rule (2) — _"in-stack PRs that don't touch the cross-tier contract need no pre-announce; the post-merge ping in (3) is enough"_.
* **Soft-404 detection in `well_known_paths`** is a NEW shared control (not in `_shared` yet). Per-target SPA/soft-404 baseline cached per scan. If a candidate response shape matches the baseline → reject the candidate as a soft-404 false positive.
