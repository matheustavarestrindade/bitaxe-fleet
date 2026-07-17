"""Constants for Bitaxe Fleet."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "bitaxe_fleet"
INTEGRATION_NAME: Final = "Bitaxe Fleet"
MANUFACTURER: Final = "Bitaxe"

CONF_ENROLLMENT_REVISION: Final = "enrollment_revision"
CONF_HOST: Final = "host"

DEFAULT_HTTP_PORT: Final = 80
SYSTEM_INFO_PATH: Final = "/api/system/info"
AXEOS_REQUEST_TIMEOUT_SECONDS: Final = 5
AXEOS_CONNECT_TIMEOUT_SECONDS: Final = 2
AXEOS_READ_TIMEOUT_SECONDS: Final = 3
MAX_AXEOS_RESPONSE_BYTES: Final = 65_536
MINER_POLL_INTERVAL: Final = timedelta(seconds=60)

PLATFORMS: Final = (Platform.SENSOR,)
STORAGE_SCHEMA_VERSION: Final = 1
