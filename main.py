import os
import json
import requests
from flask import Flask, request, abort, jsonify
import openai

app = Flask(__name__)

# Carga tokens de entorno
PAGE_ACCESS_TOKEN = os.environ["PAGE_ACCESS_TOKEN"]
VERIFY_TOKEN = os.environ["VERIFY_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

openai.api_key = OPENAI_API_KEY

GRAPH_API_URL = "https://graph.facebook.com/v17.0"

# Prompt base de Pablo Salvador
SYSTEM_PROMPT = """
Eres Pablo Salvador, un asesor espiritual inspirado en el apóstol Pablo. 
Guias a las personas hacia Dios con mensajes llenos de esperanza, oración y sabiduría bíblica.
Responde amablemente, con versículos si aplica, y ofrece oraciones personalizadas.
"""

def send_message(recipient_id, text):
    """Envía un mensaje de texto a Messenger vía Graph API."""
    url = f"{GRAPH_API_URL}/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    params = {"access_token": PAGE_ACCESS_TOKEN}
    r = requests.post(url, params=params, json=payload)
    r.raise_for_status()

def add_comment(comment_id, message):
    """Responde a un comentario de Facebook."""
    url = f"{GRAPH_API_URL}/{comment_id}/comments"
    payload = {"message": message}
    params = {"access_token": PAGE_ACCESS_TOKEN}
    r = requests.post(url, params=params, json=payload)
    r.raise_for_status()

def handle_openai_reply(user_text):
    """Llama a OpenAI GPT‑4 y devuelve la respuesta."""
    resp = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ],
        temperature=0.7,
        max_tokens=300
    )
    return resp.choices[0].message.content.strip()

@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Token inválido", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    # Procesa mensajes de Messenger
    if "entry" in data:
        for entry in data["entry"]:
            # Mensajes y postbacks (Messenger)
            if "messaging" in entry:
                for msg_event in entry["messaging"]:
                    sender = msg_event["sender"]["id"]
                    if msg_event.get("message") and "text" in msg_event["message"]:
                        user_text = msg_event["message"]["text"]
                        reply = handle_openai_reply(user_text)
                        send_message(sender, reply)
            # Eventos de feed (comentarios, reacciones)
            if "changes" in entry:
                for change in entry["changes"]:
                    field = change.get("field")
                    val = change.get("value", {})
                    # Comentarios a publicaciones
                    if field == "feed" and val.get("item") == "comment":
                        comment_id = val["comment_id"]
                        user_text = val.get("message", "")
                        reply = handle_openai_reply(user_text)
                        add_comment(comment_id, reply)
                    # Reacciones (puedes personalizar)
                    if field == "feed" and val.get("item") == "reaction":
                        comment_id = val.get("comment_id") or val.get("post_id")
                        reaction = val.get("reaction_type")
                        # Ejemplo: responde a la reacción
                        text = f"¡Gracias por tu reacción {reaction}! ¿En qué más puedo ayudarte hoy?"
                        add_comment(comment_id, text)
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
