import socket
import sys
import pickle
import _thread
import threading
import time

TIMER_STOP = -1
data_packet = 0b0101010101010101
TIMEOUT_INTERVAL = 0.5
SLEEP_INTERVAL = 0.05
ACK = 0
lock = threading.RLock()
server_port = 7735
server_address = '192.168.1.172'
base = 0
send_timer = TIMEOUT_INTERVAL


def main():
    global N
    global base
    global MSS
    global server_address
    global server_port
    server_address, server_port, file_name, N, MSS = cmd_args()

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.bind((get_ip(), 65532))

    reply = ["client_ip", get_ip()]
    client_socket.sendto(pickle.dumps(reply), (server_address, server_port))

    send_file(client_socket, MSS, file_name)

    client_socket.close()


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    return s.getsockname()[0]


def carry_around_add(a, b):
    c = a + b
    return (c & 0xffff) + (c >> 16)


def calc_checksum(msg):
    s = 0
    for i in range(0, len(msg), 2):
        message = str(msg)
        w = ord(message[i]) + (ord(message[i+1]) << 8)
        s = carry_around_add(s, w)
    return ~s & 0xffff


def make_packet(chunk, seq):
    temp = []
    check = calc_checksum(chunk)
    temp.append(seq)
    temp.append(check)
    temp.append(data_packet)
    temp.append(chunk)
    packet = pickle.dumps(temp)
    return packet


def get_mss_sized_data_chunks(mss_value, file):
    packets = []
    seq = 0
    try:
        with open(file, 'rb') as file:
            while True:
                chunk = file.read(mss_value)
                if chunk:
                    packets.append(make_packet(chunk, seq))
                    seq += 1
                else:
                    break
    except IOError:
        print("File open error")
        return
    return packets


def check_timeout(timer):
    if timer == TIMER_STOP:
        return False
    else:
        return time.time() - timer >= TIMEOUT_INTERVAL


def send_file(client_socket, mss, file):
    global base
    global lock
    global send_timer

    next_packet = 0
    packets = get_mss_sized_data_chunks(mss, file)

    no_packets = len(packets)
    print('I got', no_packets)
    window_size = min(N, no_packets - base)
    base = 0

    _thread.start_new_thread(receive_ack, (client_socket,))

    while base < no_packets:
        lock.acquire()
        while next_packet < base + window_size:
            print('Sending ', next_packet)
            client_socket.sendto(packets[next_packet], (server_address, server_port))
            next_packet += 1

        if send_timer == TIMER_STOP:
            send_timer = time.time()

        while send_timer != TIMER_STOP and not check_timeout(send_timer):
            lock.release()
            time.sleep(SLEEP_INTERVAL)
            lock.acquire()

        if check_timeout(send_timer):
            print('Timeout, sequence number', str(ACK))
            if send_timer != TIMER_STOP:
                send_timer = TIMER_STOP
            next_packet = base

        else:
            print('Shifting window')
            window_size = min(N, no_packets - base)
        lock.release()

    client_socket.sendto(b'', (server_address, server_port))


def receive_ack(s):
    global base
    global lock
    global send_timer
    global ACK
    while True:
        try:
            pkt = s.recv(256)
        except IOError:
            break
        else:
            data = pickle.loads(pkt)

            ACK = data[0]
            zero_bits = data[1]
            ack_bits = data[2]

            if ACK >= base and zero_bits == '0000000000000000' and ack_bits == '1010101010101010':
                lock.acquire()
                base = ACK + 1
                if send_timer != TIMER_STOP:
                    send_timer = TIMER_STOP
                lock.release()


def cmd_args():
    own_address = sys.argv[1]
    own_port = sys.argv[2]
    file = sys.argv[3]
    window_size = sys.argv[4]
    mss_value = sys.argv[5]
    return str(own_address), int(own_port), str(file), int(window_size), int(mss_value)


if __name__ == "__main__":
    main()
