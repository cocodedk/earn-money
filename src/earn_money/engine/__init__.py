"""Active-recon pipeline orchestration.

The passive layer has its own systemd timer; this package is the
sequential engine for active runners — runs the five active-mode
runners against one program in a fixed order, gated by RECON_ENABLED
+ per-program FROZEN flags, surfacing the result for the dashboard.
"""
