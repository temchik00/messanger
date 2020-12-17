import socket
import threading
import rsa
import pymongo
import json
from bson import ObjectId
import pickle

SIZE = 2048


# certificates: {login:str, password:str, public_key:binary, chats:[int], dialogs:[int]}

# dialogs_info: {_id: int, persons: [string]}
# dialogs_messages: {dialog_id: int, _id: int, sender: string,
#                    content_for_sender: string, content_for_receiver:string, content_type: int}

# chats_info: {_id: int, persons: [string], title: string, key: binary}
# chats_messages: {chat_id: int, _id: int, author: string, content: string, content_type: int}


class Session:
    def __init__(self, client, address):
        self.commands = [
            self.auth,
            self.register,
            self.get_dialog_messages,
            self.open_chat,
            self.send_message_to_dialog,
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

    def get_dialog_messages(self):
        dialogs = self.database['DialogsInfo']
        dialog_messages = self.database['DialogsMessages']
        self.client.sendall(bytes([0]))
        dialog_id = ObjectId(self.client.recv(SIZE).decode('utf16'))
        dialog = dialogs.find_one({'_id': dialog_id, 'persons': self.user['login']})
        if dialog is None:
            self.client.sendall(bytes([1]))
            return
        self.client.sendall(bytes([0]))
        self.client.recv(SIZE)
        messages_to_send = []
        messages = dialog_messages.find({'dialog_id': dialog_id}).limit(20)
        for message in messages:
            if message['sender'] == self.user['login']:
                message['content'] = message['content_for_sender']
            else:
                message['content'] = message['content_for_receiver']
            message.pop('content_for_sender', None)
            message.pop('content_for_receiver', None)
            message['_id'] = str(message['_id'])
            message['dialog_id'] = str(message['dialog_id'])
            messages_to_send.append(message)
        messages_to_send = pickle.dumps(messages_to_send)

        def encrypt(x):
            return rsa.encrypt(x, self.public_key)
        self.__send_big_data__(messages_to_send, encrypt)

    def open_chat(self):
        pass

    def send_message_to_dialog(self):
        certificates = self.database['Certificates']
        dialogs = self.database['DialogsInfo']
        dialog_messages = self.database['DialogsMessages']
        self.client.sendall(bytes([0]))
        dialog_id = ObjectId(self.client.recv(SIZE).decode('utf16'))
        dialog = dialogs.find_one({'_id': dialog_id, 'persons': self.user['login']})
        if dialog is None:
            self.client.sendall(bytes([1]))
            return
        self.client.sendall(bytes([0]))
        self.client.recv(SIZE)
        dialog['persons'].remove(self.user['login'])
        receiver = dialog['persons'][0]
        receiver = certificates.find_one({'login': receiver})
        self.client.sendall(receiver['public_key'])
        receiver_message = self.__receive_big_data__()
        self.client.sendall(bytes([0]))
        sender_message = self.__receive_big_data__()
        dialog_messages.insert_one({'dialog_id': dialog_id, 'sender': self.user['login'],
                                    'content_for_sender': sender_message,
                                    'content_for_receiver': receiver_message, 'content_type': 0})
        self.client.sendall(bytes([0]))

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

    def __receive_big_data__(self):
        data = bytearray()
        data_part = self.client.recv(SIZE)
        stop_sign = bytes([0])
        while data_part != stop_sign:
            data.extend(data_part)
            self.client.sendall(stop_sign)
            data_part = self.client.recv(SIZE)
        return bytes(data)

    def __send_big_data__(self, info, encryption_method):
        part_len = 245
        length = len(info)
        parts = length // part_len + (0 if length % part_len == 0 else 1)
        for part_id in range(parts):
            last = (part_id + 1) * part_len
            if last > length:
                last = length
            part = info[part_id * part_len:last]
            encrypted = encryption_method(part)
            self.client.sendall(bytes(encrypted))
            self.client.recv(SIZE)
        self.client.sendall(bytes([0]))


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


if __name__ == "__main__":
    ThreadedServer('', 8080).listen()
