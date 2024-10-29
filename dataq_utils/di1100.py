import serial
from serial.tools import list_ports
import threading
import time

stop_event = threading.Event()  # Signal threads to stop
print_lock = threading.Lock()  # Synchronize printing

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


def read_data(ser, num_channels):
    """Read and print voltage readings from the DI-1100."""
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

                with print_lock:  # Ensure thread-safe printing
                    print(f"Voltages: {voltages}")  # Print voltage readings

            time.sleep(0.1)  # Small delay to reduce CPU usage
    except Exception as e:
        print(f"Error reading data: {e}")
    finally:
        stop_scanning(ser)


def manage_device(port, channel_config, log):
    """Manage a single DI-1100 device."""
    ser = connect_to_device(port)
    if ser:
        try:
            stop_scanning(ser)  # Ensure scanning is stopped
            configure_scan_list(ser, channel_config)
            set_sample_rate(ser, 60000)  # 10 Hz sample rate
            start_scanning(ser)
            read_data(ser, len(channel_config))
        finally:
            ser.close()


def log_all_devices(channel_config, log):
    """Initialize and manage multiple DI-1100 devices."""
    ports = find_di1100_ports()
    if ports:
        threads = []
        for i, port in enumerate(ports):
            thread = threading.Thread(
                target=manage_device, args=(port, channel_config, log)
            )
            threads.append(thread)
            thread.start()

        try:
            while any(thread.is_alive() for thread in threads):
                time.sleep(1)  # Keep main thread alive while others run
        except KeyboardInterrupt:
            print("Stopping all devices...")
            stop_event.set()

        # for thread in threads:
        #     thread.join()
    else:
        print("No connected DI-1100 devices found.")
