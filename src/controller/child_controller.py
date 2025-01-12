from flask import Blueprint, request, jsonify
from src.config.mongodb import client
from bson import ObjectId
from datetime import datetime
import random
import string
import boto3
import os
import logging
from src.middleware.auth_middleware import token_required
from werkzeug.utils import secure_filename

child_controller = Blueprint("child_controller", __name__, url_prefix="/api")
db = client['alix_db']
child_collection = db['child']
support_group_collection = db['support_group']

# Initialize S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)
BUCKET_NAME = os.getenv('AWS_BUCKET_NAME')

# File upload settings
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB limit per file
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_support_code():
    return ''.join(random.choices(string.digits, k=6))

def upload_file_to_s3(file, child_id, index):
    try:
        # Generate timestamp-based filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        original_extension = os.path.splitext(secure_filename(file.filename))[1]
        new_filename = f"{timestamp}_{index}{original_extension}"
        
        # Upload to child's folder
        file_key = f"{child_id}/{new_filename}"
        
        # Upload to S3
        s3_client.upload_fileobj(
            file,
            BUCKET_NAME,
            file_key,
            ExtraArgs={'ContentType': file.content_type}
        )
        
        return {
            "success": True,
            "filename": new_filename,
            "original_name": file.filename,
            "content_type": file.content_type
        }
    except Exception as e:
        logging.error(f"Error uploading file {file.filename}: {str(e)}")
        return {
            "success": False,
            "filename": file.filename,
            "error": str(e)
        }

@child_controller.route("/child", methods=["POST"])
@token_required
def create_child():
    try:
        # Log request details
        logging.info(f"Creating child with files. Content-Type: {request.content_type}")
        logging.info(f"Form data: {request.form}")
        logging.info(f"Files: {request.files}")
        
        # Validate form data
        if not request.form:
            return jsonify({"error": "No data provided"}), 400
            
        data = request.form.to_dict()
        required_fields = ['name', 'birthday', 'sex', 'asd_type']
        
        # Validate required fields
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Get parent_uid from the authenticated user
        parent_uid = request.user['uid']
        parent_name = request.user.get('name', 'Parent')
        
        # Generate support group code
        support_code = generate_support_code()
        
        # Create support group document
        support_group = {
            "code": support_code,
            "name": f"{data['name']}'s Support Group",  # Add group name
            "child_id": None,  # Will be set after child creation
            "members": [{
                "uid": parent_uid,
                "name": parent_name,
                "role": "parent",
                "joined_at": datetime.now()
            }],
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        support_group_result = support_group_collection.insert_one(support_group)
        support_group_id = str(support_group_result.inserted_id)
        
        # Create child document
        child = {
            "name": data['name'],
            "birthday": data['birthday'],
            "sex": data['sex'],
            "asd_type": data['asd_type'],
            "parent_uid": parent_uid,
            "support_group_id": support_group_id,
            "support_code": support_code,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        # Log the support group ID for debugging
        logging.info(f"Creating child with support_group_id: {child['support_group_id']}")
        
        result = child_collection.insert_one(child)
        child_id = str(result.inserted_id)
        
        # Update support group with child ID
        support_group_collection.update_one(
            {"_id": support_group_result.inserted_id},
            {"$set": {"child_id": child_id}}
        )

        # Create S3 folder for the child
        try:
            s3_client.put_object(Bucket=BUCKET_NAME, Key=f"{child_id}/")
            logging.info(f"Created S3 folder for child {child_id}")
        except Exception as e:
            logging.error(f"Failed to create S3 folder for child {child_id}: {str(e)}")
            # Delete the child document since folder creation failed
            child_collection.delete_one({"_id": result.inserted_id})
            return jsonify({"error": f"Failed to create storage for child: {str(e)}"}), 500
        
        # Handle file uploads
        uploaded_files = []
        skipped_files = []
        
        if request.files and 'files' in request.files:
            files = request.files.getlist('files')
            logging.info(f"Processing {len(files)} files")
            
            for index, file in enumerate(files):
                if not file or file.filename == '':
                    continue
                    
                if not allowed_file(file.filename):
                    skipped_files.append({
                        "filename": file.filename,
                        "reason": "File type not allowed"
                    })
                    continue
                
                # Upload file to S3
                upload_result = upload_file_to_s3(file, child_id, index)
                
                if upload_result["success"]:
                    uploaded_files.append({
                        "original_name": upload_result["original_name"],
                        "stored_name": upload_result["filename"],
                        "content_type": upload_result["content_type"]
                    })
                else:
                    skipped_files.append({
                        "filename": upload_result["filename"],
                        "reason": upload_result["error"]
                    })
        
        # Convert ObjectId to string for JSON serialization
        child_response = {
            "_id": child_id,
            "name": child["name"],
            "birthday": child["birthday"],
            "sex": child["sex"],
            "asd_type": child["asd_type"],
            "parent_uid": child["parent_uid"],
            "support_group_id": child["support_group_id"],
            "support_code": child["support_code"],
            "created_at": child["created_at"].isoformat(),
            "updated_at": child["updated_at"].isoformat(),
            "files": uploaded_files
        }
        
        if uploaded_files:
            child_response["message"] = f"Child created with {len(uploaded_files)} files uploaded"
        if skipped_files:
            child_response["skipped_files"] = skipped_files
            child_response["warning"] = f"{len(skipped_files)} files were skipped"
        
        logging.info(f"Child created successfully. Response: {child_response}")
        return jsonify(child_response), 201
        
    except Exception as e:
        logging.error(f"Error creating child: {str(e)}")
        return jsonify({"error": str(e)}), 500

@child_controller.route("/child", methods=["GET"])
@token_required
def get_all_children():
    try:
        # Get parent_uid from the authenticated user
        parent_uid = request.user['uid']
        logging.info(f"Getting children for user: {parent_uid}")

        children = []
        
        # First get parent's own children
        parent_children = child_collection.find({"parent_uid": parent_uid})
        for child in parent_children:
            child['_id'] = str(child['_id'])
            child['is_support_child'] = False
            children.append(child)
            logging.info(f"Found parent's child: {child.get('name')}")

        # Get all support groups where this user is a member
        support_groups = list(support_group_collection.find({"members.uid": parent_uid}))
        logging.info(f"Found {len(support_groups)} support groups for user")
        
        for group in support_groups:
            group_id = str(group["_id"])
            logging.info(f"Processing support group: {group_id}")
            
            # Find children that belong to this support group
            support_children = child_collection.find({
                "support_group_id": group_id,
                "parent_uid": {"$ne": parent_uid}  # Exclude own children
            })
            
            for child in support_children:
                logging.info(f"Found support group child: {child.get('name')} in group {group_id}")
                child_dict = {
                    **child,
                    '_id': str(child['_id']),
                    'is_support_child': True,
                    'support_group_name': group.get('name', 'Support Group'),
                    'support_group_role': next(
                        (m['role'] for m in group['members'] if m['uid'] == parent_uid),
                        'member'
                    )
                }
                children.append(child_dict)

        # Log all found children
        for child in children:
            logging.info(
                f"Final child entry: {child.get('name')} - "
                f"Support Group ID: {child.get('support_group_id')} - "
                f"Is Support Child: {child.get('is_support_child')} - "
                f"Parent UID: {child.get('parent_uid')}"
            )
        
        logging.info(f"Total children found: {len(children)}")
        return jsonify(children), 200
        
    except Exception as e:
        logging.error(f"Error in get_all_children: {str(e)}")
        logging.exception("Full traceback:")
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
            "updated_at": datetime.now()
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
