#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ODOO_LOCAL_ENV_FILE:-$SCRIPT_DIR/odoo_local.env}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

export ODOO_BASE_URL="${ODOO_BASE_URL:-http://127.0.0.1:16069}"
export ODOO_DB="${ODOO_DB:-solin}"
export ODOO_API_KEY="${ODOO_API_KEY:-}"
export ODOO_APPROVER_API_KEY="${ODOO_APPROVER_API_KEY:-}"

if [[ -z "${ODOO_API_KEY:-}" ]]; then
  echo "Missing ODOO_API_KEY. Set it in the environment or in $ENV_FILE." >&2
  exit 1
fi

exec python3 "$SCRIPT_DIR/odoo_json2.py" "$@"
