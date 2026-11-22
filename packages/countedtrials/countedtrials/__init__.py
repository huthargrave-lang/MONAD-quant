"""
countedtrials — a tamper-evident ledger of every backtest you ran, and statistics
deflated by what it counted.

Extracted from MONAD Quant (https://github.com/huthargrave-lang/MONAD-quant), where it
has recorded every research attempt since 2026-09. See README.md.
"""
from countedtrials import analysis, ledger, significance
from countedtrials.analysis import (FamilyDeflation, FamilyReport, FamilySPA, best_trial, deflate,
                                    family_pbo, family_sharpes, family_spa, report)
from countedtrials.guard import UncountedEvaluationError, evaluator, uncounted
from countedtrials.ledger import (LedgerError, family_counts, iter_trials, load_returns,
                                  open_process_run, open_run, seal, verify_append_only,
                                  verify_ledger, verify_shard)
from countedtrials.study import Study, TrialResult, expand_grid

__version__ = "0.1.0"

__all__ = [
    "Study", "TrialResult", "expand_grid",
    "evaluator", "uncounted", "UncountedEvaluationError",
    "open_run", "open_process_run", "LedgerError",
    "verify_ledger", "verify_shard", "verify_append_only", "seal",
    "family_counts", "iter_trials", "load_returns",
    "deflate", "report", "best_trial", "family_sharpes", "family_pbo", "family_spa",
    "FamilyDeflation", "FamilyReport", "FamilySPA",
    "analysis", "ledger", "significance",
]
