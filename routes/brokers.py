from flask import Blueprint, request
from utils.supabase_client import supabase

brokers_bp = Blueprint("brokers", __name__)

@brokers_bp.route("/assign", methods=["POST"])
def assign_broker():
    account_id = request.json.get("account_id")
    broker_name = request.json.get("broker_name")

    supabase.table("users").update({"broker": broker_name}).eq("id", account_id).execute()
    return {"success": True, "message": f"Broker {broker_name} assigned to account {account_id}"}
