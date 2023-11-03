import socket

def recvall(sock):
    data = b""
    more = sock.recv(1024)
    data += more
    return data.decode()

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', 53540))
    sock.listen(1)

    sc, sockname = sock.accept()
    print("Aceitando conexão de ", sockname)
    print("  Nome do Socket: ", sc.getsockname())
    print("  Host Remoto: ", sc.getpeername())

    current_angle = 0
    while True:
        angulo = float(recvall(sc))

        print(angulo)

        if angulo > current_angle:
            angulo_aux = angulo - current_angle
            current_angle = angulo
        elif angulo < current_angle:
            angulo_aux = current_angle - angulo
            current_angle = angulo

        for passo in range(int(angulo_aux)):
            print(passo)

        print(current_angle)

if __name__ == '__main__':
    main()