import socket
import threading
import rsa
import pymongo
import json
from bson import ObjectId
import pickle
from Crypto.Cipher import AES
import os

SIZE = 2048


# certificates: {login:str, password:str, public_key:binary, chats:[int], dialogs:[int]}

# dialogs_info: {_id: ObjectId, persons: [string]}
# dialogs_messages: {dialog_id: ObjectId, _id: int, sender: string, content_for_sender: string,
#                    content_for_receiver:string, content_type: int,
#                    ?sender_file_id: ObjectId, ?receiver_file_id: ObjectId}
# dialog_messages_ids: {dialog_id: ObjectId, available_id: int}

# chats_info: {_id: ObjectId, persons: [string], title: string, key: binary}
# chats_messages: {chat_id: ObjectId, _id: int, sender: string, content: string,
#                  content_type: int, nonce: byte, ?file_id: ObjectId}
# chats_messages_ids: {chat_id: ObjectId, available_id: int}

# files: {_id: ObjectId, file: binary, ?nonce: byte}


class Session:
    def __init__(self, client, address):
        self.commands = [
            self.auth,
            self.register,
            self.get_dialog_messages,
            self.send_message_to_dialog,
            self.send_file_to_dialog,
            self.start_dialog,
            self.create_chat,
            self.add_to_chat,
            self.get_dialogs,
            self.get_chats,
            self.get_dialog_messages_after_id,
            self.send_message_to_chat,
            self.get_chat_messages,
            self.get_chat_messages_after_id,
            self.get_chat_members,
            self.get_file,
            self.send_file_to_chat
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

    def __encrypt_dialog_message__(self, message):
        if message['sender'] == self.user['login']:
            message['content'] = message['content_for_sender']
            if message['content_type'] == 1:
                message['file_id'] = rsa.encrypt(str(message['sender_file_id']).encode('utf-16'), self.public_key)
                message.pop('sender_file_id', None)
                message.pop('receiver_file_id', None)
        else:
            message['content'] = message['content_for_receiver']
            if message['content_type'] == 1:
                message['file_id'] = rsa.encrypt(str(message['receiver_file_id']).encode('utf-16'), self.public_key)
                message.pop('sender_file_id', None)
                message.pop('receiver_file_id', None)

        message.pop('content_for_sender', None)
        message.pop('content_for_receiver', None)
        message['dialog_id'] = rsa.encrypt(str(message['dialog_id']).encode('utf-16'), self.public_key)
        message['sender'] = rsa.encrypt(message['sender'].encode('utf-16'), self.public_key)
        return message

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
        messages = dialog_messages.find({'dialog_id': dialog_id})
        for message in messages:
            messages_to_send.append(self.__encrypt_dialog_message__(message))
        messages_to_send = pickle.dumps(messages_to_send)
        self.__send_big_data__(messages_to_send)

    def get_dialog_messages_after_id(self):
        dialogs = self.database['DialogsInfo']
        dialog_messages = self.database['DialogsMessages']
        self.client.sendall(bytes([0]))
        dialog_id = ObjectId(self.client.recv(SIZE).decode('utf16'))
        dialog = dialogs.find_one({'_id': dialog_id, 'persons': self.user['login']})
        if dialog is None:
            self.client.sendall(bytes([1]))
            return
        self.client.sendall(bytes([0]))
        last_id = int.from_bytes(self.client.recv(SIZE), 'big', signed=True)
        print(last_id)
        messages_to_send = []
        messages = dialog_messages.find({'dialog_id': dialog_id, '_id': {'$gte': last_id}})
        for message in messages:
            messages_to_send.append(self.__encrypt_dialog_message__(message))
        messages_to_send = pickle.dumps(messages_to_send)
        self.__send_big_data__(messages_to_send)

    def send_message_to_dialog(self):
        certificates = self.database['Certificates']
        dialogs = self.database['DialogsInfo']
        dialog_messages = self.database['DialogsMessages']
        messages_ids = self.database['DialogMessagesIds']
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
        message_id = messages_ids.find_one({'dialog_id': dialog_id})['available_id']
        dialog_messages.insert_one({'_id': message_id, 'dialog_id': dialog_id, 'sender': self.user['login'],
                                    'content_for_sender': sender_message,
                                    'content_for_receiver': receiver_message, 'content_type': 0})
        messages_ids.update_one({'dialog_id': dialog_id}, {'$set': {'available_id': (message_id + 1)}})
        self.client.sendall(bytes([0]))

    def send_file_to_dialog(self):
        certificates = self.database['Certificates']
        dialogs = self.database['DialogsInfo']
        dialog_messages = self.database['DialogsMessages']
        messages_ids = self.database['DialogMessagesIds']
        files = self.database['Files']
        self.client.sendall(bytes([0]))
        dialog_id = ObjectId(self.client.recv(SIZE).decode('utf16'))
        dialog = dialogs.find_one({'_id': dialog_id, 'persons': self.user['login']})
        if dialog is None:
            self.client.sendall(bytes([1]))
            return
        self.client.sendall(bytes([0]))
        dialog['persons'].remove(self.user['login'])
        receiver = dialog['persons'][0]
        receiver = certificates.find_one({'login': receiver})
        sender_filename = self.client.recv(SIZE)
        self.client.sendall(bytes([0]))
        sender_file = self.__receive_big_data__()
        file_info = files.insert_one({'file': sender_file})
        sender_file_id = file_info.inserted_id
        self.client.sendall(receiver['public_key'])
        receiver_filename = self.client.recv(SIZE)
        self.client.sendall(bytes([0]))
        receiver_file = self.__receive_big_data__()
        file_info = files.insert_one({'file': receiver_file})
        receiver_file_id = file_info.inserted_id
        message_id = messages_ids.find_one({'dialog_id': dialog_id})['available_id']
        dialog_messages.insert_one({'_id': message_id, 'dialog_id': dialog_id, 'sender': self.user['login'],
                                    'content_for_sender': sender_filename,
                                    'content_for_receiver': receiver_filename, 'content_type': 1,
                                    'sender_file_id': sender_file_id, 'receiver_file_id': receiver_file_id})
        messages_ids.update_one({'dialog_id': dialog_id}, {'$set': {'available_id': (message_id + 1)}})
        self.client.sendall(bytes([0]))

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
        self.database['DialogMessagesIds'].insert_one({'dialog_id': dialog_info.inserted_id, 'available_id': 0})
        self.client.sendall(bytes([0]))

    def create_chat(self):
        self.client.sendall(bytes([0]))
        title = self.client.recv(SIZE).decode('utf-16')
        key = os.urandom(32)
        chat_info = self.database['ChatsInfo'].insert_one({'persons': [self.user['login']],
                                                           'title': title, 'key': key})
        user = self.database['Certificates'].find_one({'login': self.user['login']})
        user['chats'].append(chat_info.inserted_id)
        self.database['Certificates'].update_one({'_id': user['_id']},
                                                 {'$set': {'chats': user['chats']}})
        self.database['ChatMessagesIds'].insert_one({'chat_id': chat_info.inserted_id, 'available_id': 0})
        self.client.sendall(bytes([0]))

    def add_to_chat(self):
        certificates = self.database['Certificates']
        chats = self.database['ChatsInfo']
        self.client.sendall(bytes([0]))
        member_nick = self.client.recv(SIZE).decode('utf-16')
        member_to_add = certificates.find_one({'login': member_nick})
        if member_to_add is None:
            self.client.sendall(bytes([1]))
            return
        self.client.sendall(bytes([0]))
        chat_id = ObjectId(self.client.recv(SIZE).decode('utf16'))
        chat = chats.find_one({'_id': chat_id, 'persons': self.user['login']})
        if chat is None or chat_id in member_to_add['chats']:
            self.client.sendall(bytes([1]))
            return
        self.client.sendall(bytes([0]))
        self.client.recv(SIZE)
        chat['persons'].append(member_nick)
        chats.update_one({'_id': chat_id}, {'$set': {'persons': chat['persons']}})
        member_to_add['chats'].append(chat_id)
        certificates.update_one({'_id': member_to_add['_id']}, {'$set': {'chats': member_to_add['chats']}})
        self.client.sendall(bytes([0]))

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
        chat_ids = self.database['Certificates'].find_one({'login': self.user['login']})['chats']
        chats = self.database['ChatsInfo'].find({'_id': {'$in': chat_ids}})
        chat_list = []
        for chat in chats:
            chat['_id'] = str(chat['_id'])
            chat_list.append(dict(chat))
        chats = pickle.dumps(chat_list)
        encrypted = rsa.encrypt(chats, self.public_key)
        self.client.sendall(encrypted)

    def send_message_to_chat(self):
        chats = self.database['ChatsInfo']
        chat_messages = self.database['ChatsMessages']
        messages_ids = self.database['ChatMessagesIds']
        self.client.sendall(bytes([0]))
        chat_id = ObjectId(self.client.recv(SIZE).decode('utf16'))
        chat = chats.find_one({'_id': chat_id, 'persons': self.user['login']})
        if chat is None:
            self.client.sendall(bytes([1]))
            return
        self.client.sendall(bytes([0]))
        nonce = self.client.recv(SIZE)
        self.client.sendall(bytes([0]))
        encrypted_message = self.__receive_big_data__()
        message_id = messages_ids.find_one({'chat_id': chat_id})['available_id']
        chat_messages.insert_one({'chat_id': chat_id, '_id': message_id, 'sender': self.user['login'],
                                  'content': encrypted_message, 'content_type': 0, 'nonce': nonce})
        messages_ids.update_one({'chat_id': chat_id}, {'$set': {'available_id': (message_id + 1)}})
        self.client.sendall(bytes([0]))

    def __encrypt_chat_message__(self, message):
        message['chat_id'] = rsa.encrypt(str(message['chat_id']).encode('utf-16'), self.public_key)
        message['sender'] = rsa.encrypt(message['sender'].encode('utf-16'), self.public_key)
        message['nonce'] = rsa.encrypt(message['nonce'], self.public_key)
        return message

    def get_chat_messages(self):
        chats = self.database['ChatsInfo']
        chat_messages = self.database['ChatsMessages']
        self.client.sendall(bytes([0]))
        chat_id = ObjectId(self.client.recv(SIZE).decode('utf16'))
        chat = chats.find_one({'_id': chat_id, 'persons': self.user['login']})
        if chat is None:
            self.client.sendall(bytes([1]))
            return
        self.client.sendall(bytes([0]))
        self.client.recv(SIZE)
        messages_to_send = []
        messages = chat_messages.find({'chat_id': chat_id})
        for message in messages:
            messages_to_send.append(self.__encrypt_chat_message__(message))
        messages_to_send = pickle.dumps(messages_to_send)
        self.__send_big_data__(messages_to_send)

    def get_chat_messages_after_id(self):
        chats = self.database['ChatsInfo']
        chat_messages = self.database['ChatsMessages']
        self.client.sendall(bytes([0]))
        chat_id = ObjectId(self.client.recv(SIZE).decode('utf16'))
        chat = chats.find_one({'_id': chat_id, 'persons': self.user['login']})
        if chat is None:
            self.client.sendall(bytes([1]))
            return
        self.client.sendall(bytes([0]))
        last_id = int.from_bytes(self.client.recv(SIZE), 'big', signed=True)
        messages_to_send = []
        messages = chat_messages.find({'chat_id': chat_id, '_id': {'$gte': last_id}})
        for message in messages:
            messages_to_send.append(self.__encrypt_chat_message__(message))

        messages_to_send = pickle.dumps(messages_to_send)
        self.__send_big_data__(messages_to_send)

    def get_chat_members(self):
        chats = self.database['ChatsInfo']
        self.client.sendall(bytes([0]))
        chat_id = ObjectId(self.client.recv(SIZE).decode('utf16'))
        chat = chats.find_one({'_id': chat_id, 'persons': self.user['login']})
        if chat is None:
            self.client.sendall(bytes([1]))
            return
        self.client.sendall(bytes([0]))
        self.client.recv(SIZE)
        members = chat['persons']
        encrypted = rsa.encrypt(pickle.dumps(members), self.public_key)
        self.client.sendall(encrypted)

    def send_file_to_chat(self):
        chats = self.database['ChatsInfo']
        chat_messages = self.database['ChatsMessages']
        messages_ids = self.database['ChatMessagesIds']
        files = self.database['Files']
        self.client.sendall(bytes([0]))
        chat_id = ObjectId(self.client.recv(SIZE).decode('utf16'))
        chat = chats.find_one({'_id': chat_id, 'persons': self.user['login']})
        if chat is None:
            self.client.sendall(bytes([1]))
            return
        self.client.sendall(bytes([0]))
        filename_nonce = self.client.recv(SIZE)
        self.client.sendall(bytes([0]))
        encrypted_filename = self.client.recv(SIZE)
        self.client.sendall(bytes([0]))
        file_nonce = self.client.recv(SIZE)
        self.client.sendall(bytes([0]))
        encrypted_file = self.__receive_big_data__()
        file_info = files.insert_one({'file': encrypted_file, 'nonce': file_nonce})
        message_id = messages_ids.find_one({'chat_id': chat_id})['available_id']
        chat_messages.insert_one({'chat_id': chat_id, '_id': message_id, 'sender': self.user['login'],
                                  'content': encrypted_filename, 'content_type': 1, 'nonce': filename_nonce,
                                  'file_id': file_info.inserted_id})
        messages_ids.update_one({'chat_id': chat_id}, {'$set': {'available_id': (message_id + 1)}})
        self.client.sendall(bytes([0]))

    def get_file(self):
        files = self.database['Files']
        self.client.sendall(bytes([0]))
        file_id = ObjectId(self.client.recv(SIZE).decode('utf16'))
        file = files.find_one({'_id': file_id})
        self.__send_big_data__(pickle.dumps(file))

    def __receive_big_data__(self):
        data = bytearray()
        data_part = self.client.recv(SIZE)
        stop_sign = bytes([0])
        while data_part != stop_sign:
            data.extend(data_part)
            self.client.sendall(stop_sign)
            data_part = self.client.recv(SIZE)
        return bytes(data)

    def __send_big_data__(self, info):
        length = len(info)
        parts = length // SIZE + (0 if length % SIZE == 0 else 1)
        for part_id in range(parts):
            last = (part_id + 1) * SIZE
            if last > length:
                last = length
            part = info[part_id * SIZE:last]
            self.client.sendall(part)
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
