# Study 61 — Broker account/model scope audit

**Date:** 2026-07-24<br>
**Status:** reproducible conditional safety audit; current Gateway account
structure intentionally unknown; no live/config/order-path change authorized<br>
**Artifact:** `tools/overnight_gap_risk_study.py` →
`broker_account_scope_audit`

## Question

Do sizing capital, reconciled positions, order destinations, local lifecycle
state, and executions all carry one explicit account/model identity—or does the
runtime assume the Gateway exposes exactly one account?

## Verdict

**Account identity is an implicit environmental assumption, not an enforced
invariant.**

The current broker adapter:

- calls `ib.accountSummary()` and stores the last value seen for each tag,
  ignoring account and currency;
- calls `ib.positions()` and returns the first row whose contract symbol is
  `TQQQ`, ignoring account, model, and contract ID;
- does not configure an authorized account/model identity;
- does not explicitly set account/model on bracket or market-close orders; and
- does not persist account/model identity in position, trade, or monitor state.

With one ordinary individual paper account, this may be dormant. In a linked,
advisor, family, or model-enabled session, callback order can choose sizing
capital and position direction without telling the caller which account supplied
the result.

The sanitized archive correctly contains no account identifiers, so the
repository cannot determine whether this condition existed historically. This
study uses only synthetic labels and never reads credentials or unsanitized
account data.

## Reproduce

```bash
venv/bin/python tools/overnight_gap_risk_study.py \
  --selfcheck --json /tmp/gap_program_study61.json
```

The audit hashes and reads repository source plus sanitized artifacts. It does
not import `live.*`, contact Gateway, inspect credentials/account IDs, submit an
order, or modify a protected path.

## Current identity chain

### Account summary

The effective selection is:

```text
for every summary row:
    if tag is NetLiquidation / TotalCashValue / BuyingPower:
        values[tag] = float(value)
```

The dictionary key is only `tag`. `item.account` and `item.currency` are not
checked. Therefore the last callback row for each tag wins.

IBKR's account-summary callback includes account and currency explicitly
([official callback reference](https://interactivebrokers.github.io/tws-api/interfaceIBApi_1_1EWrapper.html)).
For account/model-specific subscriptions, IBKR provides APIs whose result also
includes account and model code
([official multi-account update documentation](https://interactivebrokers.github.io/tws-api/account_updates.html)).

### Position reconciliation

The effective selection is:

```text
for every broker position:
    if position.contract.symbol == requested symbol:
        return the first row
```

The returned object has quantity, average cost, and derived market value—but no
account, model, or contract identity. IBKR's position callback includes the
account, while `positionMulti` includes both account and model
([official callback reference](https://interactivebrokers.github.io/tws-api/interfaceIBApi_1_1EWrapper.html)).

### Order destination

The bracket helper constructs parent/children and the force-close helper
constructs a market order, but neither assigns account or model. IBKR documents
explicit account/model fields for model portfolio orders
([official model-portfolio documentation](https://interactivebrokers.github.io/tws-api/model_portfolios.html)).

The actual default destination may be unambiguous in a single-account session.
The code does not prove or persist that precondition.

## Deterministic sizing-order counterexample

Use synthetic accounts:

| synthetic account | net liquidation | 10% plan at $100 |
|---|---:|---:|
| account_A | $100,000 | 100 shares |
| account_B | $1,000,000 | 1,000 shares |

Current last-row-per-tag behavior yields:

| callback order | selected equity | selected quantity |
|---|---:|---:|
| B then A | $100,000 | 100 |
| A then B | $1,000,000 | 1,000 |

The economic inputs are identical; only callback order changes. If an unscoped
order were routed to account_A while B's value won, the requested $100,000
notional would equal **100% of account_A**, not the intended 10%—a 10× quantity
multiple.

This is conditional arithmetic. It is not a statement about the user's current
capital, account count, or Gateway routing.

Tag-level overwriting can also combine metrics from different accounts if
callback ordering interleaves, e.g. equity from one account and buying power
from another. The current trader sizes from equity only, but the returned
`AccountSnapshot` is not a coherent identified account object.

## Deterministic position-order counterexample

Use the same TQQQ contract in two synthetic accounts:

| callback row | account | TQQQ quantity |
|---:|---|---:|
| 1 | account_A | +100 |
| 2 | account_B | −40 |

The current result is:

| row order | returned quantity | returned direction |
|---|---:|---|
| A then B | +100 | long |
| B then A | −40 | short |

The same holdings can appear as long 100 or short 40 solely from callback order.
The caller receives no account identity with which to detect the ambiguity.

Consequences depend on context:

- a local position may be treated as still open because another account holds
  the same symbol;
- a real exit in the intended account may not be reconciled;
- a desync guard may block because of an unrelated account;
- direction/quantity diagnostics can describe the wrong account; and
- sizing capital and order destination may not belong to the same account.

The current force-close path does not use the broker quantity to size its order
(Study 58), but an account-scoped repair cannot safely use it until identity is
fixed first.

## Archive observability and privacy

The audit inspects only sanitized:

- monitor events;
- trades;
- position snapshot;
- account snapshot; and
- metadata.

It finds no account/model/contract/permanent-ID fields. That is appropriate:
AGENTS.md prohibits committing account IDs. A safe future schema should use a
nonreversible, installation-scoped pseudonym or role label and keep the real
account code outside source control.

Absence from the sanitized archive means:

- current number of Gateway-managed accounts: unknown;
- historical account/model ambiguity: unidentified;
- current order destination: not proven by repository evidence.

It does not mean the Gateway was single-account.

## Existing test boundary

The tests cover:

- one matching position row;
- no matching position;
- one value for each summary tag; and
- downstream desync blocking.

They do not permute:

- two accounts with different equity;
- opposite TQQQ positions across accounts;
- account-summary callback ordering;
- currencies or segment totals;
- model-specific positions;
- explicit order destination; or
- end-to-end state/execution account identity.

## Falsification / repair gate

Before any protected-path change:

1. define one authorized **paper** account and optional model outside source
   control;
2. on connection, enumerate managed accounts and fail closed unless the
   authorized identity is present and the routing policy is unambiguous;
3. filter account values by account, currency, and model, rejecting duplicate or
   missing tags instead of accepting callback order;
4. filter positions by account/model and qualified contract identity; aggregate
   only if aggregation is the declared policy;
5. explicitly set account/model on parent, both children, and forced closes;
6. propagate a safe pseudonymous scope through intent, lifecycle, execution,
   local state, events, and exports; and
7. test callback-order permutations, opposite positions, and the 10× equity
   difference deterministically.

## Limits

- This is a conditional multi-account safety finding, not a claim that the
  current login exposes multiple accounts.
- The study intentionally avoids `.env`, Gateway UI state, credentials, real
  account IDs, and raw operational databases.
- Synthetic account labels and capital values are illustrative only.

## Decision

Make account/model identity a required end-to-end lifecycle field before using
broker quantities for reconciliation or claiming 10% sizing. Fail closed on
ambiguous account-summary or position rows; do not let callback order decide
capital, direction, or destination.
