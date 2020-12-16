import socket
import rsa
import os
import time
import enum


class Commands(enum.Enum):
    auth = 0
    register = 1
    open_dialog = 2
    open_chat = 3
    send_message = 4
    send_file = 5
    create_dialog = 6
    create_chat = 7
    add_to_chat = 8
    close_chat = 9
    close_dialog = 10
    get_dialogs = 11
    get_chats = 12


SIZE = 2048


class Client:
    def __init__(self, host, port):
        self.public_key = ""
        self.private_key = ""
        self.host = host
        self.port = port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((self.host, self.port))

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
        self.client_socket.sendall(bytes([Commands.register.value]))
        self.client_socket.recv(SIZE)
        self.client_socket.sendall(login.encode("utf16"))
        self.client_socket.recv(SIZE)
        self.client_socket.sendall(password.encode("utf16"))
        data = self.client_socket.recv(SIZE)
        if data[0] == 0:
            print('Registered' + " " + login)
            self.client_socket.sendall(self.public_key.save_pkcs1())
            return True
        else:
            print('Failed to register' + " " + login)
            return False

    def auth(self, login, password):
        self.client_socket.sendall(bytes([Commands.auth.value]))
        self.client_socket.recv(SIZE)
        self.client_socket.sendall(login.encode("utf16"))
        self.client_socket.recv(SIZE)
        self.client_socket.sendall(password.encode("utf16"))
        data = self.client_socket.recv(SIZE)
        if data[0] == 0:
            print("Signed in successfully")
        else:
            print("Failed to sign in")

    def get_all_dialogs(self):
        pass

    def end_session(self):
        self.client_socket.close()

if __name__ == "__main__":
    c = Client("", 8080)
    c.register("login", "password")
    c.register("login", "password")
    c.register("login", "password")
    c.register("Asd", "password")
    c.auth("Asd", "password")
    c.end_session()


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
