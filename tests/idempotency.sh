#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

PLAYBOOK="ansible/playbook.yml"
LIMIT="${LIMIT:-localhost}"

echo "==> first run"
if ! ansible-playbook "${PLAYBOOK}" --limit "${LIMIT}" --diff > /tmp/run1.log 2>&1; then
  echo "ERROR: first run failed"
  tail -50 /tmp/run1.log
  exit 1
fi

echo "==> second run"
if ! ansible-playbook "${PLAYBOOK}" --limit "${LIMIT}" --diff > /tmp/run2.log 2>&1; then
  echo "ERROR: second run failed"
  tail -50 /tmp/run2.log
  exit 1
fi

echo "==> checking for changes on second run"
if grep -A 1 "^PLAY RECAP" /tmp/run2.log | grep -qE "changed=[1-9]"; then
  echo "ERROR: second run produced changes — playbook is not idempotent"
  grep -B 2 -A 10 "changed=[1-9]" /tmp/run2.log
  exit 1
fi

echo "==> idempotency verified"
