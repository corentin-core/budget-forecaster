# Deployment

How to run the [web app](web-app.md) as a background service, reachable from your phone
and other PCs over your private Tailscale network, with the bank sync on a daily timer.

The app binds to `127.0.0.1` only and is never exposed to the public internet: Tailscale
is the sole entry point, and it terminates HTTPS with a valid certificate for your
machine's `*.ts.net` name.

Two hosts are supported, sharing the same units and steps:

- A dedicated Linux machine (Raspberry Pi, mini-PC) — always on, nothing to mix with a
  work laptop. Recommended.
- Your own PC through WSL2 on Windows.

Follow the [Common setup](#common-setup) first, then the
[host prerequisites](#host-prerequisites) for your machine.

## Common setup

These steps are identical on any Linux host, including WSL2.

### 1. Install the app

Clone the repository, create a virtualenv, and install:

```bash
git clone https://github.com/corentin-core/budget-forecaster.git
cd budget-forecaster
python3 -m venv ~/budget-forecaster-venv
~/budget-forecaster-venv/bin/pip install -e .
```

The systemd units expect the virtualenv at `~/budget-forecaster-venv`. If yours is
elsewhere, edit `ExecStart` in both service files.

Put your `config.yaml` and the account database where the service will find them, e.g.
`~/.config/budget-forecaster/`.

### 2. Secrets

The app needs a cookie signing key and the shared-password hash. Generate both:

```bash
# Signing key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Password hash (prompts for the password twice)
python -m budget_forecaster.main hash-password
```

Copy the environment template and fill it in:

```bash
mkdir -p ~/.config/budget-forecaster
cp deploy/service.env.example ~/.config/budget-forecaster/service.env
chmod 600 ~/.config/budget-forecaster/service.env
```

Edit `service.env`: set `BUDGET_CONFIG` to the absolute path of your config file, paste
the signing key into `BUDGET_WEB_SECRET_KEY` and the hash into
`BUDGET_WEB_PASSWORD_HASH`, and keep `BUDGET_WEB_SECURE_COOKIES=1`. Keep all variables
present — systemd applies no default for a missing one.

### 3. Tailscale

Install Tailscale and join your tailnet:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Then let Tailscale serve the app over HTTPS on your node's `*.ts.net` name:

```bash
sudo tailscale serve --bg http://127.0.0.1:8000
```

`tailscale serve` persists across reboots. Find your node name with `tailscale status`;
the app is then reachable at `https://<node>.<tailnet>.ts.net`.

### 4. systemd services

Install the units as user services (no root; they run under your account):

```bash
mkdir -p ~/.config/systemd/user
cp deploy/systemd/budget-web.service deploy/systemd/budget-sync.service deploy/systemd/budget-sync.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now budget-web.service
systemctl --user enable --now budget-sync.timer
```

Let the services keep running after you log out, and start on boot:

```bash
sudo loginctl enable-linger "$USER"
```

Check status and logs:

```bash
systemctl --user status budget-web.service
journalctl --user -u budget-web.service -f
systemctl --user list-timers budget-sync.timer
```

### 5. Bank callback

Register the callback URL in the Enable Banking portal so the OAuth redirect lands back
in the app:

```text
https://<node>.<tailnet>.ts.net/settings/bank/callback
```

Set the same URL as `enable_banking.redirect_url` in your `config.yaml`, replacing the
`localhost` value used during local development — the portal registration and the config
must match, or the bank never redirects back. See the
[Enable Banking guide](enable-banking.md) for the portal setup.

### Access

Install Tailscale on your phone and other PCs, sign in to the same tailnet, and open
`https://<node>.<tailnet>.ts.net`. Sign in with the shared password. Nothing else needs
installing on those devices.

### Updating

```bash
cd budget-forecaster
git pull
~/budget-forecaster-venv/bin/pip install -e .
systemctl --user restart budget-web.service
```

## Host prerequisites

### Raspberry Pi / mini-PC (native Linux)

Nothing extra. systemd is already the init system, user services start on boot once
linger is enabled, and Tailscale runs natively. Follow the common setup as-is.

### Windows via WSL2

Install WSL2 with a recent Ubuntu, then:

1. **Enable systemd** inside the distro. Add to `/etc/wsl.conf`:

   ```ini
   [boot]
   systemd=true
   ```

   Then `wsl --shutdown` from Windows and reopen the distro.

2. **Start WSL on Windows boot** so the services come up without you opening a terminal.
   Create a Windows Task Scheduler task that runs at logon:

   - Program: `wsl.exe`
   - Arguments: `-d Ubuntu true`

   This boots the distro (and its systemd services) in the background.

3. **Tailscale TUN fallback.** If `sudo tailscale up` reports no TUN device, run it in
   userspace-networking mode:

   ```bash
   sudo tailscaled --tun=userspace-networking &
   sudo tailscale up
   ```

Then follow the common setup.
