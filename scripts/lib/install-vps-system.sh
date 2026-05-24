# shellcheck shell=sh
# Wordlists + systemd units + Caddy reverse-proxy steps for
# install-vps.sh. Sourced from the main installer; relies on the
# `log` / `warn` helpers it defines.

install_wordlists() {
    log "wordlists (SecLists shallow + assetnote subdomains + parameters)"
    if [ ! -d /opt/seclists ]; then
        log "  SecLists: shallow clone to /opt/seclists (~1 GB)"
        git clone --depth=1 --quiet \
            https://github.com/danielmiessler/SecLists.git /opt/seclists \
            || warn "  SecLists clone failed"
    else
        log "  SecLists: already present at /opt/seclists"
    fi
    mkdir -p /opt/assetnote
    for an_file in \
        "best-dns-wordlist.txt|https://wordlists-cdn.assetnote.io/data/manual/best-dns-wordlist.txt" \
        "httparchive_parameters_top_10000.txt|https://wordlists-cdn.assetnote.io/data/manual/httparchive_parameters_top_10000.txt"; do
        fname="${an_file%%|*}"
        url="${an_file##*|}"
        if [ -s "/opt/assetnote/$fname" ]; then
            log "  $fname: already present, skipping"
            continue
        fi
        log "  $fname: fetching"
        curl -fsSL "$url" -o "/opt/assetnote/$fname" \
            || warn "  $fname: download failed"
    done
}

install_stack_unit() {
    log "Docker Compose stack systemd unit"
    if [ -f /etc/systemd/system/earn-money-dashboard.service ]; then
        systemctl disable --now earn-money-dashboard.service >/dev/null 2>&1 || true
        rm -f /etc/systemd/system/earn-money-dashboard.service
    fi
    install -m 0644 /opt/earn-money/scripts/dashboard.service \
        /etc/systemd/system/earn-money.service
    systemctl daemon-reload
    systemctl enable earn-money.service >/dev/null 2>&1 || \
        warn "  systemctl enable failed; check 'systemctl status'"
    log "  installed/updated and enabled. start with 'systemctl start earn-money'"
}

install_dashboard_unit() {
    warn "install_dashboard_unit is deprecated; installing Docker Compose stack unit instead"
    install_stack_unit
}

install_caddy() {
    log "caddy reverse proxy (HTTPS termination for h1.cocode.dk)"
    if ! command -v caddy >/dev/null 2>&1; then
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
            debian-keyring debian-archive-keyring apt-transport-https gpg
        curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/gpg.key \
            | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
        curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt \
            > /etc/apt/sources.list.d/caddy-stable.list
        apt-get update -qq
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq caddy
    fi
    if [ ! -f /etc/caddy/Caddyfile.earn-money-installed ]; then
        cat > /etc/caddy/Caddyfile <<'CADDY_EOF'
{
    email babak@cocode.dk
}

h1.cocode.dk {
    reverse_proxy 127.0.0.1:80
    encode gzip
}
CADDY_EOF
        touch /etc/caddy/Caddyfile.earn-money-installed
        systemctl restart caddy
        log "  Caddyfile installed; auto-TLS via Let's Encrypt"
    elif grep -q "reverse_proxy 127.0.0.1:8080" /etc/caddy/Caddyfile; then
        sed -i 's/reverse_proxy 127\.0\.0\.1:8080/reverse_proxy 127.0.0.1:80/' \
            /etc/caddy/Caddyfile
        systemctl restart caddy
        log "  Caddyfile updated from legacy :8080 proxy to Docker nginx :80"
    else
        log "  Caddyfile already installed; leaving in place"
    fi
}

install_passive_tick_timer() {
    log "passive-tick daily timer (scope-sync + passive_recon per program)"
    install -m 0644 /opt/earn-money/scripts/passive-tick.service \
        /etc/systemd/system/earn-money-passive-tick.service
    install -m 0644 /opt/earn-money/scripts/passive-tick.timer \
        /etc/systemd/system/earn-money-passive-tick.timer
    systemctl daemon-reload
    systemctl enable --now earn-money-passive-tick.timer >/dev/null 2>&1 || \
        warn "  passive-tick timer enable failed; check 'systemctl status'"
    log "  enabled. fires once per day at 04:30 UTC, gated by RECON_ENABLED"
}

print_installed_versions() {
    log "installed versions:"
    show_version "subfinder" subfinder -version
    show_version "httpx" httpx -version
    show_version "nuclei" nuclei -version
    show_version "katana" katana -version
    show_version "subzy" subzy version
    show_version "naabu" naabu -version
    show_version "nmap" nmap --version
    show_version "sqlmap" sqlmap --version
    show_version "ffuf" ffuf -V
    show_version "rustscan" rustscan --version
    show_version "amass" amass -version
    show_version "gau" gau --version
    show_version "dalfox" dalfox version
    show_version "gitleaks" gitleaks version
    show_version "trufflehog" trufflehog --version
}

show_version() {
    name=$1
    shift
    if command -v "$name" >/dev/null 2>&1; then
        "$@" 2>&1 | head -1 || true
    else
        warn "  $name not on PATH"
    fi
}
