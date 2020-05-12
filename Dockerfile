FROM ubuntu:bionic-20200403
LABEL maintainer="brycechambers@gmail.com"

RUN groupadd -g 1001 app && useradd -u 1001 -g app -Mr app

RUN apt-get update && \
	apt-get install -qy --no-install-recommends python3.6 && \
	apt-get install -qy --no-install-recommends python3-pip && \
        apt-get install -qy --no-install-recommends python3-setuptools && \
        apt-get install -qy curl && \
        pip3 install wheel && \
        pip3 install requests && \
        pip3 install nut2 && \
        pip3 install influxdb && \
        pip3 install urllib3

RUN mkdir /app
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
COPY requirements.txt /app
COPY run.py /app

# cleanup
RUN apt-get clean && \
	rm -rf /tmp/* && \
	rm -rf /var/lib/apt/lists/* && \
	rm -rf /var/tmp

RUN chown -R app:app /app \
    && chmod -R 777 /app/ \
    && chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8086
ENTRYPOINT ["entrypoint.sh"]
