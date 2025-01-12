from flask import Blueprint, request, jsonify
from src.config.mongodb import client
from bson import ObjectId
from datetime import datetime
import boto3
import os
import logging
from botocore.exceptions import ClientError
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

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_child_folder(child_id):
    try:
        # Try to check if folder exists
        s3_client.head_object(Bucket=BUCKET_NAME, Key=f"{child_id}/")
        logging.info(f"Folder {child_id}/ already exists in bucket {BUCKET_NAME}")
    except ClientError as e:
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:  # If folder doesn't exist
            try:
                # Create the folder
                s3_client.put_object(Bucket=BUCKET_NAME, Key=f"{child_id}/")
                logging.info(f"Created folder {child_id}/ in bucket {BUCKET_NAME}")
            except Exception as create_error:
                logging.error(f"Failed to create folder {child_id}/: {str(create_error)}")
                raise create_error
        else:
            logging.error(f"Error checking folder {child_id}/: {str(e)}")
            raise e
    except Exception as e:
        logging.error(f"Unexpected error with folder {child_id}/: {str(e)}")
        raise e

@knowledge_base_controller.route("/knowledge-base/<child_id>/upload", methods=["POST"])
@token_required
def upload_files(child_id):
    try:
        logging.info(f"Upload request received for child {child_id}")
        
        # Verify child access
        child = child_collection.find_one({
            "_id": ObjectId(child_id),
            "parent_uid": request.user['uid']
        })
        
        if not child:
            logging.warning(f"Access denied for child {child_id} by user {request.user['uid']}")
            return jsonify({"error": "Child not found or access denied"}), 404
            
        if 'files' not in request.files:
            logging.warning("No files in request")
            return jsonify({"error": "No files provided"}), 400
            
        files = request.files.getlist('files')
        if not files or all(file.filename == '' for file in files):
            logging.warning("No valid files selected")
            return jsonify({"error": "No files selected"}), 400
            
        # Ensure child's folder exists
        ensure_child_folder(child_id)
        
        uploaded_files = []
        failed_files = []
        
        for file in files:
            if file.filename == '':
                continue
                
            if not allowed_file(file.filename):
                failed_files.append({
                    "filename": file.filename,
                    "error": "File type not allowed"
                })
                logging.warning(f"Skipping file {file.filename}: File type not allowed")
                continue
                
            try:
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
                
                logging.info(f"Successfully uploaded file {file.filename} as {file_key}")
                
                uploaded_files.append({
                    "original_name": file.filename,
                    "stored_name": new_filename,
                    "content_type": file.content_type
                })
            except Exception as e:
                error_msg = f"Failed to upload {file.filename}: {str(e)}"
                logging.error(error_msg)
                failed_files.append({
                    "filename": file.filename,
                    "error": str(e)
                })
        
        response = {
            "message": f"Successfully uploaded {len(uploaded_files)} files",
            "files": uploaded_files
        }
        
        if failed_files:
            response["failed_files"] = failed_files
            response["warning"] = f"{len(failed_files)} files failed to upload"
            
        return jsonify(response), 200 if uploaded_files else 400
        
    except Exception as e:
        error_msg = f"Error processing upload request: {str(e)}"
        logging.error(error_msg)
        return jsonify({"error": error_msg}), 500

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
