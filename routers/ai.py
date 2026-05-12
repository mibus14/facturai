from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import os

router = APIRouter(prefix="/api")

SYSTEM_PROMPT = """Eres Max, el asistente virtual de FacturAI. Eres un experto amigable en facturación electrónica mexicana (CFDI 4.0), el SAT, y regulaciones fiscales de México.

Puedes ayudar con:
- CFDI 4.0: campos obligatorios, validaciones, estructura
- RFC: formato, validación, tipos de contribuyentes
- Régimen fiscal: opciones disponibles, cuál aplica según el caso
- Uso del CFDI: códigos G01-G03, I01-I08, D01-D10, S01, P01, CP01
- Forma de pago: códigos 01 (efectivo), 03 (transferencia), 04 (tarjeta crédito), 28 (tarjeta débito), 99 (por definir)
- Método de pago: PUE vs PPD
- IVA 16%, retenciones, IEPS, ISR
- Cancelación de facturas ante el SAT
- Cómo usar FacturAI para crear facturas correctas
- Plazos y obligaciones fiscales en México

Responde siempre en español mexicano, de forma amigable y concisa. Usa emojis ocasionalmente.
Si no sabes algo específico, sugiere consultar a su contador o directamente al SAT (sat.gob.mx).
Nunca des asesoría legal específica, solo información general.
"""


@router.post("/chat")
async def chat_endpoint(request: Request):
    try:
        import anthropic
    except ImportError:
        return JSONResponse({"content": "El servicio de IA no está disponible en este momento."})

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return JSONResponse({
            "content": "¡Hola! Soy Max 🤖 Para activar el asistente de IA completo, configura la variable `ANTHROPIC_API_KEY` en tu archivo `.env`. Mientras tanto, puedes consultar el SAT en sat.gob.mx o preguntarle a tu contador. ¡Estoy aquí para cuando me necesites!"
        })

    body = await request.json()
    messages = body.get("messages", [])

    if not messages:
        return JSONResponse({"content": "¡Hola! Soy Max, tu asistente de facturación mexicana. ¿En qué puedo ayudarte hoy?"})

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    return JSONResponse({"content": response.content[0].text})
