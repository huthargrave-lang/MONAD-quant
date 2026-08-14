"""Run `sweep.py` from the research UI, as a job, without ever letting it arm the trader.

WHY THIS EXISTS AS ITS OWN MODULE
---------------------------------
The research UI serves pages. Sweeping is a backtest over a parameter grid that takes tens of
seconds and writes files, and none of that belongs inside a request handler. Keeping it here
means the safety rules below are stated once, in one place, and are testable without binding a
socket or rendering a page.

THE SAFETY BOUNDARY, WHICH IS THE POINT OF THE MODULE
-----------------------------------------------------
`sweep.py --apply` REWRITES `config.py`, and `config.py` is on the manifest's deny list as an
armed-trader path: changing it needs the trader stopped and explicit approval. A web button
that could reach that flag would be a remote control for the live strategy's parameters.

So this runner:

  * never constructs `--apply`, and a test asserts the flag appears nowhere in the argv it
    builds, for any input;
  * runs with **stdin closed**. Without `--apply` sweep.py still asks
    `Apply best_overall params to config.py? [y/N]` on the terminal, and only a caught
    `EOFError` turns that into "n" (sweep.py:1702-1708). Closing stdin is what makes the EOF
    certain rather than incidental;
  * takes the ticker through a strict pattern rather than interpolating a query string into an
    argument list, and never uses a shell.

Together those mean the worst a UI visitor can do is spend CPU and overwrite a regenerable
`sweep_results_<TICKER>.json`.

THE INTERPRETER PROBLEM
-----------------------
The UI is usually started with `venv/bin/python`, and on this machine that venv is **Python
3.9.6** while `src/strategy/sizing.py` uses `dict | None`, which parses only on 3.10+. Under
the venv, importing the strategy engine raises `TypeError` before a single bar is read — the
same cause behind 30 of the errors in a full local test run. CI runs 3.11 and is unaffected.

A button that shells out to `sys.executable` would therefore fail on this machine every time,
and the page would be offering work it cannot do. `find_interpreter()` probes instead, and
`availability()` reports what it found so the page can say plainly that the engine cannot be
run here rather than rendering a control that always errors.
"""
import json
import os
import re
import subprocess
import sys
import threading
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SWEEP = os.path.join(REPO, "sweep.py")

#: Tickers are pasted from a URL. Anything that is not this shape never becomes an argument.
#: `=F` is here because the cached universe includes futures symbols like `GC=F`.
TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}(=F)?$")

#: The phases sweep.py itself accepts (`--phase`). Restated as a closed set so an unknown value
#: is refused here rather than becoming an argparse error inside a subprocess nobody is reading.
PHASES = ("1", "2", "all", "exit-tuning")

#: A sweep that has not finished in this long is treated as wedged and killed. Phase 1 over a
#: cached ticker measured 38.6s on this machine; `all` is a multiple of that. The ceiling
#: exists so a hung fetch cannot hold a worker thread for the life of the server.
TIMEOUT_S = 900

#: The import that fails on an interpreter too old for the engine. Probing with the real module
#: rather than a version number means the check keeps working if the syntax floor moves.
_PROBE = "import src.strategy.sizing"

_jobs = {}
_lock = threading.Lock()


def find_interpreter():
    """The first interpreter that can import the strategy engine, or None.

    `sys.executable` is tried first so a correctly-provisioned environment uses itself and
    nothing is guessed. The rest are the usual places a newer Python lives on a machine whose
    venv is old.
    """
    candidates = [sys.executable,
                  os.path.join(REPO, "venv", "bin", "python"),
                  "python3.13", "python3.12", "python3.11", "python3"]
    seen = set()
    for exe in candidates:
        if not exe or exe in seen:
            continue
        seen.add(exe)
        try:
            proc = subprocess.run([exe, "-c", _PROBE], cwd=REPO, timeout=60,
                                  stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except (OSError, subprocess.SubprocessError):
            continue
        if proc.returncode == 0:
            return exe
    return None


def availability():
    """What the page needs to decide between offering a run and explaining why it cannot.

    Returns the interpreter, whether it is the one running this process, and the reason when
    there is none — so the surface states a fact rather than rendering a dead button.
    """
    exe = find_interpreter()
    return {
        "runnable": exe is not None,
        "interpreter": exe,
        "is_current_process": bool(exe) and os.path.realpath(exe) == os.path.realpath(sys.executable),
        "current_process": sys.executable,
        "current_version": "%d.%d.%d" % sys.version_info[:3],
        "why_not": None if exe else (
            "no interpreter on this machine can import the strategy engine. The engine needs "
            "Python 3.10 or newer (src/strategy/sizing.py annotates with `dict | None`), and "
            "this process is running %d.%d.%d." % sys.version_info[:3]),
    }


def build_argv(interpreter, ticker, phase="1", mode="realistic"):
    """The exact argument list a job runs, split out so a test can inspect it without running.

    The `--apply` flag is not conditional here and is not passed through from anywhere: it is
    absent by construction, which is what makes "the UI cannot arm the trader" checkable rather
    than asserted.
    """
    if not TICKER_RE.match(ticker or ""):
        raise ValueError("not a ticker: %r" % (ticker,))
    if phase not in PHASES:
        raise ValueError("not a phase: %r" % (phase,))
    if mode not in ("optimistic", "realistic", "harsh"):
        raise ValueError("not a mode: %r" % (mode,))
    return [interpreter, SWEEP, ticker, "--phase", phase, "--mode", mode]


def results_path(ticker):
    return os.path.join(REPO, "sweep_results_%s.json" % ticker)


def _run(job_id, argv, ticker):
    job = _jobs[job_id]
    started = time.time()
    try:
        proc = subprocess.run(
            argv, cwd=REPO, timeout=TIMEOUT_S,
            # Closed, not inherited. This is what turns sweep.py's config.py prompt into a
            # caught EOFError rather than a process waiting forever on a terminal that is not
            # there — see the module docstring.
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        out, code = proc.stdout, proc.returncode
    except subprocess.TimeoutExpired:
        out, code = "", -1
        with _lock:
            job.update(state="timeout", seconds=round(time.time() - started, 1),
                       error="the sweep did not finish within %ds and was stopped" % TIMEOUT_S)
        return
    except OSError as exc:
        with _lock:
            job.update(state="error", seconds=round(time.time() - started, 1),
                       error="could not start the sweep: %s" % exc)
        return

    payload, read_error = None, None
    path = results_path(ticker)
    if code == 0:
        try:
            with open(path, encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, ValueError) as exc:
            read_error = "the sweep reported success but its results file could not be read: %s" % exc

    with _lock:
        job.update(
            state="done" if (code == 0 and payload is not None) else "error",
            seconds=round(time.time() - started, 1),
            returncode=code,
            # Kept whole. A sweep that fails is diagnosed from what it printed, and truncating
            # to a tidy summary is how the actual cause gets thrown away.
            log=out,
            results=payload,
            error=read_error or (None if code == 0 else
                                 "the sweep exited %s — see the log below" % code),
        )


def start(ticker, phase="1", mode="realistic", interpreter=None):
    """Launch a sweep in the background. Returns the job id.

    Raises ValueError on a bad ticker/phase/mode and RuntimeError when no interpreter on this
    machine can run the engine — both before anything is spawned.
    """
    exe = interpreter or find_interpreter()
    if exe is None:
        raise RuntimeError(availability()["why_not"])
    argv = build_argv(exe, ticker, phase, mode)
    job_id = "%s-%s-%d" % (ticker, phase, int(time.time() * 1000))
    with _lock:
        _jobs[job_id] = {"id": job_id, "ticker": ticker, "phase": phase, "mode": mode,
                         "state": "running", "started_at": time.time(),
                         "interpreter": exe, "log": "", "results": None, "error": None}
    threading.Thread(target=_run, args=(job_id, argv, ticker), daemon=True).start()
    return job_id


def status(job_id):
    """A snapshot of one job, or None. Copied under the lock so a caller cannot observe a job
    mid-update and render half of one state and half of another."""
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def jobs():
    with _lock:
        return [dict(j) for j in _jobs.values()]


def reset():
    """Drop every job. For tests — a module-level registry that persists between them turns one
    test's leftovers into another test's passing assertion."""
    with _lock:
        _jobs.clear()
