from flask import Blueprint, request
from utils.supabase_client import supabase

accounts_bp = Blueprint("accounts", __name__)

@accounts_bp.route("/list", methods=["GET"])
def list_accounts():
    data = supabase.table("users").select("*").execute()
    return {"accounts": data.data}

@accounts_bp.route("/freeze", methods=["POST"])
def freeze_account():
    account_id = request.json.get("account_id")
    supabase.table("users").update({"status": "frozen"}).eq("id", account_id).execute()
    return {"success": True, "message": f"Account {account_id} frozen"}

@accounts_bp.route("/unfreeze", methods=["POST"])
def unfreeze_account():
    account_id = request.json.get("account_id")
    supabase.table("users").update({"status": "active"}).eq("id", account_id).execute()
    return {"success": True, "message": f"Account {account_id} unfrozen"}
