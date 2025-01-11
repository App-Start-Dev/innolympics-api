from flask import Flask, jsonify, request
from flask_cors import CORS
from src.config.mongodb import db
from src.config.firebase import initialize_firebase
from src.middleware.auth_middleware import token_required

# Import controllers
from src.controller.child_controller import child_controller
from src.controller.support_group_controller import support_group_controller
from src.controller.journal_controller import journal_controller
from src.controller.chat_controller import chat_controller

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Initialize Firebase
initialize_firebase()

# Register blueprints
app.register_blueprint(child_controller)
app.register_blueprint(support_group_controller)
app.register_blueprint(journal_controller)
app.register_blueprint(chat_controller)

# Test route
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "message": "API is running"}), 200

# Protected route example
@app.route('/api/protected', methods=['GET'])
@token_required
def protected():
    user = getattr(request, 'user', None)
    return jsonify({
        "message": "This is a protected route",
        "user": user
    }), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)