import socket
import threading
import rsa
import pymongo


SIZE = 2048
class ThreadedServer(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.db = pymongo.MongoClient('localhost', port=27017)['Database']
        self.certificates = self.db['Certificates']
        # self.certificates = {} #{login:{password:... public_key:... chats:[] dialogs:[]}}
        self.chats = {} #{chat_id: {messages:[], public_key:... private_key:...}}
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
            self.close_dialog
        ]
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))

    def listen(self):
        self.sock.listen(10)
        while True:
            client, address = self.sock.accept()
            client.settimeout(60)
            threading.Thread(target=self.listenToClient, args=(client, address)).start()
            # self.listenToClient(client, address)

    def listenToClient(self, client, address):
        db_client = pymongo.MongoClient('localhost', port=27017)
        database = db_client['Database']
        while True:
            try:
                data = client.recv(SIZE)
                if data:
                    if data[0] < len(self.commands):
                        self.commands[data[0]](database, client)
                else:
                    raise socket.error('Client disconnected')
            except:
                client.close()
                return False

    def auth(self):
        pass

    def register(self, database, client):
        certificates = database['Certificates']
        client.sendall(bytes([0]))
        login = client.recv(SIZE).decode('utf16')
        client.sendall(bytes([0]))
        password = client.recv(SIZE).decode('utf16')
        if certificates.find_one({"login": login}) is not None:
            client.sendall(bytes([1]))
            return
        client.sendall(bytes([0]))
        key = client.recv(SIZE)
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

if __name__ == "__main__":
    ThreadedServer('', 8080).listen()
