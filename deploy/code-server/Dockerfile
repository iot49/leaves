FROM linuxserver/code-server

RUN apt-get update --yes && \
    apt-get upgrade --yes && \
    apt-get install --yes \
    clang && \
    rsync && \
    echo 'abc ALL=(ALL) NOPASSWD:ALL' | EDITOR='tee -a' visudo

WORKDIR /usr/local/src

COPY ./deploy/code-server/start.sh . 

CMD [ "/bin/bash", "/usr/local/src/start.sh" ]
