# 6B cleanup-verify prompt (resumed codex)

Paste-ready prompt for the resumed codex cleanup-verify run when the gpt-5.5 usage limit resets (2026-05-20 02:38 local).

## Invocation

```bash
codex exec resume --last -m gpt-5.5 -c model_reasoning_effort=xhigh "$(cat docs/superpowers/specs/2026-05-19-scan-run-detail-6B-cleanup-verify-prompt.md)"
```

Or pass the doc paths explicitly:

```bash
SPEC=docs/superpowers/specs/2026-05-19-scan-run-detail-6B-design.md
STATE=docs/superpowers/specs/2026-05-19-scan-run-detail-6B-review-state.md
ANCHORS=docs/superpowers/specs/2026-05-19-scan-run-detail-6B-backend-anchors.md
LINT_YAML=docs/superpowers/specs/2026-05-19-scan-run-detail-6B-lint.yaml
codex exec resume --last -m gpt-5.5 -c model_reasoning_effort=xhigh "$(< prompt-body.md)"
```

## Prompt body

```text
Outside-protocol cleanup verification after round 6 of mutual-acceptance for the 6B spec at $SPEC.

Inputs you already have access to in the workspace:
- $STATE — review state, including what changed in rounds 5-6 and what's stable.
- $ANCHORS — verified backend file:line refs. DO NOT re-grep these.
- $LINT_YAML — the consistency vocab. Lint already passes locally.
- $SPEC — the design doc itself (only the changed sections need re-reading; see $STATE).

DO NOT perform a full review. DO NOT re-grep the backend tree.

Verify only that:
1. The round-6 terminology cleanup is complete (no old invalidateQueries({ cancelRefetch: true }) / invalidate-and-refetch / no-op'd by cancelRefetch wording remains in active spec body — mentions inside <!-- lint:allow --> marked lines are intentional explanatory references).
2. The new cancelQueries + refetchQueries contract in §Hook contract is consistent with all downstream test bullets and §Render integration step 4.
3. §Decisions item 4 (DetailPageGuard narrowing) is consistent with the §Files modifications for DetailPageGuard.tsx and DetailPageGuard.test.tsx.

Return only:
- The single line "ACCEPT" if the cleanup is complete and no contradictions remain.
- OR a numbered list of remaining cleanup contradictions, each with file:line and the contradicting passage.
```

## Notes

- This is a one-shot verification, not a new review round. The codex-mutual-acceptance protocol's 6-round cap has been reached; this call is for cleanup confirmation only.
- If codex returns ACCEPT: mark the 6B design accepted, move on to the 3-phase plan tree at `docs/superpowers/plans/2026-05-19-SCAN-RUN-DETAIL-6B/`.
- If codex returns contradictions: address them with diffs surfaced to the operator first (per `feedback_confer_before_spec_edits` rule), then re-run this same prompt.
- **Portable-state principle:** if `codex exec resume --last` fails (session pruned, CLI version mismatch), fall back to a fresh `codex exec` and pass `$STATE` + `$ANCHORS` + the spec diff in the prompt body — the state files are designed to be self-contained.
