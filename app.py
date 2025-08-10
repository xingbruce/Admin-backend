import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Please set SUPABASE_URL and SUPABASE_KEY in environment")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

APP_SECRET = os.getenv("FLASK_SECRET", "change-this-secret")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = APP_SECRET

# ---------- Utility helpers ----------
def ok_resp(data=None, msg=None):
    return jsonify({"status": "ok", "data": data, "message": msg})

def err_resp(message, code=400):
    return jsonify({"status": "error", "message": message}), code

def get_user_by_username(username):
    res = supabase.table("users").select("*").eq("username", username).limit(1).execute()
    if res.error:
        return None, res.error
    data = res.data or []
    return (data[0] if data else None), None

def seed_test_user():
    # attempt to create a test user if not exists
    username = "testuser"
    user, err = get_user_by_username(username)
    if err:
        print("Seed check error (probably missing table):", err)
        return
    if user:
        print("Test user already exists.")
        return
    password_hash = generate_password_hash("testpass")
    new_user = {
        "username": username,
        "password_hash": password_hash,
        "balance": 5000.00,
        "broker": "John Smith",
        "is_frozen": False,
        "created_at": datetime.utcnow().isoformat()
    }
    res = supabase.table("users").insert(new_user).execute()
    if res.error:
        print("Failed to create test user:", res.error)
    else:
        print("Created test user: testuser / testpass")

# ---------- Routes ----------
@app.route("/")
def root():
    return redirect(url_for("admin_login"))

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == ADMIN_USER and password == ADMIN_PASS:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            return render_template("admin_login.html", error="Invalid credentials")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))

def admin_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return fn(*a, **kw)
    return wrapper

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    return render_template("admin_dashboard.html", admin_user=ADMIN_USER)

# ---------- API: Users ----------
@app.route("/api/users", methods=["GET"])
def api_list_users():
    # optional query param: username
    username = request.args.get("username")
    q = supabase.table("users").select("*")
    if username:
        q = q.ilike("username", f"%{username}%")
    res = q.execute()
    if res.error:
        return err_resp("Failed to fetch users: " + str(res.error))
    return ok_resp(res.data)

@app.route("/api/users", methods=["POST"])
@admin_required
def api_create_user():
    payload = request.json or {}
    required = ["username", "password"]
    for r in required:
        if r not in payload:
            return err_resp(f"Missing field: {r}")
    username = payload["username"]
    password = payload["password"]
    # do not allow duplicates
    existing, _ = get_user_by_username(username)
    if existing:
        return err_resp("Username already exists", 409)
    password_hash = generate_password_hash(password)
    user_row = {
        "username": username,
        "password_hash": password_hash,
        "balance": float(payload.get("balance", 0.0)),
        "broker": payload.get("broker", ""),
        "is_frozen": bool(payload.get("is_frozen", False)),
        "created_at": datetime.utcnow().isoformat()
    }
    res = supabase.table("users").insert(user_row).execute()
    if res.error:
        return err_resp("Failed to create user: " + str(res.error))
    return ok_resp(res.data, "User created")

@app.route("/api/users/<int:user_id>", methods=["PUT"])
@admin_required
def api_update_user(user_id):
    payload = request.json or {}
    allowed = {"balance", "broker", "is_frozen", "username"}
    update = {k: payload[k] for k in payload if k in allowed}
    # coerce types
    if "balance" in update:
        try:
            update["balance"] = float(update["balance"])
        except:
            return err_resp("Invalid balance")
    if "is_frozen" in update:
        update["is_frozen"] = bool(update["is_frozen"])
    if not update:
        return err_resp("No valid fields to update")
    res = supabase.table("users").update(update).eq("id", user_id).execute()
    if res.error:
        return err_resp("Failed to update user: " + str(res.error))
    return ok_resp(res.data, "User updated")

@app.route("/api/users/<int:user_id>/reset_password", methods=["POST"])
@admin_required
def api_reset_password(user_id):
    payload = request.json or {}
    new_password = payload.get("new_password")
    if not new_password:
        return err_resp("Missing new_password")
    password_hash = generate_password_hash(new_password)
    res = supabase.table("users").update({"password_hash": password_hash}).eq("id", user_id).execute()
    if res.error:
        return err_resp("Failed to reset password: " + str(res.error))
    return ok_resp(None, "Password updated")

@app.route("/api/users/<int:user_id>", methods=["DELETE"])
@admin_required
def api_delete_user(user_id):
    res = supabase.table("users").delete().eq("id", user_id).execute()
    if res.error:
        return err_resp("Failed to delete user: " + str(res.error))
    return ok_resp(None, "User deleted")

# ---------- API: Notifications ----------
@app.route("/api/notifications", methods=["POST"])
@admin_required
def api_send_notification():
    payload = request.json or {}
    required = ["user_id", "message"]
    for r in required:
        if r not in payload:
            return err_resp(f"Missing field: {r}")
    note = {
        "user_id": int(payload["user_id"]),
        "message": payload["message"],
        "is_read": False,
        "created_at": datetime.utcnow().isoformat()
    }
    res = supabase.table("notifications").insert(note).execute()
    if res.error:
        return err_resp("Failed to send notification: " + str(res.error))
    return ok_resp(res.data, "Notification sent")

@app.route("/api/notifications", methods=["GET"])
def api_get_notifications():
    user_id = request.args.get("user_id")
    if not user_id:
        return err_resp("Missing user_id")
    res = supabase.table("notifications").select("*").eq("user_id", int(user_id)).order("created_at", desc=True).execute()
    if res.error:
        return err_resp("Failed to fetch notifications: " + str(res.error))
    return ok_resp(res.data)

# ---------- Startup: seed test user ----------
with app.app_context():
    try:
        seed_test_user()
    except Exception as e:
        print("Seed attempt failed:", e)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=os.getenv("FLASK_DEBUG", "0") == "1")
