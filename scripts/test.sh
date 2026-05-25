#!/usr/bin/env bash
# @category: runtime/test
# @runs-on:  host
# @summary:  Host-side test runner for Dockerized backend/frontend tests.
# @danger:   local
# @usage:    ./scripts/test.sh [backend|quick|frontend|all|ci|help] [args...]

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

COMPOSE=(docker compose)

header() { printf "\n${BLUE}> %s${NC}\n\n" "$1"; }
ok() { printf "${GREEN}[ok]${NC} %s\n" "$1"; }
note() { printf "${YELLOW}[note]${NC} %s\n" "$1"; }
die() { printf "${RED}[error]${NC} %s\n" "$1" >&2; exit 1; }

usage() {
    cat <<'EOF'
Earn Money Test Runner

USAGE:
  ./scripts/test.sh COMMAND [args...]
  ./scripts/test.sh backend/apps/agent/tests/test_plateau.py -q

COMMANDS:
  backend [args...]   Run backend pytest in Docker. With args, coverage is
                      disabled unless you pass --cov/--no-cov yourself.
  quick [args...]     Run backend pytest in Docker with --no-cov.
  coverage [args...]  Run backend pytest in Docker with pyproject coverage.
  frontend [args...]  Run frontend Vitest in Docker.
  all                 Run backend coverage suite, then frontend tests.
  ci                  Alias for all.
  help                Show this help.

PATHS:
  Host paths are normalized for container workdirs:
    backend/apps/agent/tests/test_plateau.py -> apps/agent/tests/test_plateau.py
    frontend/src/App.e2e.test.tsx            -> src/App.e2e.test.tsx

EXAMPLES:
  ./scripts/test.sh backend
  ./scripts/test.sh quick apps/agent/tests/test_plateau.py -q
  ./scripts/test.sh backend/apps/agent/tests/test_plateau.py::TestRoutePlateau -q
  ./scripts/test.sh coverage apps/agent/tests/test_plateau.py
  ./scripts/test.sh frontend src/lib/http.test.ts
  ./scripts/test.sh all

ENV:
  DOCKER_COMPOSE="docker compose"  Override compose command.
  NO_START=1                       Do not auto-start Docker services.
EOF
}

if [[ -n "${DOCKER_COMPOSE:-}" ]]; then
    # shellcheck disable=SC2206
    COMPOSE=($DOCKER_COMPOSE)
fi

need_docker() {
    command -v docker >/dev/null 2>&1 || die "docker is not installed or not on PATH"
    "${COMPOSE[@]}" version >/dev/null 2>&1 || die "docker compose is not available"
}

compose() {
    (cd "$PROJECT_ROOT" && "${COMPOSE[@]}" "$@")
}

container_id_for() {
    compose ps -q "$1" 2>/dev/null || true
}

is_running() {
    local service="$1"
    local cid
    cid="$(container_id_for "$service")"
    [[ -n "$cid" ]] || return 1
    [[ "$(docker inspect -f '{{.State.Running}}' "$cid" 2>/dev/null || true)" == "true" ]]
}

supports_compose_wait() {
    compose up --help 2>/dev/null | grep -q -- '--wait'
}

wait_for_exec() {
    local service="$1"
    local timeout="${2:-60}"
    local start now elapsed
    start="$(date +%s)"

    while true; do
        if compose exec -T "$service" true >/dev/null 2>&1; then
            return 0
        fi
        now="$(date +%s)"
        elapsed=$((now - start))
        if (( elapsed >= timeout )); then
            return 1
        fi
        sleep 2
    done
}

ensure_service() {
    local service="$1"
    shift
    local services=("$@")

    need_docker
    if is_running "$service"; then
        wait_for_exec "$service" 20 || die "service '$service' is running but not accepting exec"
        return 0
    fi

    [[ "${NO_START:-0}" != "1" ]] || die "service '$service' is not running and NO_START=1"

    note "starting Docker service(s): ${services[*]}"
    if supports_compose_wait; then
        compose up -d --wait "${services[@]}"
    else
        compose up -d "${services[@]}"
    fi
    wait_for_exec "$service" 90 || die "service '$service' did not become ready for docker exec"
}

normalize_backend_args() {
    local arg
    for arg in "$@"; do
        case "$arg" in
            backend) printf '%s\n' "." ;;
            backend/*) printf '%s\n' "${arg#backend/}" ;;
            ./backend/*) printf '%s\n' "${arg#./backend/}" ;;
            *) printf '%s\n' "$arg" ;;
        esac
    done
}

normalize_frontend_args() {
    local arg
    for arg in "$@"; do
        case "$arg" in
            frontend) printf '%s\n' "." ;;
            frontend/*) printf '%s\n' "${arg#frontend/}" ;;
            ./frontend/*) printf '%s\n' "${arg#./frontend/}" ;;
            *) printf '%s\n' "$arg" ;;
        esac
    done
}

args_include_cov_control() {
    local arg
    for arg in "$@"; do
        case "$arg" in
            --cov|--cov=*|--no-cov|--cov-fail-under|--cov-fail-under=*) return 0 ;;
        esac
    done
    return 1
}

readarray_args() {
    local -n out="$1"
    shift
    local normalized
    out=()
    normalized="$("$@" || true)"
    [[ -n "$normalized" ]] || return 0
    readarray -t out <<<"$normalized"
}

run_backend() {
    local mode="$1"
    shift
    local args=()
    readarray_args args normalize_backend_args "$@"

    ensure_service backend postgres redis backend

    if [[ "$mode" == "quick" ]]; then
        args=(--no-cov "${args[@]}")
    elif [[ "$mode" == "auto" && "${#args[@]}" -gt 0 ]] && ! args_include_cov_control "${args[@]}"; then
        args=(--no-cov "${args[@]}")
    fi

    header "Running backend pytest in Docker"
    if [[ "${#args[@]}" -gt 0 ]]; then
        note "pytest args: ${args[*]}"
    else
        note "pytest args: pyproject defaults"
    fi
    compose exec -T -e DJANGO_ALLOW_ASYNC_UNSAFE=true backend python -m pytest "${args[@]}"
    ok "backend tests passed"
}

run_frontend() {
    local args=()
    readarray_args args normalize_frontend_args "$@"

    ensure_service frontend frontend

    header "Running frontend Vitest in Docker"
    if [[ "${#args[@]}" -gt 0 ]]; then
        note "vitest args: ${args[*]}"
        compose exec -T frontend npm test -- "${args[@]}"
    else
        compose exec -T frontend npm test
    fi
    ok "frontend tests passed"
}

is_backend_target() {
    local arg="${1:-}"
    [[ -z "$arg" ]] && return 1
    [[ "$arg" == -* ]] && return 0
    [[ "$arg" == backend/* || "$arg" == ./backend/* ]] && return 0
    [[ "$arg" == apps/* || "$arg" == config/* ]] && return 0
    [[ "$arg" == *.py || "$arg" == *::* ]] && return 0
    return 1
}

is_frontend_target() {
    local arg="${1:-}"
    [[ -z "$arg" ]] && return 1
    [[ "$arg" == frontend/* || "$arg" == ./frontend/* ]] && return 0
    [[ "$arg" == src/* ]] && return 0
    [[ "$arg" == *.test.ts || "$arg" == *.test.tsx || "$arg" == *.spec.ts || "$arg" == *.spec.tsx ]] && return 0
    return 1
}

main() {
    local command="${1:-help}"

    if is_frontend_target "$command"; then
        run_frontend "$@"
        return
    fi

    if is_backend_target "$command"; then
        run_backend quick "$@"
        return
    fi

    case "$command" in
        backend|pytest)
            shift
            run_backend auto "$@"
            ;;
        quick|unit)
            shift
            run_backend quick "$@"
            ;;
        coverage|cov)
            shift
            run_backend coverage "$@"
            ;;
        frontend|vitest)
            shift
            run_frontend "$@"
            ;;
        all|ci)
            run_backend coverage
            run_frontend
            ;;
        help|--help|-h|"")
            usage
            ;;
        *)
            die "unknown command '$command'. Run ./scripts/test.sh help"
            ;;
    esac
}

main "$@"
