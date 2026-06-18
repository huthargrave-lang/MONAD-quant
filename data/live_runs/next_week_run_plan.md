# MONAD-quant — Next-Week Paper Data Collection Plan

*Prepared 2026-06-18 (Pi: `raspberrypi`, Europe/London). Paper trading only — port 7497, never 7496.*

The goal of next week's run is to collect **clean, trustworthy** TQQQ paper-trading
data so we can finally judge whether the strategy has real edge. The previous run's
headline (+35%) was mostly an artifact of broken bracket fills and a state desync;
both are now fixed on this branch.

---

## 1. Current Pi status (as of 2026-06-18 ~03:00 BST)

| Component | State |
|---|---|
| Host / OS | `raspberrypi`, Debian 12 (Pi 5), 19 GB free disk, 7 GB RAM free, idle load |
| Network | WiFi + Tailscale up; GitHub + IBKR web reachable |
| IB Gateway | Installed; **autostart timer enabled** → next run **08:00 ET (13:00 BST)**. Currently down (nightly IBKR restart at ~23:45 BST). |
| Trader | `monad-trader.service` **stopped + boot-disabled** (intentional). |
| Run branch | **`pi-ops-automation`** = dev tip + state-reconciliation fix + software-take-profit fix + diagnostic + these ops scripts. |
| Data | `live/state.db` present, flat (0 open positions), last cycle 2026-06-17 16:32. |

## 2. What is already working
- **Gateway autostart** (systemd timer, timezone-aware, full re-auth from `~/.ibkr-paper.env`).
- **The two correctness fixes** (entry-desync guard, software take-profit) — merged + tested on this branch.
- **Version-controlled ops tooling** in `ops/`: `status_check.sh`, `start_trader.sh`, `healthcheck.sh`, `export_daily_data.py`, `start_ibkr_gateway.sh`, `healthcheck_ibkr.sh`, plus `ops/systemd/` unit templates and `ops/README.md`.
- **Installed + enabled systemd timers** (all paper, none place orders):
  `ibkr-gateway-paper.timer` (08:00 ET start), `monad-healthcheck.timer` (every 5 min, market hours), `monad-daily-export.timer` (16:15 ET). The Gateway service now runs the tracked `ops/start_ibkr_gateway.sh`.
- **Read-only diagnostic** `tools/diagnose_brackets.py`.

## 3. What is broken or unknown
- ⚠️ **yfinance rate-limiting (HTTP 429)** observed once — the trader's signal source. If it persists, signal fetches fail and entries are (correctly) blocked. Recheck tomorrow.
- ⚠️ **No mid-market Gateway auto-recovery** — the healthcheck timer is installed and *observes* gateway/port every 5 min (writes `local_logs/healthcheck.json`), but it does **not** auto-restart the Gateway. If the Gateway dies mid-session, recovery is still manual (`sudo systemctl start ibkr-gateway-paper.service`). Adding an auto-restart action is a deliberate future step.
- ⚠️ **IBC `AutoRestartTime` is blank** — the Gateway uses its own restart time. Confirmed it currently restarts ~23:45 BST (after US close), which is safe, but it's not pinned.
- ❓ **Whether brackets fill reliably enough** in live paper — the software TP/stop now backstop this, but we want to measure how often the native bracket actually fills vs. the software net firing.

## 4. Tomorrow morning checklist (before US market open, 09:30 ET / 14:30 BST)

**Automated (no action needed):**
- IB Gateway Paper starts at **08:00 ET** via `ibkr-gateway-paper.timer` → logs in → opens port 7497.

**Manual (you):**
1. **Confirm Gateway is up & connected** (a few min after 08:00 ET):
   ```bash
   bash ~/MONAD-quant/ops/status_check.sh
   ```
   Expect: `gateway: RUNNING`, `port 7497 (paper): OPEN`, `port 7496 (live): closed`.
2. **Confirm the bot can connect to IBKR** (read-only, no orders):
   ```bash
   cd ~/MONAD-quant && venv/bin/python tools/diagnose_brackets.py
   ```
   Expect: `Connected … accounts=[…]`, and **position FLAT, no stray orders**.
3. **Start the paper trader** (guards paper-mode + port 7497):
   ```bash
   bash ~/MONAD-quant/ops/start_trader.sh
   ```
4. *(Optional)* **Dashboard**:
   ```bash
   cd ~/MONAD-quant && venv/bin/python -m uvicorn live.dashboard:app --host 127.0.0.1 --port 8000
   ```
   View via Tailscale at `http://100.76.6.75:8000` (or localhost).

**Still requires manual attention:** the IBKR login itself is automated for *paper*
(no 2FA). If you ever switch to live, 2FA blocks unattended login — do not attempt.

## 5. How to verify, during the day

| Check | Command | Healthy result |
|---|---|---|
| IBKR connected | `bash ops/status_check.sh` | port 7497 OPEN, gateway RUNNING |
| Trader running | `systemctl status monad-trader.service` | `active (running)` |
| Data being written | `bash ops/status_check.sh` | `data_age` < 20 min during market hours |
| Health snapshot | `bash ops/healthcheck.sh && cat local_logs/healthcheck.json` | `"status":"ok"` |
| Live trader log | `journalctl -u monad-trader.service -f` | hourly `on_bar` cycles, no tracebacks |

## 6. End-of-day export (after 16:00 ET / 21:00 BST)
```bash
cd ~/MONAD-quant && venv/bin/python ops/export_daily_data.py
```
Writes sanitized JSONL/JSON to `data/live_runs/pi_export_<date>/` (account IDs redacted,
no raw `.db`). Review, then optionally commit that folder.

## 7. Failure recovery
| Symptom | Fix |
|---|---|
| Port 7497 closed / gateway down | `sudo systemctl start ibkr-gateway-paper.service`; watch `tail -f local_logs/ibkr_gateway_start.log` |
| Trader not active | `bash ops/start_trader.sh` (it refuses if Gateway is down) |
| `ConnectionRefused` storm | restart Gateway, then trader; check `journalctl -u ibkr-gateway-paper.service` |
| Stale data (`data_age` high) | check trader log for signal-fetch failures (yfinance 429); restart trader |
| Stray/desync position | the trader now **blocks entries** on desync (logs CRITICAL `entry_blocked_desync`); flatten manually in Gateway, then it resumes |
| Disk filling | `du -sh ~/MONAD-quant/local_logs ~/MONAD-quant/data` ; rotate logs |

## 8. What data proves whether the strategy has real edge
Collect across the week and compute (the weekly-analysis step / `export_daily_data.py` feeds this):
- **Confirmed-fill performance only** — exclude `inferred`/`estimated`/software-net exits; that's the honest edge.
- **Win rate, avg win/loss, compounded return** on confirmed fills.
- **How often the software TP/stop fired** vs the native bracket — measures bracket reliability.
- **Count of estimated/inferred fills, bracket failures, IBKR disconnects** — data-quality denominators.
- **Dashboard vs source-DB consistency** — the dashboard compounds + filters; the alert path simple-sums. Numbers must reconcile.
- Minimum bar for "real edge": a week of **mostly confirmed fills** with **positive confirmed-only compounded return** and **no state desyncs**.

## 9. Important caveat
With the software take-profit now capping winners at +1%, **live numbers will look lower
but honest** than the old +35%. That figure was the broken-bracket artifact. Expect the
real edge to be modest (the confirmed-fill backtest range was ~+6%/9 weeks). A smaller,
trustworthy number is the win condition here.
