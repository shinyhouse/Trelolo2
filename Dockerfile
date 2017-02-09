FROM python:3

MAINTAINER Matus Bolka

RUN mkdir -p /usr/src/app /usr/src/packages
WORKDIR /usr/src/app

RUN apt-get update && \
    apt-get install -y unzip && \
    rm -rf /var/lib/apt/lists/*

RUN apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8
RUN echo "deb http://apt.postgresql.org/pub/repos/apt/ precise-pgdg main" > /etc/apt/sources.list.d/pgdg.list
RUN apt-get update && apt-get install -y python-software-properties software-properties-common postgresql-9.3 postgresql-client-9.3 postgresql-contrib-9.3

COPY . /usr/src/app/
RUN pip install --src /usr/src/packages --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED="1"
ENV PYTHONPATH="/usr/src/app/"
ENV TERM=xterm

EXPOSE 8010
ENTRYPOINT ["/usr/src/app/manage.py"]

CMD ["runserver"]
