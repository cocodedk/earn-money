# Out of scope (tracked, deferred)

* Passive-recon runners (subfinder / amass / chaos integration) — separate Phase 2 work.
* Web UI for managing programs/scope/RoE — admin via files for MVP.
* `bin/scope-sync` (H1 API → scope.md refresh) — for now, copy scope.md from v1 install on h1.cocode.dk; v2 scope-sync is its own future slice.
* Out-of-scope finding suppression in the Findings list view — `OUT_OF_SCOPE_REJECTED` events already mark them; UI filtering is a 6F slice on the frontend.
* Per-target RECON_ENABLED override (some programs paused while others run) — current MVP uses repo-wide flag. Per-program FROZEN file handles the "pause one program" case.
* `clawpwn` shared-finding bridge (`em:` / `clw:` tag namespacing per [[project-clawpwn-peer]]) — orthogonal to scope-enforcement.
