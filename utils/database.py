import os
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "thumbai")
client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=10000)
db = client[MONGODB_DATABASE]
users_collection = db["users"]
thumbnails_collection = db["thumbnails"]