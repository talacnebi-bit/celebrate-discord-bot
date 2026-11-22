
import os
import time
import logging
import threading
import requests

from flask import Flask, request, jsonify
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

# ==========================================
# BOTIKE SETTINGS - EDIT THESE WHENEVER YOU WANT
# ==========================================

CELEBRATE_MESSAGE = "HEIL HITLER FUCK NIGGERS https://imglink.cc/cdn/RReTvdXqXU.mp4"
CELEBRATE_TOTAL_MESSAGES = 6

POINT_MESSAGE_BEFORE = "thanks to "
POINT_MESSAGE_AFTER = " for succesfuly using BOTIKE lite."

SPONSOR_MESSAGE = (
    "Imageboard for this server has succesfully been created using BOTIKE!, "
    "available at "
    "[**Һttρs://support.discord.com/hc/en-us/articles/"
    "6208479917079-Forum-Channels-FAQ**](https://joyjak.st/)!"
)

# ==========================================
# DISCORD CONFIGURATION
# Add these values later in Render Environment.
# ==========================================

PUBLIC_KEY = os.environ.get("DISCORD_PUBLIC_KEY", "")
APPLICATION_ID = os.environ.get("DISCORD_APP_ID", "")
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


# ==========================================
# REGISTER DISCORD SLASH COMMANDS
# ==========================================

def register_commands():
    if not APPLICATION_ID or not BOT_TOKEN:
        logging.warning("Missing Discord credentials.")
        return

    commands = [
        {
            "name": "celebrate",
            "description": "Send the celebration video link",
            "integration_types": [1],
            "contexts": [0]
        },
        {
            "name": "point",
            "description": "Thank someone for using Botike",
            "integration_types": [1],
            "contexts": [0],
            "options": [
                {
                    "name": "person",
                    "description": "Who should be thanked?",
                    "type": 6,
                    "required": True
                }
            ]
        },
        {
            "name": "sponsor",
            "description": "Share the BOTINX imageboard announcement",
            "integration_types": [1],
            "contexts": [0]
        }
    ]

    url = (
        f"https://discord.com/api/v10/"
        f"applications/{APPLICATION_ID}/commands"
    )

    try:
        response = requests.put(
            url,
            headers={"Authorization": f"Bot {BOT_TOKEN}"},
            json=commands,
            timeout=20
        )
        response.raise_for_status()
        logging.info("Botike commands registered.")

    except requests.RequestException:
        logging.exception("Command registration failed.")


# ==========================================
# SEND FOLLOW-UP MESSAGES
# ==========================================

def send_followup(app_id, token, content, allowed_mentions=None):
    url = (
        f"https://discord.com/api/v10/"
        f"webhooks/{app_id}/{token}"
    )

    payload = {"content": content}

    if allowed_mentions is not None:
        payload["allowed_mentions"] = allowed_mentions

    while True:
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=20
            )

            if response.status_code == 429:
                retry = response.json().get("retry_after", 1)
                time.sleep(float(retry) + 0.2)
                continue

            response.raise_for_status()
            return True

        except requests.RequestException:
            logging.exception("Follow-up message failed.")
            return False


# ==========================================
# INITIAL PUBLIC RESPONSE
# ==========================================

def initial_response(content, allowed_mentions=None):
    data = {"content": content}

    if allowed_mentions is not None:
        data["allowed_mentions"] = allowed_mentions

    return jsonify({
        "type": 4,
        "data": data
    })


# ==========================================
# DISCORD INTERACTION ENDPOINT
# ==========================================

@app.route("/", methods=["GET"])
def home():
    return "Botike is online!"


@app.route("/interactions", methods=["POST"])
def interactions():

    signature = request.headers.get("X-Signature-Ed25519")
    timestamp = request.headers.get("X-Signature-Timestamp")

    if not signature or not timestamp or not PUBLIC_KEY:
        return "Missing signature information", 401

    try:
        verify_key = VerifyKey(bytes.fromhex(PUBLIC_KEY))
        verify_key.verify(
            timestamp.encode() + request.get_data(),
            bytes.fromhex(signature)
        )
    except (BadSignatureError, ValueError):
        return "Invalid signature", 401

    interaction = request.get_json()

    if interaction.get("type") == 1:
        return jsonify({"type": 1})

    if interaction.get("type") != 2:
        return "Unsupported interaction", 400

    command = interaction.get("data", {}).get("name")
    token = interaction.get("token")
    app_id = interaction.get("application_id")

    # ======================================
    # /CELEBRATE
    # ======================================

    if command == "celebrate":

        total = max(1, min(int(CELEBRATE_TOTAL_MESSAGES), 6))

        def send_remaining():
            time.sleep(1)

            for _ in range(total - 1):
                if not send_followup(
                    app_id,
                    token,
                    CELEBRATE_MESSAGE
                ):
                    break

        if total > 1:
            threading.Thread(
                target=send_remaining,
                daemon=True
            ).start()

        return initial_response(CELEBRATE_MESSAGE)

    # ======================================
    # /POINT
    # ======================================

    if command == "point":

        options = interaction.get("data", {}).get("options", [])

        if not options:
            return initial_response("Please select someone.")

        user_id = options[0].get("value")

        if not user_id:
            return initial_response("I couldn't find that user.")

        message = (
            POINT_MESSAGE_BEFORE
            + f"<@{user_id}>"
            + POINT_MESSAGE_AFTER
        )

        return initial_response(
            message,
            allowed_mentions={"users": [str(user_id)]}
        )

    # ======================================
    # /SPONSOR
    # ======================================

    if command == "sponsor":
        return initial_response(SPONSOR_MESSAGE)

    return initial_response("Unknown Botike command.")


# ==========================================
# START BOTIKE
# ==========================================

register_commands()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
