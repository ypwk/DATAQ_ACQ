from dataq_utils.di245 import manage_di245_device, find_di245_ports
from dataq_utils.di1100 import manage_di1100_device, find_di1100_ports
from datetime import datetime
import csv
import os
import threading
import time

TC_TYPE = "K"  # Thermocouple type for DI-245
LOG_FILE = "device_readings.csv"  # Output file path

stop_event = threading.Event()
print_lock = threading.Lock()


# Ensure the log file exists and has headers
def initialize_log_file():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Device Type", "Channel", "Type", "Value"])


def log_to_file(device_id, device_type, channel_type, value):
    """Log readings to a CSV file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, mode="a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, device_type, device_id, channel_type, value])


def log_temperature(temperature_buffer, channel_config, device_id):
    """Log temperature readings from DI-245."""
    print(f"\nDevice {device_id} - Temperature Readings:")
    print(f"{'Channel':<10}{'Type':<10}{'Temperature (°C)':<15}")
    for i, temp in enumerate(temperature_buffer):
        channel_type = channel_config[i]
        print(f"{i:<10}{channel_type:<10}{temp:<15.2f}")
        log_to_file(device_id, "DI-245", channel_type, temp)

    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def log_voltage(voltage_buffer, channel_config, device_id):
    """Log voltage readings from DI-1100."""
    print(f"\nDevice {device_id} - Voltage Readings:")
    print(f"{'Channel':<10}{'Type':<10}{'Voltage (V)':<15}")
    for i, voltage in enumerate(voltage_buffer):
        channel_type = f"CH-{channel_config[i]}"
        print(f"{i:<10}{channel_type:<10}{voltage:<15.2f}")
        log_to_file(device_id, "DI-1100", channel_type, voltage)

    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def start_device_threads(devices, manage_device_func, channel_config, dev_type):
    """Start threads for managing devices."""
    log_type = {"di245": log_temperature, "di1100": log_voltage}
    threads = []
    for i, device in enumerate(devices):
        thread = threading.Thread(
            target=manage_device_func,
            args=(
                device,
                i,
                channel_config,
                log_type[dev_type],
                stop_event,
                print_lock,
            ),
        )
        threads.append(thread)
        thread.start()

    return threads  # Return the threads to manage them later


def main():
    # Initialize the log file
    initialize_log_file()

    # Start DI-1100 threads in parallel
    di1100_ports = find_di1100_ports()
    if di1100_ports:
        print("Starting DI-1100 devices...")
        di1100_threads = start_device_threads(
            di1100_ports, manage_di1100_device, [0, 1, 2, 3], "di1100"
        )
    else:
        di1100_threads = []
        print("No DI-1100 devices found.")

    # Start DI-245 threads in parallel
    di245_ports = find_di245_ports()
    if di245_ports:
        print("Starting DI-245 devices...")
        di245_threads = start_device_threads(
            di245_ports,
            manage_di245_device,
            [TC_TYPE, TC_TYPE, TC_TYPE, TC_TYPE],
            "di245",
        )
    else:
        di245_threads = []
        print("No DI-245 devices found.")

    # Monitor all threads until they finish or stop event is triggered
    all_threads = di1100_threads + di245_threads
    try:
        while any(thread.is_alive() for thread in all_threads):
            time.sleep(1)  # Keep main thread alive
    except KeyboardInterrupt:
        print("Stopping all devices...")
        stop_event.set()  # Signal all threads to stop

    for thread in all_threads:
        thread.join()  # Ensure all threads finish before exiting


if __name__ == "__main__":
    main()
