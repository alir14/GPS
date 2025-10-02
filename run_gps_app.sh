#!/bin/bash

echo "BU-353N5 GPS Data Capture Tool"
echo "=============================="
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 not found! Please install Python 3.7+ and try again."
    exit 1
fi

echo "Python version:"
python3 --version
echo

# Create virtual environment if it doesn't exist
if [ ! -d "gpsDataEnv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv gpsDataEnv
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create virtual environment!"
        exit 1
    fi
fi

# Activate virtual environment
echo "Activating virtual environment..."
source gpsDataEnv/bin/activate

# Install requirements
echo "Installing required packages..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "Error: Failed to install requirements!"
    exit 1
fi

echo
echo "Choose an option:"
echo "1. Test GPS connection only"
echo "2. Capture GPS data to files"
echo "3. Exit"
echo

read -p "Enter your choice (1-3): " choice

case $choice in
    1)
        echo
        echo "Running GPS connection test..."
        python3 gps_test.py
        ;;
    2)
        echo
        echo "Running GPS data capture..."
        python3 gps_data_capture.py
        ;;
    3)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo "Invalid choice!"
        exit 1
        ;;
esac

echo
echo "Press Enter to continue..."
read
