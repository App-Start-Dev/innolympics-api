from flask import Blueprint, request, jsonify
from src.config.mongodb import client
from bson import ObjectId
from datetime import datetime
from src.middleware.auth_middleware import token_required
import random
import string

support_group_controller = Blueprint("support_group_controller", __name__, url_prefix="/api")
db = client['alix_db']
child_collection = db['child']
support_group_collection = db['support_group']

def generate_new_code():
    return ''.join(random.choices(string.digits, k=6))

@support_group_controller.route("/support-group/join", methods=["POST"])
@token_required
def join_support_group():
    try:
        data = request.json
        if 'code' not in data:
            return jsonify({"error": "Support group code is required"}), 400
            
        # Get user information from token
        user_uid = request.user['uid']
        user_name = request.user.get('name', 'Support Member')
        
        # Find child with this support code
        child = child_collection.find_one({"support_code": data['code']})
        if not child:
            return jsonify({"error": "Invalid support group code"}), 404
            
        # Check if user is already in the support group
        support_group = support_group_collection.find_one({
            "_id": ObjectId(child['support_group_id']),
            "members.uid": user_uid
        })
        
        if support_group:
            return jsonify({"error": "You are already a member of this support group"}), 400
            
        # Add user to support group
        result = support_group_collection.update_one(
            {"_id": ObjectId(child['support_group_id'])},
            {
                "$push": {
                    "members": {
                        "uid": user_uid,
                        "name": user_name,
                        "role": "none",
                        "joined_at": datetime.utcnow()
                    }
                },
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        if result.modified_count:
            return jsonify({
                "message": "Successfully joined support group",
                "child_name": child['name']
            }), 200
        return jsonify({"error": "Failed to join support group"}), 500
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@support_group_controller.route("/support-group/<child_id>/members", methods=["GET"])
@token_required
def get_support_group_members(child_id):
    try:
        # Get user information
        user_uid = request.user['uid']
        
        # Find child and verify access
        child = child_collection.find_one({
            "_id": ObjectId(child_id),
            "$or": [
                {"parent_uid": user_uid},
                {"support_group_id": {"$exists": True}}
            ]
        })
        
        if not child:
            return jsonify({"error": "Child not found or access denied"}), 404
            
        # Get support group members
        support_group = support_group_collection.find_one({
            "_id": ObjectId(child['support_group_id']),
            "members.uid": user_uid
        })
        
        if not support_group:
            return jsonify({"error": "Support group not found or access denied"}), 404
            
        return jsonify({
            "child_name": child['name'],
            "support_code": child['support_code'],
            "members": support_group['members']
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@support_group_controller.route("/support-group/<child_id>/members/<member_uid>/name", methods=["PUT"])
@token_required
def update_member_name(child_id, member_uid):
    try:
        data = request.json
        if 'name' not in data:
            return jsonify({"error": "Name is required"}), 400
            
        # Get user information
        user_uid = request.user['uid']
        
        # Verify it's the member updating their own name
        if user_uid != member_uid:
            return jsonify({"error": "You can only update your own name"}), 403
            
        # Find child and verify member access
        child = child_collection.find_one({"_id": ObjectId(child_id)})
        if not child:
            return jsonify({"error": "Child not found"}), 404
            
        # Update member name
        result = support_group_collection.update_one(
            {
                "_id": ObjectId(child['support_group_id']),
                "members.uid": member_uid
            },
            {
                "$set": {
                    "members.$.name": data['name'],
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count:
            return jsonify({"message": "Name updated successfully"}), 200
        return jsonify({"error": "Member not found"}), 404
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@support_group_controller.route("/support-group/<child_id>/members/<member_uid>/role", methods=["PUT"])
@token_required
def update_member_role(child_id, member_uid):
    try:
        data = request.json
        if 'role' not in data:
            return jsonify({"error": "Role is required"}), 400
            
        # Get parent information
        parent_uid = request.user['uid']
        
        # Verify parent access
        child = child_collection.find_one({
            "_id": ObjectId(child_id),
            "parent_uid": parent_uid
        })
        
        if not child:
            return jsonify({"error": "Child not found or access denied"}), 404
            
        # Update member role
        result = support_group_collection.update_one(
            {
                "_id": ObjectId(child['support_group_id']),
                "members.uid": member_uid
            },
            {
                "$set": {
                    "members.$.role": data['role'],
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count:
            return jsonify({"message": "Member role updated successfully"}), 200
        return jsonify({"error": "Member not found"}), 404
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@support_group_controller.route("/support-group/<child_id>/members/<member_uid>", methods=["DELETE"])
@token_required
def remove_member(child_id, member_uid):
    try:
        # Get parent information
        parent_uid = request.user['uid']
        
        # Verify parent access
        child = child_collection.find_one({
            "_id": ObjectId(child_id),
            "parent_uid": parent_uid
        })
        
        if not child:
            return jsonify({"error": "Child not found or access denied"}), 404
            
        # Remove member from support group
        result = support_group_collection.update_one(
            {"_id": ObjectId(child['support_group_id'])},
            {
                "$pull": {"members": {"uid": member_uid}},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        if result.modified_count:
            return jsonify({"message": "Member removed successfully"}), 200
        return jsonify({"error": "Member not found"}), 404
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@support_group_controller.route("/support-group/<child_id>/code", methods=["POST"])
@token_required
def regenerate_code(child_id):
    try:
        # Get parent information
        parent_uid = request.user['uid']
        
        # Verify parent access
        child = child_collection.find_one({
            "_id": ObjectId(child_id),
            "parent_uid": parent_uid
        })
        
        if not child:
            return jsonify({"error": "Child not found or access denied"}), 404
            
        # Generate new code
        new_code = generate_new_code()
        
        # Update code in child document
        result = child_collection.update_one(
            {"_id": ObjectId(child_id)},
            {"$set": {"support_code": new_code}}
        )
        
        if result.modified_count:
            return jsonify({
                "message": "Support group code regenerated successfully",
                "new_code": new_code
            }), 200
        return jsonify({"error": "Failed to regenerate code"}), 500
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
