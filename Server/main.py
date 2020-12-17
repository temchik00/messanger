import socket
import threading
import rsa
import pymongo
import json


SIZE = 2048


# certificates: {login:str, password:str, public_key:binary, chats:[int], dialogs:[int]}

# dialogs_info: {_id: int, persons: [string]}
# dialogs_messages: {dialog_id: int, _id: int, author: string, content: string, content_type: int}

# chats_info: {_id: int, persons: [string], title: string, key: binary}
# chats_messages: {chat_id: int, _id: int, author: string, content: string, content_type: int}


class Session:
    def __init__(self, client, address):
        self.commands = [
            self.auth,
            self.register,
            self.open_dialog,
            self.open_chat,
            self.send_message,
            self.send_file,
            self.start_dialog,
            self.create_chat,
            self.add_to_chat,
            self.close_chat,
            self.close_dialog,
            self.get_dialogs,
            self.get_chats
        ]
        self.user = None
        self.client = client
        self.address = address
        self.db_client = pymongo.MongoClient('localhost', port=27017)
        self.database = self.db_client['Database']
        self.public_key = None

    def start(self):
        while True:
            try:
                data = self.client.recv(SIZE)
                if data:
                    if data[0] < len(self.commands):
                        self.commands[data[0]]()
                else:
                    raise socket.error('Client disconnected')
            except BaseException as error:
                print(error)

                self.client.close()
                return False

    def auth(self):
        certificates = self.database['Certificates']
        self.client.sendall(bytes([0]))
        login = self.client.recv(SIZE).decode('utf16')
        self.client.sendall(bytes([0]))
        password = self.client.recv(SIZE).decode('utf16')
        user = certificates.find_one({"login": login, "password": password})
        if user is None:
            self.client.sendall(bytes([1]))
            return
        else:
            self.public_key = rsa.PublicKey.load_pkcs1(user['public_key'])
            self.user = dict(user)
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
        return

    def open_dialog(self):
        pass

    def open_chat(self):
        pass

    def send_message(self):
        pass

    def send_file(self):
        pass

    def start_dialog(self):
        self.client.sendall(bytes([0]))
        other_user = self.client.recv(SIZE)
        other_user = self.database['Certificates'].find_one({'login': other_user.decode('utf16')})
        if other_user is None:
            self.client.sendall(bytes([1]))
            return
        user = self.database['Certificates'].find_one({'login': self.user['login']})
        for id1 in other_user["dialogs"]:
            if id1 in user["dialogs"]:
                self.client.sendall(bytes([1]))
                return
        dialog_info = self.database['DialogsInfo'].insert_one({'persons': [user['login'], other_user['login']]})
        user['dialogs'].append(dialog_info.inserted_id)
        other_user['dialogs'].append(dialog_info.inserted_id)
        self.database['Certificates'].update_one({'_id': user['_id']}, {'$set':
                                                 {'dialogs': user['dialogs']}})
        self.database['Certificates'].update_one({'_id': other_user['_id']}, {'$set':
                                                 {'dialogs': other_user['dialogs']}})
        self.client.sendall(bytes([0]))

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
        dialog_ids = self.database['Certificates'].find_one({'login': self.user['login']})['dialogs']
        dialogs = self.database['DialogsInfo'].find({'_id': {'$in': dialog_ids}})
        dialog_list = []
        for dialog in dialogs:
            dialog['_id'] = str(dialog['_id'])
            dialog_list.append(dict(dialog))
        dialogs = json.dumps(dialog_list).encode("utf16")
        encrypted = rsa.encrypt(dialogs, self.public_key)
        self.client.sendall(encrypted)

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
