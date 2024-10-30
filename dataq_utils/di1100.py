import serial
from serial.tools import list_ports
import time

# Constants from the DI-1100 Protocol
VID = 0x0683
PID = 0x1101


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
    print(f"Scan list configured: {channels}")


def set_sample_rate(ser, divisor):
    """Set the sample rate based on the given divisor."""
    send_command(ser, f"srate {divisor}")


def log(voltage_buffer, channel_config, device_id, log_func, print_lock):
    with print_lock:  # Ensure only one thread prints at a time
        log_func(voltage_buffer, channel_config, device_id)


def read_data(ser, channel_config, device_id, log_func, stop_event, print_lock):
    """Read and print voltage readings from the DI-1100."""
    num_channels = len(channel_config)
    try:
        while not stop_event.is_set():
            data = ser.read(2 * num_channels)  # Read bytes for all channels
            if data and len(data) == 2 * num_channels:
                voltages = []
                for i in range(num_channels):
                    # Extract each 2-byte word (16 bits)
                    raw_value = int.from_bytes(
                        data[i * 2 : (i * 2) + 2], byteorder="little", signed=True
                    )

                    # Convert the raw ADC value to voltage
                    voltage = (
                        raw_value / 2048
                    ) * 10  # Scale to voltage range (-10V to 10V)
                    voltages.append(voltage)

                log(
                    voltages,
                    channel_config,
                    device_id,
                    log_func,
                    print_lock,
                )

            time.sleep(0.1)  # Small delay to reduce CPU usage
    except Exception as e:
        print(f"Error reading data: {e}")
    finally:
        stop_scanning(ser)


def manage_di1100_device(
    port, device_id, channel_config, log_func, stop_event, print_lock
):
    """Manage a single DI-1100 device."""
    ser = connect_to_device(port)
    if ser:
        try:
            stop_scanning(ser)
            configure_scan_list(ser, channel_config)
            set_sample_rate(ser, 60000)  # 10 Hz sample rate
            start_scanning(ser)
            read_data(ser, channel_config, device_id, log_func, stop_event, print_lock)
        finally:
            ser.close()
