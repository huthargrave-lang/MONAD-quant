# Deploying the research UI — localhost, the Pi, and the published site

Written 2026-08-13, when `/sweep` was added. It is the first surface in this server that
**runs a subprocess**, and that changes the deployment story enough to be worth writing down
rather than inferring from three service units.

There are three places this code runs. They are not the same product and should not be
configured as if they were.

| | What it is | Can run sweeps | Who can reach it |
|---|---|---|---|
| **Localhost** | the dev loop | yes | you |
| **The Pi, `:8002`** | the always-on instance | depends on its venv | anyone on the network it binds |
| **GitHub Pages** | a static export | **no, by construction** | the public |

---

## 1. Localhost

```bash
venv/bin/python tools/research_ui.py serve --port 8765
```

Then <http://127.0.0.1:8765>. Nothing else is needed: no build step, no database, no broker.
Every page renders from the working tree at request time, so an edit is visible on reload.

**The one wrinkle worth knowing.** This repo's `venv` is Python 3.9.6, and
`src/strategy/sizing.py` annotates with `dict | None`, which parses only on 3.10+. Under the
venv the strategy engine **cannot be imported at all** — which is why 30 of the errors in a
full local `unittest` run are one cause, not thirty. CI runs 3.11 and is unaffected.

`/sweep` handles this rather than breaking on it: `sweep_runner.find_interpreter()` probes for
an interpreter that can import the engine and uses that, and the page says out loud when the
server and the sweep are running on two different Pythons. Check what yours will do:

```bash
venv/bin/python -c "import sys; sys.path.insert(0,'tools'); import sweep_runner, json; print(json.dumps(sweep_runner.availability(), indent=1))"
```

If `runnable` is `false`, `/sweep` explains why instead of rendering a button that errors. The
real fix is a venv on 3.11+, which would also clear those 30 test errors.

---

## 2. The Pi

`deploy/monad-researchui.service` already exists and predates `/sweep`:

```ini
User=hudson
WorkingDirectory=/home/hudson/MONAD-quant
ExecStart=/home/hudson/MONAD-quant/venv/bin/python /home/hudson/MONAD-quant/tools/research_ui.py serve --host 0.0.0.0 --port 8002
Restart=on-failure
```

### The safety property that already holds, and why it matters more now

The trader and the research UI run as **different users from different checkouts**:

```
monad-trader.service     User=pi       /home/pi/MONAD-quant
monad-researchui.service User=hudson   /home/hudson/MONAD-quant
```

`config.py` is the file that arms the trader, and `sweep.py --apply` is the thing that rewrites
it. Even if that flag were somehow reached from the web — it is unreachable by construction,
see `tools/sweep_runner.py` and `tests/test_sweep_runner.py` — it would rewrite **hudson's**
copy, which the trader never reads. That separation was not built for this feature and it is
the strongest thing protecting it. **Do not collapse the two checkouts into one.**

### The change `/sweep` forces: stop binding `0.0.0.0`

`--host 0.0.0.0` binds every interface. That was defensible when every surface was read-only.
It is not now: a sweep is 40 seconds of CPU on a machine whose main job is running a trader,
and the endpoint that starts one is an unauthenticated GET.

Bind the tailnet address instead, exactly as `OPERATIONS.md` already advises for `ctx serve`:

```ini
ExecStart=/home/hudson/MONAD-quant/venv/bin/python /home/hudson/MONAD-quant/tools/research_ui.py serve --host 100.76.6.75 --port 8002
```

There is no auth in this server and none should be added for this — a tailnet is the access
control, and adding a login to a single-user research tool is more surface than it removes.

### If you would rather the Pi never sweep at all

That is a reasonable position: the Pi's CPU belongs to the trader. Two ways, in order of
preference:

1. **Leave its venv on 3.9.** `/sweep` then renders "Cannot run here" with the reason, and no
   run control is drawn. This is the honest default and needs no code change.
2. Remove `"/sweep"` from the route table in `tools/research_ui.py`. Blunter, and it makes the
   rail item 404 rather than explain itself.

---

## 3. GitHub Pages

`.github/workflows/pages.yml` runs `tools/export_pages.py`, which renders the same server
routes to static files. **`/sweep` is excluded and cannot be included**: a static host has no
way to spawn a subprocess, so publishing the page would ship a control that silently does
nothing.

This is enforced, not remembered. `research_ui.SERVER_ONLY_VIEWS` is one list read by both the
rail and the export's "the published views match the server's" check, so adding a server-only
surface without excluding it fails the build rather than shipping a dead link.

---

## 4. What changed about the threat model

Before `/sweep`, the worst an unauthenticated visitor could do was read. Now:

| | Reachable | Bounded by |
|---|---|---|
| Spend CPU | yes | one sweep at a time per click; a 900s timeout kills a wedged run |
| Write files | yes, two | `sweep_results_<TICKER>.json` and `experiments.jsonl` — both gitignored and regenerable |
| Change the trader | **no** | `--apply` is never constructed; stdin is closed so sweep.py's prompt EOFs to "n"; separate user and checkout |
| Run arbitrary commands | **no** | the ticker is matched against a pattern, never interpolated; no shell is used |

The footer on every page used to say this server is read-only. It now names the exception,
because the old sentence became false the moment a button ran a backtest.

---

## 5. Before deploying

```bash
# the suites that cover this surface
venv/bin/python -m unittest tests.test_sweep_runner tests.test_research_ui \
  tests.test_screener_ui tests.test_export_pages tests.test_screener_regression

# the static export still builds and links nothing server-only
venv/bin/python tools/export_pages.py --out _site

# what the target machine will actually do with /sweep
venv/bin/python -c "import sys; sys.path.insert(0,'tools'); import sweep_runner, json; print(json.dumps(sweep_runner.availability(), indent=1))"
```

Then, on the Pi:

```bash
sudo cp deploy/monad-researchui.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl restart monad-researchui
curl -s -o /dev/null -w '%{http_code}\n' http://100.76.6.75:8002/health
```

Restarting this service is safe and unrelated to the trader — different unit, different user,
different checkout. It is not covered by the "never auto-restart the trader" rule.

---

## 6. Open, and deliberately not decided here

- **The venv on 3.9.** Fixing it makes the Pi able to sweep, which may not be what you want.
  Decide the sweep question first, then the venv follows.
- **`0.0.0.0` on the other services.** `ctx serve` has the same bind and `OPERATIONS.md`
  already flags it. Worth doing in one pass rather than one service at a time.
- **A concurrency cap.** Nothing stops several sweeps at once beyond one disabled button per
  browser tab. On a tailnet with one user that is theoretical; it stops being theoretical the
  moment this binds anything wider.
