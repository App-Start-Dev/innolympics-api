from flask import Blueprint, request, jsonify
from src.config.mongodb import client
from bson import ObjectId
from datetime import datetime
import boto3
import os
from src.config.gemini import respond_to_message
import asyncio

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

def serialize_chat(chat):
    return {
        "_id": str(chat["_id"]),
        "child_id": str(chat["child_id"]),
        "question": chat["question"],
        "response": chat["response"],
        "created_at": chat["created_at"].isoformat() if isinstance(chat["created_at"], datetime) else chat["created_at"]
    }

@chat_controller.route("/chat/<child_id>", methods=["GET"])
def list_chats(child_id):
    try:
        chats = collection.find(
            {"child_id": ObjectId(child_id)}, 
            sort=[("created_at", -1)]
        )
        serialized_chats = [serialize_chat(chat) for chat in chats]
        return jsonify({"data": serialized_chats}), 200
    except Exception as e:
        print(f"Error in list_chats: {str(e)}")
        return jsonify({"message": str(e)}), 500

@chat_controller.route("/chat/<child_id>", methods=["POST"])
async def send_chat(child_id):
    try:
        request_data = request.get_json()
        chat_data = {
            "child_id": ObjectId(child_id),
            "question": request_data["question"],
            "created_at": datetime.now()
        }
        
        # Get AI response
        response = await respond_to_message(request_data["question"])
        chat_data["response"] = response
        
        # Insert into database
        chat = collection.insert_one(chat_data)
        
        # Return the complete chat object
        inserted_chat = collection.find_one({"_id": chat.inserted_id})
        return jsonify({"data": serialize_chat(inserted_chat)}), 201
    except KeyError as e:
        print(f"KeyError in send_chat: {str(e)}")
        return jsonify({"message": "Missing required field: question"}), 400
    except Exception as e:
        print(f"Error in send_chat: {str(e)}")
        return jsonify({"message": str(e)}), 500
