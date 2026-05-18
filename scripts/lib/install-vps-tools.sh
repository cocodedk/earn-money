# shellcheck shell=sh
# ProjectDiscovery + apt-package + rustscan + go-install tool steps for
# install-vps.sh. Sourced from the main installer; relies on the `log` /
# `warn` helpers it defines.

install_pd_tools() {
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
}

install_apt_tools() {
    log "apt packages (nmap, sqlmap, ffuf)"
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nmap sqlmap ffuf
}

install_rustscan() {
    log "rustscan (.deb release; cargo skipped to avoid pulling the Rust toolchain)"
    if command -v rustscan >/dev/null 2>&1; then
        log "  rustscan: already present, skipping"
        return
    fi
    rs_ver=$(curl -fsSL "https://api.github.com/repos/bee-san/RustScan/releases/latest" \
        | jq -r .tag_name)
    if [ -z "$rs_ver" ] || [ "$rs_ver" = "null" ]; then
        warn "  rustscan: failed to resolve latest version from GitHub API"
        return
    fi
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
}

install_go_tools() {
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
        "trufflehog|github.com/trufflesecurity/trufflehog/v3@latest" \
        "subzy|github.com/PentestPad/subzy@latest"; do
        bin="${entry%%|*}"
        path="${entry##*|}"
        if command -v "$bin" >/dev/null 2>&1; then
            log "  $bin: already present, skipping"
            continue
        fi
        log "  $bin: go install $path"
        GOBIN=/usr/local/bin go install "$path" || warn "  $bin: go install failed; re-run manually"
    done
}
