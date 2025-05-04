import os
import openai
import requests
from flask import Flask, request

app = Flask(__name__)

# Lee las credenciales de las env vars en Render
PAGE_ACCESS_TOKEN = os.environ['PAGE_ACCESS_TOKEN']
VERIFY_TOKEN      = os.environ['VERIFY_TOKEN']
OPENAI_API_KEY    = os.environ['OPENAI_API_KEY']

openai.api_key = OPENAI_API_KEY

# Ruta raíz (opcional)
@app.route("/", methods=["GET"])
def home():
    return "Webhook is live 🎉"

# El endpoint que Facebook usa para verificación y para recibir eventos
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode      = request.args.get("hub.mode")
        token     = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        return "Verification failed", 403

    # Si es POST, procesamos el payload
    data = request.get_json()
    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                handle_event(event)
    return "OK", 200

def handle_event(event):
    sender_id = event["sender"]["id"]

    # 1) Mensajes de texto
    if "message" in event and "text" in event["message"]:
        texto = event["message"]["text"]
        respuesta = chatgpt_responde(texto)
        enviar_mensaje(sender_id, respuesta)

    # 2) Reacciones (me gusta, etc)
    if "reaction" in event:
        enviar_mensaje(sender_id, "🙌 ¡Gracias por tu reacción!")

    # 3) Comentarios en el feed (feed)
    if "feed" in event:
        enviar_mensaje(sender_id, "📝 ¡Gracias por tu comentario!")

    # 4) Postbacks (botones)
    if "postback" in event:
        payload = event["postback"].get("payload", "")
        respuesta = chatgpt_responde(payload)
        enviar_mensaje(sender_id, respuesta)

def chatgpt_responde(texto_usuario: str) -> str:
    # Prompt inspirado en el Apóstol Pablo
    system_prompt = {
        "role":    "system",
        "content": (
            "Eres Pablo Salvador, un mentor digital "
            "inspirado en el apóstol Pablo. Oras, enseñas "
            "y guías a las personas a Dios con respeto y sabiduría."
        )
    }
    user_prompt = {"role": "user", "content": texto_usuario}

    respuesta = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[system_prompt, user_prompt],
        temperature=0.7,
        max_tokens=200,
    )
    return respuesta.choices[0].message.content.strip()

def enviar_mensaje(recipient_id: str, texto: str):
    url = f"https://graph.facebook.com/v17.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    payload = {
        "recipient": {"id": recipient_id},
        "message":   {"text": texto}
    }
    headers = {"Content-Type": "application/json"}
    requests.post(url, params=params, json=payload, headers=headers)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
