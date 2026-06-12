#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

PLAYBOOK="ansible/playbook.yml"
LIMIT="${LIMIT:-localhost}"

echo "==> first run"
ansible-playbook "${PLAYBOOK}" --limit "${LIMIT}" --diff > /tmp/run1.log 2>&1 \
  || { tail -50 /tmp/run1.log; exit 1; }

echo "==> second run"
ansible-playbook "${PLAYBOOK}" --limit "${LIMIT}" --diff > /tmp/run2.log 2>&1 \
  || { tail -50 /tmp/run2.log; exit 1; }

echo "==> checking for changes on second run"
if grep -E "^\s*changed:.*localhost" /tmp/run2.log; then
  echo "ERROR: second run produced changes — playbook is not idempotent"
  grep -B 2 -A 5 "changed:" /tmp/run2.log
  exit 1
fi

echo "==> idempotency verified"
