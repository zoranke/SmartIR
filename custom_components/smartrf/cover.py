import asyncio
import json
import logging
import os.path

import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    SUPPORT_OPEN,
    SUPPORT_CLOSE,
    PLATFORM_SCHEMA,
    CoverEntity,
)
from homeassistant.const import (
    CONF_NAME, STATE_OPEN, STATE_OPENING, STATE_CLOSED, STATE_CLOSING, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

from homeassistant.helpers.event import track_utc_time_change, async_track_time_interval
from homeassistant.helpers.event import async_track_state_change

from . import COMPONENT_ABS_DIR, Helper
from .controller import get_controller

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "SmartRF Cover"

CONF_UNIQUE_ID = 'unique_id'
CONF_DEVICE_CODE = 'device_code'
CONF_CONTROLLER_DATA = "controller_data"
CONF_TRAVEL_TIME = 'travel_time'
CONF_POS_SENSOR = 'position_sensor'

#CONF_COMMAND_OPEN = 'command_open'
#CONF_COMMAND_CLOSE = 'command_close'
#CONF_COMMAND_STOP = 'command_stop'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_DEVICE_CODE): cv.positive_int,
    vol.Required(CONF_CONTROLLER_DATA): cv.string,
    vol.Optional(CONF_TRAVEL_TIME, default=None): cv.positive_int,
    vol.Optional(CONF_POS_SENSOR): cv.entity_id,
   
#    vol.Optional(CONF_COMMAND_STOP, default=None): cv.string,
#    vol.Optional(CONF_COMMAND_OPEN, default=None): cv.string,
#    vol.Optional(CONF_COMMAND_CLOSE, default=None): cv.string,
})

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the RF Cover platform."""
    device_code = config.get(CONF_DEVICE_CODE)
    device_files_subdir = os.path.join('codes', 'cover')
    device_files_absdir = os.path.join(COMPONENT_ABS_DIR, device_files_subdir)

    if not os.path.isdir(device_files_absdir):
        os.makedirs(device_files_absdir)

    device_json_filename = str(device_code) + '.json'
    device_json_path = os.path.join(device_files_absdir, device_json_filename)

    if not os.path.exists(device_json_path):
        _LOGGER.warning("Couldn't find the device Json file. The component will " \
                        "try to download it from the GitHub repo.")

        try:
            codes_source = ("https://raw.githubusercontent.com/"
                            "zoranke/SmartRF/master/"
                            "codes/cover/{}.json")

            await Helper.downloader(codes_source.format(device_code), device_json_path)
        except Exception:
            _LOGGER.error("There was an error while downloading the device Json file. " \
                          "Please check your internet connection or if the device code " \
                          "exists on GitHub. If the problem still exists please " \
                          "place the file manually in the proper directory.")
            return

    with open(device_json_path) as j:
        try:
            device_data = json.load(j)
        except Exception:
            _LOGGER.error("The device JSON file is invalid")
            return

    async_add_entities([SmartRFCover(
        hass, config, device_data
    )])
class SmartRFCover(CoverEntity, RestoreEntity):
    def __init__(self, hass, config, device_data):
        self.hass = hass
        self._unique_id = config.get(CONF_UNIQUE_ID)
        self._name = config.get(CONF_NAME)
        self._device_code = config.get(CONF_DEVICE_CODE)
        self._controller_data = config.get(CONF_CONTROLLER_DATA)
        self._travel_time = config.get(CONF_TRAVEL_TIME)
        self._pos_sensor = config.get(CONF_POS_SENSOR)

        self._manufacturer = device_data['manufacturer']
        self._supported_models = device_data['supportedModels']
        self._supported_controller = device_data['supportedController']
        self._commands_encoding = device_data['commandsEncoding']
#        self._speed_list = [SPEED_OFF] + device_data['speed']
        self._commands = device_data['commands']
        
#        self._speed = SPEED_OFF
#        self._direction = None
#        self._last_on_speed = None
#        self._oscillating = None
#        self._support_flags = SUPPORT_SET_SPEED

#        if (DIRECTION_REVERSE in self._commands and \
#            DIRECTION_FORWARD in self._commands):
#            self._direction = DIRECTION_REVERSE
#            self._support_flags = (
#                self._support_flags | SUPPORT_DIRECTION)
#        if ('oscillate' in self._commands):
#            self._oscillating = False
#            self._support_flags = (
#                self._support_flags | SUPPORT_OSCILLATE)


#        self._temp_lock = asyncio.Lock()
#        self._on_by_remote = False

        #Init the IR/RF controller
        self._controller = get_controller(
            self.hass,
            self._supported_controller, 
            self._commands_encoding,
            self._controller_data)
    
    @callback
    def _async_update_pos(self, state):
        if state.state in ('false', STATE_CLOSED, 'off'):
            if self._device_class == 'window':
                self._position = 0
            self._closed = True
        else:
            self._closed = False
            if self._position == 0:
                self._position = 100

    @asyncio.coroutine
    def _async_pos_changed(self, entity_id, old_state, new_state):
        if new_state is None:
            return
        self._async_update_pos(new_state)
        yield from self.async_update_ha_state()

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._supported_features is not None:
            return self._supported_features
        return super().supported_features

    @property
    def should_poll(self):
        """No polling needed for a demo cover."""
        return False

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return self._position
#######
    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self._position is None:
            return self._closed
        else:
            return self._position == 0         

    @property
    def is_closing(self):
        """Return if the cover is closing."""
        return self._is_closing
##############################
    @property
    def is_opened(self):
        """Return if the cover is opened."""
        if self._position is None:
            return self._opened
        else:
            return self._position == 100
##################
    @property
    def is_opening(self):
        """Return if the cover is opening."""
        return self._is_opening

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    def close_cover(self, **kwargs):
        """Close the cover."""
        if self._position == 0:
            return
        elif self._position is None:
            if self._sendpacket(self._cmd_close):
                self._closed = True
                self.schedule_update_ha_state()
            return

        if self._sendpacket(self._cmd_close):
            self._travel = self._travel_time + 1
            self._is_closing = True
            self._listen_cover()
            self._requested_closing = True
            self.schedule_update_ha_state()

    def open_cover(self, **kwargs):
        """Open the cover."""
        if self._position == 100:
            return
        elif self._position is None:
            if self._sendpacket(self._cmd_open):
#                self._closed = False
                self._opened = True
                self.schedule_update_ha_state()
            return

        if self._sendpacket(self._cmd_open):
            self._travel = self._travel_time + 1
            self._is_opening = True
            self._listen_cover()
            self._requested_closing = False
#            self._requested_opening = True
            self.schedule_update_ha_state()

    def set_cover_position(self, position, **kwargs):
        """Move the cover to a specific position."""
        if position <= 0:
            self.close_cover()
        elif position >= 100:
            self.open_cover()
        elif round(self._position) == round(position):
            return
        elif self._travel > 0:
            return
        else:
            steps = abs((position - self._position) / self._step)
            if steps >= 1:        
                self._travel = round(steps, 0)
            else:
                self._travel = 1
            self._requested_closing = position < self._position
            if self._requested_closing:
                if self._sendpacket(self._cmd_close):
                    self._listen_cover()
            else:
                if self._sendpacket(self._cmd_open):
                    self._listen_cover()


    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._is_closing = False
        self._is_opening = False
        if self._position is None:
            self._sendpacket(self._cmd_stop)
            return
        elif self._position > 0 and self._position < 100:
                self._sendpacket(self._cmd_stop)

        if self._unsub_listener_cover is not None:
            self._unsub_listener_cover()
            self._unsub_listener_cover = None

    def _listen_cover(self):
        """Listen for changes in cover."""
        if self._unsub_listener_cover is None:
            self._unsub_listener_cover = track_utc_time_change(
                self.hass, self._time_changed_cover)
            self._delay = True

    def _time_changed_cover(self, now):
        """Track time changes."""
        if self._delay:
            self._delay = False
        else:
            if self._requested_closing:
                if round(self._position - self._step) > 0:
                    self._position -= self._step
                else:
                    self._position = 0
                    self._travel = 0
            else:
                if round(self._position + self._step) < 100:
                    self._position += self._step
                else:
                    self._position = 100
                    self._travel = 0

            self._travel -= 1

            if self._travel == 0:
               self.stop_cover()
            
            self.schedule_update_ha_state()
            self.async_write_ha_state()
    async def async_added_to_hass(self):
#        await super().async_added_to_hass()
#        last_state = await self.async_get_last_state()
#        
#        if last_state:
#           self._position = last_state.attributes['current_position']
#        else:
#           self._position = None
