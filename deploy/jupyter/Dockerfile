FROM jupyter/scipy-notebook:latest

# this works
WORKDIR /home/jovyan

# fails in RUN below ???
WORKDIR /usr/local/src


COPY ./requirements.lock .
COPY ./requirements-dev.lock .

RUN sed '/-e/d' requirements.lock > requirements.txt && \
    sed '/-e/d' requirements-dev.lock > requirements-dev.txt && \
    pip install --quiet --no-cache-dir --upgrade pip && \
    pip install --quiet --no-cache-dir -r requirements.txt && \
    pip install --quiet --no-cache-dir -r requirements-dev.txt

RUN fix-permissions "${CONDA_DIR}"

WORKDIR /home/jovyan
