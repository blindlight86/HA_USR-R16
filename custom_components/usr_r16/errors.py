  
"""Errors for the USR-R16 component."""
from homeassistant.exceptions import HomeAssistantError


class R16Exception(HomeAssistantError):
    """Base class for USR-R16 exceptions."""


class AlreadyConfigured(R16Exception):
    """USR-R16 is already configured."""


class CannotConnect(R16Exception):
    """Unable to connect to the USR-R16."""