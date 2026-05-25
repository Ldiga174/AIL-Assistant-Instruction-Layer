#!/usr/bin/env bash
set -u

INTERVAL="${1:-20}"
AIL_REPO="${2:-${AIL_REPO:-}}"
AIL_LABEL="${AIL_LABEL:-ail-task}"
INBOX_FILE=".ail/inbox/current-task.md"
STATE_DIR=".ail/state"

if [ -z "$AIL_REPO" ]; then
  echo "AIL_REPO is required. Usage: AIL_REPO=\"owner/repo\" $0 [interval]" >&2
  echo "Or: $0 [interval] owner/repo" >&2
  exit 2
fi

mkdir -p ".ail/inbox" ".ail/outbox" "$STATE_DIR"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 2
  fi
}

require_cmd gh
require_cmd jq

echo "AIL AutoTasks watcher started"
echo "repo=$AIL_REPO label=$AIL_LABEL interval=${INTERVAL}s"

while true; do
  issue_json="$(
    gh issue list \
      --repo "$AIL_REPO" \
      --label "$AIL_LABEL" \
      --state open \
      --limit 20 \
      --json number,title,url,body,updatedAt \
      2>/tmp/ail-watch-issues.err
  )"
  status=$?

  if [ "$status" -ne 0 ]; then
    echo "GitHub issue fetch failed; retrying in ${INTERVAL}s" >&2
    if [ -s /tmp/ail-watch-issues.err ]; then
      sed -n '1,3p' /tmp/ail-watch-issues.err >&2
    fi
    sleep "$INTERVAL"
    continue
  fi

  issue="$(
    printf '%s' "$issue_json" |
      jq -c 'sort_by(.updatedAt) | reverse | .[0] // empty'
  )"

  if [ -z "$issue" ]; then
    echo "No open issues with label '$AIL_LABEL'; retrying in ${INTERVAL}s"
    sleep "$INTERVAL"
    continue
  fi

  number="$(printf '%s' "$issue" | jq -r '.number')"
  title="$(printf '%s' "$issue" | jq -r '.title')"
  url="$(printf '%s' "$issue" | jq -r '.url')"
  body="$(printf '%s' "$issue" | jq -r '.body // ""')"
  current="$(cat "$STATE_DIR/current_issue_number" 2>/dev/null || true)"

  if [ "$number" != "$current" ]; then
    {
      printf '# AIL TASK FROM GITHUB\n\n'
      printf '## Issue\n'
      printf '#%s - %s\n\n' "$number" "$title"
      printf 'URL: %s\n\n' "$url"
      printf -- '---\n\n'
      printf '%s\n' "$body"
    } > "$INBOX_FILE"

    printf '%s\n' "$number" > "$STATE_DIR/current_issue_number"
    printf '%s\n' "$number" > "$STATE_DIR/last_issue_number"
    printf '%s\n' "$url" > "$STATE_DIR/current_issue_url"

    echo "New AIL task written to $INBOX_FILE: #$number $title"

    if command -v notify-send >/dev/null 2>&1; then
      notify-send "AIL task #$number" "$title" || true
    fi

    if command -v code >/dev/null 2>&1; then
      code "$INBOX_FILE" >/dev/null 2>&1 || true
    fi
  fi

  sleep "$INTERVAL"
done
