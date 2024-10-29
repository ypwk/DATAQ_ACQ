from dataq_utils import di245
from dataq_utils import di1100

from datetime import datetime

TC_TYPE = "K"


def log(temperature_buffer, channel_config, device_id):
    print(f"\nDevice {device_id} - Temperature Readings:")
    print(f"{'Channel':<10}{'Type':<10}{'Temperature (°C)':<15}")
    for i, temp in enumerate(temperature_buffer):
        channel_type = channel_config[i]
        print(f"{i:<10}{channel_type:<10}{temp:<15.2f}")
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def main():
    di245.log_all_devices([TC_TYPE, TC_TYPE, TC_TYPE, TC_TYPE], log)
    di1100.log_all_devices([0, 1, 2, 3], log)


if __name__ == "__main__":
    main()
