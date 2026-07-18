# Synthetic AxeOS Fixtures

These fixtures model documented public fields from AxeOS/ESP-Miner `v2.14`
responses for `GET /api/system/info`, `GET /api/system/asic`, and
`GET /api/system/logs`. They are synthetic compatibility fixtures based on the
public OpenAPI shape, not captures from a household miner.

Every identity, hostname, model value, fault, and log line is synthetic. The
MAC addresses are locally administered and do not identify real hardware. No
fixture contains a household address, SSID, wallet, pool URL, credential, or
other secret.

On 2026-07-17, the typed read boundary was validated read-only against a local
BM1370 Gamma running AxeOS `v2.14.2`. System information, ASIC capabilities,
and the log endpoint parsed successfully. The real response was not retained;
these fixtures remain synthetic. Automatic recovery and every mutation still
require separate controlled hardware validation.
