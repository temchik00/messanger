import socket
import rsa
import os
import time


SIZE = 2048


class Client:
    def __init__(self, host, port):
        self.public_key = ""
        self.private_key = ""
        self.host = host
        self.port = port

    def __generate_keys__(self):
        os.mkdir("./keys")
        public_key, private_key = rsa.newkeys(SIZE, poolsize=8)
        key = public_key.save_pkcs1()
        with open("./keys/public_key.PEM", "wb") as file:
            file.write(key)
        key = private_key.save_pkcs1()
        with open("./keys/private_key.PEM", "wb") as file:
            file.write(key)

    def __load_keys__(self):
        with open("./keys/public_key.PEM", "rb") as file:
            self.public_key = rsa.PublicKey.load_pkcs1(file.read())

        with open("./keys/private_key.PEM", "rb") as file:
            self.private_key = rsa.PrivateKey.load_pkcs1(file.read())

    def register(self, login, password):
        if not os.path.isdir("./keys"):
            self.__generate_keys__()
        self.__load_keys__()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((self.host, self.port))
            client_socket.sendall(bytes([1]))
            client_socket.recv(SIZE)
            client_socket.sendall(login.encode("utf16"))
            client_socket.recv(SIZE)
            client_socket.sendall(password.encode("utf16"))
            data = client_socket.recv(SIZE)
            if data[0] == 0:
                print('registred' + " " + login)
                client_socket.sendall(self.public_key.save_pkcs1())
                return True
            else:
                print('Failed to register' + " " + login)
                return False


c = Client("", 8080)
c.register("login", "password")
c.register("login", "password")
c.register("login", "password")
c.register("Asd", "password")



# HOST = '127.0.0.1'  # The server's hostname or IP address
# PORT = 8080        # The port used by the server
#
# with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
#     s.connect((HOST, PORT))
#     s.sendall(b'Hello, world')
#     data = s.recv(1024)
#     for letter in data:
#         print(letter)
# print('Received', str(data))
