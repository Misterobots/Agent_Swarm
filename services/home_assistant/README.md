# Home Assistant Services

Native Home Assistant deployment assets that belong on the Home Assistant box at `192.168.2.100`, not on Hive or the R730 gateway.

## Layout

| Path | Purpose |
|------|---------|
| `addons/` | Native Home Assistant add-on scaffolds |

## Notes

- These assets are intentionally separate from Hive and Saltbox.
- Mission Control is currently implemented as a native Home Assistant add-on scaffold, not as a Docker Compose service.
- The Home Assistant UI is reachable at `http://192.168.2.100:8123`.