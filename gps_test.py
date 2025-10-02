#!/usr/bin/env python3
import os
import sys
import time
import glob
import argparse
import serial
import pynmea2
from serial.tools import list_ports


def find_gps_ports_cross_platform():
    """Return a prioritized list of candidate GPS ports across Windows/macOS/Linux.

    For Linux/Raspberry Pi, prefer stable paths under /dev/serial/by-id/ first,
    then /dev/ttyACM* and /dev/ttyUSB* which are typical for USB GPS receivers.
    """
    candidates = []

    # Prefer explicit USB serial devices that look like GPS on all platforms
    try:
        for port in list_ports.comports():
            desc = (port.description or "").upper()
            hwid = (port.hwid or "").upper()

            # Skip Bluetooth/virtual devices
            if any(skip in desc for skip in ["BLUETOOTH", "BT", "WIRELESS"]):
                continue

            # BU-353N5 is a GlobalSat device that uses a u-blox chipset and presents
            # as a USB serial device. Common identifiers include: GLOBALSAT, BU-353N5, UBLOX, GPS
            if any(tag in desc for tag in ["BU-353N5", "GLOBALSAT", "UBLOX", "GPS"]) or (
                "UBLOX" in hwid or "GPS" in hwid
            ):
                candidates.append(port.device)

            # Generic USB serial might also be the GPS
            elif "USB" in desc and "SERIAL" in desc:
                candidates.append(port.device)
    except Exception:
        pass

    # Fallbacks by OS
    if sys.platform.startswith("win"):
        # On Windows, if nothing was found, try common COM range
        if not candidates:
            for i in range(3, 21):
                candidates.append(f"COM{i}")
    else:
        # Linux/macOS device patterns (ordered by stability/likelihood)
        for pattern in [
            "/dev/serial/by-id/*",  # best, persistent symlink that often includes device model
            "/dev/ttyACM*",         # many u-blox show up as ACM
            "/dev/ttyUSB*",         # USB-to-serial bridge
            "/dev/tty.SLAB_USBtoUART*",  # macOS SiLabs
            "/dev/tty.usbserial*",       # macOS FTDI/Prolific
        ]:
            matches = glob.glob(pattern)
            for m in matches:
                if m not in candidates:
                    candidates.append(m)

    # Deduplicate while preserving order
    seen = set()
    uniq = []
    for c in candidates:
        if c not in seen:
            uniq.append(c)
            seen.add(c)
    return uniq


def try_read_gps(port, baudrates=(4800, 9600), read_seconds=12):
    """Try opening a port at common GPS baudrates and read NMEA sentences."""
    last_error = None
    for baud in baudrates:
        try:
            print(f"Trying {port} at {baud} baud...")
            with serial.Serial(port=port, baudrate=baud, timeout=1) as ser:
                start = time.time()
                nmea_count = 0
                got_fix_info = False

                while time.time() - start < read_seconds:
                    try:
                        line = ser.readline().decode("ascii", errors="replace").strip()
                        if not line or not line.startswith("$"):
                            continue

                        nmea_count += 1

                        if line.startswith(("$GPGGA", "$GNGGA")):
                            msg = pynmea2.parse(line)
                            print("GGA:", f"time={msg.timestamp}", f"sats={msg.num_sats}", f"qual={msg.gps_qual}")
                            if msg.gps_qual and int(msg.gps_qual) > 0:
                                print(
                                    f"Position: {msg.latitude}° {msg.lat_dir}, {msg.longitude}° {msg.lon_dir}"
                                )
                                got_fix_info = True

                        elif line.startswith(("$GPRMC", "$GNRMC")):
                            msg = pynmea2.parse(line)
                            print(
                                "RMC:",
                                f"time={msg.timestamp}",
                                f"status={msg.status}",
                                f"lat={msg.latitude}{msg.lat_dir}",
                                f"lon={msg.longitude}{msg.lon_dir}",
                            )
                            got_fix_info = True

                        # Print a small sample then stop early if healthy traffic
                        if nmea_count >= 10 and got_fix_info:
                            print("Healthy NMEA stream detected.")
                            return True
                    except (pynmea2.ParseError, UnicodeDecodeError, ValueError):
                        # Ignore malformed lines and continue reading
                        continue

                if nmea_count > 0:
                    print(f"Received {nmea_count} NMEA sentences at {baud} baud.")
                    return True
        except Exception as e:
            last_error = e
            continue

    if last_error:
        print(f"Last error while trying {port}: {last_error}")
    return False


def linux_permissions_help():
    print("Permissions help (Linux/Raspberry Pi):")
    print("- Ensure your user is in the 'dialout' (or 'uucp' on some distros) group")
    print("  sudo usermod -aG dialout $USER && newgrp dialout")
    print("- Or temporarily: sudo chmod a+rw /dev/ttyACM0 (adjust device path)")
    print("- Prefer stable path under /dev/serial/by-id/ if available")


def test_bu353n5(selected_port=None, selected_baud=None, list_only=False, read_seconds=12):
    print("Testing GlobalSat BU-353N5 / u-blox USB GPS on Linux/Raspberry Pi...")

    ports = find_gps_ports_cross_platform()

    if list_only:
        print("Discovered ports:")
        for p in ports:
            print(" -", p)
        return True

    # Allow env overrides
    env_port = os.getenv("GPS_PORT")
    env_baud = os.getenv("GPS_BAUD")
    if selected_port is None and env_port:
        selected_port = env_port
    if selected_baud is None and env_baud:
        try:
            selected_baud = int(env_baud)
        except ValueError:
            pass

    if selected_port:
        ports = [selected_port] + [p for p in ports if p != selected_port]

    if not ports:
        print("No candidate GPS ports found.")
        print("- On Raspberry Pi/Linux, check /dev/tty* and /dev/serial/by-id/*")
        linux_permissions_help()
        return False

    print("Candidate ports:")
    for p in ports:
        print(" -", p)

    baudrates = (selected_baud,) if selected_baud else (4800, 9600)
    print("Baudrates to try:", baudrates)

    for port in ports:
        ok = try_read_gps(port, baudrates=baudrates, read_seconds=read_seconds)
        if ok:
            print(f"\nGPS appears to be working on: {port}")
            print("If this is your BU-353N5, you're good to go.")
            return True

    print("\nUnable to read GPS data from any candidate ports.")
    print("Troubleshooting:")
    print("1) Unplug and replug the receiver, then re-run this test")
    print("2) Close any other app using the serial device (e.g., gpsd, mapping tools)")
    print("3) Confirm the device path, e.g., ls -l /dev/serial/by-id/")
    print("4) Set GPS_PORT=/dev/ttyACM0 and optionally GPS_BAUD=4800, then rerun")
    linux_permissions_help()
    return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test GlobalSat BU-353N5 / u-blox USB GPS on Linux/Raspberry Pi")
    parser.add_argument("--port", help="Serial device path (e.g., /dev/ttyACM0)")
    parser.add_argument("--baud", type=int, help="Baud rate to force (e.g., 4800 or 9600)")
    parser.add_argument("--list", action="store_true", help="List detected candidate ports and exit")
    parser.add_argument("--read-seconds", type=int, default=12, help="Seconds to read before deciding")
    args = parser.parse_args()

    test_bu353n5(selected_port=args.port, selected_baud=args.baud, list_only=args.list, read_seconds=args.read_seconds)