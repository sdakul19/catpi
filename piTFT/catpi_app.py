import json
import pigpio
import os
import time

from kivy.app import App
from kivy.properties import NumericProperty, AliasProperty, BooleanProperty, StringProperty
from kivy.clock import Clock
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from paho.mqtt.client import Client

from catpi_common import *
import piTFT.catpi_util


MQTT_CLIENT_ID = "catpi_ui"

version_path = os.path.join(os.path.dirname(__file__), '__VERSION__')
try:
    with open(version_path, 'r') as version_file:
        CATPI_APP_VERSION = version_file.read()
except IOError:
    # if version file cannot be opened, we'll stick with unknown
    CATPI_APP_VERSION = 'Unknown'
# PIN_R = 19
# PIN_G = 26
# PIN_B = 13
# PINS = [PIN_R, PIN_G, PIN_B]
# PWM_RANGE = 1000
# PWM_FREQUENCY = 1000

# class CatpiDriver(object):

#     def __init__(self):
#         self._gpio = pigpio.pi()
#         self.amount = 1.0
        
#         for color_pin in PINS:
#             self._gpio.set_mode(color_pin, pigpio.OUTPUT)
#             self._gpio.set_PWM_dutycycle(color_pin, 0)
#             self._gpio.set_PWM_frequency(color_pin, PWM_FREQUENCY)
#             self._gpio.set_PWM_range(color_pin, PWM_RANGE)

#     def feed(self):
#         # print("knippi_driver")
#         self._gpio.write(PIN_R, 1)
#         time.sleep(2)
#         self._gpio.write(PIN_R,0)
        
        
class CatpiApp(App):
    _updated = False
    _updating_ui = False

    _remaining = NumericProperty()
    # _auto = BooleanProperty()
    _breakfast = StringProperty()
    _lunch = StringProperty()
    _dinner = StringProperty()


    def _get_remaining(self):
        return self._remaining
    
    def _set_remaining(self, value):
        self._remaining = value

    # def _get_auto(self):
    #     return self._auto

    # def _set_auto(self, value):
    #     self._auto = value

    def _get_breakfast(self):
        return self._breakfast

    def _set_breakfast(self, value):
        self._breakfast = value

    def _get_lunch(self):
        return self._lunch

    def _set_lunch(self, value):
        self._lunch = value

    def _get_dinner(self):
        return self._dinner

    def _set_dinner(self, value):
        self._dinner = value

    remaining = AliasProperty(_get_remaining, _set_remaining, bind=['_remaining'])
    # auto = AliasProperty(_get_auto, _set_auto, bind='_auto')
    breakfast = AliasProperty(_get_breakfast, _set_breakfast, bind=['_breakfast'])
    lunch = AliasProperty(_get_lunch, _set_lunch, bind=['_lunch'])
    dinner = AliasProperty(_get_dinner, _set_dinner, bind=['_dinner'])

    gpio17_pressed = BooleanProperty(False)
    device_associated = BooleanProperty(True)

    def on_start(self):
        self._publish_clock = None
        self.mqtt_broker_bridged = False
        self._associated = True
        self.association_code = None
        self.mqtt = Client(client_id=MQTT_CLIENT_ID)
        self.mqtt.enable_logger()
        self.mqtt.will_set(client_state_topic(MQTT_CLIENT_ID), "0",
                           qos=2, retain=True)
        self.mqtt.on_connect = self.on_connect
        self.mqtt.connect(MQTT_BROKER_HOST, port=MQTT_BROKER_PORT,
                          keepalive=MQTT_BROKER_KEEP_ALIVE_SECS)
        self.mqtt.loop_start()
        self.set_up_gpio_and_device_status_popup()
        self.associated_status_popup = self._build_associated_status_popup()
        self.associated_status_popup.bind(on_open=self.update_popup_associated)
        Clock.schedule_interval(self._poll_associated, 0.1)

    def _build_associated_status_popup(self):
        return Popup(title='Associate your Feeder',
                     content=Label(text='Msg here', font_size='30sp'),
                     size_hint=(1, 1), auto_dismiss=False)

    def on_feed(self):
        if self._updating_ui:
            return
        if self._publish_clock is None:
            self._publish_clock = Clock.schedule_once(
                lambda dt: self._update_device(), 0.01)

    def on_auto(self):
        if self._updating_ui:
            return
        if self._publish_clock is None:
            self._publish_clock = Clock.schedule_once(
                lambda dt: self._update_device(), 0.01)


    def save_times(self, breakfast_time, lunch_time, dinner_time):
        print(f"Breakfast: {breakfast_time}, Lunch: {lunch_time}, Dinner: {dinner_time}")

    def on_connect(self, client, userdata, flags, rc):
        self.mqtt.publish(client_state_topic(MQTT_CLIENT_ID), b"1",
                          qos=2, retain=True)
        self.mqtt.message_callback_add(TOPIC_CATPI_CHANGE_NOTIFICATION,
                                       self.receive_new_feeder_state)
        self.mqtt.message_callback_add(broker_bridge_connection_topic(),
                                       self.receive_bridge_connection_status)
        self.mqtt.message_callback_add(TOPIC_CATPI_ASSOCIATED,
                                       self.receive_associated)
        self.mqtt.subscribe(broker_bridge_connection_topic(), qos=1)
        self.mqtt.subscribe(TOPIC_CATPI_CHANGE_NOTIFICATION, qos=1)
        self.mqtt.subscribe(TOPIC_CATPI_ASSOCIATED, qos=2)

    def _poll_associated(self, dt):
        # this polling loop allows us to synchronize changes from the
        #  MQTT callbacks (which happen in a different thread) to the
        #  Kivy UI
        self.device_associated = self._associated

    def receive_associated(self, client, userdata, message):
        # this is called in MQTT event loop thread
        new_associated = json.loads(message.payload.decode('utf-8'))
        if self._associated != new_associated['associated']:
            if not new_associated['associated']:
                self.association_code = new_associated['code']
            else:
                self.association_code = None
            self._associated = new_associated['associated']

    def on_device_associated(self, instance, value):
        if value:
            self.associated_status_popup.dismiss()
        else:
            self.associated_status_popup.open()

        
    def update_popup_associated(self, instance):
        code = self.association_code[0:6]
        instance.content.text = ("Please use the\n"
                                 "following code\n"
                                 "to associate\n"
                                 "your device\n"
                                 f"on the Web\n{code}")

    def receive_bridge_connection_status(self, client, userdata, message):
        # monitor if the MQTT bridge to our cloud broker is up
        if message.payload == b"1":
            self.mqtt_broker_bridged = True
        else:
            self.mqtt_broker_bridged = False

    def receive_new_feeder_state(self, client, userdata, message):
        new_state = json.loads(message.payload.decode('utf-8'))
        Clock.schedule_once(lambda dt: self._update_ui(new_state), 0.01)


    def _update_ui(self, new_state):

        if self._updated and new_state['client'] == MQTT_CLIENT_ID:
            return
        self._updating_ui = True

        try:
            if 'remaining' in new_state:
                self.remaining = new_state['remaining']
            if 'auto' in new_state:
                self.auto = new_state['auto']
            if 'time' in new_state:
                self.breakfast = new_state['time']['breakfast']
                self.lunch = new_state['time']['lunch']
                self.dinner = new_state['time']['dinner']
        finally:
            self._updating_ui = False

        self._updated = True

    #  def _update_leds(self):
    #     msg = {'color': {'h': self._hue, 's': self._saturation},
    #            'brightness': self._brightness,
    #            'on': self.lamp_is_on,
    #            'client': MQTT_CLIENT_ID}
    #     self.mqtt.publish(TOPIC_SET_LAMP_CONFIG,
    #                       json.dumps(msg).encode('utf-8'),
    #                       qos=1)
    #     self._publish_clock = None

    def _update_device(self):
        msg = {'remaining': self._remaining,
            #    'auto': self._auto,
               'time': {'breakfast': self._breakfast,'lunch': self._lunch,'dinner': self._dinner},
               'client': MQTT_CLIENT_ID}
        self.mqtt.publish(TOPIC_SET_CATPI_CONFIG,
                          json.dumps(msg).encode('utf-8'),
                          qos=1)
        self._publish_clock = None

    def set_up_gpio_and_device_status_popup(self):
        self.pi = pigpio.pi()
        self.pi.set_mode(17, pigpio.INPUT)
        self.pi.set_pull_up_down(17, pigpio.PUD_UP)
        Clock.schedule_interval(self._poll_gpio, 0.05)
        self.network_status_popup = self._build_network_status_popup()
        self.network_status_popup.bind(on_open=self._update_dev_status_popup)

    def _build_network_status_popup(self):
        return Popup(title='Device Status',
                     content=Label(text='IP ADDRESS WILL GO HERE'),
                     size_hint=(1, 1), auto_dismiss=False)
    
    def _update_dev_status_popup(self, instance):
        """Update the popup with the current IP address"""
        interface = "wlan0"
        ipaddr = piTFT.catpi_util.get_ip_address(interface)
        deviceid = piTFT.catpi_util.get_device_id()
        msg = (f"Version: {CATPI_APP_VERSION}\n"
               f"{interface}: {ipaddr}\n"
               f"DeviceID: {deviceid}"
               f"\nBroker Bridged: {self.mqtt_broker_bridged}"
               "\nBuffered Analytics")
        instance.content.text = msg

    def on_gpio17_pressed(self, instance, value):
        """Open or close the popup depending on the provided value"""
        if value:
            self.network_status_popup.open()
        else:
            self.network_status_popup.dismiss()

    def _poll_gpio(self, _delta_time):
        # GPIO17 is the rightmost button when looking front of LAMPI
        self.gpio17_pressed = not self.pi.read(17)








   # _updated = False
   # _updating_ui = False()

   

#     def on_start(self):
#         self._publish_clock = None
#         self.mqtt_broker_bridged = False
#         self._associated = True
#         self.association_code = None
#         self.mqtt = Client(client_id=MQTT_CLIENT_ID)
#         self.mqtt.enable_logger()
#         self.mqtt.will_set(client_state_topic(MQTT_CLIENT_ID), "0",
#                               qos=2, retain=True)
#         self.mqtt.on_connect = self.on_connect
#         self.mqtt.connect(MQTT_BROKER_HOST, port=MQTT_BROKER_PORT,
#                           keepalive=MQTT_BROKER_KEEP_ALIVE_SECS)
#         self.mqtt.loop_start()
#         self.set_up_gpio_and_network_status_popup()
#         self.associated_status_popup = self._build_associated_status_popup()
#         self.associated_status_popup.bind(on_open=self.update_popup_associated)
#         Clock.schedule_interval(self._poll_associated, 0.1)
# 
#     def _build_associated_status_popup(self):
#         return Popup(title='Associate your Lamp',
#                      content=Label(text='Msg here', font_size='30sp'),
#                      size_hint=(1, 1), auto_dismiss=False)
# 
#     def on_connect(self, client, userdata, flags, rc):
#         self.mqtt.publish(client_state_topic(MQTT_CLIENT_ID), b"1",
#                            qos=2, retain=True)
#         self.mqtt.message_callback_add(TOPIC_LAMP_CHANGE_NOTIFICATION,
#                                        self.receive_new_lamp_state)
#         self.mqtt.message_callback_add(broker_bridge_connection_topic(),
#                                        self.receive_bridge_connection_status)
#         self.mqtt.message_callback_add(TOPIC_LAMP_ASSOCIATED,
#                                        self.receive_associated)
#         self.mqtt.subscribe(broker_bridge_connection_topic(), qos=1)
#         self.mqtt.subscribe(TOPIC_LAMP_CHANGE_NOTIFICATION, qos=1)
#         self.mqtt.subscribe(TOPIC_LAMP_ASSOCIATED, qos=2)
# 
    # def _poll_associated(self, dt):
    #     # this polling loop allows us to synchronize changes from the
    #     #  MQTT callbacks (which happen in a different thread) to the
    #     #  Kivy UI
    #     self.device_associated = self._associated

    # def receive_associated(self, client, userdata, message):
    #     # this is called in MQTT event loop thread
    #     new_associated = json.loads(message.payload.decode('utf-8'))
    #     if self._associated != new_associated['associated']:
    #         if not new_associated['associated']:
    #             self.association_code = new_associated['code']
    #         else:
    #             self.association_code = None
    #         self._associated = new_associated['associated']

    # def on_device_associated(self, instance, value):
    #     if value:
    #         self.associated_status_popup.dismiss()
    #     else:
    #         self.associated_status_popup.open()

    # def update_popup_associated(self, instance):
    #     code = self.association_code[0:6]
    #     instance.content.text = ("Please use the\n"
    #                              "following code\n"
    #                              "to associate\n"
    #                              "your device\n"
    #                              f"on the Web\n{code}")

    # def receive_bridge_connection_status(self, client, userdata, message):
    #     # monitor if the MQTT bridge to our cloud broker is up
    #     if message.payload == b"1":
    #         self.mqtt_broker_bridged = True
    #     else:
    #         self.mqtt_broker_bridged = False

#     def receive_new_lamp_state(self, client, userdata, message):
#         new_state = json.loads(message.payload.decode('utf-8'))
#         Clock.schedule_once(lambda dt: self._update_ui(new_state), 0.01)
#    
#     def _update_ui(self, new_state):
#         if self._updated and new_state['client'] == MQTT_CLIENT_ID:
#             # ignore updates generated by this client, except the first to
#             #   make sure the UI is syncrhonized with the lamp_service
#             return
#         self._updating_ui = True
#         try:
#             if 'color' in new_state:
#                 self.hue = new_state['color']['h']
#                 self.saturation = new_state['color']['s']
#             if 'brightness' in new_state:
#                 self.brightness = new_state['brightness']
#             if 'on' in new_state:
#                 self.lamp_is_on = new_state['on']
#         finally:
#             self._updating_ui = False
# 
#         self._updated = True
#     
#     def _update_leds(self):
#         msg = {'color': {'h': self._hue, 's': self._saturation},
#                'brightness': self._brightness,
#                'on': self.lamp_is_on,
#                'client': MQTT_CLIENT_ID}
#         self.mqtt.publish(TOPIC_SET_LAMP_CONFIG,
#                           json.dumps(msg).encode('utf-8'),
#                           qos=1)
#         self._publish_clock = None
   
    # def set_up_gpio_and_network_status_popup(self):
    #     self.pi = pigpio.pi()
    #     self.pi.set_mode(17, pigpio.INPUT)
    #     self.pi.set_pull_up_down(17, pigpio.PUD_UP)
    #     Clock.schedule_interval(self._poll_gpio, 0.05)
    #     self.network_status_popup = self._build_network_status_popup()
    #     self.network_status_popup.bind(on_open=self.update_popup_ip_address)

    # def _build_network_status_popup(self):
    #     return Popup(title='Network Status',
    #                  content=Label(text='IP ADDRESS WILL GO HERE'),
    #                  size_hint=(1, 1), auto_dismiss=False)

    # def update_popup_ip_address(self, instance):
    #     """Update the popup with the current IP address"""
    #     interface = "wlan0"
    #     ipaddr = lampi.lampi_util.get_ip_address(interface)
    #     deviceid = lampi.lampi_util.get_device_id()
    #     msg = f"{interface}: {ipaddr}\nDeviceID: {deviceid}" + \
    #         f"\nBroker Bridged: {self.mqtt_broker_bridged}"
    #     instance.content.text = msg

    # def on_gpio17_pressed(self, instance, value):
    #     """Open or close the popup depending on the provided value"""
    #     if value:
    #         self.network_status_popup.open()
    #     else:
    #         self.network_status_popup.dismiss()

    # def _poll_gpio(self, _delta_time):
    #     # GPIO17 is the rightmost button when looking front of LAMPI
    #     self.gpio17_pressed = not self.pi.read(17)
