from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import pymongo
import os

load_dotenv()
mongodb_user = os.getenv("MONGODB_USER")
mongodb_password = os.getenv("MONGODB_PASSWORD")

uri = f"mongodb+srv://{mongodb_user}:{mongodb_password}@innolympicscluster.tg5iy.mongodb.net/?retryWrites=true&w=majority&appName=innolympicscluster"

client = pymongo.MongoClient(uri)

try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
    db = client['alix_db']
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    raise e
