#!/bin/sh
# Configure a fresh Ubuntu 24.04+ VPS for the earn-money pipeline.
# Run as root on the VPS. Idempotent — safe to re-run after partial failure.
#
# Assumes:
#   - Ubuntu 24.04 LTS (Python 3.12 already on PATH)
#   - Outbound HTTPS to api.github.com and github.com is open
#   - You have already SSHed in as root
#
# This script does NOT:
#   - Push the repo to the VPS (use rsync from the laptop, see end-of-run notes)
#   - Transfer .env (use scp from the laptop)
#   - Touch RECON_ENABLED (that's an operator-explicit step, the consent gate)

set -eu

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

log() { printf "${GREEN}[install-vps]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[install-vps]${NC} %s\n" "$*" >&2; }

if [ "$(id -u)" -ne 0 ]; then
    warn "must be run as root"; exit 1
fi

log "apt prereqs"
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3-venv python3-pip jq curl unzip ca-certificates

log "ProjectDiscovery tools (subfinder, httpx, nuclei, katana, naabu) via prebuilt releases"
mkdir -p /opt/recon-tools
cd /opt/recon-tools
for tool in subfinder httpx nuclei katana naabu; do
    if [ -x "/usr/local/bin/$tool" ]; then
        log "  $tool: already present, skipping"
        continue
    fi
    ver=$(curl -fsSL "https://api.github.com/repos/projectdiscovery/${tool}/releases/latest" \
        | jq -r .tag_name)
    if [ -z "$ver" ] || [ "$ver" = "null" ]; then
        warn "  $tool: failed to resolve latest version from GitHub API"; exit 1
    fi
    ver_num="${ver#v}"
    url="https://github.com/projectdiscovery/${tool}/releases/download/${ver}/${tool}_${ver_num}_linux_amd64.zip"
    log "  $tool: fetching $ver"
    # -f makes curl fail on HTTP 4xx/5xx instead of silently saving the error body
    curl -fsSL "$url" -o "${tool}.zip"
    unzip -qo "${tool}.zip"
    install -m 0755 "$tool" "/usr/local/bin/$tool"
    rm -f "${tool}.zip" "$tool"
done

log "nuclei templates"
if [ ! -d /root/nuclei-templates ]; then
    nuclei -update-templates >/dev/null 2>&1 || warn "template install failed; re-run manually"
else
    log "  templates already present at /root/nuclei-templates"
fi

log "apt packages (nmap, sqlmap, ffuf)"
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nmap sqlmap ffuf

log "rustscan (.deb release; cargo skipped to avoid pulling the Rust toolchain)"
if command -v rustscan >/dev/null 2>&1; then
    log "  rustscan: already present, skipping"
else
    rs_ver=$(curl -fsSL "https://api.github.com/repos/bee-san/RustScan/releases/latest" \
        | jq -r .tag_name)
    if [ -z "$rs_ver" ] || [ "$rs_ver" = "null" ]; then
        warn "  rustscan: failed to resolve latest version from GitHub API"
    else
        rs_num="${rs_ver#v}"
        rs_url="https://github.com/bee-san/RustScan/releases/download/${rs_ver}/rustscan_${rs_num}_amd64.deb"
        log "  rustscan: fetching $rs_ver"
        cd /tmp
        if curl -fsSL "$rs_url" -o rustscan.deb; then
            dpkg -i rustscan.deb >/dev/null 2>&1 || \
                apt-get install -y -qq --fix-broken
            rm -f rustscan.deb
        else
            warn "  rustscan: download failed; re-run manually"
        fi
    fi
fi

log "non-PD Go tools (amass, gau, dalfox, gitleaks, trufflehog)"
# Ensure `go` is available before any go-install path. Apt's golang-go
# is acceptable for tool builds; the runtime version of these tools
# does not constrain the rest of the pipeline.
if ! command -v go >/dev/null 2>&1; then
    log "  installing golang-go for go-install fallbacks"
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq golang-go
fi
# Each entry: bin_name|go-install-path. Skip when already on PATH.
for entry in \
    "amass|github.com/owasp-amass/amass/v4/...@master" \
    "gau|github.com/lc/gau/v2/cmd/gau@latest" \
    "dalfox|github.com/hahwul/dalfox/v2@latest" \
    "gitleaks|github.com/gitleaks/gitleaks/v8@latest" \
    "trufflehog|github.com/trufflesecurity/trufflehog/v3@latest"; do
    bin="${entry%%|*}"
    path="${entry##*|}"
    if command -v "$bin" >/dev/null 2>&1; then
        log "  $bin: already present, skipping"
        continue
    fi
    log "  $bin: go install $path"
    GOBIN=/usr/local/bin go install "$path" || warn "  $bin: go install failed; re-run manually"
done

log "installed versions:"
subfinder -version 2>&1 | grep -i "current version" | head -1
httpx -version 2>&1 | grep -i "current version" | head -1
nuclei -version 2>&1 | grep -i "version" | head -1
katana -version 2>&1 | grep -i "current version" | head -1
naabu -version 2>&1 | grep -i "current version" | head -1

cat <<EOF

${GREEN}VPS base install complete.${NC} Tools at /usr/local/bin.

Remaining steps (run from your laptop):

  1. Rsync the repo (excluding gitignored + .git):
       rsync -a --delete \\
         --exclude='.venv/' --exclude='__pycache__' --exclude='.git/' \\
         --exclude='.env' --exclude='*.sqlite' --exclude='recon/outputs/' \\
         --exclude='RECON_ENABLED' --exclude='.claude/' --exclude='.mcp.json' \\
         /path/to/earn-money/ root@<VPS>:/opt/earn-money/

  2. Copy .env (CHAOS_API_TOKEN + HACKERONE_API_*):
       scp -p .env root@<VPS>:/opt/earn-money/.env
       ssh root@<VPS> chmod 600 /opt/earn-money/.env

  3. Set up the Python venv (on the VPS):
       cd /opt/earn-money
       python3 -m venv .venv
       .venv/bin/pip install -e ".[dev]" --quiet

  4. Arm the kill-switch when ready (explicit operator consent gate):
       touch /opt/earn-money/RECON_ENABLED

  5. Smoke test:
       cd /opt/earn-money && set -o allexport && . ./.env && set +o allexport
       .venv/bin/python -m earn_money.runners.passive_recon \\
         --program security --root /opt/earn-money

EOF
