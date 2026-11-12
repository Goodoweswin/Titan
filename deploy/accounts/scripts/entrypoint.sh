#!/bin/sh
set -eu
# Runtime startup must pass the actual DB privilege check. Migration/admin commands
# are deliberately separate one-off operations using their explicitly selected role.
if [ "$1" = gunicorn ] || { [ "$1" = python ] && [ "${2:-}" = worker.py ]; }; then
    python manage.py check --deploy --fail-level WARNING
    python manage.py check_accounts_deployment
fi
exec "$@"
