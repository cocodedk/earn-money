# Merge gate

Per [[feedback-merge-heuristic]].

Stack depth is 9 slices (AUDIT + A-H). `backend/apps/programs/` line + branch coverage is 100%; full backend suite is green. Spec-review closed. No in-flight FU. → squash-merge tip into main + ping em-frontend per [[project-merge-coordination]] rule (3). No frontend impact expected beyond additive event type; existing event consumers must ignore unknown event payload fields.
