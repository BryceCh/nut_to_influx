# nut_to_influx
Dockerised Python script to send metrics from Network UPS Tools to Grafana

[![Docker Registry](https://dockeri.co/image/brycech/nut_to_influx)](https://hub.docker.com/r/brycech/nut_to_influx)

## Getting started

Grab the example config above, and edit to suit your environment

### Configuration within config.ini

#### GENERAL
|Key            |Description                                                                                                         |
|:--------------|:-------------------------------------------------------------------------------------------------------------------|
|Delay          |Delay between updating metrics                                                                                      |
#### INFLUXDB
|Key            |Description                                                                                                         |
|:--------------|:-------------------------------------------------------------------------------------------------------------------|
|Address        |Host running influxdb                                                                                               |
|Port           |InfluxDB port to connect to.  8086 in most cases                                                                    |
|Database       |Database to write collected stats to                                                                                |
|Username       |User that has access to the database                                                                                |
|Password       |Password for above user                                                                                             |
|Verify_SSL     |Disable SSL verification for InfluxDB Connection                                                                    |
#### NUT
|Key            |Description                                                                                                         |
|:--------------|:-------------------------------------------------------------------------------------------------------------------|
|Server         |Host running Network UPS Tools                                                                                      |
|UPSName        |This is the name of the UPS (configured on NUT Server)                                                              |
|Username       |User that has access to monitor NUT Server                                                                          |
|Password       |Password for above user                                                                                             |
#### LOGGING
|Key            |Description                                                                                                         |
|:--------------|:-------------------------------------------------------------------------------------------------------------------|
|Level          |Minimum type of message to log.  Valid options are: critical, error, warning, info, debug                           |

## Docker

### Getting started using Docker

*Installing docker isn't going to be covered here, it varies by platform.*

Docker has instructions for install [here](https://docs.docker.com/engine/install/)<br>
Docker compose install details are [here](https://docs.docker.com/compose/install/)

### Docker run

```
docker run --name nut_to_influx -v /path/to/config/config.ini:/app/config.ini:ro brycech/nut_to_influx

```
### Docker Compose

```
version: '2'
services:
  ups:
    image: brycech/nut_to_influx
    container_name: nut_to_influx
    volumes:
      - /path/to/config/config.ini:/app/config.ini:ro
    restart: always
```

### Build from Source

```bash
git clone https://github.com/BryceCh/nut_to_influx.git
cd nut_to_influx
docker build -t nut_to_influx .
```

## Grafana

Add influx database to Grafana and graph away

Metrics are [fully compatible with this dashboard](https://grafana.com/grafana/dashboards/10914)

![](grafana.gif)
