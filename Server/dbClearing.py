import pymongo


db_client = pymongo.MongoClient('localhost', port=27017)
database = db_client['Database']
database['Certificates'].delete_many({})
database['DialogsInfo'].delete_many({})
database['DialogsMessages'].delete_many({})
database['DialogMessagesIds'].delete_many({})
database['ChatsInfo'].delete_many({})
database['ChatsMessages'].delete_many({})
database['ChatMessagesIds'].delete_many({})
