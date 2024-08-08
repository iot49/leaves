FROM linuxserver/code-server

RUN apt-get update --yes && \
    apt-get upgrade --yes && \
    apt-get install --yes \
    python3.11 python3-pip \
    rsync && \
    echo 'abc ALL=(ALL) NOPASSWD:ALL' | EDITOR='tee -a' visudo

WORKDIR /usr/local/src

COPY ./requirements.lock .
COPY ./requirements-dev.lock .

RUN sed '/-e/d' requirements.lock > requirements.txt && \
    sed '/-e/d' requirements-dev.lock > requirements-dev.txt && \
    /usr/bin/pip3 install --quiet --no-cache-dir -r requirements.txt && \
    /usr/bin/pip3 install --quiet --no-cache-dir -r requirements-dev.txt

COPY ./deploy/code-server/start.sh . 

CMD [ "/bin/bash", "/usr/local/src/start.sh" ]
