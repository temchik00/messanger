import rsa
import pymongo


with open("../Client/keys/private_key.PEM", "rb") as file:
    private_key = rsa.PrivateKey.load_pkcs1(file.read())

db_client = pymongo.MongoClient('localhost', port=27017)
database = db_client['Database']
messages = database['DialogsMessages']
message = messages.find_one({'sender': 'Asd'})
message = message['content_for_sender']


def __convert_back__(info, private_key):
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
    decrypted = decrypted.decode('utf16')
    return decrypted


print(__convert_back__(message, private_key))

