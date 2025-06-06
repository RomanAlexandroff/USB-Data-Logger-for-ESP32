# ********************************************************************************************** #
#                                                                                                #
#   Raspberry Pi Data Logger                                          :::::::::        :::       #
#   logger.py                                                        :+:    :+:     :+: :+:      #
#                                                                   +:+    +:+    +:+   +:+      #
#   By: Roman Alexandrov <r.aleksandroff@gmail.com>                +#++:++#:    +#++:++#++:      #
#                                                                 +#+    +#+   +#+     +#+       #
#   Created: 2025/05/18 12:00:00                                 #+#    #+#   #+#     #+#        #
#   Updated: 2025/05/18 12:00:00                                ###    ###   ###     ###         #
#                                                                                                #
# ********************************************************************************************** #

#!/usr/bin/env python3

import os
import time
import serial
import serial.tools.list_ports
from datetime import datetime

VENDOR_ID = '303a'
MANUFACTURER_NAME = 'Espressif'

LOG_DIR = '/home/roman/data_logger/LOGS'
ISSUE_LOG_FILE = '/home/roman/data_logger/data_logger_issues_log.txt'

RETRY_DELAY = 0.6
SESSION_GRACE_PERIOD = 2  # seconds
GRACE_CHECK_INTERVAL = 0.1
BAUD_RATE = 115200
POST_DISCONNECT_FLUSH_DELAY = 1  # seconds

def log_issue(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(ISSUE_LOG_FILE, 'a') as f:
        f.write(f'[{timestamp}] {message}\n')

def find_esp32_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if port.vid and port.manufacturer:
            if format(port.vid, '04x') == VENDOR_ID and MANUFACTURER_NAME in port.manufacturer:
                return port.device
    return None

def start_logging_session(port_name):
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_filename = os.path.join(LOG_DIR, f'log_{timestamp}.txt')
    print(f"[INFO] Logging to {log_filename}")
    try:
        with serial.Serial(port_name, BAUD_RATE, timeout=None) as ser, open(log_filename, 'w') as log_file:
            while True:
                if not os.path.exists(port_name):
                    print("[INFO] Device disconnected. Continuing to read for final data...")
                    disconnect_time = time.time()
                    while time.time() - disconnect_time < POST_DISCONNECT_FLUSH_DELAY:
                        if ser.in_waiting:
                            data = ser.read(ser.in_waiting).decode(errors='replace')
                            log_file.write(data)
                            log_file.flush()
                        time.sleep(0.01)
                    print("[INFO] Final read window expired. Closing logging session.")
                    return
                if ser.in_waiting:
                    data = ser.read(ser.in_waiting).decode(errors='replace')
                    log_file.write(data)
                    log_file.flush()
                time.sleep(0.01)
    except Exception as e:
        log_issue(f"Error during logging session: {e}")
        print(f"[ERROR] {e}")

def main():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    session_active = False
    grace_period_end = None

    while True:
        port_name = find_esp32_port()

        if port_name:
            current_time = time.time()
            if session_active:
                if grace_period_end and current_time <= grace_period_end:
                    print("[INFO] Device reappeared within grace period. Continuing logging session.")
                    grace_period_end = None  # reset
                    start_logging_session(port_name)
                else:
                    print("[INFO] Device reappeared after grace period. Starting new logging session.")
                    session_active = True
                    grace_period_end = None
                    start_logging_session(port_name)
            else:
                print("[INFO] Device detected. Starting new logging session.")
                session_active = True
                start_logging_session(port_name)
        else:
            if session_active and grace_period_end is None:
                grace_period_end = time.time() + SESSION_GRACE_PERIOD
                print("[INFO] Device disconnected. Starting grace period.")
            elif session_active and time.time() > grace_period_end:
                print("[INFO] Grace period expired. Session marked as inactive.")
                session_active = False
                grace_period_end = None

        time.sleep(GRACE_CHECK_INTERVAL)

if __name__ == '__main__':
    main()
