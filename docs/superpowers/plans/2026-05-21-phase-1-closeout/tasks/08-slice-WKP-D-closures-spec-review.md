# Slice WKP-D — frontmatter closures + post-implementation spec-review

Complements the pre-implementation 6-spec audit at [`04b-slice-WKP-AUDIT-spec-review-first.md`](04b-slice-WKP-AUDIT-spec-review-first.md). This slice verifies the implementation conforms to that audit + closes the spec frontmatter.

1. Flip spec frontmatter to `status: done` on 1.20, 1.21, 1.22, 1.23, 1.24, 1.25. Add closure note in each body pointing to `well_known_paths` stub (same template as 1.18 closure). Note: 1.20 is also the registered spec ID for the stub via `@register("1.20")`; the closure note for 1.20 explicitly says "implementation lives at `apps/stubs/well_known_paths/`; this stub also absorbs 1.21–1.25".
2. Regenerate PROGRESS.md once for the whole closeout (Overall: 5/278 → 12/278 done, covering 1.19 + 1.20–1.25 from this stack — seven new closures on top of the five specs already `status: done` today: 1.10, 1.11, 1.12, 1.13, 1.18).
3. Post-implementation spec-review pass: audit `well_known_paths` shipped code against each of the 6 specs. Report at `docs/superpowers/spec-reviews/2026-05-21-stub-well-known-paths.md`.
4. Commit. Commit subject: `docs(cookbook): close 1.20–1.25 + well_known_paths post-impl audit + Phase 1 PROGRESS`.
