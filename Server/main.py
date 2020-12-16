import socket
import threading
import rsa
import pymongo


SIZE = 2048


# certificates: {login:str, password:str, public_key:binary, chats:[int], dialogs:[int]}
# dialogs: {id: int, persons: [string], messages: {id: int, author: string, content: string}}


class Session:
    def __init__(self, client, address):
        self.commands = [
            self.auth,
            self.register,
            self.open_dialog,
            self.open_chat,
            self.send_message,
            self.send_file,
            self.create_dialog,
            self.create_chat,
            self.add_to_chat,
            self.close_chat,
            self.close_dialog,
            self.get_dialogs,
            self.get_chats
        ]
        self.client = client
        self.address = address
        self.db_client = pymongo.MongoClient('localhost', port=27017)
        self.database = self.db_client['Database']

    def start(self):
        while True:
            try:
                data = self.client.recv(SIZE)
                if data:
                    if data[0] < len(self.commands):
                        self.commands[data[0]]()
                else:
                    raise socket.error('Client disconnected')
            except:
                self.client.close()
                return False

    def auth(self):
        certificates = self.database['Certificates']
        self.client.sendall(bytes([0]))
        login = self.client.recv(SIZE).decode('utf16')
        self.client.sendall(bytes([0]))
        password = self.client.recv(SIZE).decode('utf16')
        if certificates.find_one({"login": login, "password": password}) is None:
            self.client.sendall(bytes([1]))
            return
        else:
            self.client.sendall(bytes([0]))

    def register(self):
        certificates = self.database['Certificates']
        self.client.sendall(bytes([0]))
        login = self.client.recv(SIZE).decode('utf16')
        self.client.sendall(bytes([0]))
        password = self.client.recv(SIZE).decode('utf16')
        if certificates.find_one({"login": login}) is not None:
            self.client.sendall(bytes([1]))
            return
        self.client.sendall(bytes([0]))
        key = self.client.recv(SIZE)
        certificates.insert_one({"login": login, "password": password, "public_key": key, "chats": [], "dialogs": []})
        print('updated')
        return

    def open_dialog(self):
        pass

    def open_chat(self):
        pass

    def send_message(self):
        pass

    def send_file(self):
        pass

    def create_dialog(self):
        pass

    def create_chat(self):
        pass

    def add_to_chat(self):
        pass

    def __subscribe_to_changes__(self):
        pass

    def close_chat(self):
        pass

    def close_dialog(self):
        pass

    def __unsubscribe__(self):
        pass

    def get_dialogs(self):
        pass

    def get_chats(self):
        pass


class ThreadedServer(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))

    def listen(self):
        self.sock.listen(10)
        while True:
            client, address = self.sock.accept()
            client.settimeout(600)
            session = Session(client, address)
            threading.Thread(target=session.start).start()
            # self.listenToClient(client, address)



if __name__ == "__main__":
    ThreadedServer('', 8080).listen()
