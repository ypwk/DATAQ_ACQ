import serial
from serial.tools import list_ports
import time
import threading


def find_di1100_ports():
    """Auto-detect DI-245 COM port"""
    ports = list_ports.comports()
    p245 = []
    for port in ports:
        if port.vid == 0x0683 and port.pid == 0x1100:
            print(f"DI-245 found on {port.device}")
            p245.append(port.device)
    return p245


def log_all_devices(log_func):
    ports = find_di1100_ports()
    if ports:
        threads = []

        for i, port in enumerate(ports):
            # thread = threading.Thread(
            #     target=manage_device, args=(port, i, channel_config, log_func)
            # )
            # threads.append(thread)
            # thread.start()
            print(i, port)

        # try:
        #     while any(thread.is_alive() for thread in threads):
        #         time.sleep(1)  # Keep main thread alive while others run
        # except KeyboardInterrupt:
        #     print("Stopping all devices...")
        #     stop_event.set()  # Signal all threads to stop

        # for thread in threads:
        #     thread.join()
    else:
        print("No connected DI-1100 devices found.")
