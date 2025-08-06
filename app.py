from flask import Flask, request, jsonify, render_template
from datetime import datetime, timedelta
import uuid
import json
import os
import requests
from cryptography.fernet import Fernet

app = Flask(__name__)

# === Encryption Key (Do NOT share this publicly) ===
ENCRYPTION_KEY = b"hQ4S1jT1TfQcQk_XLhJ7Ky1n3ht9ABhxqYUt09Ax0CM="
cipher = Fernet(ENCRYPTION_KEY)

# === Files ===
KEYS_FILE = "keys.json"
TEMP_TOKENS_FILE = "temp_tokens.json"

# === ShortJambo API ===
SHORTJAMBO_API = "https://short-jambo.com/api"
SHORTJAMBO_TOKEN = "https://short-jambo.com/api?api=6e49817e3eab65f2f9b06f8c1319ba768a4ae9c4&url=https://keysystemv3.onrender.com/genkey&alias=CustomAlias://short-jambo.com/api319ba768a4ae9c4"
TOKEN_EXPIRY_SECONDS = 60  # 1 minute

# === Helper functions ===

def load_keys():
    if not os.path.exists(KEYS_FILE):
        return {}
    with open(KEYS_FILE, 'r') as f:
        return json.load(f)

def save_keys(keys):
    with open(KEYS_FILE, 'w') as f:
        json.dump(keys, f)

def generate_unique_key(existing_keys):
    while True:
        new_key = str(uuid.uuid4())
        if new_key not in existing_keys:
            return new_key

def load_temp_tokens():
    if not os.path.exists(TEMP_TOKENS_FILE):
        return {}
    with open(TEMP_TOKENS_FILE, 'r') as f:
        return json.load(f)

def save_temp_tokens(tokens):
    with open(TEMP_TOKENS_FILE, 'w') as f:
        json.dump(tokens, f)

def is_valid_temp_token(token):
    tokens = load_temp_tokens()
    token_info = tokens.get(token)

    if not token_info:
        return False

    expires_at = datetime.fromisoformat(token_info["expires"])
    if datetime.now() > expires_at:
        return False

    # One-time use
    del tokens[token]
    save_temp_tokens(tokens)
    return True

# === Routes ===

@app.route("/getshortlink")
def get_short_link():
    temp_token = str(uuid.uuid4())
    expires = (datetime.now() + timedelta(seconds=TOKEN_EXPIRY_SECONDS)).isoformat()

    tokens = load_temp_tokens()
    tokens[temp_token] = {"expires": expires}
    save_temp_tokens(tokens)

    target_url = f"https://hs-tooolz10.onrender.com/genkey?token={temp_token}"
    shortjambo_url = f"{SHORTJAMBO_API}?api={SHORTJAMBO_TOKEN}&url={target_url}&format=text"

    try:
        response = requests.get(shortjambo_url)
        if response.status_code == 200:
            short_url = response.text.strip()
            return jsonify({
                "shortened_link": short_url,
                "expires_in": f"{TOKEN_EXPIRY_SECONDS} seconds"
            })
        else:
            return jsonify({"error": "Failed to get shortened URL"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/genkey")
def generate_key():
    temp_token = request.args.get("token")
    if not temp_token or not is_valid_temp_token(temp_token):
        return "Access denied. You must visit this page through the authorized short link.", 403

    keys = load_keys()
    new_key = generate_unique_key(keys)
    expiration = (datetime.now() + timedelta(hours=24)).isoformat()

    keys[new_key] = {"expires": expiration, "used": False}
    save_keys(keys)

    encrypted_key = cipher.encrypt(new_key.encode()).decode()
    return render_template("keygen.html", key=encrypted_key, expires=expiration)

@app.route("/verify")
def verify_key():
    encrypted_key = request.args.get("key")
    if not encrypted_key:
        return jsonify({"valid": False, "reason": "No key provided"}), 400

    try:
        key = cipher.decrypt(encrypted_key.encode()).decode()
    except Exception:
        return jsonify({"valid": False, "reason": "Invalid encrypted key"}), 400

    keys = load_keys()
    key_info = keys.get(key)

    if not key_info:
        return jsonify({"valid": False, "reason": "Key not found"}), 404

    if key_info.get("used"):
        return jsonify({"valid": False, "reason": "Key already used"}), 403

    if datetime.fromisoformat(key_info["expires"]) < datetime.now():
        return jsonify({"valid": False, "reason": "Key expired"}), 403

    keys[key]["used"] = True
    save_keys(keys)

    return jsonify({"valid": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

