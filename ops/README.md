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

### Screener snapshot refresh (safe: read-only research, no broker)

`monad-screener.timer` refreshes the screener snapshots at **17:30 ET, weekdays** —
after the close and after `monad-daily-export` (16:15 ET), so it never overlaps the
export or a trading session. It runs `tools/stock_screener.py fetch` (full curated fund
universe → `data/screener/fundamentals.json`) then `tools/screener_lab.py refresh`
(vendor fundamentals + Bloomberg/Reddit public feeds → `data/cache/screener_snapshot.json`).
Production `/screener` joins both; neither touches `state.db`, `live/**`, `config.py`,
or the broker.

```bash
sudo cp ~/MONAD-quant/deploy/monad-screener.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now monad-screener.timer
systemctl list-timers monad-screener.timer      # confirm the next run
sudo systemctl start monad-screener.service     # run once now, to check it
journalctl -u monad-screener -n 40 --no-pager
```

It is deliberately unobtrusive on the trading host: `Nice=15`, idle CPU and I/O
classes, a 30-minute `TimeoutStartSec` ceiling, and `ProtectSystem=strict` with
`data/cache` and `data/screener` as the only writable paths. `Persistent=true` catches
up a run missed while the Pi was off; `RandomizedDelaySec=600` avoids hitting
rate-limited vendors at the same second daily. If it does not run at all, the page
renders a stale-but-labelled snapshot — a state it is designed for.

**Reddit needs no credentials.** The fetcher uses the public Atom feeds and paces itself
from Reddit's own `x-ratelimit-reset` header (7–60s), which is why a full run takes a
few minutes and is mostly waiting. Setting `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` in
`.env` switches it to the higher-limit OAuth path; nothing else changes.

### Research UI (separate read-only service, :8002)

The same read-only pattern as `monad-ctxweb` (:8001), one port up — the research web,
node views, UI-surface census and the screener. It **renders the snapshot and never
fetches during a request**, so page loads cost no vendor calls.

```bash
sudo cp ~/MONAD-quant/deploy/monad-researchui.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now monad-researchui
```
Then browse via Tailscale: `http://100.76.6.75:8002/screener`. Use
`--host 100.76.6.75` in the unit to keep it tailnet-only (off the LAN).

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
```

The dashboard normally runs as **`monad-dashboard.service`**, coupled to the trader
(up iff the trader is up — see OPERATIONS.md §6), bound to the Tailscale IP. Browse it
at **http://100.76.6.75:8000** whenever the trader is active. Manage it with:

```bash
systemctl status monad-dashboard.service          # is it up?
sudo systemctl start  monad-dashboard.service      # manual start (no-op while trader up)
journalctl -u monad-dashboard.service -n 50        # logs
# Ad-hoc localhost-only run (e.g. on-Pi check while the service is stopped):
cd ~/MONAD-quant && venv/bin/python -m uvicorn live.dashboard:app --host 127.0.0.1 --port 8000
```

The dashboard reads the same `live/state.db`; if `status_check.sh` shows fresh data,
the dashboard reflects it. Cross-check trade count between dashboard and
`status_check.sh` — they read the same source and should agree.

## Context-web map (separate read-only service, :8001)

The research idea-graph has its own web view, deliberately kept separate from the
(fenced) trading dashboard — no DB writes, no broker, no secrets:

```bash
# Ad-hoc, then browse via Tailscale http://100.76.6.75:8001 :
cd ~/MONAD-quant && venv/bin/python tools/ctx.py serve --host 0.0.0.0 --port 8001
# Persistent (auto-restart + start on boot — safe for this read-only daemon):
sudo cp deploy/monad-ctxweb.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now monad-ctxweb
systemctl status monad-ctxweb        # verify; journalctl -u monad-ctxweb -f for logs
```
Endpoints: `GET /` (the interactive map, rebuilt fresh each load), `GET /health`.
Use `--host 100.76.6.75` instead of `0.0.0.0` to keep it tailnet-only (off the LAN).

## Safety notes
- Re-pointing or editing `monad-trader.service` is **out of scope** for routine ops — the trader stays manually started until the system is validated.
- If `status_check.sh` shows **port 7496 OPEN**, stop immediately — that is the live port and must never be used here.
- The paper account ID can appear in `local_logs/` and `~/ibc`/`~/Jts` logs (all gitignored / outside the repo). Don't share raw logs.
