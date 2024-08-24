######################################################################
# BUILDER
FROM python:3.11-bookworm AS builder

WORKDIR /usr/src/app

# install dependencies (rye) and wrap them up in a wheel
COPY ./requirements.lock .
RUN sed '/-e/d' requirements.lock > requirements.txt && \
    pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip wheel --no-cache-dir --no-deps --wheel-dir /usr/src/app/wheels -r requirements.txt 


######################################################################
# FINAL
FROM python:3.11-slim-bookworm

# setuidgid
RUN apt-get update --yes && \
    apt-get install --yes --no-install-recommends daemontools

# create user with app-wide uid and gid
RUN mkdir -p /home/app && \
    addgroup --gid 1000 --system app && adduser --uid 1000 --system --group app

ENV HOME=/home/app
ENV APP_HOME=/home/app/web
RUN mkdir $APP_HOME
WORKDIR $APP_HOME

COPY --from=builder /usr/src/app/wheels /wheels
COPY --from=builder /usr/src/app/requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache /wheels/*

# code: dev runs from /home/repo; prod runs from /home/app/web
COPY ./leaf $APP_HOME/leaf
COPY ./lib $APP_HOME/lib

# Note: build runs from repo root!
WORKDIR $HOME
COPY ./deploy/leaf/start.sh .

RUN chown -R app:app .

CMD ["/bin/bash", "start.sh"]

