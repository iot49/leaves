FROM linuxserver/code-server

RUN echo 'abc ALL=(ALL) NOPASSWD:ALL' | EDITOR='tee -a' visudo

RUN apt-get update --yes && \
    apt-get upgrade --yes && \
    apt-get install --yes clang rsync

WORKDIR /usr/local/src

COPY ./deploy/code-server/start.sh . 

CMD [ "/bin/bash", "/usr/local/src/start.sh" ]
