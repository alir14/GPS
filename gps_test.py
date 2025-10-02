#!/usr/bin/env python3
import serial
import pynmea2
import time
import glob
import os

def find_gps_port():
    """Find the USB port for the u-blox GPS receiver"""
    patterns = [
        '/dev/ttyACM*',  # Common for u-blox devices
        '/dev/ttyUSB*',  # For USB-to-Serial devices
        '/dev/serial/by-id/*u-blox*'  # Specific u-blox pattern
    ]
    
    for pattern in patterns:
        ports = glob.glob(pattern)
        if ports:
            return ports[0]
    return None

def test_gps():
    print("Testing u-blox GPS connection...")
    
    # Find GPS port
    port = find_gps_port()
    if not port:
        print("\nError: GPS device not found!")
        print("Available USB devices:")
        os.system('ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null')
        print("\nTroubleshooting steps:")
        print("1. Check USB connection")
        print("2. Run 'dmesg | grep tty' to see USB device recognition")
        print("3. Check permissions with 'ls -l' on the device file")
        return False
    
    try:
        print(f"\nFound GPS device at: {port}")
        
        # Check permissions
        if not os.access(port, os.R_OK | os.W_OK):
            print(f"\nPermission denied for {port}")
            print(f"Try running: sudo chmod a+rw {port}")
            return False
            
        # Try to connect and read data
        print("Attempting to read GPS data...")
        ser = serial.Serial(
            port=port,
            baudrate=9600,  # u-blox typical baudrate
            timeout=1
        )
        
        start_time = time.time()
        nmea_count = 0
        valid_fix = False
        
        while time.time() - start_time < 10:  # Try for 10 seconds
            try:
                line = ser.readline().decode('ascii', errors='replace').strip()
                
                if line.startswith('$'):
                    nmea_count += 1
                    
                    if line.startswith('$GNGGA') or line.startswith('$GPGGA'):
                        msg = pynmea2.parse(line)
                        print(f"\nReceived NMEA data:")
                        print(f"Timestamp: {msg.timestamp}")
                        print(f"Fix Quality: {msg.gps_qual}")
                        print(f"Satellites: {msg.num_sats}")
                        
                        if msg.gps_qual > 0:
                            valid_fix = True
                            print(f"Position: {msg.latitude}° {msg.lat_dir}, {msg.longitude}° {msg.lon_dir}")
                            break
                        
            except pynmea2.ParseError:
                continue
            except UnicodeDecodeError:
                continue
                
        ser.close()
        
        print(f"\nNMEA sentences received: {nmea_count}")
        if nmea_count > 0:
            print("GPS is connected and sending data!")
            if valid_fix:
                print("GPS has a valid position fix!")
            else:
                print("Waiting for GPS fix - this is normal if device just started")
            return True
        else:
            print("No GPS data received - check device configuration")
            return False
            
    except serial.SerialException as e:
        print(f"\nError accessing GPS: {str(e)}")
        print("Troubleshooting:")
        print("1. Check if device is properly powered")
        print("2. Try unplugging and replugging the device")
        print("3. Check if device appears in 'dmesg' output")
        return False
        
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")
        return False

if __name__ == "__main__":
    test_gps()