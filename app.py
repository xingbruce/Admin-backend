from flask import Flask
from routes.accounts import accounts_bp
from routes.auth import auth_bp
from routes.brokers import brokers_bp

app = Flask(__name__)

# Register Blueprints
app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(accounts_bp, url_prefix="/accounts")
app.register_blueprint(brokers_bp, url_prefix="/brokers")

@app.route("/")
def home():
    return {"status": "Admin Backend API Running"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
