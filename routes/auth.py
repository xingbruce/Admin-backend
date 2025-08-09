from flask import Blueprint, request
import os

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if username == os.getenv("ADMIN_USERNAME") and password == os.getenv("ADMIN_PASSWORD"):
        return {"success": True, "message": "Login successful"}
    return {"success": False, "message": "Invalid credentials"}, 401
