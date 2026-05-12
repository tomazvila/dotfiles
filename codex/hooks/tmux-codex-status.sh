#!/usr/bin/env bash
set -euo pipefail

state="${1:-}"
if [ -z "$state" ]; then
  state="${CODEX_TMUX_STATE:-running}"
fi

if [ -z "${TMUX_PANE:-}" ]; then
  exit 0
fi

set_window_option() {
  tmux set-option -q -w -t "$TMUX_PANE" "$1" "$2" 2>/dev/null || true
}

unset_window_option() {
  tmux set-option -q -w -u -t "$TMUX_PANE" "$1" 2>/dev/null || true
}

case "$state" in
  running)
    set_window_option @codex-state running
    set_window_option @codex-running 1
    unset_window_option @ai-waiting
    ;;
  waiting)
    set_window_option @codex-state waiting
    unset_window_option @codex-running
    set_window_option @ai-waiting 1
    ;;
  idle)
    set_window_option @codex-state idle
    unset_window_option @codex-running
    unset_window_option @ai-waiting
    ;;
  *)
    exit 0
    ;;
esac
