from dataq_utils.di245 import manage_di245_device, find_di245_ports
from dataq_utils.di1100 import manage_di1100_device, find_di1100_ports
from datetime import datetime, timedelta
import csv
import os
import threading
import time

import boto3

TC_TYPE = "K"  # Thermocouple type for DI-245
LOG_FILE = "data/device_readings.csv"  # Output file path
TIME_PER_LOG = timedelta(minutes=1)
TIME_PER_UPLOAD = timedelta(minutes=5)
VERBOSE = False
BUCKET_NAME = "aqp-readout-data"
REGION_NAME = "us-west-1"

stop_event = threading.Event()
print_lock = threading.Lock()

last_log_time = []
last_upload_time = datetime.now()
current_device_index = 0

verboseprint = print if VERBOSE else lambda *a, **k: None

s3_client = boto3.client("s3", region_name=REGION_NAME)


def upload_file_to_s3(file_name, bucket_name):
    global last_upload_time
    if datetime.now() - TIME_PER_UPLOAD > last_upload_time:
        last_upload_time = datetime.now()
        try:
            s3_client.upload_file(file_name, bucket_name, file_name)
            verboseprint(f"File {file_name} uploaded successfully to {bucket_name}")
        except Exception as e:
            print(f"Failed to upload {file_name} to S3: {e}")


def initialize_log_file():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["Timestamp", "Device Name", "Device ID", "Channel", "Value"]
            )


def log_to_file(device_id, device_type, channel, value):
    """Log readings to a CSV file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, mode="a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, device_type, device_id, channel, value])


def log_temperature(temperature_buffer, channel_config, device_id):
    """Log temperature readings from DI-245."""
    global last_log_time
    verboseprint(f"\nDevice {device_id} - Temperature Readings:")
    verboseprint(f"{'Channel':<10}{'Type':<10}{'Temperature (°C)':<15}")

    current_time = datetime.now()
    if current_time - TIME_PER_LOG > last_log_time[device_id]:
        last_log_time[device_id] = current_time
        for i, temp in enumerate(temperature_buffer):
            channel_type = channel_config[i]
            verboseprint(f"{i:<10}{channel_type:<10}{temp:<15.2f}")
            log_to_file(device_id, "DI-245", i, temp)

    verboseprint(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    upload_file_to_s3(LOG_FILE, BUCKET_NAME)


def log_pressure(voltage_buffer, channel_config, device_id):
    """Log voltage readings from DI-1100."""
    global last_log_time
    verboseprint(f"\nDevice {device_id} - Pressure Readings:")
    verboseprint(f"{'Channel':<10}{'Type':<10}{'Pressure (mbar)':<15}")

    current_time = datetime.now()
    if current_time - TIME_PER_LOG > last_log_time[device_id]:
        last_log_time[device_id] = current_time
        # for i, voltage in enumerate(voltage_buffer):
        mbar = 10 ** ((voltage_buffer[0] - 7.75) / 0.75)
        verboseprint(f"{0:<10}{channel_config[0]:<10}{mbar:<15.2f}")
        log_to_file(device_id, "DI-1100", channel_config[0], mbar)

    verboseprint(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    upload_file_to_s3(LOG_FILE, BUCKET_NAME)


def start_device_threads(devices, manage_device_func, channel_config, dev_type):
    """Start threads for managing devices."""
    log_type = {"di245": log_temperature, "di1100": log_pressure}
    threads = []
    global current_device_index, last_log_time
    for _, device in enumerate(devices):
        thread = threading.Thread(
            target=manage_device_func,
            args=(
                device,
                current_device_index,
                channel_config,
                log_type[dev_type],
                stop_event,
                print_lock,
            ),
        )
        current_device_index += 1
        last_log_time.append(datetime.now())
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
