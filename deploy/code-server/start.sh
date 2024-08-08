#! /bin/bash

# add hostname to /etc/hosts (makes sudo happy)
if ! grep -q `hostname` /etc/hosts; then
    bash -c 'echo "127.0.0.1" `hostname` >> /etc/hosts'
fi

# Note: /config/custom-cont-init.d executed (if it exists) when code-server starts

sleep infinity
