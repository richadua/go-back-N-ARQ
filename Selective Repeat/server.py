import socket
import random
import struct
import time
import sys


def decapsulate(packet):
    
    tcp_headers = struct.unpack('!LHH', packet[0:8]) 
    sequence_number = tcp_headers[0]
    check_sum = tcp_headers[1]
    packet_type = tcp_headers[2]
    data = packet[8:] 
    data = data.decode('utf-8')
    return sequence_number, check_sum, packet_type, data


def carry_around_add(a, b):
    c = a + b
    return (c & 0xffff) + (c >> 16)


def check_check_sum(packet, check_sum_from_client):
    sum = 0
    for i in range(0, len(packet), 2):
        if (i + 1) < len(packet):
            temp_sum = ord(packet[i]) + (ord(packet[i + 1]) << 8)
            sum = carry_around_add(temp_sum, sum)
    
    return (~sum & 0xffff) & check_sum_from_client


def acknowledge_packet(server_socket, client_address, sequence_number, zeros, packet_type):
    tcp_header = struct.pack("!LHH", sequence_number, str_binary_to_i(zeros), str_binary_to_i(packet_type))
    server_socket.sendto(tcp_header, client_address)


def str_binary_to_i(str):
    return int(str, 2)


def build_file(packet_dict, n, file_printer1):
    for i in range(n):
        if i in packet_dict:
            file_printer1.write(packet_dict[i])


def completeTransaction():
    print("total time :", end_time - start_time)
    global packets_received, last_packet, file_printer
    build_file(packets_received, total_packets_temp, file_printer)
    file_printer.close()
    server_socket.close()
    sys.exit()


if __name__ == '__main__':
    CLIENT_PORT = 60000
    HOST_NAME = '0.0.0.0'
    packet_type_data_16_bits = "0101010101010101"
    packet_type_ack_16_bits = "1010101010101010"
    zeros = "0000000000000000"
    fin_16_bits = '1111111111111111'
    packets_received = {}
    last_packet = 0
    RTT = 0.100
    SERVER_PORT = int(sys.argv[1])
    FILE_LOC = sys.argv[2]
    LOSS_PROBABILITY = float(sys.argv[3])
    in_transfer = True
    flag = True

    file_printer = open(FILE_LOC, "w")
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(('', SERVER_PORT))

    print("Server started and is listening at port : ", SERVER_PORT)
    data, addr = server_socket.recvfrom(2048)
    total_packets = int(data.decode())
    total_packets_temp = total_packets

    print("total number of packets: ", total_packets)
    first_data = True
    start_time = time.time()
    end_time = 0

    while flag:
        data, addr = server_socket.recvfrom(2048)
        client_host_name = addr[0]
        sequence_number, checksum, packet_type, data = decapsulate(data)

        if check_check_sum(data, checksum) == 0: 

            if packet_type == str_binary_to_i(fin_16_bits):
                acknowledge_packet(server_socket, (client_host_name, CLIENT_PORT), sequence_number, zeros, packet_type_ack_16_bits)
                last_packet = sequence_number
                print("Last packet received"+ str(sequence_number))
                continue

            if random.random() < LOSS_PROBABILITY:
                print('Packet loss, sequence number = ', str(sequence_number))
                continue

            if not packet_type == str_binary_to_i(packet_type_data_16_bits):
                print("received packet type = ", str(packet_type))
                print("received data ", data)
                print("Packet type not supported")
                server_socket.close()
                break

            if not int(sequence_number) in packets_received:
                packets_received[int(sequence_number)] = data
                total_packets -= 1
                if total_packets <= 1:
                    flag = False
                    end_time = time.time()
                    completeTransaction()
                    acknowledge_packet(server_socket, (client_host_name, CLIENT_PORT), sequence_number, fin_16_bits, packet_type_ack_16_bits)
                    break

            acknowledge_packet(server_socket, (client_host_name, CLIENT_PORT), sequence_number, zeros, packet_type_ack_16_bits)
        else:
            print('Improper Checksum, sequence number = ', str(sequence_number))