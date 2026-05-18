#!/usr/bin/env bash
# Start/stop/status the aethier-mcp host bridge.
# Idempotent: calling `start` while already running is a no-op.
# State (pid, port, host) lives in ~/.aedev/aethier-mcp.yaml via aedev-state.
set -euo pipefail

WORKSPACE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PKG_DIR="$WORKSPACE_DIR/packages/aethier-mcp-bridge"
STATE="$WORKSPACE_DIR/bin/aedev-state"

HOST="${BRIDGE_HOST:-127.0.0.1}"
PORT="${BRIDGE_PORT:-9000}"
LOG_FILE="${BRIDGE_LOG_FILE:-$("$STATE" dir)/bridge.log}"

log() { echo "[bridge] $*"; }
err() { echo "[bridge] $*" >&2; }

get_pid() { "$STATE" get bridge.pid; }

is_running() {
    local pid
    pid="$(get_pid)"
    [[ -n "$pid" ]] || return 1
    kill -0 "$pid" 2>/dev/null
}

port_open() {
    (echo > "/dev/tcp/$HOST/$PORT") 2>/dev/null
}

cmd_start() {
    if is_running; then
        log "already running, pid $(get_pid) on $HOST:$PORT"
        return 0
    fi

    "$STATE" unset bridge

    log "starting on $HOST:$PORT"
    log "log:  $LOG_FILE"

    BRIDGE_HOST="$HOST" BRIDGE_PORT="$PORT" \
        nohup uv run --project "$PKG_DIR" \
            python -m aethier_mcp_bridge \
        > "$LOG_FILE" 2>&1 &

    local pid=$!
    "$STATE" set bridge.pid  "$pid"
    "$STATE" set bridge.host "$HOST"
    "$STATE" set bridge.port "$PORT"

    for _ in {1..120}; do
        if port_open; then
            log "started, pid $pid"
            return 0
        fi
        if ! kill -0 "$pid" 2>/dev/null; then
            err "process died before port opened; see $LOG_FILE"
            "$STATE" unset bridge
            return 1
        fi
        sleep 0.25
    done

    err "timed out waiting for port; see $LOG_FILE"
    return 1
}

cmd_stop() {
    if ! is_running; then
        log "not running"
        "$STATE" unset bridge
        return 0
    fi

    local pid
    pid="$(get_pid)"

    log "stopping pid $pid"
    kill "$pid" 2>/dev/null || true

    for _ in {1..30}; do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.1
    done

    if kill -0 "$pid" 2>/dev/null; then
        log "sigterm ignored, sending sigkill"
        kill -9 "$pid" 2>/dev/null || true
    fi

    "$STATE" unset bridge
    log "stopped"
}

cmd_status() {
    if is_running; then
        log "running, pid $(get_pid) on $HOST:$PORT"
        log "log:  $LOG_FILE"
        return 0
    fi
    log "not running"
    return 1
}

cmd_restart() {
    cmd_stop
    cmd_start
}

cmd_logs() {
    if [[ ! -f "$LOG_FILE" ]]; then
        err "no log file yet at $LOG_FILE"
        return 1
    fi
    tail -f "$LOG_FILE"
}

usage() {
    cat >&2 <<EOF
usage: $0 {start|stop|restart|status|logs}

env (current values):
  BRIDGE_HOST     = $HOST
  BRIDGE_PORT     = $PORT
  BRIDGE_LOG_FILE = $LOG_FILE
  project dir     = $("$STATE" dir)
EOF
    exit 2
}

case "${1:-}" in
    start)   cmd_start   ;;
    stop)    cmd_stop    ;;
    restart) cmd_restart ;;
    status)  cmd_status  ;;
    logs)    cmd_logs    ;;
    *)       usage       ;;
esac
