#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

echo "==> ansible-lint"
ansible-lint ansible/

echo "==> yamllint"
yamllint ansible/

echo "==> shellcheck bootstrap.sh"
shellcheck bootstrap.sh

echo "==> all lints passed"
