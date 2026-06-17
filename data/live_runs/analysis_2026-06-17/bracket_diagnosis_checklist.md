# Bracket-Fill Diagnosis — Run This Before Any Code Fix

**Why:** The live run's headline +35% collapses to ~+0.2–6.4% once you remove fills
the bot couldn't confirm. The root cause of the inflation is that **both** bracket
legs fail to fill (9 `time_exit` winners rode past the +1% take-profit; 6 CRITICAL
software-stop forced closes because "IBKR bracket did not execute"). Before we add a
software take-profit (a workaround), confirm *why* the native brackets fail. The fix
differs depending on the answer:

- **Orders not accepted/transmitted at the broker** → fix order submission in `live/broker.py`. The strategy may still be viable in a funded account.
- **Orders accepted but the IBKR *paper* fill-engine doesn't simulate them** → known paper limitation; the software take-profit fallback is the correct mitigation, and real brackets would likely work in a funded account.

The verdict gates everything else.

## The tool

`tools/diagnose_brackets.py` — queries IBKR directly. Read-only by default; never
touches `state.db`; uses clientId 51 so it won't collide with the running trader
(clientId 1). Output contains only order metadata — **no secrets**, safe to paste back.

## Step 1 — Make sure IB Gateway / TWS is up

The trader logged **46 `ConnectionRefused ('127.0.0.1', 7497)`** errors (a ~5-day
outage May 22–27). First confirm the API is actually reachable:

- [ ] IB Gateway (or TWS) is running and logged into the **paper** account.
- [ ] API enabled: *Configure → Settings → API → Settings → "Enable ActiveX and Socket Clients"*.
- [ ] Socket port = **7497** (paper); 7496 is live.
- [ ] "Allow connections from localhost only" is ON (fine for the Pi) and **127.0.0.1** is trusted.
- [ ] "Read-Only API" is **OFF** (the trader must place orders).
- [ ] No leftover clientId 1 lock from a crashed session (restart Gateway if unsure).

## Step 2 — Read-only inspection (always safe)

Best run **while a position is open** (so a live bracket exists to inspect). On the Pi:

```bash
cd ~/MONAD-quant
venv/bin/python tools/diagnose_brackets.py
```

What to look for:
- **OPEN ORDERS**: an open position **must** show a matching `LMT` (take-profit) **and**
  `STP` (stop) child with the same `parent=<id>`. A position with **no children listed
  = the bug** (unprotected position → rides to time-exit / software stop).
- **BROKER POSITIONS** vs **OPEN ORDERS**: every position needs both protective legs.
- **COMPLETED ORDERS**: lines flagged `child ended WITHOUT filling (suspect)` mean a
  TP/SL leg was `Cancelled`/`ApiCancelled`/`Inactive` instead of `Filled`.
- Note each child's `tif` (should be `GTC`), `transmit` (should be `True`), and `status`.

## Step 3 — Test-bracket probe (opt-in, PAPER only, takes NO position)

Submits a parent **BUY LMT 5% below market** (so it rests and never fills) with the
exact GTC bracket children the live code uses, prints each leg's status, then cancels
everything. No position is taken.

```bash
venv/bin/python tools/diagnose_brackets.py --place-test-bracket --i-understand-this-trades
```

Read the **leg statuses after placement**:
- Children `PreSubmitted` (held pending parent) → broker **accepted** them → submission is healthy.
- Children `Submitted` → live and working.
- Children `Inactive` / `ApiCancelled` / **absent** → broker **rejected/dropped** them → **submission bug** (investigate `live/broker.py:285-303`: the `tif` mutation + place loop, transmit sequencing, OCA grouping).

## Step 4 — Decide the fix

| Step 3 result | Conclusion | Next fix |
|---|---|---|
| Children rejected/inactive/absent | Order **submission** is broken | Fix `place_bracket_order` (transmit/OCA/tif); re-test before trusting any result |
| Children accepted (PreSubmitted/Submitted) but live trades still ride past TP | IBKR **paper fill-engine** limitation | Add software take-profit fallback in `trader.py` (mirror the software stop at `trader.py:413-449`); real brackets likely fine in a funded account — confirm with a funded-account test before scaling |

## Specific things to suspect in `live/broker.py`

- **Lines 293-298**: children's `tif` is set to `"GTC"` *after* `bracketOrder()`. Confirm this
  doesn't clear the transmit flags `bracketOrder()` set (parent `transmit=False`,
  TP `transmit=False`, SL `transmit=True` — they must transmit together).
- **Lines 301-303**: orders placed in a loop. Confirm the parent is placed first and the
  last child carries `transmit=True` so all three go live atomically.
- **OCA group**: ib_insync brackets normally share an OCA group so filling one child
  cancels the other. Confirm the `ocaGroup` is present in Step 2 output; a missing/broken
  OCA group can leave children inactive.

## What to send back

Paste the Step 2 output and (if run) the Step 3 leg statuses. From that we can tell in
one read whether to pursue the submission fix or the software take-profit, and proceed.
