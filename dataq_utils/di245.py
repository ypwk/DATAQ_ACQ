import serial
from serial.tools import list_ports


def send_command(ser, command):
    full_command = b"\x00" + command.encode()
    ser.write(full_command)
    response = ser.read_until(b"\r")
    print(f"Response: {response.decode().strip()}")


def find_di245_ports():
    """Auto-detect DI-245 COM port"""
    ports = list_ports.comports()
    p245 = []
    for port in ports:
        if port.vid == 0x0683 and port.pid == 0x2450:
            print(f"DI-245 found on {port.device}")
            p245.append(port.device)
    return p245


def connect_to_device(port, baudrate=115200):
    try:
        ser = serial.Serial(port, baudrate, timeout=1)
        print(f"Connected to {port}")
        return ser
    except serial.SerialException as e:
        print(f"Error connecting to {port}: {e}")
        return None


def derive_temp(tc_type, adc_counts):
    tc_m = {
        "B": 0.095825,
        "E": 0.073242,
        "J": 0.08606,
        "K": 0.095947,
        "N": 0.091553,
        "R": 0.110962,
        "S": 0.110962,
        "T": 0.036621,
    }
    tc_b = {
        "B": 1035,
        "E": 400,
        "J": 495,
        "K": 586,
        "N": 550,
        "R": 859,
        "S": 859,
        "T": 100,
    }

    return tc_m[tc_type] * adc_counts + tc_b[tc_type]


def configure_thermocouple_channel(ser, channel=0, thermocouple_type="K"):
    tc_config = {
        "B": 0b000,
        "E": 0b001,
        "J": 0b010,
        "K": 0b011,
        "N": 0b100,
        "R": 0b101,
        "S": 0b110,
        "T": 0b111,
    }

    mode_bits = tc_config[thermocouple_type]

    # Build the configuration value:
    # Bits 8-10 = mode_bits (thermocouple type)
    # Channel selection in the lower bits (bit positions 0-1)
    config_value = (
        (1 << 12) | (0 << 11) | (mode_bits << 8) | channel
    )  # Set "Mode = 1", "Range = Don't care" (bit 12 = 1, bit 11 = anything, 1 here)
    # print(bin(config_value))
    command = f"chn {channel} {config_value}\r"
    ser.write(command.encode())
    # print(f"Configured channel {channel} for {thermocouple_type}-type thermocouple.")


def set_sample_rate(ser, channels=1):
    # Parameters from the DI-245 protocol table for 20 Hz burst rate
    SF = 99
    AF = 1

    # AF in bits 7-11, SF in bits 0-6
    arg0 = (AF << 7) | SF

    # Set the desired burst rate in arg1 (closest value from table is 3.58 Hz)
    burst_rate = 20.0

    # Adjust burst rate for number of channels
    effective_rate = burst_rate / channels

    # Build the command and send it to the device
    command = f"xrate {arg0} {int(effective_rate)}\r"
    ser.write(command.encode())
    print(
        f"Sample rate set to {effective_rate:.2f} Hz per channel with {channels} channels."
    )


def start_scanning(ser):
    ser.write(b"\x00S1")


def stop_scanning(ser):
    ser.write(b"\x00S0")


def log(temperature_buffer, channel_config, device_id, log_func, print_lock):
    with print_lock:  # Ensure only one thread prints at a time
        log_func(temperature_buffer, channel_config, device_id)


def read_data(ser, channel_config, device_id, log_func, stop_event, print_lock):
    num_channels = len(channel_config)
    ser.read_until(b"S1")  # Sync with data stream
    current_channel = 0
    current_byte = 0
    temperature_buffer = [0 for _ in range(num_channels)]
    adc_buffer = [0 for _ in range(num_channels)]
    lsb = 0

    try:
        while not stop_event.is_set():  # Stop if event is set
            data = ser.read(1)
            if data == b"":
                continue

            current_byte += 1
            byte_int = int.from_bytes(data, byteorder="little")
            if current_byte == 1:
                lsb = byte_int >> 1
            elif current_byte == 2:
                msb = byte_int >> 1
                adc_value = ((msb & 0x7F) << 7) | lsb
                # print(f"msb: {format(msb, '07b')}")
                # print(f"lsb: {format(lsb, '07b')}")
                # print(f"adc: {format(adc_value, '014b')}")
                # print(f"inv: {format(1 << 13, '014b')}")
                # print(f"anv: {format(adc_value ^ (1 << 13), '014b')}")
                adc_value ^= 1 << 13
                if adc_value & (1 << 13):
                    adc_value -= 1 << 14
                # print(f"adc: {format(adc_value, '014b')}")
                temperature_buffer[current_channel] = derive_temp(
                    channel_config[current_channel], adc_counts=adc_value
                )
                adc_buffer[current_channel] = adc_value
                current_channel += 1
                current_byte = 0

                if current_channel == num_channels:
                    current_channel = 0
                    log(
                        temperature_buffer,
                        channel_config,
                        device_id,
                        log_func,
                        print_lock,
                    )
            # time.sleep(0.1)  # Small delay to reduce CPU usage
    except KeyboardInterrupt:
        print(f"Terminating data read for Device {device_id}...")
    finally:
        stop_scanning(ser)


def manage_di245_device(
    port, device_id, channel_config, log_func, stop_event, print_lock
):
    """Manages a single device: connect, configure, and read data."""
    ser = connect_to_device(port)
    if ser:
        stop_scanning(ser)
        for channel in range(len(channel_config)):
            configure_thermocouple_channel(
                ser, channel=channel, thermocouple_type=channel_config[channel]
            )
        set_sample_rate(ser, channels=len(channel_config))
        start_scanning(ser)

        print(f"Reading data from Device {device_id}...")
        try:
            read_data(ser, channel_config, device_id, log_func, stop_event, print_lock)
        finally:
            stop_scanning(ser)
            ser.close()
            print(f"Connection closed for Device {device_id}.")
