from flask import Blueprint, request, jsonify
from src.config.mongodb import client
from bson import ObjectId
from datetime import datetime
from src.middleware.auth_middleware import token_required
import random
import string

def generate_support_code():
    return ''.join(random.choices(string.digits, k=6))

child_controller = Blueprint("child_controller", __name__, url_prefix="/api")
db = client['alix_db']
child_collection = db['child']
support_group_collection = db['support_group']

@child_controller.route("/child", methods=["POST"])
@token_required
def create_child():
    try:
        data = request.json
        required_fields = ['name', 'birthday', 'sex', 'asd_type']
        
        # Validate required fields
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Get parent_uid from the authenticated user
        parent_uid = request.user['uid']
        parent_name = request.user.get('name', 'Parent')  # Get parent name from Firebase
        
        # Generate support group code
        support_code = generate_support_code()
        
        # Create support group document
        support_group = {
            "code": support_code,
            "members": [{
                "uid": parent_uid,
                "name": parent_name,
                "role": "parent",
                "joined_at": datetime.utcnow()
            }],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        support_group_result = support_group_collection.insert_one(support_group)
        
        # Create child document with support group reference
        child = {
            "name": data['name'],
            "birthday": data['birthday'],
            "sex": data['sex'],
            "asd_type": data['asd_type'],
            "parent_uid": parent_uid,
            "support_group_id": str(support_group_result.inserted_id),
            "support_code": support_code,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = child_collection.insert_one(child)
        
        # Return the created child with ID
        child['_id'] = str(result.inserted_id)
        return jsonify(child), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@child_controller.route("/child", methods=["GET"])
@token_required
def get_all_children():
    try:
        # Get parent_uid from the authenticated user
        parent_uid = request.user['uid']
        
        # Query children for this parent only
        children = []
        for child in child_collection.find({"parent_uid": parent_uid}):
            child['_id'] = str(child['_id'])
            children.append(child)
        return jsonify(children), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@child_controller.route("/child/<id>", methods=["GET"])
@token_required
def get_child(id):
    try:
        # Get parent_uid from the authenticated user
        parent_uid = request.user['uid']
        
        # Query child with both ID and parent_uid for security
        child = child_collection.find_one({
            "_id": ObjectId(id),
            "parent_uid": parent_uid
        })
        
        if child:
            child['_id'] = str(child['_id'])
            return jsonify(child), 200
        return jsonify({"error": "Child not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@child_controller.route("/child/<id>", methods=["PUT"])
@token_required
def update_child(id):
    try:
        # Get parent_uid from the authenticated user
        parent_uid = request.user['uid']
        
        data = request.json
        
        # Prepare update data
        update_data = {
            "updated_at": datetime.utcnow()
        }
        
        # Add fields that are present in the request
        for field in ['name', 'birthday', 'sex', 'asd_type']:
            if field in data:
                update_data[field] = data[field]
        
        # Update child only if it belongs to the authenticated parent
        result = child_collection.update_one(
            {
                "_id": ObjectId(id),
                "parent_uid": parent_uid
            },
            {"$set": update_data}
        )
        
        if result.modified_count:
            child = child_collection.find_one({"_id": ObjectId(id)})
            child['_id'] = str(child['_id'])
            return jsonify(child), 200
        return jsonify({"error": "Child not found or unauthorized"}), 404
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@child_controller.route("/child/<id>", methods=["DELETE"])
@token_required
def delete_child(id):
    try:
        # Get parent_uid from the authenticated user
        parent_uid = request.user['uid']
        
        # Delete child only if it belongs to the authenticated parent
        result = child_collection.delete_one({
            "_id": ObjectId(id),
            "parent_uid": parent_uid
        })
        
        if result.deleted_count:
            return jsonify({"message": "Child deleted successfully"}), 200
        return jsonify({"error": "Child not found or unauthorized"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
