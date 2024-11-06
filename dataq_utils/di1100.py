import serial
from serial.tools import list_ports
import time
import sys, os

# Constants for DI-1100 Protocol
VID = 0x0683
PID = 0x1101
DECIMATION_FACTOR = 10  # From test.py, to reduce noise
achan_accumulation_table = []  # Accumulated values for averaging

def find_di1100_ports():
    """Auto-detect DI-1100 USB devices by VID and PID."""
    ports = list_ports.comports()
    devices = []
    for port in ports:
        if port.vid == VID and port.pid == PID:
            print(f"DI-1100 found on {port.device}")
            devices.append(port.device)
    return devices

def connect_to_device(port):
    """Connect to the DI-1100 device via the specified COM port."""
    ser = serial.Serial(port, baudrate=115200, timeout=0.1)
    return ser

def send_command(ser, command):
    """Send a command to the DI-1100 device."""
    ser.write((command + "\r").encode())
    time.sleep(0.1)

def start_scanning(ser):
    """Start the DI-1100 scan."""
    send_command(ser, "start 0")

def stop_scanning(ser):
    """Stop the DI-1100 scan."""
    send_command(ser, "stop")

def configure_scan_list(ser, channels):
    """Configure the scan list for the selected channels."""
    for i, channel in enumerate(channels):
        send_command(ser, f"slist {i} {channel}")
        achan_accumulation_table.append(0)  # Initialize the accumulator for each channel
    print(f"Scan list configured: {channels}")

def set_sample_rate(ser, divisor):
    """Set the sample rate based on the given divisor."""
    send_command(ser, f"srate {divisor}")

def log(voltage_buffer, channel_config, device_id, log_func, print_lock):
    with print_lock:  # Ensure only one thread prints at a time
        log_func(voltage_buffer, channel_config, device_id)

def read_data(ser, channel_config, device_id, log_func, stop_event, print_lock):
    """Read and log voltage readings from the DI-1100 using decimation to reduce noise."""
    num_channels = len(channel_config)
    slist_pointer = 0
    dec_count = DECIMATION_FACTOR
    achan_accumulation_table = [0 for _ in range(num_channels)]
    achan_number = 0

    try:
        while not stop_event.is_set():
            while (ser.inWaiting() > (2 * num_channels)):
                for i in range(num_channels):
                    # Always two bytes per sample...read them
                    b = ser.read(2)
                    # Only analog channels for a DI-1100, with dig_in states appearing in the two LSBs of ONLY the first slist position
                    result = int.from_bytes(b, byteorder='little', signed=True)
                    if (dec_count == 1) and (slist_pointer == 0):
                        dig_in = result & 0x3
                        # Strip two LSBs from value to be added to the analog channel accumulation, preserving sign
                        result = result >> 2
                        result = result << 2
                        # Add the value to the accumulator
                        achan_accumulation_table[achan_number] += result
                        achan_number += 1
                    elif (dec_count == 1) and (slist_pointer != 0):
                        # Just add value to the accumulator
                        achan_accumulation_table[achan_number] += result
                        achan_number += 1
                    elif (dec_count != 1) and (slist_pointer == 0):
                        # Just strip two LSBs, preserving sign, and add to accumulator
                        result = result >> 2
                        result = result << 2
                        achan_accumulation_table[achan_number] += result
                        achan_number += 1
                    else:
                        # Nothing to do except add the value to the accumulator
                        achan_accumulation_table[achan_number] += result
                        achan_number += 1

                    # Get the next position in slist
                    slist_pointer += 1

                    if (slist_pointer + 1) > num_channels:
                        # End of a pass through slist items
                        if dec_count == 1:
                            # Decimation complete, convert accumulated values to voltages
                            voltages = [
                                (achan_accumulation_table[j] * 10 / 32768 / DECIMATION_FACTOR)
                                for j in range(num_channels)
                            ]
                            # Reset accumulators
                            achan_accumulation_table = [0] * num_channels
                            # Log the voltages
                            log(voltages, channel_config, device_id, log_func, print_lock)
                            dec_count = DECIMATION_FACTOR
                        else:
                            dec_count -= 1

                        slist_pointer = 0
                        achan_number = 0

            time.sleep(0.1)  # Small delay to reduce CPU usage
    except Exception as e:
        print(f"Error reading data: {e}")
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
    finally:
        stop_scanning(ser)


def manage_di1100_device(port, device_id, channel_config, log_func, stop_event, print_lock):
    """Manage a single DI-1100 device."""
    ser = connect_to_device(port)
    if ser:
        try:
            stop_scanning(ser)
            configure_scan_list(ser, channel_config)
            set_sample_rate(ser, 60000)  # 10 Hz sample rate
            start_scanning(ser)
            time.sleep(1)
            read_data(ser, channel_config, device_id, log_func, stop_event, print_lock)
        finally:
            ser.close()
