from functools import wraps
from flask import request, jsonify
from src.config.firebase import verify_token

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Check if token is in headers
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]  # Bearer token
            except IndexError:
                return jsonify({'message': 'Token is missing!'}), 401

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            # Verify the token
            current_user = verify_token(token)
            if not current_user:
                return jsonify({'message': 'Token is invalid!'}), 401
            
            # Add user info to request
            request.user = current_user
            
        except Exception as e:
            return jsonify({'message': 'Token is invalid!', 'error': str(e)}), 401

        return f(*args, **kwargs)

    return decorated
