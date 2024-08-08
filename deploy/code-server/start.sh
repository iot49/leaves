#! /bin/bash

# add hostname to /etc/hosts (makes sudo happy)
if ! grep -q `hostname` /etc/hosts; then
    bash -c 'echo "127.0.0.1" `hostname` >> /etc/hosts'
fi

# asks lots of questions, do as user
# curl -sSf https://rye.astral.sh/get | bash
# rye sync

# Note: /config/custom-cont-init.d executed (if it exists) when code-server starts

sleep infinity
