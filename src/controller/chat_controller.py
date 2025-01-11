from flask import Blueprint, request, jsonify
from src.config.mongodb import client
from bson import ObjectId
from datetime import datetime
import boto3
import os
from src.config.gemini import respond_to_message

chat_controller = Blueprint("chat_controller", __name__, url_prefix="/api")
db = client['alix_db']
collection = db['chat']

# Initialize S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)
BUCKET_NAME = os.getenv('AWS_BUCKET_NAME')

@chat_controller.route("/chat/<child_id>", methods=["GET"])
def list_chats(child_id):
    try:
        chats = collection.find({"child_id": ObjectId(child_id)}, projection={"_id": True}, sort=[("created_at", -1)])
        return jsonify({"data": chats}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@chat_controller.route("/chat/<child_id>", methods=["POST"])
def send_chat(child_id):
    try:
        request_data = request.get_json()
        request_data["child_id"] = ObjectId(child_id)
        request_data["created_at"] = datetime.now()
        response = respond_to_message(request_data["question"])
        request_data["response"] = response
        chat = collection.insert_one(request_data)
        return jsonify({"data": str(chat.inserted_id)}), 201
    except Exception as e:
        return jsonify({"message": str(e)}), 500
