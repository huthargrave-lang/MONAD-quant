# MONAD-quant — Operations (`ops/`)

Version-controlled, **no-secret** operational tooling for running the **paper**
trading stack on the Pi and collecting clean data. Credentials, logs, raw
databases, and runtime state stay **out of git** (see `.gitignore`).

> Paper only. Everything here targets IBKR paper (port **7497**). Nothing in this
> folder enables real-money trading or an auto-start trader.
>
> **The trader is DECOMMISSIONED (2026-10-29).** `ops/DECOMMISSIONED.json` is the tracked
> marker; the four `monad-trader*` units are masked on the Pi. Read **OPERATIONS.md §6.1**
> before touching any of them — revival is a reviewed commit, not an ops action.

## Contents

| File | Purpose | Safe to run |
|---|---|---|
| `status_check.sh` | One-shot human-readable status (system, gateway, trader, data) | read-only |
| `healthcheck.sh` | Lightweight probe → `local_logs/healthcheck.json` (for the timer) | read-only |
| `healthcheck_ibkr.sh` | Deeper check incl. a live diagnostic connect (manual) | read-only, connects |
| `start_trader.sh` | Guarded trader starter (paper + port 7497 required); **refuses while `DECOMMISSIONED.json` exists** | refuses (decommissioned) |
| `preflight_trader_start.sh` | The 11-check arming gate (`ExecStartPre`); check 11 fails while `DECOMMISSIONED.json` exists | read-only, connects |
| `decommission_trader.sh` | One-shot, idempotent, fail-closed decommission of the trader on the Pi (OPERATIONS.md §6.1) | changes unit state; paper only |
| `export_stop_exits.py` | Stop-exit rows with labelled provenance → the decommission archive (ENGINE_V3 item (g)) | read-only on db |
| `DECOMMISSIONED.json` | Tracked decommission marker (date, decision, revival pointer, archive id + receipt filled by the operator) | data |
| `start_ibkr_gateway.sh` | Headless IB Gateway Paper launcher via IBC+Xvfb (reads `~/.ibkr-paper.env`) | starts gateway |
| `export_daily_data.py` | Sanitized export of `state.db` → `data/live_runs/pi_export_<date>/` | read-only on db |
| `systemd/` | Unit + timer templates | install manually |
| `forward_watch_cycle.sh` | One cycle of the forward records (`daily` / `weekly`): fetch, log, verify, commit, push to `forward-ledger` | research only; commits + pushes the ledger branch |

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

> The trader autostart is **decommissioned** — see OPERATIONS.md §6.1. Do not install or
> enable `monad-trader*` units; the preflight's check 11 refuses while the marker exists.

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

### Preflight-gated trader autostart — DECOMMISSIONED, see OPERATIONS.md §6.1

The install/enable recipe that used to live here is retired with the trader. The
`monad-trader.service`/`.timer` and `monad-trader-rearm.*` units are **masked** on the Pi
(unit files parked in `/etc/systemd/system/.decommissioned/` by `decommission_trader.sh`),
`preflight_trader_start.sh` check 11 fails while `ops/DECOMMISSIONED.json` exists, and
`deploy/setup-pi.sh` refuses to install the boot-enabled unit. The revival condition and the
exact re-arm sequence are stated **once**, in **OPERATIONS.md §6.1** — follow that, not a
remembered recipe.

```bash
# Still safe and useful by hand (read-only; exits non-zero — check 11 — while decommissioned):
bash ~/MONAD-quant/ops/preflight_trader_start.sh
```

## Enable / disable

```bash
systemctl list-timers 'monad-*' 'ibkr-*'        # see schedules + next run
sudo systemctl disable --now monad-healthcheck.timer   # stop a timer
sudo systemctl enable  --now monad-healthcheck.timer   # restart it
systemctl is-enabled monad-trader.service               # should be 'masked' (decommissioned — OPERATIONS.md §6.1)
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

## Manually start the trader — DECOMMISSIONED, see OPERATIONS.md §6.1

`start_trader.sh` refuses (exit 3) in both modes while `ops/DECOMMISSIONED.json` exists, so
the manual-start recipe is retired with the trader. Revival condition and mechanics:
**OPERATIONS.md §6.1** only. What remains useful here:

```bash
bash ~/MONAD-quant/ops/status_check.sh                                 # read-only status
cd ~/MONAD-quant && venv/bin/python tools/diagnose_brackets.py         # read-only; expect FLAT, no stray orders (needs the Gateway up)
bash ~/MONAD-quant/ops/decommission_trader.sh                          # idempotent; prints the unit table when already done
```

To stop a trader process that should not be running: `sudo systemctl stop monad-trader.service`
(a masked unit cannot be started, so this is only relevant to a process launched by hand).

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

The dashboard ran as **`monad-dashboard.service`**, coupled to the trader (up iff the
trader is up — see OPERATIONS.md §6) and is **disabled with it** (decommissioned; dark by
design). The ad-hoc localhost run below still serves the archive view. Manage it with:

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

## Forward records (research host role)

With the hourly trader decommissioned (D-3), the Pi's standing job is to keep the three
**forward records** current — the only paths to a positive admitted result in this repo
(`docs/DIRECTIONS.md` D-1; the admission route they feed was ratified 2026-10-29,
`docs/research/FORWARD_ROUTE_PROPOSAL.md` "Ratification"). Nothing here touches the broker,
`state.db`, `live/**`, `config*` or `ops/systemd/`.

| Record | Unit | When (ET; the Pi clock is Europe/London) | What runs |
|---|---|---|---|
| H366201 NAV vintage, then both watches' session lines | `deploy/monad-forward-watch.timer` | **Mon..Fri 18:40**, `Persistent=true` | `ops/forward_watch_cycle.sh daily` → `forward_watch.py fetch H366201`, `log H366200`, `log H366201`, `verify --against origin/development`, commit, push |
| H404702 weekly as-of holdings | `deploy/monad-forward-log.timer` | **Sat 10:15**, `Persistent=true` | `ops/forward_watch_cycle.sh weekly` → `forward_log.py H404702`, `verify`, commit, push |

**Why 18:40 ET.** Session t's H366201 decision executes at session t+1's close (20:00 UTC)
and may read only a NAV vintage fetched before then (`forward_watch.vintage_for`); otherwise
it reads the latest earlier vintage under the rule's 14-day staleness. An evening fetch lands
~20 h ahead of that deadline, after `monad-screener` (17:30) so two vendor-heavy jobs never
overlap, and a same-evening `log` is valid (session t reads only NAVs dated before t). A run
missed while the Pi was off fires at boot (`Persistent=true`); `log` catches up every session
since its last line. `fetch` writes `vintage` lines only — it never reads a return.

**Why a dedicated branch and checkout.** `development` is branch-protected on the `test`
check, so a direct push is refused; the records go to **`forward-ledger`** (the tone ledger's
pattern, `.github/workflows/pages.yml`) over the SSH URL (OPERATIONS.md §1.6) and reach
`development` by PR. Every record is append-only and every spec/policy file is frozen
(`verify`'s prefix/identical rules), so the PR passes `verify --against origin/development`
and merges clean as long as **this is the only place that appends to the chains**. The cycle
runs in a **linked worktree** on that branch, so the main checkout stays on `development`
and the drift oracle keeps telling the truth. Each step commits before the next (every
record command refuses a dirty tree, because each line names the code it ran on).

### One-time setup (on the Pi, as `hudson`)

```bash
# 1. SSH push key (OPERATIONS.md §1.6): must authenticate non-interactively.
ssh -o BatchMode=yes -T git@github.com

# 2. The ledger worktree, beside the main checkout. First time (no forward-ledger yet):
git -C ~/MONAD-quant fetch origin development
git -C ~/MONAD-quant worktree add ../MONAD-quant-forward -b forward-ledger origin/development
#    If origin/forward-ledger already exists (someone logged by hand and pushed):
#    git -C ~/MONAD-quant fetch origin forward-ledger:forward-ledger
#    git -C ~/MONAD-quant worktree add ../MONAD-quant-forward forward-ledger

# 3. The private store. H366201's log reads the NAV vintages already recorded (private
#    observations, local_research_data/, gitignored). Export on the machine that has them,
#    import here, then share one store between the two checkouts:
#      owner:  venv/bin/python tools/data_inventory.py export      # -> an archive
#      Pi:     venv/bin/python tools/data_inventory.py import <archive>
ln -s ~/MONAD-quant/local_research_data ~/MONAD-quant-forward/local_research_data

# 4. Install and enable the two timers (templates assume user hudson and these paths):
sudo cp ~/MONAD-quant-forward/deploy/monad-forward-watch.* ~/MONAD-quant-forward/deploy/monad-forward-log.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now monad-forward-watch.timer monad-forward-log.timer
systemctl list-timers 'monad-forward-*'

# 5. First run by hand, without pushing, and read what it did:
MONAD_FORWARD_NO_PUSH=1 ~/MONAD-quant-forward/ops/forward_watch_cycle.sh daily
git -C ~/MONAD-quant-forward log --oneline -5
journalctl -u monad-forward-watch -n 50 --no-pager
```

**Before the first `log` can run** (owner's machine, where the private store is): the
ratification PR edits `src/research/forward_watch.py`, a source both specs pin, so `log`
refuses with "the evaluator sources changed ... attest the change" until
`venv/bin/python tools/forward_watch.py attest-evaluator H366200 --reason "..."` and the same
for `H366201` have been run (they run the watch tests with the private store required and no
skips) and their `evaluator_change` lines are committed on the branch the worktree tracks.
`fetch` needs no attestation and should run daily from 2026-10-29 regardless.

The cycle **exits non-zero on any failure** and the journal names the step; the other steps
still run (a CEFConnect outage must not stop H366200's log). Commits made before a failure
stay local and go out with the next good cycle. Env knobs: `MONAD_FORWARD_REPO`,
`MONAD_FORWARD_PYTHON`, `MONAD_FORWARD_BRANCH`, `MONAD_FORWARD_PUSH_URL`,
`MONAD_FORWARD_NO_PUSH=1`.

### Weekly: the PR from `forward-ledger` into `development`

The records are evidence only once they are on `development` (the window dates, the
`admit_watch` chain and `verify --against` all read development's first-parent history).
Once a week, from any machine with `gh`:

```bash
gh pr create --repo huthargrave-lang/MONAD-quant --base development --head forward-ledger \
  --title "Forward records: week of $(date -u +%Y-%m-%d)" \
  --body "Machine-written record commits from the Pi (monad-forward-watch / monad-forward-log). Append-only; verify --against origin/development is the CI check."
```

CI runs `tools/forward_watch.py verify --against origin/development` on the PR; merge when it
is green. The next cycle fast-forwards (or merges) `origin/development` back into the worktree
before it logs, so the ledger branch always carries development's attestations.

## Safety notes
- Re-pointing or editing `monad-trader.service` is **out of scope** for routine ops — the trader is **decommissioned** (OPERATIONS.md §6.1); re-arming it is a reviewed commit that deletes `ops/DECOMMISSIONED.json`, never an ops action.
- If `status_check.sh` shows **port 7496 OPEN**, stop immediately — that is the live port and must never be used here.
- The paper account ID can appear in `local_logs/` and `~/ibc`/`~/Jts` logs (all gitignored / outside the repo). Don't share raw logs.
