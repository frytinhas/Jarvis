#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

static volatile sig_atomic_t running = 1;
static void stop_server(int signal_number) { (void)signal_number; running = 0; }

int main(int argc, char **argv) {
    const char *host = NULL;
    const char *key_path = NULL;
    int port = 0;
    for (int i = 1; i + 1 < argc; i++) {
        if (strcmp(argv[i], "--host") == 0) host = argv[++i];
        else if (strcmp(argv[i], "--port") == 0) port = atoi(argv[++i]);
        else if (strcmp(argv[i], "--api-key-file") == 0) key_path = argv[++i];
        else if (strcmp(argv[i], "--model") == 0) i++;
        else if (argv[i][0] == '-' && i + 1 < argc && argv[i + 1][0] != '-') i++;
    }
    if (!host || strcmp(host, "127.0.0.1") != 0 || port < 1 || !key_path) return 64;
    /* Jarvis passes the already-validated private key descriptor through
       /proc/self/fd so a pathname swap cannot substitute credentials. */
    int key_fd = open(key_path, O_RDONLY);
    if (key_fd < 0) return 65;
    char key[256] = {0};
    ssize_t key_size = read(key_fd, key, sizeof(key) - 1);
    close(key_fd);
    if (key_size <= 0) return 66;

    int listener = socket(AF_INET, SOCK_STREAM, 0);
    if (listener < 0) return 67;
    struct sockaddr_in address = {0};
    address.sin_family = AF_INET;
    address.sin_port = htons((unsigned short)port);
    inet_pton(AF_INET, host, &address.sin_addr);
    if (bind(listener, (struct sockaddr *)&address, sizeof(address)) != 0) return 68;
    if (listen(listener, 8) != 0) return 69;
    const char *raw_output = "RAW_SERVER_OUTPUT_MUST_NOT_PERSIST\n";
    for (int i = 0; i < 40000; i++) {
        write(STDOUT_FILENO, raw_output, strlen(raw_output));
        write(STDERR_FILENO, raw_output, strlen(raw_output));
    }
    struct sigaction action = {0};
    action.sa_handler = stop_server;
    sigemptyset(&action.sa_mask);
    action.sa_flags = 0;
    sigaction(SIGTERM, &action, NULL);
    sigaction(SIGINT, &action, NULL);
    while (running) {
        int client = accept(listener, NULL, NULL);
        if (client < 0) {
            if (errno == EINTR) continue;
            break;
        }
        char request[4096] = {0};
        ssize_t count = read(client, request, sizeof(request) - 1);
        char authorization[512];
        snprintf(authorization, sizeof(authorization), "Authorization: Bearer %s", key);
        if (count > 0 && strstr(request, "GET /health ") && strstr(request, authorization)) {
            const char *body = "{\"status\":\"ok\"}";
            char response[512];
            int size = snprintf(response, sizeof(response),
                "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %zu\r\nConnection: close\r\n\r\n%s",
                strlen(body), body);
            write(client, response, (size_t)size);
        } else {
            const char *response = "HTTP/1.1 401 Unauthorized\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
            write(client, response, strlen(response));
        }
        close(client);
    }
    close(listener);
    return 0;
}
