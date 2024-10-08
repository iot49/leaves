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

# clone/update leaves repo
if [[ -d /home/repo/leaves ]]; then
    # TODO: version control
    # (cd /home/repo/leaves; git pull)
else
    (cd /home/repo; git clone https://github.com/iot49/leaves.git)
fi

# clone/update ${DEPLOY_NAME}-config repo
if [[ -d /home/repo/${DEPLOY_NAME}-config ]]; then
    # TODO: version control
    (cd /home/repo/${DEPLOY_NAME}-config; git pull)
else
    (cd /home/repo; git clone https://${GITHUB_ACCESS_TOKEN}@github.com/iot49/${DEPLOY_NAME}-config.git)
fi

# fix ownership and permissions to edit files with code-server
chown -R app:app /home/repo
# homeassistant runs as root ...
chmod a+w /home/homeassistant/*.yaml  

while true ; do
    # start app
    if [[ ${ENVIRONMENT} == "prod" ]]; then
        # run from docker image
        (cd app/leaf; setuidgid app python main.py)
    else
        # run from repo (setup in editor with rye)
        (cd /home/repo/leaves/leaf/remote; setuidgid app python main.py)
    fi
done

