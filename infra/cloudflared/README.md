# Cloudflare Tunnel — cadence-api

Public ingress for `cadence-api` via Cloudflare. Sidesteps Bell's residential
TCP block (inbound TCP is dropped at the ISP regardless of router config).

End result: `https://cadence-api.poisedgenie.com` → `http://localhost:8010`
on the Windows host, with valid TLS and no inbound ports opened.

## One-time setup

All commands run on **Windows** in PowerShell (non-admin unless noted).

### 1. Install cloudflared

```powershell
winget install --id Cloudflare.cloudflared
# new shell — confirm:
cloudflared --version
```

### 2. Authenticate (opens a browser)

```powershell
cloudflared tunnel login
```

Pick the `poisedgenie.com` zone in the browser. Cloudflare drops a cert at
`%USERPROFILE%\.cloudflared\cert.pem`.

### 3. Create the tunnel

```powershell
cloudflared tunnel create cadence
```

Note the **Tunnel UUID** it prints — the credentials file path uses it. Confirm:

```powershell
cloudflared tunnel list
```

### 4. Bind the hostname to the tunnel

```powershell
cloudflared tunnel route dns cadence cadence-api.poisedgenie.com
```

This creates a CNAME `cadence-api.poisedgenie.com → <UUID>.cfargotunnel.com`
in your Cloudflare DNS automatically.

### 5. Place the config file

Copy `config.yml` from this folder to the cloudflared config dir, then edit
the two placeholders (`<TUNNEL_UUID>` and `<YOUR_USER>`):

```powershell
$dst = "$env:USERPROFILE\.cloudflared\config.yml"
Copy-Item p:\Avyra\avyra-cadence\infra\cloudflared\config.yml $dst
notepad $dst   # replace <TUNNEL_UUID> and <YOUR_USER>
```

### 6. Smoke-test the tunnel in foreground

```powershell
cloudflared tunnel run cadence
```

Leave that running. In another shell:

```powershell
Invoke-RestMethod https://cadence-api.poisedgenie.com/health
```

Should return `{ok=True, service=cadence-api}`. Ctrl-C the tunnel after.

### 7. Install as a Windows service (admin PowerShell)

```powershell
cloudflared service install
```

That registers cloudflared to auto-start on boot. Verify:

```powershell
Get-Service cloudflared
```

Should show `Running`.

## Validation

From any other network (Mac, phone on cellular):

```bash
curl https://cadence-api.poisedgenie.com/health
```

## When the cadence-api container changes ports

Edit `service: http://localhost:8010` in `config.yml`, then restart the
service: admin PowerShell → `Restart-Service cloudflared`.
