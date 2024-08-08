#!/bin/bash

# running as root!

# credentials used by certbot
cat > /home/cloudflare/credentials <<EOF
dns_cloudflare_api_token = "${CF_API_TOKEN}"
EOF

chmod 600 /home/cloudflare/credentials

# we need access to certificates ...
chmod a+rx /home/letsencrypt/live
chmod a+rx /home/letsencrypt/archive

# fix ownership and permissions to edit files with code-server
chown -R app:app /home/config
chown -R app:app /home/repo
chown -R app:app /home/ui
chmod a+w /home/homeassistant/*.yaml  # homeassistant runs as root ...

# IMPORTANT: single worker
# otherwise e.g. current state is randomly assigned to (and split between) workers
# after a looong time, most states may be available from all workers, but the updates are 
# still randomly assigned
# solutions are difficult - store states in a database, e.g. redis, or just use a single worker

# TODO: if
# prod 
setuidgid app uvicorn app.main:app --workers 1 --host 0.0.0.0 --port 8000 --log-level error

# dev
# (cd /home/repo/backend; setuidgid app uvicorn app.main:app --workers 1 --host 0.0.0.0 --port 8000 --log-level error --reload)

# setuidgid app uvicorn alembic upgrade head && uvicorn app.main:app --workers 1 --host 0.0.0.0 --port 8000
# setuidgid app uvicorn alembic upgrade head && gunicorn -w 1 -k uvicorn.workers.UvicornWorker app.main:app  --bind 0.0.0.0:8000 --preload --log-level=debug --timeout 120

sleep infinity


