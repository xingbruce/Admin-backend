import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
from supabase_client import get_supabase_client
from datetime import datetime
from functools import wraps

load_dotenv()

# Environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
FLASK_SECRET = os.getenv("FLASK_SECRET", "King-bruce-112233")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Please set SUPABASE_URL and SUPABASE_KEY environment variables")

supabase = get_supabase_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = FLASK_SECRET

def ok_resp(data=None, msg=None):
    return jsonify({"status": "ok", "data": data, "message": msg})

def err_resp(message, code=400):
    return jsonify({"status": "error", "message": message}), code

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper

# --- Admin Login & Logout ---

@app.route("/")
def root():
    return redirect(url_for("admin_login"))

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            return render_template("admin_login.html", error="Invalid credentials")
    return render_template("admin_login.html")

@app.route("/admin/logout")
@admin_required
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    return render_template("admin_dashboard.html", admin_user=ADMIN_USERNAME)

# --- API: Users ---

@app.route("/api/users", methods=["GET"])
@admin_required
def api_list_users():
    res = supabase.table("users").select("*").execute()
    if hasattr(res, "error") and res.error:
        return err_resp("Failed to fetch users: " + str(res.error))
    return ok_resp(res.data)

@app.route("/api/users/<int:user_id>", methods=["PUT"])
@admin_required
def api_update_user(user_id):
    data = request.json or {}
    update_data = {}
    if "is_frozen" in data:
        update_data["is_frozen"] = bool(data["is_frozen"])
    if "balance" in data:
        try:
            update_data["balance"] = float(data["balance"])
        except:
            return err_resp("Invalid balance value")
    if not update_data:
        return err_resp("No valid fields to update")
    res = supabase.table("users").update(update_data).eq("id", user_id).execute()
    if hasattr(res, "error") and res.error:
        return err_resp("Failed to update user: " + str(res.error))
    return ok_resp(res.data, "User updated")

@app.route("/api/users/<int:user_id>", methods=["DELETE"])
@admin_required
def api_delete_user(user_id):
    res = supabase.table("users").delete().eq("id", user_id).execute()
    if hasattr(res, "error") and res.error:
        return err_resp("Failed to delete user: " + str(res.error))
    return ok_resp(None, "User deleted")

# --- API: Transactions ---

@app.route("/api/transactions", methods=["GET"])
@admin_required
def api_list_transactions():
    res = supabase.table("transactions").select("*").order("created_at", desc=True).execute()
    if hasattr(res, "error") and res.error:
        return err_resp("Failed to fetch transactions: " + str(res.error))
    return ok_resp(res.data)

@app.route("/api/transactions", methods=["POST"])
@admin_required
def api_add_transaction():
    data = request.json or {}
    required_fields = ["user_id", "type", "amount"]
    if not all(k in data for k in required_fields):
        return err_resp("Missing required transaction fields")

    user_id = int(data["user_id"])
    tx_type = data["type"]
    amount = float(data["amount"])

    # Check if user is frozen, block transaction if yes
    user_res = supabase.table("users").select("is_frozen").eq("id", user_id).single().execute()
    if hasattr(user_res, "error") and user_res.error:
        return err_resp("Failed to fetch user data: " + str(user_res.error))
    if user_res.data.get("is_frozen", False):
        return err_resp("User account is frozen. Cannot perform transactions.", 403)

    transaction = {
        "user_id": user_id,
        "type": tx_type,
        "amount": amount,
        "created_at": datetime.utcnow().isoformat()
    }
    res = supabase.table("transactions").insert(transaction).execute()
    if hasattr(res, "error") and res.error:
        return err_resp("Failed to add transaction: " + str(res.error))
    return ok_resp(res.data, "Transaction added")

@app.route("/api/transactions/<int:tx_id>", methods=["DELETE"])
@admin_required
def api_delete_transaction(tx_id):
    res = supabase.table("transactions").delete().eq("id", tx_id).execute()
    if hasattr(res, "error") and res.error:
        return err_resp("Failed to delete transaction: " + str(res.error))
    return ok_resp(None, "Transaction deleted")

# --- API: Notifications ---

@app.route("/api/notifications", methods=["GET"])
@admin_required
def api_list_notifications():
    res = supabase.table("notifications").select("*").order("created_at", desc=True).execute()
    if hasattr(res, "error") and res.error:
        return err_resp("Failed to fetch notifications: " + str(res.error))
    return ok_resp(res.data)

@app.route("/api/notifications", methods=["POST"])
@admin_required
def api_send_notification():
    data = request.json or {}
    if not all(k in data for k in ["user_id", "message"]):
        return err_resp("Missing required fields")
    notification = {
        "user_id": int(data["user_id"]),
        "message": data["message"],
        "is_read": False,
        "created_at": datetime.utcnow().isoformat()
    }
    res = supabase.table("notifications").insert(notification).execute()
    if hasattr(res, "error") and res.error:
        return err_resp("Failed to send notification: " + str(res.error))
    return ok_resp(res.data, "Notification sent")

# --- Seed test user on startup ---

def seed_test_user():
    username = "testuser"
    res = supabase.table("users").select("*").eq("username", username).limit(1).execute()
    if hasattr(res, "error") and res.error:
        print("Seed check error:", res.error)
        return
    if res.data and len(res.data) > 0:
        print("Test user already exists.")
        return
    password_hash = generate_password_hash("testpass")
    new_user = {
        "username": username,
        "password_hash": password_hash,
        "balance": 5000.00,
        "broker": "Default Broker",
        "is_frozen": False,
        "created_at": datetime.utcnow().isoformat()
    }
    res = supabase.table("users").insert(new_user).execute()
    if hasattr(res, "error") and res.error:
        print("Failed to create test user:", res.error)
    else:
        print("Created test user: testuser / testpass")

with app.app_context():
    try:
        seed_test_user()
    except Exception as e:
        print("Seed attempt failed:", e)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "0") == "1")
