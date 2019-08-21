"""Support for USR-R16 switches."""
import logging

from homeassistant.components.switch import ToggleEntity
from homeassistant.const import CONF_NAME

from . import DATA_DEVICE_REGISTER, R16Device

_LOGGER = logging.getLogger(__name__)


def devices_from_config(hass, domain_config):
    """Parse configuration and add USR-R16 switch devices."""
    switches = domain_config[0]
    device_id = domain_config[1]
    device_client = hass.data[DATA_DEVICE_REGISTER][device_id]
    devices = []
    for device_port, device_config in switches.items():
        device_name = device_config.get(CONF_NAME, device_port)
        device = R16Switch(device_name, device_port, device_id, device_client)
        devices.append(device)
    return devices


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the USR-R16 platform."""
    async_add_entities(devices_from_config(hass, discovery_info))


class R16Switch(R16Device, ToggleEntity):
    """Representation of a USR-R16 switch."""

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._client.turn_on(self._device_port)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._client.turn_off(self._device_port)
    
    async def async_toggle(self, **kwargs):
        """Turn the device off."""
        await self._client.toggle(self._device_port)