#!/usr/bin/env python3
import serial
import pynmea2
import time
from serial.tools import list_ports
import os
from datetime import datetime
import csv
import json

class GPSDataCapture:
    def __init__(self):
        self.port = None
        self.ser = None
        self.data_dir = "gps_data"
        self.csv_filename = None
        self.create_data_directory()
        
    def create_data_directory(self):
        """Create directory for GPS data files"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            print(f"Created data directory: {self.data_dir}")
    
    def find_gps_port(self):
        """Find the COM port for the BU-353N5 GPS receiver"""
        ports = list_ports.comports()
        print("Available COM ports:")
        gps_ports = []
        
        for port in ports:
            print(f" - {port.device}: {port.description}")
            # Look for specific GPS device identifiers
            description_upper = port.description.upper()
            
            # Skip Bluetooth and non-USB devices
            if any(skip_keyword in description_upper for skip_keyword in ['BLUETOOTH', 'BT', 'WIRELESS']):
                continue
                
            # Look for GPS-specific identifiers
            if any(gps_keyword in description_upper for gps_keyword in ['BU-353N5', 'GLOBALSAT', 'GPS', 'UBLOX']):
                gps_ports.append(port.device)
            # Also check for USB Serial devices that might be GPS
            elif 'USB' in description_upper and 'SERIAL' in description_upper:
                gps_ports.append(port.device)
        
        if gps_ports:
            print(f"\nPotential GPS devices found: {gps_ports}")
            return gps_ports[0]  # Return the first GPS device found
        
        print("\nNo GPS devices detected. Available USB devices:")
        for port in ports:
            if 'USB' in port.description.upper():
                print(f" - {port.device}: {port.description}")
        
        return None
    
    def connect_gps(self):
        """Connect to GPS device"""
        self.port = self.find_gps_port()
        if not self.port:
            print("Error: BU-353N5 GPS device not found!")
            
            # Offer manual port selection
            print("\nWould you like to try a specific COM port?")
            manual_port = input("Enter COM port (e.g., COM3) or press Enter to skip: ").strip()
            if manual_port:
                self.port = manual_port
                print(f"Trying manual port: {self.port}")
            else:
                return False
        
        try:
            print(f"Connecting to GPS on {self.port}...")
            self.ser = serial.Serial(
                port=self.port,
                baudrate=4800,  # BU-353N5 typical baudrate
                timeout=1,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            print("GPS connected successfully!")
            return True
        except serial.SerialException as e:
            print(f"Error connecting to GPS: {e}")
            return False
    
    def get_direction(self, degrees):
        """Convert degrees to cardinal direction"""
        if degrees is None:
            return None
        
        directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                     'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
        index = round(degrees / 22.5) % 16
        return directions[index]
    
    def parse_gps_data(self, line):
        """Parse NMEA data and return user-friendly format"""
        try:
            if line.startswith('$GPRMC') or line.startswith('$GNRMC'):
                msg = pynmea2.parse(line)
                speed_knots = msg.spd_over_grnd
                speed_kmh = float(speed_knots) * 1.852 if speed_knots else None
                speed_mph = float(speed_knots) * 1.15078 if speed_knots else None
                
                return {
                    'timestamp': msg.timestamp.isoformat() if msg.timestamp else None,
                    'latitude': msg.latitude,
                    'longitude': msg.longitude,
                    'lat_dir': msg.lat_dir,
                    'lon_dir': msg.lon_dir,
                    'speed_knots': speed_knots,
                    'speed_kmh': speed_kmh,
                    'speed_mph': speed_mph,
                    'course': msg.true_course,
                    'course_direction': self.get_direction(msg.true_course) if msg.true_course else None,
                    'date': msg.datestamp.isoformat() if msg.datestamp else None,
                    'status': msg.status,
                    'type': 'RMC'
                }
            elif line.startswith('$GPGGA') or line.startswith('$GNGGA'):
                msg = pynmea2.parse(line)
                return {
                    'timestamp': msg.timestamp.isoformat() if msg.timestamp else None,
                    'latitude': msg.latitude,
                    'longitude': msg.longitude,
                    'lat_dir': msg.lat_dir,
                    'lon_dir': msg.lon_dir,
                    'altitude': msg.altitude,
                    'altitude_units': msg.altitude_units,
                    'satellites': msg.num_sats,
                    'fix_quality': msg.gps_qual,
                    'hdop': msg.horizontal_dil,
                    'type': 'GGA'
                }
            elif line.startswith('$GPVTG') or line.startswith('$GNVTG'):
                msg = pynmea2.parse(line)
                return {
                    'course_true': msg.true_track,
                    'course_magnetic': msg.mag_track,
                    'speed_knots_vtg': msg.spd_over_grnd_kts,
                    'speed_kmh_vtg': msg.spd_over_grnd_kmph,
                    'type': 'VTG'
                }
            elif line.startswith('$GPGSV') or line.startswith('$GNGSV'):
                msg = pynmea2.parse(line)
                return {
                    'satellites_in_view': msg.num_sv_in_view,
                    'type': 'GSV'
                }
        except pynmea2.ParseError:
            return None
        return None
    
    def save_to_csv(self, data):
        """Save GPS data to single CSV file"""
        if not self.csv_filename:
            # Create filename with current date
            timestamp = datetime.now().strftime("%Y%m%d")
            self.csv_filename = f"gps_data_{timestamp}.csv"
        
        filepath = os.path.join(self.data_dir, self.csv_filename)
        
        # Check if file exists to write headers
        file_exists = os.path.exists(filepath)
        
        with open(filepath, 'a', newline='', encoding='utf-8') as csvfile:
            fieldnames = list(data.keys())
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
            
            writer.writerow(data)
        
        return filepath
    
    def save_to_json(self, data):
        """Save GPS data to single JSON file"""
        json_filename = f"gps_data_{datetime.now().strftime('%Y%m%d')}.json"
        filepath = os.path.join(self.data_dir, json_filename)
        
        # Load existing data or create new list
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                try:
                    existing_data = json.load(f)
                except json.JSONDecodeError:
                    existing_data = []
        else:
            existing_data = []
        
        # Add timestamp to data
        data['recorded_at'] = datetime.now().isoformat()
        existing_data.append(data)
        
        # Save updated data
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def capture_data(self, duration_minutes=5, save_interval_seconds=5, save_json=True):
        """Capture GPS data for specified duration"""
        if not self.connect_gps():
            return
        
        print(f"\nStarting GPS data capture for {duration_minutes} minutes...")
        print(f"Data will be saved every {save_interval_seconds} seconds")
        print("Press Ctrl+C to stop early\n")
        
        start_time = time.time()
        last_save_time = start_time
        data_count = 0
        
        try:
            while time.time() - start_time < (duration_minutes * 60):
                try:
                    line = self.ser.readline().decode('ascii', errors='replace').strip()
                    
                    if line.startswith('$'):
                        data = self.parse_gps_data(line)
                        
                        if data:
                            current_time = time.time()
                            
                            # Print current data
                            if data.get('type') == 'RMC' and data.get('latitude'):
                                print(f"\nGPS Fix: {data['latitude']:.6f}° {data['lat_dir']}, "
                                      f"{data['longitude']:.6f}° {data['lon_dir']}")
                                if data.get('speed_kmh'):
                                    print(f"   Speed: {data['speed_kmh']:.1f} km/h ("
                                          f"{data['speed_mph']:.1f} mph, {data['speed_knots']:.1f} knots)")
                                if data.get('course'):
                                    print(f"   Course: {data['course']:.1f}° {data.get('course_direction', '')}")
                                print(f"   Time: {data.get('timestamp', 'N/A')}")
                            
                            # Save data periodically
                            if current_time - last_save_time >= save_interval_seconds:
                                csv_file = self.save_to_csv(data)
                                if save_json:
                                    json_file = self.save_to_json(data)
                                data_count += 1
                                last_save_time = current_time
                                
                                print(f"   Saved data #{data_count} to {self.csv_filename}")
                
                except KeyboardInterrupt:
                    print("\n\nStopping GPS data capture...")
                    break
                except Exception as e:
                    print(f"Error reading GPS data: {e}")
                    continue
        
        finally:
            if self.ser:
                self.ser.close()
                print("GPS connection closed")
            
            print(f"\nData capture complete!")
            print(f"   Total data points saved: {data_count}")
            if self.csv_filename:
                print(f"   CSV file: {self.data_dir}/{self.csv_filename}")
            print(f"   Data files saved in: {self.data_dir}")
    
    def read_saved_data(self, filename):
        """Read and display saved GPS data"""
        filepath = os.path.join(self.data_dir, filename)
        
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            return
        
        if filename.endswith('.csv'):
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                data = list(reader)
        elif filename.endswith('.json'):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            print("Unsupported file format")
            return
        
        print(f"\nReading GPS data from: {filename}")
        print(f"   Total records: {len(data)}")
        
        for i, record in enumerate(data[:5]):  # Show first 5 records
            print(f"\nRecord {i+1}:")
            for key, value in record.items():
                print(f"   {key}: {value}")

def main():
    gps = GPSDataCapture()
    
    print("BU-353N5 GPS Data Capture Tool")
    print("=" * 40)
    
    # Test GPS connection first
    if not gps.connect_gps():
        print("\nFailed to connect to GPS. Please check:")
        print("1. USB connection")
        print("2. Device drivers")
        print("3. COM port availability")
        return
    
    gps.ser.close()  # Close test connection
    
    # Start data capture
    try:
        duration = int(input("\nEnter capture duration in minutes (default 5): ") or "5")
        interval = int(input("Enter save interval in seconds (default 5): ") or "5")
        save_json = input("Save JSON file as well? (y/n, default y): ").lower() != 'n'
        
        gps.capture_data(duration, interval, save_json)
        
        # Option to read saved data
        if input("\nWould you like to read the saved data? (y/n): ").lower() == 'y':
            files = [f for f in os.listdir(gps.data_dir) if f.endswith(('.csv', '.json'))]
            if files:
                print("\nAvailable data files:")
                for i, file in enumerate(files):
                    print(f"{i+1}. {file}")
                
                try:
                    choice = int(input("Enter file number to read: ")) - 1
                    if 0 <= choice < len(files):
                        gps.read_saved_data(files[choice])
                except (ValueError, IndexError):
                    print("Invalid selection")
    
    except KeyboardInterrupt:
        print("\n\nData capture stopped by user")

if __name__ == "__main__":
    main()
