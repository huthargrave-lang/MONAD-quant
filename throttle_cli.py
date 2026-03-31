#!/usr/bin/env python3
"""
throttle_cli.py – CLI RC/throttle tester using yamspy (MSP).

Adapted from the web UI controller to preserve:
- Preferred serial port discovery order
- Arming/disarming gesture support
- Continuous RC streaming loop
"""

import argparse
import atexit
import glob
import os
import sys
import threading
import time

import yamspy

# Prefer USB first for setup/debug, then common UARTs
PREFS = [
    "/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyUSB0", "/dev/ttyUSB1",
    "/dev/serial0", "/dev/ttyAMA10", "/dev/ttyAMA0", "/dev/ttyS0",
]

ARMING_FLAG_NAMES = [
    "NO_GYRO", "FAILSAFE", "RX_FAILSAFE", "NOT_DISARMED",
    "BOXFAILSAFE", "RUNAWAY_TAKEOFF", "CRASH_DETECTED", "THROTTLE",
    "ANGLE", "BOOT_GRACE_TIME", "NOPREARM", "LOAD",
    "CALIBRATING", "CLI", "CMS_MENU", "BST",
    "MSP", "PARALYZE", "GPS", "RESC",
    "DSHOT_TELEM", "REBOOT_REQUIRED", "DSHOT_BITBANG", "ACC_CALIBRATION",
    "MOTOR_PROTOCOL", "CRASHFLIP", "ALTHOLD", "POSHOLD", "ARM_SWITCH",
]


def list_ports():
    usb = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
    uart = sorted(glob.glob("/dev/serial*") + glob.glob("/dev/ttyAMA*") + glob.glob("/dev/ttyS*"))
    ports = usb + [p for p in uart if p not in usb]

    out, seen = [], set()
    for p in PREFS + ports:
        if os.path.exists(p) and p not in seen:
            seen.add(p)
            out.append(p)
    return out


class FCState:
    def __init__(self, rate_hz=20, max_throttle=1500):
        self.lock = threading.Lock()
        self.fc = None
        self.connected = False
        self.streaming = False
        self.stop_event = threading.Event()
        self.rate_hz = max(1, min(200, int(rate_hz)))
        self.period = max(0.01, 1.0 / self.rate_hz)
        self.max_throttle = max(1000, min(2000, int(max_throttle)))
        # [roll, pitch, throttle, yaw, aux1..aux4]
        self.current_rc = [1500, 1500, 1000, 1500, 1000, 1000, 1000, 1000]

    def connect(self, port):
        try:
            if self.fc:
                self.disconnect()
            self.fc = yamspy.MSPy(device=port)
            ok = self.fc.connect()
            self.connected = bool(ok and self.check_connected())
            if self.connected:
                self.start_stream()
            return self.connected, None
        except Exception as exc:
            self.connected = False
            self.fc = None
            return False, str(exc)

    def disconnect(self):
        self.stop_stream()
        try:
            if self.fc:
                if hasattr(self.fc, "disconnect"):
                    self.fc.disconnect()
                elif hasattr(self.fc, "close"):
                    self.fc.close()
        except Exception:
            pass
        self.fc = None
        self.connected = False

    def check_connected(self):
        if self.fc is None:
            self.connected = False
            return False
        try:
            st = self.fc.get_status()
            self.connected = isinstance(st, dict)
            return self.connected
        except Exception:
            self.connected = False
            return False

    def status(self):
        if self.fc is None:
            return {"connected": False}
        try:
            st = self.fc.get_status()
            flags = st.get("armingDisableFlags", 0)
            active = [name for bit, name in enumerate(ARMING_FLAG_NAMES) if flags & (1 << bit)]
            return {
                "connected": True,
                "flags": flags,
                "arming_ok": flags == 0,
                "flag_names": active,
                "rc": list(self.current_rc[:8]),
            }
        except Exception:
            return {"connected": True, "flags": 9999, "arming_ok": False, "flag_names": ["STATUS_ERROR"]}

    def start_stream(self):
        if self.streaming:
            return
        self.stop_event.clear()
        self.streaming = True
        threading.Thread(target=self._stream_loop, daemon=True).start()

    def stop_stream(self):
        self.stop_event.set()
        self.streaming = False

    def _stream_loop(self):
        while not self.stop_event.is_set() and self.fc is not None:
            try:
                with self.lock:
                    pkt = list(self.current_rc) + [1000] * (8 - len(self.current_rc))
                self.fc.send_RAW_RC(pkt)
            except Exception:
                pass
            time.sleep(self.period)
        self.streaming = False

    def set_throttle_pct(self, pct):
        pct = max(0, min(100, int(pct)))
        us = 1000 + pct * 10
        us = min(us, self.max_throttle)
        with self.lock:
            self.current_rc[2] = us
        return us

    def set_rc(self, roll=None, pitch=None, thr=None, yaw=None, aux1=None):
        def clamp(v, d):
            if v is None:
                return d
            try:
                return max(1000, min(2000, int(v)))
            except Exception:
                return d

        with self.lock:
            self.current_rc[0] = clamp(roll, self.current_rc[0])
            self.current_rc[1] = clamp(pitch, self.current_rc[1])
            self.current_rc[2] = clamp(thr, self.current_rc[2])
            self.current_rc[3] = clamp(yaw, self.current_rc[3])
            self.current_rc[4] = clamp(aux1, self.current_rc[4])
            return list(self.current_rc[:8])

    def arm_gesture(self):
        if not self.check_connected():
            return False
        t_end = time.time() + 1.2
        while time.time() < t_end:
            self.fc.send_RAW_RC([1500, 1500, 1000, 2000, 1000, 1000, 1000, 1000])
            time.sleep(0.05)
        self.fc.send_RAW_RC([1500, 1500, 1000, 1500, 1000, 1000, 1000, 1000])
        return True

    def disarm_gesture(self):
        if not self.check_connected():
            return False
        t_end = time.time() + 1.2
        while time.time() < t_end:
            self.fc.send_RAW_RC([1500, 1500, 1000, 1000, 1000, 1000, 1000, 1000])
            time.sleep(0.05)
        with self.lock:
            self.current_rc[2] = 1000
        self.fc.send_RAW_RC([1500, 1500, 1000, 1500, 1000, 1000, 1000, 1000])
        return True

    def panic(self):
        with self.lock:
            self.current_rc[2] = 1000


def parse_args():
    ap = argparse.ArgumentParser(description="CLI RC/throttle tester (yamspy)")
    ap.add_argument("--port", default=None, help="Serial port; if omitted, auto-pick preferred available port")
    ap.add_argument("--rate", type=int, default=20, help="RC streaming rate in Hz (default: 20)")
    ap.add_argument("--max", type=int, default=1500, dest="max_throttle", help="Throttle safety cap in us (1000-2000)")
    return ap.parse_args()


def print_help():
    print(
        """
Commands:
  ports                 List discovered ports in preference order.
  status | s            Show connection + arming status + RC values.
  arm                   Arm via yaw-right + min-throttle gesture.
  disarm                Disarm via yaw-left + min-throttle gesture.
  set N                 Set throttle percent (0-100).
  +N / -N               Adjust throttle percent.
  rc r p t y a1         Set RC values (1000-2000).
  panic | kill | k      Immediate throttle cut (1000us).
  rate N                Change streaming rate (1-200 Hz).
  max N                 Set throttle cap in us (1000-2000).
  help | h              Show this help.
  quit | q              Disarm, disconnect, exit.
"""
    )


def main():
    args = parse_args()
    ports = list_ports()
    port = args.port or (ports[0] if ports else None)
    if not port:
        print("No serial ports found. Use 'ports' once hardware is connected.")
        sys.exit(1)

    state = FCState(rate_hz=args.rate, max_throttle=args.max_throttle)
    ok, err = state.connect(port)
    if not ok:
        print(f"Failed to connect on {port}: {err}")
        sys.exit(1)

    def cleanup():
        try:
            state.disarm_gesture()
        except Exception:
            pass
        state.disconnect()

    atexit.register(cleanup)

    print("=" * 56)
    print("  FC CLI (yamspy / MSP)")
    print("=" * 56)
    print(f"  Connected:  {port}")
    print(f"  Stream:     {state.rate_hz} Hz")
    print(f"  Max cap:    {state.max_throttle} us")
    print("  Type 'help' for commands.")
    print()

    throttle_pct = 0

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nInterrupted – disarming and exiting.")
            break

        if not line:
            continue

        parts = line.split()
        cmd = parts[0].lower()

        if cmd in ("help", "h"):
            print_help()
        elif cmd == "ports":
            p = list_ports()
            if p:
                print("Ports:", ", ".join(p))
            else:
                print("No ports found.")
        elif cmd in ("status", "s"):
            st = state.status()
            print(st)
        elif cmd == "arm":
            print("ARM sent." if state.arm_gesture() else "Not connected.")
        elif cmd == "disarm":
            print("DISARM sent." if state.disarm_gesture() else "Not connected.")
            throttle_pct = 0
        elif cmd in ("panic", "kill", "k"):
            state.panic()
            print("PANIC CUT: throttle -> 1000us")
        elif cmd == "set" and len(parts) >= 2:
            try:
                throttle_pct = max(0, min(100, int(parts[1])))
                us = state.set_throttle_pct(throttle_pct)
                print(f"Throttle -> {throttle_pct}% ({us}us)")
            except ValueError:
                print("Usage: set <0-100>")
        elif cmd.startswith(("+", "-")):
            try:
                throttle_pct = max(0, min(100, throttle_pct + int(cmd)))
                us = state.set_throttle_pct(throttle_pct)
                print(f"Throttle -> {throttle_pct}% ({us}us)")
            except ValueError:
                print("Usage: +N / -N")
        elif cmd == "rc" and len(parts) >= 6:
            try:
                r, p, t, y, a1 = map(int, parts[1:6])
                rc = state.set_rc(r, p, t, y, a1)
                print(f"RC -> {rc}")
            except ValueError:
                print("Usage: rc <roll> <pitch> <thr> <yaw> <aux1>")
        elif cmd == "rate" and len(parts) >= 2:
            try:
                hz = max(1, min(200, int(parts[1])))
                state.rate_hz = hz
                state.period = max(0.01, 1.0 / hz)
                print(f"Rate -> {hz} Hz")
            except ValueError:
                print("Usage: rate <1-200>")
        elif cmd == "max" and len(parts) >= 2:
            try:
                mx = max(1000, min(2000, int(parts[1])))
                state.max_throttle = mx
                print(f"Max throttle cap -> {mx}us")
            except ValueError:
                print("Usage: max <1000-2000>")
        elif cmd in ("quit", "q"):
            break
        else:
            print("Unknown command. Type 'help'.")

    cleanup()


if __name__ == "__main__":
    main()
