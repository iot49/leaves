#! /bin/bash

# add hostname to /etc/hosts (makes sudo happy)
if ! grep -q `hostname` /etc/hosts; then
    bash -c 'echo "127.0.0.1" `hostname` >> /etc/hosts'
fi

cat <<EOT >> /config/.bashrc
alias python=/usr/bin/python3
alias pip=/usr/bin/pip3
export PATH=\$PATH:/usr/bin
EOT

# Note: /config/custom-cont-init.d executed (if it exists) when code-server starts

sleep infinity
