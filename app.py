import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from supabase_client import get_supabase_client
from datetime import datetime

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = generate_password_hash(os.getenv("ADMIN_PASSWORD", "admin123"))
FLASK_SECRET = os.getenv("FLASK_SECRET", "your-secret-key")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")

supabase = get_supabase_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)
app.secret_key = FLASK_SECRET

# Helpers
def ok_resp(data=None, msg=None):
    return jsonify({"status": "ok", "data": data, "message": msg})

def err_resp(msg, code=400):
    return jsonify({"status": "error", "message": msg}), code

def admin_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper

def get_user_by_username(username):
    res = supabase.table("users").select("*").eq("username", username).limit(1).execute()
    if res.error:
        return None
    return res.data[0] if res.data else None

def get_user_by_id(user_id):
    res = supabase.table("users").select("*").eq("id", user_id).limit(1).execute()
    if res.error:
        return None
    return res.data[0] if res.data else None

def is_user_frozen(user_id):
    user = get_user_by_id(user_id)
    return user.get("is_frozen", False) if user else False

# Routes

@app.route("/")
def root():
    return redirect(url_for("admin_login"))

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        return render_template("admin_login.html", error="Invalid credentials")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    return render_template("admin_dashboard.html", admin_user=ADMIN_USERNAME)

# --- API for Users ---

@app.route("/api/users", methods=["GET"])
@admin_required
def api_list_users():
    res = supabase.table("users").select("*").execute()
    if res.error:
        return err_resp("Failed to fetch users: " + str(res.error))
    return ok_resp(res.data)

@app.route("/api/users", methods=["POST"])
@admin_required
def api_create_user():
    data = request.json
    required = ["username", "password"]
    for r in required:
        if r not in data:
            return err_resp(f"Missing field: {r}")
    if get_user_by_username(data["username"]):
        return err_resp("Username already exists", 409)

    password_hash = generate_password_hash(data["password"])
    user_row = {
        "username": data["username"],
        "password_hash": password_hash,
        "balance": float(data.get("balance", 0)),
        "broker": data.get("broker", ""),
        "is_frozen": False,
        "created_at": datetime.utcnow().isoformat()
    }
    res = supabase.table("users").insert(user_row).execute()
    if res.error:
        return err_resp("Failed to create user: " + str(res.error))
    return ok_resp(res.data, "User created")

@app.route("/api/users/<int:user_id>", methods=["PUT"])
@admin_required
def api_update_user(user_id):
    data = request.json
    update_fields = {}
    if "balance" in data:
        try:
            update_fields["balance"] = float(data["balance"])
        except:
            return err_resp("Invalid balance")
    if "broker" in data:
        update_fields["broker"] = data["broker"]
    if "is_frozen" in data:
        update_fields["is_frozen"] = bool(data["is_frozen"])
    if "username" in data:
        update_fields["username"] = data["username"]
    if not update_fields:
        return err_resp("No valid fields to update")

    res = supabase.table("users").update(update_fields).eq("id", user_id).execute()
    if res.error:
        return err_resp("Failed to update user: " + str(res.error))
    return ok_resp(res.data, "User updated")

@app.route("/api/users/<int:user_id>", methods=["DELETE"])
@admin_required
def api_delete_user(user_id):
    res = supabase.table("users").delete().eq("id", user_id).execute()
    if res.error:
        return err_resp("Failed to delete user: " + str(res.error))
    return ok_resp(None, "User deleted")

# --- API for Transactions ---

@app.route("/api/transactions", methods=["GET"])
@admin_required
def api_list_transactions():
    user_id = request.args.get("user_id")
    query = supabase.table("transactions").select("*").order("created_at", desc=True)
    if user_id:
        query = query.eq("user_id", int(user_id))
    res = query.execute()
    if res.error:
        return err_resp("Failed to fetch transactions: " + str(res.error))
    return ok_resp(res.data)

@app.route("/api/transactions", methods=["POST"])
@admin_required
def api_add_transaction():
    data = request.json
    required = ["user_id", "amount", "type", "description"]
    for r in required:
        if r not in data:
            return err_resp(f"Missing field: {r}")

    # Check if user is frozen
    if is_user_frozen(data["user_id"]):
        return err_resp("Account is frozen. Cannot perform transactions.")

    transaction = {
        "user_id": int(data["user_id"]),
        "amount": float(data["amount"]),
        "type": data["type"],  # e.g. "deposit", "withdrawal", "transfer"
        "description": data["description"],
        "created_at": datetime.utcnow().isoformat()
    }
    res = supabase.table("transactions").insert(transaction).execute()
    if res.error:
        return err_resp("Failed to add transaction: " + str(res.error))
    return ok_resp(res.data, "Transaction added")

@app.route("/api/transactions/<int:transaction_id>", methods=["DELETE"])
@admin_required
def api_delete_transaction(transaction_id):
    res = supabase.table("transactions").delete().eq("id", transaction_id).execute()
    if res.error:
        return err_resp("Failed to delete transaction: " + str(res.error))
    return ok_resp(None, "Transaction deleted")

# --- Notifications ---

@app.route("/api/notifications", methods=["POST"])
@admin_required
def api_send_notification():
    data = request.json
    required = ["user_id", "message"]
    for r in required:
        if r not in data:
            return err_resp(f"Missing field: {r}")
    note = {
        "user_id": int(data["user_id"]),
        "message": data["message"],
        "is_read": False,
        "created_at": datetime.utcnow().isoformat()
    }
    res = supabase.table("notifications").insert(note).execute()
    if res.error:
        return err_resp("Failed to send notification: " + str(res.error))
    return ok_resp(res.data, "Notification sent")

@app.route("/api/notifications", methods=["GET"])
@admin_required
def api_get_notifications():
    user_id = request.args.get("user_id")
    if not user_id:
        return err_resp("Missing user_id")
    res = supabase.table("notifications").select("*").eq("user_id", int(user_id)).order("created_at", desc=True).execute()
    if res.error:
        return err_resp("Failed to fetch notifications: " + str(res.error))
    return ok_resp(res.data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=True)
