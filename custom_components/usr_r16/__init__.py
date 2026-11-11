"""Support for USR-R16 relay switches."""
import asyncio
import logging

from usr_r16.protocol import USR16Client
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PASSWORD,
    CONF_SWITCHES,
    CONF_NAME,
    Platform,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
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
PLATFORMS = (Platform.SWITCH,)

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
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    password = entry.data[CONF_PASSWORD]
    address = f"{host}:{port}"

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

    client = R16Client(
        hass,
        entry,
        host=host,
        port=port,
        password=password,
        disconnect_callback=disconnected,
        reconnect_callback=reconnected,
        loop=hass.loop,
        timeout=CONNECTION_TIMEOUT,
        reconnect_interval=DEFAULT_RECONNECT_INTERVAL,
        keep_alive_interval=DEFAULT_KEEP_ALIVE_INTERVAL,
    )

    @callback
    def cleanup():
        """Release this entry's connection on setup failure or unload."""
        client.stop()
        if (entries := hass.data.get(DOMAIN)) is not None:
            entries.pop(entry.entry_id, None)
            if not entries:
                hass.data.pop(DOMAIN)

    entry.async_on_unload(cleanup)
    _LOGGER.info("Initiating USR-R16 connection to %s", address)
    try:
        async with asyncio.timeout(CONNECTION_TIMEOUT):
            await client.setup()
    except (TimeoutError, OSError) as err:
        raise ConfigEntryNotReady(f"Could not connect to USR-R16 at {address}") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_DEVICE_REGISTER: client}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class R16Client(USR16Client):
    """Tie the driver's reconnect tasks to the config entry lifecycle."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, **kwargs):
        super().__init__(**kwargs)
        self._hass = hass
        self._entry = entry

    async def handle_disconnect_callback(self):
        """Run automatic reconnect as a task Home Assistant can cancel."""
        self.is_connected = False
        if self.reconnect:
            await self._entry.async_create_background_task(
                self._hass, super().handle_disconnect_callback(), "USR-R16 reconnect"
            )


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
        _LOGGER.info(f"is_on: {self._is_on}")
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
        callbacks = self._client.status_callbacks[self._device_port]
        self.async_on_remove(lambda: callbacks.remove(self.handle_event_callback))
        self._is_on = self._client.states.get(self._device_port)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"usr_r16_device_available_{self._entry_id}",
                self._availability_callback,
            )
        )