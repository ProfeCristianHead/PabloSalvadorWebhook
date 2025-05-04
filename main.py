import os
import json
import requests
import openai
from flask import Flask, request

app = Flask(__name__)

# Carga los tokens desde las environment vars en Render
PAGE_ACCESS_TOKEN = os.environ["PAGE_ACCESS_TOKEN"]
VERIFY_TOKEN      = os.environ["VERIFY_TOKEN"]
openai.api_key    = os.environ["OPENAI_API_KEY"]

def get_ai_response(user_text: str) -> str:
    """Llama a OpenAI para generar la respuesta de ‘Pablo Salvador’."""
    resp = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": (
                    "Eres Pablo Salvador, asesor espiritual inspirado en el apóstol Pablo. "
                    "Ora por las personas, guíalas a acercarse a Dios, usa versículos bíblicos pertinentes, "
                    "ofrece consuelo y ánimo en un tono cálido y pastoral."
                )
            },
            {"role": "user", "content": user_text},
        ],
        max_tokens=200,
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()

def send_message(recipient_id: str, message_text: str):
    """Envía un mensaje de texto al usuario vía la Graph API de Facebook."""
    url = "https://graph.facebook.com/v15.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    payload = {
        "recipient": {"id": recipient_id},
        "message":   {"text": message_text}
    }
    r = requests.post(url, params=params, headers=headers, json=payload)
    if r.status_code != 200:
        print("Error enviando mensaje:", r.text)
    return r

@app.route("/", methods=["GET"])
def home():
    return "✅ Webhook activo", 200

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    # Verificación del token (GET)
    if request.method == "GET":
        mode      = request.args.get("hub.mode")
        token     = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        return "Token de verificación incorrecto", 403

    # Recepción de eventos (POST)
    data = request.get_json()
    print(json.dumps(data, indent=2))  # Para debug

    if data.get("object") == "page":
        for entry in data.get("entry", []):
            # 1) Mensajes de Messenger, reacciones y feedback
            for event in entry.get("messaging", []):
                sender_id = event["sender"]["id"]

                # Texto recibido: pasa a OpenAI
                if event.get("message") and event["message"].get("text"):
                    text = event["message"]["text"]
                    reply = get_ai_response(text)
                    send_message(sender_id, reply)

                # Reacción a mensaje
                if event.get("message_reaction"):
                    react = event["message_reaction"]["reaction"]
                    send_message(sender_id, f"👍 Vi tu reacción: «{react}»")

                # Feedback del mensaje
                if event.get("messaging_feedback"):
                    send_message(sender_id, "📝 Gracias por tu feedback.")

                # Info de cliente
                if event.get("messaging_customer_information"):
                    info = event["messaging_customer_information"]
                    send_message(sender_id, f"📋 Info cliente: {json.dumps(info)}")

            # 2) Cambios en feed (comentarios en la página)
            for change in entry.get("changes", []):
                if change.get("field") == "feed":
                    val       = change["value"]
                    commenter = val.get("from", {}).get("name")
                    message   = val.get("message")
                    page_id   = entry.get("id")
                    send_message(
                        page_id,
                        f"💬 Nuevo comentario de {commenter}: «{message}»"
                    )

    return "EVENT_RECEIVED", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
