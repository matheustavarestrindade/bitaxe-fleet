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
MAX_AXEOS_LOG_RESPONSE_BYTES: Final = 1_048_576
MAX_AXEOS_LOG_TEXT_BYTES: Final = 65_536
MINER_POLL_INTERVAL: Final = timedelta(seconds=60)
MAX_STORED_INCIDENTS: Final = 100

AXEOS_ZEROCONF_SERVICE_TYPE: Final = "_axeos._sub._http._tcp.local."
MAX_ACTIVE_SCAN_HOSTS: Final = 256
ACTIVE_SCAN_CONCURRENCY: Final = 16

PLATFORMS: Final = (Platform.SENSOR,)
STORAGE_STORE_VERSION: Final = 1
STORAGE_SCHEMA_VERSION: Final = 2
