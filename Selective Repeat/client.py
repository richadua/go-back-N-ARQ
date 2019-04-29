import socket
import sys
import threading
import time
import struct
import random
from queue import *

def carry_around_add(a, b):
    c = a + b
    return (c & 0xffff) + (c >> 16)


def checksum(packet):
    packet = packet.decode('utf-8')
    sum = 0
    for i in range(0, len(packet), 2):
        if (i + 1) < len(packet):
            temp_sum = ord(packet[i]) + (ord(packet[i + 1]) << 8)
            sum = carry_around_add(temp_sum, sum)
    return sum & 0xffff

def form_packet(packet, seq, packet_type):
    value = checksum(packet)
    packet_type = str_binary_to_i(packet_type)
    header = struct.pack('!LHH', int(seq), int(value), int(packet_type))
    return header + packet


def extract_from_file(file, mss):
    current_seq = 0
    packet = ''
    fileread = open(file, 'rb')
    read_mss_bytes = fileread.read(mss)
    while read_mss_bytes:
        packet_to_send.append(form_packet(read_mss_bytes, current_seq, data_packet))
        read_mss_bytes = fileread.read(mss)
        current_seq += 1
    
    packet = "0".encode('utf-8')
    packet_to_send.append(form_packet(packet, current_seq, finish_packet))
    fileread.close()
    global total_packets
    global track_packets
    total_packets = len(packet_to_send)
    track_packets = [False] * total_packets

def rdt_send(client_socket, window_size, server_name, sever_port):
    global packet_number_tracking
    global window_start
    global timestamp
    global resend_queue
    global ret
    global flag

    timestamp = [0.0]*total_packets
    last_packet_send = -1
    
    while receivedacks < total_packets:
        if not flag:
            break
        lock.acquire()
       
        packet_number_tracking_len = len(packet_number_tracking)

        if (packet_number_tracking_len < window_size) and ((window_start + packet_number_tracking_len) < total_packets):
            while not resend_queue.empty():
                i = resend_queue.get()
                if not track_packets[i]:
                    packet_to_be_sent = packet_to_send[i]
                    timestamp[i] = time.time()
                    send_packet(packet_to_be_sent)
                    packet_number_tracking.append(i)
 
            j = last_packet_send + 1
            temp = min(window_start + window_size, total_packets)
            while j < temp:
                if not track_packets[j]:
                    packet_to_be_sent = packet_to_send[j]
                    timestamp[j] = time.time()
                    send_packet(packet_to_be_sent)
                    packet_number_tracking.append(j)
                    last_packet_send = j
                j += 1

        
        packet_number_tracking_len = len(packet_number_tracking)
        to_be_removed = []  
        if packet_number_tracking_len > 0:
            for packet_number in packet_number_tracking:
                if track_packets[packet_number]: 
                    to_be_removed.append(packet_number)

                elif (time.time() - timestamp[packet_number]) > RTO:
                    if not track_packets[packet_number]:
                        if random.random() > 0.6: 
                            print("Time out, Sequence number: " + str(packet_number))
                        resend_queue.put(packet_number)
                        ret += 1
                        to_be_removed.append(packet_number)

        
        if len(to_be_removed) > 0:
            packet_number_tracking = remove_items_util(packet_number_tracking, to_be_removed)
            to_be_removed.clear()

        lock.release()


def  remove_items_util(a,b):
  
    return list(set(a)-set(b))


def receive_ACK(client_socket):
    global packet_number_tracking
    global window_start
    global receivedacks
    global flag

    while receivedacks < total_packets:

        if not flag:
            break

        packet_number_tracking_len = len(packet_number_tracking)
        if packet_number_tracking_len > 0:
            data = client_socket.recv(2048)  
            lock.acquire()
            ack_number, zeroes_received, packet_type = decapsulate(data)
            if ack_number in packet_number_tracking:
                packet_number_tracking.remove(ack_number)

            if zeroes_received == str_binary_to_i(finish_packet):
                
                print("last ack")
                flag = False
                lock.release()
                continue

            if not zeroes_received == str_binary_to_i(zeros) or not packet_type == str_binary_to_i(ack_bits):
                print("Invalid Acknowledgement, Sequence number = ", window_start)
                resend_queue.put(ack_number)
                track_packets[ack_number] = False
            else:

                if not track_packets[ack_number]:  
                    receivedacks += 1
                    track_packets[ack_number] = True  
                    i = window_start
                    end = min(i+n, total_packets)  
                    while i < end and track_packets[i]:
                        i += 1
                        continue
                    window_start = i
            lock.release()

def send_packet(packet):
    global client_socket
    client_socket.sendto(packet, (server_name, server_port))

def decapsulate(packet):
    tcp_headers = struct.unpack('!LHH', packet[0:8])
    sequence_number = tcp_headers[0]  
    zeroes = tcp_headers[1]
    packet_type = tcp_headers[2]
    return sequence_number, zeroes, packet_type

def str_binary_to_i(str):
    return int(str, 2)

if __name__ == "__main__":
    
    client_host = socket.gethostname()
    client_ip = socket.gethostbyname(client_host)
    print("received host",client_ip)
    client_port = 60000

    packet_to_send = [] 
    track_packets = []  
    packet_number_tracking = []  
    timestamp = []  
    window_start = 0
    lock = threading.Lock()
    total_packets = 0

    data_packet = "0101010101010101"  
    finish_packet = "1111111111111111"  
    ack_bits = "1010101010101010 " 
    zeros = "0000000000000000"   
    ret = 0
    receivedacks = 0
    flag = True

    RTO = 0.1  
    server_name = sys.argv[1]
    server_port = int(sys.argv[2])
    file = sys.argv[3]
    n = int(sys.argv[4])
    mss = int(sys.argv[5])
    resend_queue = Queue(maxsize=n)
   
    
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.bind(('0.0.0.0', client_port))
    print("client running on IP " + str(client_ip) + " and port " + str(client_port))
    extract_from_file(file, mss)
    print("Total Packets present : "+str(total_packets))

    
    client_socket.sendto(str(total_packets).encode(),(server_name,server_port))

    t = threading.Thread(target= receive_ACK, args= (client_socket,))
    t.start()
    start_time = time.time()
    rdt_send(client_socket, n, server_name, server_port)
    t.join()
    end_time = time.time()
    time_taken = end_time - start_time
    print("Time for sending and receiving Acknowledgements", str(time_taken))
    print("ret", str(ret))
    client_socket.close()