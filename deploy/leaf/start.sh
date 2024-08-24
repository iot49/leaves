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

# do we need this? we run from repo ...
# fix ownership and permissions to edit files with code-server
chown -R app:app /home/config
chown -R app:app /home/repo
chmod a+w /home/homeassistant/*.yaml  # homeassistant runs as root ...

if [[ ${ENVIRONMENT} == "prod" ]]; then
    # run from docker image
    (cd app; setuidgid app python leaf/main.py)
else
    # run from repo (setup in editor with rye)
    (cd /home/repo; setuidgid app python leaf/main.py)
fi

sleep infinity

