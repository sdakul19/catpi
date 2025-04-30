#!/usr/bin/env python3
import time
import json
import pigpio
import paho.mqtt.client as mqtt
import shelve
import colorsys

from catpi_common import *

PIN_R = 19
PIN_G = 26
PIN_B = 13
PINS = [PIN_R, PIN_G, PIN_B]
PWM_RANGE = 1000
PWM_FREQUENCY = 1000

CATPI_STATE_FILENAME = "catpi_state"

MQTT_CLIENT_ID = "catpi_service"


MAX_STARTUP_WAIT_SECS = 10.0


class InvalidLampConfig(Exception):
    pass


class CatpiDriver(object):

    def __init__(self):
        self._gpio = pigpio.pi()
        for color_pin in PINS:
            self._gpio.set_mode(color_pin, pigpio.OUTPUT)
            self._gpio.set_PWM_dutycycle(color_pin, 0)
            self._gpio.set_PWM_frequency(color_pin, PWM_FREQUENCY)
            self._gpio.set_PWM_range(color_pin, PWM_RANGE)

    

class InvalidCatpiConfig(Exception):
    pass

class CatpiService(object):
    def __init__(self):
        self.catpi_driver = CatpiDriver()
        self._client = self._create_and_configure_broker_client()
        self.db = shelve.open(CATPI_STATE_FILENAME, writeback=True)
        if 'settings' not in self.db:
            self.db['settings'] = {'breakfast': '8:00 AM',
                               'lunch': '12:00 PM',
                               'dinner': '6:00 PM'}
        if 'auto' not in self.db:
            self.db['auto'] = False
        if 'remaining' not in self.db:
            self.db['remaining'] = 10
        if 'client' not in self.db:
            self.db['client'] = ''
        # self.write_current_settings_to_hardware()

    def _create_and_configure_broker_client(self):
        client = mqtt.Client(client_id=MQTT_CLIENT_ID, protocol=MQTT_VERSION)
        client.will_set(client_state_topic(MQTT_CLIENT_ID), "0",
                        qos=2, retain=True)
        client.enable_logger()
        client.on_connect = self.on_connect
        client.message_callback_add(TOPIC_SET_CATPI_CONFIG,
                                    self.on_message_set_config)
        client.on_message = self.default_on_message
        return client

    def serve(self):
        start_time = time.time()
        while True:
            try:
                self._client.connect(MQTT_BROKER_HOST,
                                     port=MQTT_BROKER_PORT,
                                     keepalive=MQTT_BROKER_KEEP_ALIVE_SECS)
                print("Connnected to broker")
                break
            except ConnectionRefusedError as e:
                current_time = time.time()
                delay = current_time - start_time
                if (delay) < MAX_STARTUP_WAIT_SECS:
                    print("Error connecting to broker; delaying and "
                          "will retry; delay={:.0f}".format(delay))
                    time.sleep(1)
                else:
                    raise e
        self._client.loop_forever()
    
    def on_connect(self, client, userdata, rc, unknown):
        self._client.publish(client_state_topic(MQTT_CLIENT_ID),
                             qos=2, retain=True)
        self._client.subscribe(TOPIC_SET_CATPI_CONFIG, qos=1)
        self.publish_config_change()

    def default_on_message(self, client, userdata, msg):
        print("Received unexpected message on topic " +
              msg.topic + " with payload '" + str(msg.payload) + "'")

    def on_message_set_config(self, client, userdata, msg):
        
        try:
            new_config = json.loads(msg.payload.decode('utf-8'))
            if 'client' not in new_config:
                raise InvalidCatpiConfig()
            self.set_last_client(new_config['client'])
            
            if 'remaining' in new_config:
                self.set_current_remaining(new_config['remaining'])
            if 'auto' in new_config:
                self.set_current_auto(new_config['auto'])
            if 'settings' in new_config:
                self.set_current_auto(new_config['settings'])
            self.publish_config_change()
        except InvalidCatpiConfig:
            print("error applying new settings " + str(msg.payload))

    def publish_config_change(self):
        config = {'remaining': self.get_current_remaining(),
                  'auto': self.get_current_auto(),
                  'settings': self.get_current_settings()}
        self._client.publish(TOPIC_CATPI_CHANGE_NOTIFICATION,
                             json.dumps(config).encode('utf-8'), qos=1,
                             retain=True)


    def get_last_client(self):
        return self.db['client']

    def set_last_client(self, new_client):
        self.db['client'] = new_client

    def get_current_auto(self):
        return self.db['auto']
    
    def set_current_auto(self, new_auto):
        if new_auto not in [True, False]:
            raise InvalidCatpiConfig
        self.db['auto'] = new_auto

    def get_current_remaining(self):
        return self.db['remaining']

    def set_current_remaining(self, new_remaining):
        if new_remaining < 0 or new_remaining > 10:
            raise InvalidCatpiConfig
        self.db['remaining'] = new_remaining

    def get_current_settings(self):
        return self.db['settings'].copy()
    
    def set_current_settings(self, new_settings):
        for time in ['breakfast', 'lunch', 'dinner']:
            if new_settings[time] not in ['7:00 AM', '7:30 AM', '8:00 AM', '8:30 AM', '9:00 AM', '9:30 AM', '10:00 AM', '10:30 AM',
                '11:00 AM', '11:30 AM', '12:00 PM', '12:30 PM', '1:00 PM', '1:30 PM', '2:00 PM', '2:30 PM', '3:00 PM', '3:30 PM',
                '4:00 PM', '4:30 PM', '5:00 PM', '5:30 PM', '6:00 PM', '6:30 PM', '7:00 PM', '7:30 PM', '8:00 PM', '8:30 PM', '9:00 PM']:
                raise InvalidCatpiConfig
        for time in ['breakfast', 'lunch', 'dinner']:
            self.db['settings'][time] = new_settings[time]
       
    # def write_current_settings_to_hardware(self):
    #     auto = self.get_current_auto()
    #     remaining = self.get_current_remaining()
    #     breakfast = self.get_current_breakfast()
    #     lunch = self.get_current_lunch()
    #     dinner = self.get_current_dinner()

    #     self.CatpiDriver.set_config(remaining, auto, breakfast, lunch, dinner)
    #     self.db.sync()

if __name__ == '__main__':
    catpi = CatpiService().serve()