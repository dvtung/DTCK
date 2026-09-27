#!/usr/bin/env bash
# =============================================================================
# DTCK Platform Health & Readiness Alert Check
# Spec §46 / docs/SYSTEM_SPECIFICATION.md §30/§46
#
# Inspects /healthz, /readyz, and /metrics. Returns 0 if all nominal, 1 on alert.
# Can be run via cron (e.g. every 5 minutes):
#   */5 * * * * /path/to/DTCK/scripts/health_alert.sh >> /var/log/dtck_health.log 2>&1
# =============================================================================

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
TIMEOUT_SEC="${TIMEOUT_SEC:-5}"

echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Checking DTCK Platform Health at ${API_URL}..."

# 1. Liveness Probe (/healthz)
HEALTH_RESP="$(curl -s --max-time "${TIMEOUT_SEC}" "${API_URL}/healthz" || echo "")"
if [[ -z "${HEALTH_RESP}" ]] || ! echo "${HEALTH_RESP}" | grep -q '"status":"ok"'; then
    echo "[ALERT] API Liveness failure on ${API_URL}/healthz! Response: ${HEALTH_RESP}" >&2
    exit 1
fi

# 2. Readiness Probe (/readyz)
READYZ_RESP="$(curl -s --max-time "${TIMEOUT_SEC}" "${API_URL}/readyz" || echo "")"
if [[ -z "${READYZ_RESP}" ]] || ! echo "${READYZ_RESP}" | grep -q '"status":"ready"'; then
    echo "[ALERT] API Readiness failure on ${API_URL}/readyz! Response: ${READYZ_RESP}" >&2
    exit 1
fi

# Check individual dependencies
DB_STATUS="$(echo "${READYZ_RESP}" | grep -o '"database":"[^"]*"' | cut -d'"' -f4)"
if [[ "${DB_STATUS}" == "unreachable" ]]; then
    echo "[ALERT] Database dependency is UNREACHABLE according to /readyz!" >&2
    exit 1
fi

echo "[OK] Healthz OK, Readyz OK (DB=${DB_STATUS}). System nominal."
exit 0
