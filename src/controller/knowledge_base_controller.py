from flask import Blueprint, request, jsonify
from src.config.mongodb import client
from bson import ObjectId
from datetime import datetime
import boto3
import os
from src.middleware.auth_middleware import token_required
from werkzeug.utils import secure_filename

knowledge_base_controller = Blueprint("knowledge_base_controller", __name__, url_prefix="/api")
db = client['alix_db']
child_collection = db['child']

# Initialize S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)
BUCKET_NAME = os.getenv('AWS_BUCKET_NAME')

def ensure_child_folder(child_id):
    try:
        s3_client.head_object(Bucket=BUCKET_NAME, Key=f"{child_id}/")
    except:
        s3_client.put_object(Bucket=BUCKET_NAME, Key=f"{child_id}/")

@knowledge_base_controller.route("/knowledge-base/<child_id>/upload", methods=["POST"])
@token_required
def upload_files(child_id):
    try:
        # Verify child access
        child = child_collection.find_one({
            "_id": ObjectId(child_id),
            "parent_uid": request.user['uid']
        })
        
        if not child:
            return jsonify({"error": "Child not found or access denied"}), 404
            
        if 'files' not in request.files:
            return jsonify({"error": "No files provided"}), 400
            
        files = request.files.getlist('files')
        if not files or all(file.filename == '' for file in files):
            return jsonify({"error": "No files selected"}), 400
            
        # Ensure child's folder exists
        ensure_child_folder(child_id)
        
        uploaded_files = []
        for file in files:
            if file.filename != '':
                # Generate timestamp-based filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                original_extension = os.path.splitext(secure_filename(file.filename))[1]
                new_filename = f"{timestamp}_{len(uploaded_files)}{original_extension}"
                
                # Upload to child's folder
                file_key = f"{child_id}/{new_filename}"
                
                # Upload to S3
                s3_client.upload_fileobj(
                    file,
                    BUCKET_NAME,
                    file_key,
                    ExtraArgs={'ContentType': file.content_type}
                )
                
                uploaded_files.append({
                    "original_name": file.filename,
                    "stored_name": new_filename,
                    "content_type": file.content_type
                })
        
        return jsonify({
            "message": f"Successfully uploaded {len(uploaded_files)} files",
            "files": uploaded_files
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@knowledge_base_controller.route("/knowledge-base/<child_id>/files", methods=["GET"])
@token_required
def list_files(child_id):
    try:
        # Verify child access
        child = child_collection.find_one({
            "_id": ObjectId(child_id),
            "$or": [
                {"parent_uid": request.user['uid']},
                {"support_group_id": {"$exists": True}}
            ]
        })
        
        if not child:
            return jsonify({"error": "Child not found or access denied"}), 404
            
        # List objects in child's folder
        response = s3_client.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix=f"{child_id}/"
        )
        
        files = []
        if 'Contents' in response:
            for obj in response['Contents']:
                # Skip the folder itself
                if not obj['Key'].endswith('/'):
                    # Generate presigned URL for each file
                    url = s3_client.generate_presigned_url(
                        'get_object',
                        Params={
                            'Bucket': BUCKET_NAME,
                            'Key': obj['Key']
                        },
                        ExpiresIn=3600  # URL expires in 1 hour
                    )
                    
                    files.append({
                        "filename": os.path.basename(obj['Key']),
                        "size": obj['Size'],
                        "last_modified": obj['LastModified'].isoformat(),
                        "url": url
                    })
        
        return jsonify({"files": files}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@knowledge_base_controller.route("/knowledge-base/<child_id>/files/<filename>", methods=["DELETE"])
@token_required
def delete_file(child_id, filename):
    try:
        # Verify parent access (only parents can delete files)
        child = child_collection.find_one({
            "_id": ObjectId(child_id),
            "parent_uid": request.user['uid']
        })
        
        if not child:
            return jsonify({"error": "Child not found or access denied"}), 404
            
        # Delete file from S3
        file_key = f"{child_id}/{filename}"
        s3_client.delete_object(
            Bucket=BUCKET_NAME,
            Key=file_key
        )
        
        return jsonify({"message": "File deleted successfully"}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
