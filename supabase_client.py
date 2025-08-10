from supabase import create_client
import os

def get_supabase_client(supabase_url=None, supabase_key=None):
    supabase_url = supabase_url or os.getenv("SUPABASE_URL")
    supabase_key = supabase_key or os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise RuntimeError("Supabase URL and Key must be set")
    return 
