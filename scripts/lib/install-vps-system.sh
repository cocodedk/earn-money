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

install_dashboard_unit() {
    log "dashboard systemd unit"
    if [ ! -f /etc/systemd/system/earn-money-dashboard.service ]; then
        install -m 0644 /opt/earn-money/scripts/dashboard.service \
            /etc/systemd/system/earn-money-dashboard.service
        systemctl daemon-reload
        systemctl enable earn-money-dashboard.service >/dev/null 2>&1 || \
            warn "  systemctl enable failed; check 'systemctl status'"
        log "  installed and enabled. start with 'systemctl start earn-money-dashboard'"
    else
        log "  unit already installed; reload with 'systemctl daemon-reload' if you changed it"
    fi
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
    reverse_proxy 127.0.0.1:8080
    encode gzip
}
CADDY_EOF
        touch /etc/caddy/Caddyfile.earn-money-installed
        systemctl restart caddy
        log "  Caddyfile installed; auto-TLS via Let's Encrypt"
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
    subfinder -version 2>&1 | grep -i "current version" | head -1
    httpx -version 2>&1 | grep -i "current version" | head -1
    nuclei -version 2>&1 | grep -i "version" | head -1
    katana -version 2>&1 | grep -i "current version" | head -1
    subzy version 2>&1 | head -1 || warn "  subzy not on PATH — go install may have failed"
    naabu -version 2>&1 | grep -i "current version" | head -1
    nmap --version 2>&1 | head -1
    sqlmap --version 2>&1 | head -1
    ffuf -V 2>&1 | head -1
    rustscan --version 2>&1 | head -1
    amass -version 2>&1 | head -1
    gau --version 2>&1 | head -1
    dalfox version 2>&1 | head -1
    gitleaks version 2>&1 | head -1
    trufflehog --version 2>&1 | head -1
}
