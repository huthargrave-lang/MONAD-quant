# MONAD-quant — Operations (`ops/`)

Version-controlled, **no-secret** operational tooling for running the **paper**
trading stack on the Pi and collecting clean data. Credentials, logs, raw
databases, and runtime state stay **out of git** (see `.gitignore`).

> Paper only. Everything here targets IBKR paper (port **7497**). Nothing in this
> folder enables real-money trading or an auto-start trader.

## Contents

| File | Purpose | Safe to run |
|---|---|---|
| `status_check.sh` | One-shot human-readable status (system, gateway, trader, data) | read-only |
| `healthcheck.sh` | Lightweight probe → `local_logs/healthcheck.json` (for the timer) | read-only |
| `healthcheck_ibkr.sh` | Deeper check incl. a live diagnostic connect (manual) | read-only, connects |
| `start_trader.sh` | Guarded trader starter (paper + port 7497 required) | starts trader |
| `start_ibkr_gateway.sh` | Headless IB Gateway Paper launcher via IBC+Xvfb (reads `~/.ibkr-paper.env`) | starts gateway |
| `export_daily_data.py` | Sanitized export of `state.db` → `data/live_runs/pi_export_<date>/` | read-only on db |
| `systemd/` | Unit + timer templates | install manually |

Credentials live in `~/.ibkr-paper.env` (chmod 600, **outside the repo**). None of
these scripts contain secret values — `start_ibkr_gateway.sh` reads them at runtime.

## Install the systemd timers

The **healthcheck** and **daily-export** timers are safe (read-only / no orders).
The **gateway** units are usually already installed; templates here document them.

```bash
sudo cp ~/MONAD-quant/ops/systemd/monad-healthcheck.* /etc/systemd/system/
sudo cp ~/MONAD-quant/ops/systemd/monad-daily-export.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now monad-healthcheck.timer monad-daily-export.timer
```

> The trader autostart below is **preflight-gated** and ships **disabled**. Install/enable
> it only after you have verified a clean paper run.

### Preflight-gated trader autostart (install only after approval)

`monad-trader.service` runs `preflight_trader_start.sh` as a hard `ExecStartPre`
gate (branch, Gateway up, port 7497 open, **7496 closed**, IBKR connects, account
flat, no duplicate trader, writable db/logs, no recent healthcheck failure). Only
if **all** checks pass does it run `start_trader.sh --exec`. `Restart=no` (a crashed
trader stays down for review). `monad-trader.timer` fires weekdays **09:22 ET**.

```bash
# Install the templates (does NOT enable them):
sudo cp ~/MONAD-quant/ops/systemd/monad-trader.service ~/MONAD-quant/ops/systemd/monad-trader.timer /etc/systemd/system/
sudo systemctl daemon-reload
# Dry-run the gate by hand first (safe; exits non-zero if anything is off):
bash ~/MONAD-quant/ops/preflight_trader_start.sh
# Enable the timer ONLY after a verified clean run:
# sudo systemctl enable --now monad-trader.timer
```

## Enable / disable

```bash
systemctl list-timers 'monad-*' 'ibkr-*'        # see schedules + next run
sudo systemctl disable --now monad-healthcheck.timer   # stop a timer
sudo systemctl enable  --now monad-healthcheck.timer   # restart it
systemctl is-enabled monad-trader.service               # should be 'disabled' until validated
```

## Check logs

```bash
cat ~/MONAD-quant/local_logs/healthcheck.json            # latest health snapshot
tail -f ~/MONAD-quant/local_logs/healthcheck.log         # health history
journalctl -u monad-healthcheck.service -n 20            # healthcheck runs
journalctl -u monad-daily-export.service -n 20           # export runs
journalctl -u ibkr-gateway-paper.service -f              # gateway/IBC
journalctl -u monad-trader.service -f                    # trader (when running)
tail -f ~/MONAD-quant/local_logs/ibkr_gateway_start.log  # gateway launcher
```

## Manually start the trader (after verifying it's safe)

1. Confirm Gateway is up and the account is **flat** (no orphan position):
   ```bash
   bash ~/MONAD-quant/ops/status_check.sh
   cd ~/MONAD-quant && venv/bin/python tools/diagnose_brackets.py   # expect FLAT, no stray orders
   ```
2. Start the trader (refuses unless paper-mode + port 7497 open):
   ```bash
   bash ~/MONAD-quant/ops/start_trader.sh
   ```
3. Watch it: `journalctl -u monad-trader.service -f`

To stop: `sudo systemctl stop monad-trader.service`

## Export data after market close (≥ 16:00 ET)

```bash
cd ~/MONAD-quant && venv/bin/python ops/export_daily_data.py
```
(Or let `monad-daily-export.timer` run it at 16:15 ET.) Output:
`data/live_runs/pi_export_<date>/` — sanitized JSON/JSONL, account IDs redacted,
no raw `.db`. Review, then commit the folder if you want it tracked.

## Verify dashboard / source data are updating

```bash
# Source DB freshness:
bash ~/MONAD-quant/ops/status_check.sh        # data_age should be < 20 min in market hours
# Dashboard (read-only FastAPI), then browse via Tailscale http://100.76.6.75:8000 :
cd ~/MONAD-quant && venv/bin/python -m uvicorn live.dashboard:app --host 127.0.0.1 --port 8000
```
The dashboard reads the same `live/state.db`; if `status_check.sh` shows fresh data,
the dashboard reflects it. Cross-check trade count between dashboard and
`status_check.sh` — they read the same source and should agree.

## Safety notes
- Re-pointing or editing `monad-trader.service` is **out of scope** for routine ops — the trader stays manually started until the system is validated.
- If `status_check.sh` shows **port 7496 OPEN**, stop immediately — that is the live port and must never be used here.
- The paper account ID can appear in `local_logs/` and `~/ibc`/`~/Jts` logs (all gitignored / outside the repo). Don't share raw logs.
