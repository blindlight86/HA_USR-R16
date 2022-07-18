"""Support for USR-R16 relay switches."""
import logging

from usr_r16 import create_usr_r16_client_connection
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PASSWORD,
    CONF_SWITCHES,
    CONF_NAME,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.dispatcher import (
    async_dispatcher_send,
    async_dispatcher_connect,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONNECTION_TIMEOUT,
    DEFAULT_KEEP_ALIVE_INTERVAL,
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    DEFAULT_RECONNECT_INTERVAL,
    DOMAIN,

)

_LOGGER = logging.getLogger(__name__)

DATA_DEVICE_REGISTER = "usr_r16_device_register"
DATA_DEVICE_LISTENER = "usr_r16_device_listener"

# SIGNAL_AVAILABILITY = "usr_r16_device_available_{}"

SWITCH_SCHEMA = vol.Schema({vol.Optional(CONF_NAME): cv.string})

RELAY_ID = vol.All(
    vol.Any(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16), vol.Coerce(str)
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                cv.string: vol.Schema(
                    {
                        vol.Required(CONF_HOST): cv.string,
                        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
                        vol.Required(CONF_SWITCHES): vol.Schema(
                            {RELAY_ID: SWITCH_SCHEMA}
                        ),
                    }
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Component setup, do nothing."""
    if DOMAIN not in config:
        return True

    for device_id in config[DOMAIN]:
        conf = config[DOMAIN][device_id]
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={CONF_HOST: conf[CONF_HOST], CONF_PORT: conf[CONF_PORT], CONF_PASSWORD: conf[CONF_PASSWORD]},
            )
        )
    return True
    
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the USR-R16 switch."""
    hass.data.setdefault(DOMAIN, {})
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    password = entry.data[CONF_PASSWORD]
    address = f"{host}:{port}"

    hass.data[DOMAIN][entry.entry_id] = {}

    # def add_device(device):
    #     switches = config[DOMAIN][device][CONF_SWITCHES]

    #     host = config[DOMAIN][device][CONF_HOST]
    #     port = config[DOMAIN][device][CONF_PORT]
    #     password = config[DOMAIN][device][CONF_PASSWORD]

    @callback
    def disconnected():
        """Schedule reconnect after connection has been lost."""
        _LOGGER.warning("USR-R16 %s disconnected", address)
        async_dispatcher_send(hass, f'usr_r16_device_available_{entry.entry_id}', False)

    @callback
    def reconnected():
        """Schedule reconnect after connection has been lost."""
        _LOGGER.warning("USR-R16 %s connected", address)
        async_dispatcher_send(hass, f'usr_r16_device_available_{entry.entry_id}', True)

    async def connect():
        """Set up connection and hook it into HA for reconnect/shutdown."""
        _LOGGER.info("Initiating USR-R16 connection to %s", address)

        client = await create_usr_r16_client_connection(
            host=host,
            port=port,
            password=password,
            disconnect_callback=disconnected,
            reconnect_callback=reconnected,
            loop=hass.loop,
            timeout=CONNECTION_TIMEOUT,
            reconnect_interval=DEFAULT_RECONNECT_INTERVAL,
        )

        hass.data[DOMAIN][entry.entry_id][DATA_DEVICE_REGISTER] = client

        # Load entites
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "switch")
        )

        _LOGGER.info("Connected to USR-R16 device: %s", address)

    hass.loop.create_task(connect())

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    client = hass.data[DOMAIN][entry.entry_id].pop(DATA_DEVICE_REGISTER)
    client.stop()
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "switch")

    if unload_ok:
        if hass.data[DOMAIN][entry.entry_id]:
            hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload_ok

class R16Device(Entity):
    """Representation of a USR-R16 device.
    Contains the common logic for USR-R16 entities.
    """

    def __init__(self, device_port, entry_id, client):
        """Initialize the device."""
        # USR-R16 specific attributes for every component type
        self._entry_id = entry_id
        self._device_port = str(device_port)
        self._is_on = None
        self._client = client
        self._name = f'{DOMAIN}_{device_port}'

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._entry_id}_{self._device_port}"

    @callback
    def handle_event_callback(self, event):
        """Propagate changes through ha."""
        _LOGGER.info("Relay %s new state callback: %r", self.unique_id, event)
        self._is_on = event
        _LOGGER.info("is_on", self._is_on)
        self.async_write_ha_state()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return a name for the device."""
        return self._name

    @property
    def available(self):
        """Return True if entity is available."""
        return bool(self._client.is_connected)

    @callback
    def _availability_callback(self, availability):
        """Update availability state."""
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register update callback."""
        self._client.register_status_callback(
            self.handle_event_callback, self._device_port
        )
        for switch in range(1,17):
            _LOGGER.info(f'callback is {self._client.status_callbacks.get(switch, [])}')
        self._is_on = await self._client.status(self._device_port)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"usr_r16_device_available_{self._entry_id}",
                self._availability_callback,
            )
        )