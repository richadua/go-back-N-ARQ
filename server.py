import socket
import sys
import pickle
from random import *


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    return s.getsockname()[0]

RECEIVER_ADDR = (get_ip(), 7735)
prob_loss = 0.0

def cmd_args():
    server_port = sys.argv[1]
    file_name = sys.argv[2]
    prob = sys.argv[3]

    return int(server_port), file_name, float(prob)


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


def receive(s, filename):
    global prob_loss
    try:
        file = open(filename, 'wb')
    except IOError:
        print('Unable to open', filename)
        return

    expected_num = 0
    client_ip = ""
    while True:
        pkt = s.recv(1024)
        if not pkt:
            break

        data = pickle.loads(pkt)
        if(data[0] == "client_ip"):
            client_ip = data[1]
        else:
            seq_num = data[0]
            checksum = data[1]
            msg = data[3]

            loss = uniform(0,1)
            if loss <= prob_loss:
                print("Packet loss, sequence number = ", seq_num)
            else:
                print('Got packet', seq_num)
                if checksum == calc_checksum(msg):
                    if seq_num == expected_num:
                        print('Sending ACK', expected_num)
                        reply = [expected_num, "0000000000000000", "1010101010101010"]
                        s.sendto(pickle.dumps(reply), (client_ip, 65532))
                        expected_num += 1
                        with open(filename, 'ab') as file:
                            file.write(msg)
                    else:
                        print('Sending ACK', expected_num - 1)
                        reply = [expected_num - 1, "0000000000000000", "1010101010101010"]
                        s.sendto(pickle.dumps(reply), (client_ip, 65532))
                else:
                    print("Incorrect checksum, packet dropped")
            file.close()


if __name__ == '__main__':
    
    port, output_file, prob_loss = cmd_args()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(RECEIVER_ADDR)
    receive(sock, output_file)
    sock.close()
