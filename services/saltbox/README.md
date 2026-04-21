# Saltbox Custom Containers

Custom services deployed on the Turing following the [Saltbox Traefik Template](https://docs.saltbox.dev/reference/modules/traefik_template/) pattern.

## Services

| Service | URL | Compose |
|---------|-----|---------|
| Seafile | `seafile.shivelymedia.com` | `seafile/compose.yaml` |
| Romm | `romm.shivelymedia.com` | `romm/compose.yaml` |

## Deployment

Each service is deployed independently under `/opt/<appname>/` on the Turing:

```bash
# Seafile
sudo mkdir -p /opt/seafile/{data,server,mysql}
cp seafile/compose.yaml /opt/seafile/compose.yaml
cp seafile/.env.example /opt/seafile/.env
# Edit /opt/seafile/.env with real secrets
cd /opt/seafile && docker compose up -d

# Romm
sudo mkdir -p /opt/romm/{mysql,resources,redis-data}
sudo mkdir -p /mnt/storage/{roms,romm-assets}
cp romm/compose.yaml /opt/romm/compose.yaml
cp romm/.env.example /opt/romm/.env
# Edit /opt/romm/.env with real secrets
cd /opt/romm && docker compose up -d
```

## Labels

All containers include standard Saltbox labels:
- `com.github.saltbox.saltbox_managed: true` — included in Saltbox backups
- `diun.enable: true` — monitored for image updates
- Full Traefik routing with `globalHeaders`, `secureHeaders`, `robotHeaders`, `cloudflarewarp`, TLS via `cfdns`, and Authentik SSO
