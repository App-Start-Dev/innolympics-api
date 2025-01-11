from flask import Blueprint

journal_controller = Blueprint("journal_controller", __name__, url_prefix="/api")

@journal_controller.route("/journal", methods=["POST"])
def create_journal():
    pass