# Trelolo

# Docker environment on local machine

With the help of Docker it is possible to easily run Trelolo on your very
own computer.

## Prerequisite

You have installed Docker on your machine (this instructions is valid for
*Docker for Mac*, there could be small differencies on other systems).

## Build

1. Go into root folder of Trelolo project (you should see `Dockerfile`)
2. Make copy of `env.example` file: `cp env.example .env`
3. Edit `.env` and fill there your configuration values
4. Make copy of `docker-compose.override-local.yml` file:
   `cp docker-compose.override-local.yml docker-compose.override.yml`
5. Edit `docker-compose.overide.yml` and fill
   environment variables for ngrok docker service    
6. Build Docker image: `docker-compose build`

Now you have prepared environment for Docker run. You should repeat step (6)
everytime your `requirements.*` or `Dockerfile` change.

## Run

Go to Trelolo root folder and type:

    $ docker-compose up

Your source code from your machine is shared into Docker container, so you
could change application in your favourite editor/IDE and all changes will be
automaticaly available within container (so there is no need for rebuilding
image).

After change, you have to restart containers. If they already run, press
CTRL+C, wait for while and once you will be back in console type:

    $ docker-compose kill && docker-compose rm -f
    $ docker-compose up

## Configuration

Required environment variables are:

- `SECRET KEY`
- `TRELOLO_API_KEY`
- `TRELOLO_TOKEN`
- `WEBHOOK_URL`
- `TRELOLO_MAIN_BOARD`
- `TRELOLO_TOP_BOARD`
- `GITLAB_URL`
- `GITLAB_TOKEN` (OAuth access token)
- `REDIS`
- `FLASK_HOST`
- `FLASK_PORT`
- `SQLALCHEMY_DATABASE_URI` (optional on local)
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
