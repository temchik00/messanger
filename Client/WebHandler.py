import socket
import rsa
import os
import enum
import json
import pickle
from Crypto.Cipher import AES
import time


class Commands(enum.Enum):
    auth = 0
    register = 1
    get_dialog_messages = 2
    send_message_to_dialog = 3
    send_file_to_dialog = 4
    start_dialog = 5
    create_chat = 6
    add_to_chat = 7
    get_dialogs = 8
    get_chats = 9
    get_dialog_new_messages = 10
    send_message_to_chat = 11
    get_chat_messages = 12
    get_chat_messages_after_id = 13
    get_chat_members = 14
    get_file = 15
    send_file_to_chat = 16


SIZE = 2048


class Client:
    def __init__(self, host="", port=8080):
        self.public_key = None
        self.private_key = None
        self.host = host
        self.port = port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((self.host, self.port))

    def __del__(self):
        self.end_session()
        del self.client_socket
        del self.public_key
        del self.private_key
        del self.host
        del self.port

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
            key = file.read()
            self.public_key = rsa.PublicKey.load_pkcs1(key)

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
            self.client_socket.sendall(self.public_key.save_pkcs1())
            return True
        else:
            return False

    def auth(self, login, password):
        self.__load_keys__()
        self.client_socket.sendall(bytes([Commands.auth.value]))
        self.client_socket.recv(SIZE)
        self.client_socket.sendall(login.encode("utf16"))
        self.client_socket.recv(SIZE)
        self.client_socket.sendall(password.encode("utf16"))
        data = self.client_socket.recv(SIZE)
        if data[0] == 0:
            return True
        else:
            return False

    def get_all_dialogs(self):
        self.client_socket.sendall(bytes([Commands.get_dialogs.value]))
        encrypted_dialogs_info = self.client_socket.recv(SIZE)
        dialogs_info = rsa.decrypt(encrypted_dialogs_info, self.private_key).decode('utf-16')
        dialogs_info = json.loads(dialogs_info)
        return dialogs_info

    def start_dialog(self, other_user):
        self.client_socket.sendall(bytes([Commands.start_dialog.value]))
        self.client_socket.recv(SIZE)
        self.client_socket.sendall(other_user.encode('utf16'))
        data = self.client_socket.recv(SIZE)
        if data[0] == 0:
            return True
        else:
            return False

    def end_session(self):
        self.client_socket.close()

    def __send_big_data__(self, info, encryption_method):
        part_len = 245
        length = len(info)
        parts = length // part_len + (0 if length % part_len == 0 else 1)
        for part_id in range(parts):
            last = (part_id+1) * part_len
            if last > length:
                last = length
            part = info[part_id * part_len:last]
            encrypted = encryption_method(part)
            self.client_socket.sendall(bytes(encrypted))
            self.client_socket.recv(SIZE)
        self.client_socket.sendall(bytes([0]))

    def __receive_big_data__(self):
        data = bytearray()
        data_part = self.client_socket.recv(SIZE)
        stop_sign = bytes([0])
        while data_part != stop_sign:
            data.extend(data_part)
            self.client_socket.sendall(stop_sign)
            data_part = self.client_socket.recv(SIZE)
        return bytes(data)

    def __decrypt_big_data__(self, info, private_key):
        decrypted = bytearray()
        part_len = 256
        length = len(info)
        parts = length // part_len + (0 if length % part_len == 0 else 1)
        for part_id in range(parts):
            last = (part_id + 1) * part_len
            if last > length:
                last = length
            part = info[part_id * part_len:last]
            decrypted.extend(rsa.decrypt(part, private_key))
        return decrypted

    def send_message_to_dialog(self, dialog_id, message):
        self.client_socket.sendall(bytes([Commands.send_message_to_dialog.value]))
        self.client_socket.recv(SIZE)
        self.client_socket.sendall(dialog_id.encode('utf16'))
        result = self.client_socket.recv(SIZE)
        if result[0] != 0:
            return False
        self.client_socket.sendall(bytes([0]))
        receiver_public_key = self.client_socket.recv(SIZE)
        receiver_public_key = rsa.PublicKey.load_pkcs1(receiver_public_key)
        message = message.encode("utf16")

        def encode(x):
            return rsa.encrypt(x, receiver_public_key)
        self.__send_big_data__(message, encode)
        self.client_socket.recv(SIZE)

        def encode(x):
            return rsa.encrypt(x, self.public_key)
        self.__send_big_data__(message, encode)

        result = self.client_socket.recv(SIZE)
        if result[0] != 0:
            return False
        else:
            return True

    def get_dialog_messages(self, dialog_id):
        self.client_socket.sendall(bytes([Commands.get_dialog_messages.value]))
        self.client_socket.recv(SIZE)
        self.client_socket.sendall(dialog_id.encode('utf16'))
        result = self.client_socket.recv(SIZE)
        if result[0] != 0:
            return False
        self.client_socket.sendall(bytes([0]))
        data = self.__receive_big_data__()
        data = pickle.loads(data)
        for message in data:
            message['content'] = self.__decrypt_big_data__(message['content'], self.private_key).decode('utf16')
            message['dialog_id'] = rsa.decrypt(message['dialog_id'], self.private_key).decode('utf-16')
            message['sender'] = rsa.decrypt(message['sender'], self.private_key).decode('utf-16')
            if message['content_type'] == 1:
                message['file_id'] = rsa.decrypt(message['file_id'], self.private_key).decode('utf-16')
        return data

    def get_new_dialog_messages(self, dialog_id, last_id):
        self.client_socket.sendall(bytes([Commands.get_dialog_new_messages.value]))
        self.client_socket.recv(SIZE)
        self.client_socket.sendall(dialog_id.encode('utf16'))
        result = self.client_socket.recv(SIZE)
        if result[0] != 0:
            return False
        self.client_socket.sendall(last_id.to_bytes(4, 'big', signed=True))
        data = self.__receive_big_data__()
        data = pickle.loads(data)
        for message in data:
            message['content'] = self.__decrypt_big_data__(message['content'], self.private_key).decode('utf16')
            message['dialog_id'] = rsa.decrypt(message['dialog_id'], self.private_key).decode('utf-16')
            message['sender'] = rsa.decrypt(message['sender'], self.private_key).decode('utf-16')
            if message['content_type'] == 1:
                message['file_id'] = rsa.decrypt(message['file_id'], self.private_key).decode('utf-16')
        return data

    def create_chat(self, title):
        self.client_socket.sendall(bytes([Commands.create_chat.value]))
        self.client_socket.recv(SIZE)
        self.client_socket.sendall(title.encode('utf16'))
        self.client_socket.recv(SIZE)

    def get_chats(self):
        self.client_socket.sendall(bytes([Commands.get_chats.value]))
        encrypted_chats_info = self.client_socket.recv(SIZE)
        chats_info = rsa.decrypt(encrypted_chats_info, self.private_key)
        chats_info = pickle.loads(chats_info)
        return chats_info

    def send_message_to_chat(self, chat_id, key, message):
        self.client_socket.sendall(bytes([Commands.send_message_to_chat.value]))
        self.client_socket.recv(SIZE)
        self.client_socket.sendall(chat_id.encode('utf-16'))
        result = self.client_socket.recv(SIZE)
        if result[0] != 0:
            return False
        cipher = AES.new(key, AES.MODE_EAX)
        nonce = cipher.nonce
        self.client_socket.sendall(nonce)
        self.client_socket.recv(SIZE)
        encrypted_message = cipher.encrypt(message.encode('utf-16'))

        def encode(x):
            return x
        self.__send_big_data__(encrypted_message, encode)
        self.client_socket.recv(SIZE)
        return True

    def get_chat_messages(self, chat_id, key):
        self.client_socket.sendall(bytes([Commands.get_chat_messages.value]))
        self.client_socket.recv(SIZE)
        self.client_socket.sendall(chat_id.encode('utf-16'))
        result = self.client_socket.recv(SIZE)
        if result[0] != 0:
            return False
        self.client_socket.sendall(bytes([0]))
        data = self.__receive_big_data__()
        data = pickle.loads(data)
        for message in data:
            message['chat_id'] = rsa.decrypt(message['chat_id'], self.private_key).decode('utf-16')
            message['sender'] = rsa.decrypt(message['sender'], self.private_key).decode('utf-16')
            message['nonce'] = rsa.decrypt(message['nonce'], self.private_key)
            cipher = AES.new(key, AES.MODE_EAX, nonce=message['nonce'])
            message['content'] = cipher.decrypt(message['content']).decode('utf-16')
            if message['content_type'] == 1:
                message['file_id'] = rsa.decrypt(message['file_id'], self.private_key).decode('utf-16')
        return data

    def get_new_chat_messages(self, chat_id, last_id, key):
        self.client_socket.sendall(bytes([Commands.get_chat_messages_after_id.value]))
        self.client_socket.recv(SIZE)
        self.client_socket.sendall(chat_id.encode('utf-16'))
        result = self.client_socket.recv(SIZE)
        if result[0] != 0:
            return False
        self.client_socket.sendall(last_id.to_bytes(4, 'big', signed=True))
        data = self.__receive_big_data__()
        data = pickle.loads(data)
        for message in data:
            message['chat_id'] = rsa.decrypt(message['chat_id'], self.private_key).decode('utf-16')
            message['sender'] = rsa.decrypt(message['sender'], self.private_key).decode('utf-16')
            message['nonce'] = rsa.decrypt(message['nonce'], self.private_key)
            cipher = AES.new(key, AES.MODE_EAX, nonce=message['nonce'])
            message['content'] = cipher.decrypt(message['content']).decode('utf-16')
            if message['content_type'] == 1:
                message['file_id'] = rsa.decrypt(message['file_id'], self.private_key).decode('utf-16')
        return data

    def add_member_to_chat(self, chat_id, member_nickname):
        self.client_socket.sendall(bytes([Commands.add_to_chat.value]))
        self.client_socket.recv(SIZE)
        self.client_socket.sendall(member_nickname.encode('utf-16'))
        result = self.client_socket.recv(SIZE)
        if result[0] != 0:
            return False
        self.client_socket.sendall(chat_id.encode('utf-16'))
        result = self.client_socket.recv(SIZE)
        if result[0] != 0:
            return False
        self.client_socket.sendall(bytes([0]))
        self.client_socket.recv(SIZE)
        return True

    def get_chat_members(self, chat_id):
        self.client_socket.sendall(bytes([Commands.get_chat_members.value]))
        self.client_socket.recv(SIZE)
        self.client_socket.sendall(chat_id.encode('utf-16'))
        result = self.client_socket.recv(SIZE)
        if result[0] != 0:
            return False
        self.client_socket.sendall(bytes([0]))
        encrypted = self.client_socket.recv(SIZE)
        members = pickle.loads(rsa.decrypt(encrypted, self.private_key))
        return members

    def send_file_to_dialog(self, dialog_id, filename, file):
        self.client_socket.sendall(bytes([Commands.send_file_to_dialog.value]))
        self.client_socket.recv(SIZE)
        self.client_socket.sendall(dialog_id.encode('utf-16'))
        result = self.client_socket.recv(SIZE)
        if result[0] != 0:
            return False
        self.client_socket.sendall(rsa.encrypt(filename.encode('utf-16'), self.public_key))
        self.client_socket.recv(SIZE)
        def encrypt(x):
            return rsa.encrypt(x, self.public_key)
        self.__send_big_data__(file, encrypt)
        receiver_public_key = self.client_socket.recv(SIZE)
        receiver_public_key = rsa.PublicKey.load_pkcs1(receiver_public_key)

        self.client_socket.sendall(rsa.encrypt(filename.encode('utf-16'), receiver_public_key))
        self.client_socket.recv(SIZE)
        def encrypt(x):
            return rsa.encrypt(x, receiver_public_key)
        self.__send_big_data__(file, encrypt)
        self.client_socket.recv(SIZE)
        return True

    def send_file_to_chat(self, chat_id, key, filename, file):
        self.client_socket.sendall(bytes([Commands.send_file_to_chat.value]))
        self.client_socket.recv(SIZE)
        self.client_socket.sendall(chat_id.encode('utf-16'))
        result = self.client_socket.recv(SIZE)
        if result[0] != 0:
            return False
        cipher = AES.new(key, AES.MODE_EAX)
        nonce = cipher.nonce
        self.client_socket.sendall(nonce)
        self.client_socket.recv(SIZE)
        encrypted_filename = cipher.encrypt(filename.encode('utf-16'))
        self.client_socket.sendall(encrypted_filename)
        self.client_socket.recv(SIZE)

        cipher = AES.new(key, AES.MODE_EAX)
        nonce = cipher.nonce
        self.client_socket.sendall(nonce)
        self.client_socket.recv(SIZE)
        encrypted_file = cipher.encrypt(file)

        def encode(x):
            return x
        self.__send_big_data__(encrypted_file, encode)
        self.client_socket.recv(SIZE)
        return True

    def get_file(self, file_id):
        self.client_socket.sendall(bytes([Commands.get_file.value]))
        self.client_socket.recv(SIZE)
        self.client_socket.sendall(file_id.encode('utf-16'))
        file = self.__receive_big_data__()
        return pickle.loads(file)

if __name__ == "__main__":
    c = Client("", 8080)
    c.register("login", "password")
    c.register("Asd", "password")
    c.auth("Asd", "password")
    c.start_dialog("login")
    dialogs = c.get_all_dialogs()
    c.send_message_to_dialog(dialogs[0]['_id'], """Роман охватывает события на протяжении 12 лет (с 1861 по 1873 годы), развивающиеся на фоне гражданской войны между северными промышленными и южными земледельческими штатами Америки.
Южная красавица Скарлетт О’Хара — наполовину ирландка, наполовину француженка — умеет очаровывать мужчин, но тайно влюблена в сына соседского плантатора Эшли Уилкса. Чтобы не допустить свадьбы Эшли с его кузиной Мелани Гамильтон, Скарлетт решается признаться ему в любви, надеясь на тайное бракосочетание с возлюбленным. Благовоспитанный Эшли не готов нарушить данное слово и отказаться от союза с кузиной. Скарлетт негодует и даёт Эшли пощёчину. Невольный свидетель любовной сцены, человек сомнительной репутации Ретт Батлер появляется перед Скарлетт с усмешкой и обещанием не давать истории огласки.
Поддавшись слепому гневу, Скарлетт принимает предложение Чарльза Гамильтона — брата Мелани, и через две недели выходит замуж за день до свадьбы Эшли.
Начинается война. Потерявшая на войне молодого супруга, 17-летняя Скарлетт производит на свет сына Уэйда Хэмптона. Опечаленная вдовством, Скарлетт ищет возможность скрасить своё безрадостное существование и едет с сыном и служанкой Присси в Атланту к родственникам мужа. Она останавливается в доме тётушки Питтипэт и Мелани, лелея надежду встретиться с Эшли.
В Атланте ей вновь встречается Ретт Батлер, который скрашивает её унылые будни, оказывая знаки внимания. В суматохе войны, когда все торопятся жить, она идёт против принятых в обществе правил и снимает траур раньше времени. Строгие взгляды южан на условности постепенно меняются, война диктует свои правила — привычный мир рушится.
После рождественского отпуска Эшли его жена объявляет о своей беременности. С фронта нет вестей об Эшли, который, вероятно, попал в плен. Тем временем, Ретт Батлер наживается на контрабанде и предлагает Скарлетт стать его любовницей, но получает отказ.""")
    print(c.get_dialog_messages(dialogs[0]['_id']))
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
