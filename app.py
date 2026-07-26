import os
from twilio.rest import Client

# Pega as credenciais direto das variáveis de ambiente do Render
ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE = os.environ.get('TWILIO_PHONE_NUMBER')

@app.route('/ligar/<numero>', methods=['GET', 'POST'])
def ligar(numero):
    try:
        client = Client(ACCOUNT_SID, AUTH_TOKEN)
        
        # Formata o número para o padrão internacional (+55...)
        numero_limpo = numero.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        if not numero_limpo.startswith('+'):
            numero_limpo = f"+55{numero_limpo}"

        # Dispara a chamada via Twilio
        call = client.calls.create(
            twiml='<Response><Say language="pt-BR">Chamada iniciada pelo painel Company 777.</Say></Response>',
            to=numero_limpo,
            from_=TWILIO_PHONE
        )
        return {"status": "sucesso", "call_sid": call.sid}, 200
    except Exception as e:
        return {"status": "erro", "detalhes": str(e)}, 500