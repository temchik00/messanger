import pymongo
client = pymongo.MongoClient('localhost', port=27017)
db = client['Database']
certificates = db['Certificates']
certificates.insert_one({'test': 'test'})
print("asd")
print(certificates.find_one({"test": "test"}))
