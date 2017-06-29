import socket

import serial

DEFAULT_SERIAL_PORT = "/dev/ttyUSB0"
DEFAULT_SERIAL_BAUD = 1000000

DEFAULT_UDP_ADDRESS = "127.0.0.1"
DEFAULT_UDP_PORT = 13320


def get_args():
    """
    Get and parse arguments.
    """
    import argparse
    parser = argparse.ArgumentParser(
        description="Swift Navigation UDP Receive tool.")
    parser.add_argument(
        "-s",
        "--serial-port",
        default=[DEFAULT_SERIAL_PORT],
        nargs=1,
        help="specify the serial port to use.")
    parser.add_argument(
        "-b",
        "--baud",
        default=[DEFAULT_SERIAL_BAUD],
        nargs=1,
        help="specify the baud rate to use.")
    parser.add_argument(
        "-a",
        "--address",
        default=[DEFAULT_UDP_ADDRESS],
        nargs=1,
        help="specify the UDP IP Address to use.")
    parser.add_argument(
        "-p",
        "--udp-port",
        default=[DEFAULT_UDP_PORT],
        nargs=1,
        help="specify the UDP Port to use.")
    return parser.parse_args()


def main():
    """Simple Command line interface for receiving observations over UDP and repeating
       them over serial
    """
    args = get_args()
    port = int(args.udp_port[0])
    address = args.address[0]
    ser = serial.Serial(args.serial_port[0], args.baud[0])
    sock = socket.socket(
        socket.AF_INET,  # Internet
        socket.SOCK_DGRAM)  # UDP
    sock.bind((args.address[0], args.udp_port[0]))
    try:
        while True:
            data, addr = sock.recvfrom(1024)
            if data:
                ser.write(data)
    except KeyboardInterrupt:
        pass
    if ser.isopen():
        ser.close()


if __name__ == "__main__":
    main()
