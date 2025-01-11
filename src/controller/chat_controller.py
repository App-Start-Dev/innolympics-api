from flask import Blueprint

chat_controller = Blueprint("chat_controller", __name__, url_prefix="/api")

@chat_controller.route("/chat", methods=["GET"])
def get_chat():
    pass

@chat_controller.route("/chat", methods=["POST"])
def create_chat():
    pass
