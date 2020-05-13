#!/usr/bin/python
import socket
import collections
import time
import json
import base64
import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from nut2 import PyNUTClient
import xml.etree.ElementTree as ET
import configparser
import logging
import argparse
import re

import requests

from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError

#Define keys for sending json to influx
remove_keys = ['driver.version.internal', 'driver.version.usb', 'ups.beeper.status', 'driver.name', 'battery.mfr.date']
tag_keys = ['battery.type', 'device.model', 'device.serial', 'driver.version', 'driver.version.data', 'device.mfr', 'device.type', 'ups.mfr', 'ups.model', 'ups.productid', 'ups.serial', 'ups.vendorid']

#Define nutCollector class
class nutCollector():

    def __init__(self, silent, config=None):
        #Grab config values to instantiate object
        self.config = configManager(silent, config=config)
        self.server = self.config.nut_server
        self.upsname = self.config.nut_upsname
        self.port = self.config.nut_port
        self.user = self.config.nut_user
        self.password = self.config.nut_password
        self.output = self.config.output
        self.logger = None
        self.delay = self.config.delay
        self.influx_client = InfluxDBClient(
            self.config.influx_address,
            self.config.influx_port,
            database=self.config.influx_database,
            username=self.config.influx_user,
            password=self.config.influx_password

        )
        self._set_logging()
    
    #Define Logging Options
    def _set_logging(self):
        """
        Create the logger object if enabled in the config
        :return: None
        """

        if self.config.logging:
            if self.output:
                print('Logging is enabled.  Log output will be sent to {}'.format(self.config.logging_file))
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(self.config.logging_level)
            formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
            fhandle = logging.FileHandler(self.config.logging_file)
            fhandle.setFormatter(formatter)
            self.logger.addHandler(fhandle)

    def send_log(self, msg, level):
        """
        Used as a shim to write log messages.  Allows us to sanitize input before logging
        :param msg: Message to log
        :param level: Level to log message at
        :return: None
        """

        if not self.logger:
            return

        if self.output and self.config.valid_log_levels[level.upper()] >= self.config.logging_print_threshold:
            print(msg)

        # Make sure a good level was given
        if not hasattr(self.logger, level):
            self.logger.error('Invalid log level provided to send_log')
            return

        output = self._sanitize_log_message(msg)

        log_method = getattr(self.logger, level)
        log_method(output)

    def _sanitize_log_message(self, msg):
        """
        Take the incoming log message and clean and sensitive data out
        :param msg: incoming message string
        :return: cleaned message string
        """

        msg = str(msg)

        if not self.config.logging_censor:
            return msg

        # Remove server addresses
        for server in self.server:
            msg = msg.replace(server, '*******')

        for match in re.findall(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", msg):
            msg = msg.replace(match, '***.***.***.***')

        return msg

    #Use nut2 library to grab NUT data
    def get_data(self):
         if len(self.user) != 0:
           ups_client = PyNUTClient(host=self.server, port=self.port, login=self.user, password=self.password)
           ups_data = ups_client.list_vars(self.upsname)
         else:
        # Using Python 3.4 here will result in a TypeError: unsupported operand type(s) for %: 'bytes' when passing self.server, self.port 
        # IMPORTANT - Please use at least Python3.6 
           ups_client = PyNUTClient(host=self.server, port=self.port)
           ups_data = ups_client.list_vars(self.upsname)
        
         if ups_data:
           self.send_log('Successfully connected to NUT Server', "info")
         return ups_data

    def convert_to_type(self, s):
        """ A function to convert a str to either integer or float. If neither, it will return the str. """
        try:
            int_var = int(s)
            return int_var
        except ValueError:
            try:
                float_var = float(s)
                return float_var
            except ValueError:
                return s

    def construct_object(self, data, remove_keys, tag_keys):
        """
        Constructs NUT data into  an object that can be sent directly to InfluxDB

        :param data: data received from NUT
        :param remove_keys: some keys which are considered superfluous
        :param tag_keys: some keys that are actually considered tags and not measurements
        :return:
        """
        fields = {}
        tags = {'host': os.getenv('HOSTNAME', 'localhost')}

        for k, v in data.items():
            if k not in remove_keys:
                if k in tag_keys:
                    tags[k] = v
                else:
                    fields[k] = self.convert_to_type(v)

        watts = float(fields['ups.realpower.nominal'])
        fields['watts'] = watts * 0.01 * fields['ups.load']

        result = [
            {
                'measurement': 'ups_status',
                'fields': fields,
                'tags': tags
            }
        ]
        return result

    #Use influxdb library to write json_data to db
    def write_influx_data(self, json_data):
        """
        Writes the provided JSON to the database
        :param json_data:
        :return:
        """
        try:
            self.influx_client.write_points(json_data)
        except (InfluxDBClientError, ConnectionError, InfluxDBServerError) as e:
            if hasattr(e, 'code') and e.code == 404:

                self.send_log('Database {} Does Not Exist.  Attempting To Create', 'error')

                # TODO Grab exception here
                self.influx_client.create_database(self.config.influx_database)
                self.influx_client.write_points(json_data)

                return

            self.send_log('Failed to write data to InfluxDB', 'error')

        self.send_log('Written To Influx: {}'.format(json_data), 'debug')

    def run(self):
        self.send_log('Starting Monitoring Loop with delay {}'.format(self.delay), 'info')
        while True:
            try:
                ups_data = self.get_data()
                json_body = self.construct_object(ups_data, remove_keys, tag_keys)
                print(json_body)
                self.write_influx_data(json_body)
            except Exception as e:
                self.send_log('Error getting data from NUT: {}'.format(e), 'error')

            time.sleep(self.delay)

#Load config values
class configManager():

    def __init__(self, silent, config):

        self.valid_log_levels = {
            'DEBUG': 0,
            'INFO': 1,
            'WARNING': 2,
            'ERROR': 3,
            'CRITICAL': 4
        }
        self.silent = silent

        if not self.silent:
            print('Loading Configuration File {}'.format(config))

        config_file = os.path.join(os.getcwd(), config)
        if os.path.isfile(config_file):
            self.config = configparser.ConfigParser()
            self.config.read(config_file)
        else:
            print('ERROR: Unable To Load Config File: {}'.format(config_file))
            sys.exit(1)

        self._load_config_values()
        self._validate_logging_level()
        if not self.silent:
            print('Configuration Successfully Loaded')

    def _load_config_values(self):

        # General
        self.delay = self.config['GENERAL'].getint('Delay', fallback=20)
        if not self.silent:
            self.output = self.config['GENERAL'].getboolean('Output', fallback=True)
        else:
            self.output = None

        # InfluxDB
        self.influx_address = self.config['INFLUXDB']['Address']
        self.influx_port = self.config['INFLUXDB'].getint('Port', fallback=8086)
        self.influx_database = self.config['INFLUXDB'].get('Database', fallback='ups')
        self.influx_ssl = self.config['INFLUXDB'].getboolean('SSL', fallback=False)
        self.influx_verify_ssl = self.config['INFLUXDB'].getboolean('Verify_SSL', fallback=True)
        self.influx_user = self.config['INFLUXDB'].get('Username', fallback='')
        self.influx_password = self.config['INFLUXDB'].get('Password', fallback='', raw=True)

        # NUT
        self.nut_user = self.config['NUT'].get('Username', fallback=None)
        self.nut_password = self.config['NUT'].get('Password', fallback=None, raw=True)
        self.nut_upsname = self.config['NUT'].get('UPSName', fallback='ups')
        self.nut_server = self.config['NUT'].get('Server', raw=True)
        self.nut_port = self.config['NUT'].getint('Port', raw=True, fallback='3493')
        server = len(self.config['NUT']['Server'])

        #Logging
        self.logging = self.config['LOGGING'].getboolean('Enable', fallback=False)
        self.logging_level = self.config['LOGGING']['Level'].upper()
        self.logging_file = self.config['LOGGING']['LogFile']
        self.logging_censor = self.config['LOGGING'].getboolean('CensorLogs', fallback=True)
        self.logging_print_threshold = self.config['LOGGING'].getint('PrintThreshold', fallback=2)

        if server:
            print('SERVER FOUND. Proceeding')
        else:
            print('ERROR: No NUT Servers Provided.  Aborting')
            sys.exit(1)

    def _validate_logging_level(self):
        """
        Make sure we get a valid logging level
        :return:
        """

        if self.logging_level in self.valid_log_levels:
            self.logging_level = self.logging_level.upper()
            return
        else:
            if not self.silent:
                print('Invalid logging level provided. {}'.format(self.logging_level))
                print('Logging will be disabled')
            self.logging = None

#Execute program
def main():
    parser = argparse.ArgumentParser(description="A tool to send UPS statistics to InfluxDB")
    parser.add_argument('--config', default='config.ini', dest='config', help='Specify a custom location for the config file')
    parser.add_argument('--silent', action='store_true', help='Supress All Output, regardless of config settings')
    args = parser.parse_args()
    collector = nutCollector(args.silent, config=args.config)
    collector.run()

if __name__ == '__main__':
    main()

