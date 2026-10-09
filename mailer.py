"""CAN-SPAM Act & RFC 8058 compliant email notification helper with One-Click Unsubscribe."""
import hmac
import hashlib
import json
import base64
from email.message import EmailMessage

DEFAULT_PHYSICAL_ADDRESS = "Av. Winston Churchill #1099, Torre Acrópolis, Piso 14, Santo Domingo, D.N., República Dominicana, 10148"
UNSUB_KEY = b"ZERO_CAN_SPAM_UNSUB_SIGNING_KEY_2026"

def generate_unsubscribe_token(company_id: int, user_email: str) -> str:
    payload = json.dumps({"cid": company_id, "email": user_email.strip().lower()}).encode()
    sig = hmac.new(UNSUB_KEY, payload, hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(payload).decode() + "." + sig

def verify_unsubscribe_token(token: str) -> dict:
    try:
        raw_payload, sig = token.split(".", 1)
        payload = base64.urlsafe_b64decode(raw_payload.encode())
        expected = hmac.new(UNSUB_KEY, payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("Firma de desuscripción inválida.")
        return json.loads(payload.decode())
    except Exception:
        raise ValueError("Token de desuscripción inválido o adulterado.")

def build_compliant_email(
    to_email: str,
    subject: str,
    body_html: str,
    company_id: int,
    company_name: str = "Zero Enterprise",
    physical_address: str = DEFAULT_PHYSICAL_ADDRESS,
    base_url: str = "http://127.0.0.1:8000"
) -> EmailMessage:
    msg = EmailMessage()
    msg['To'] = to_email
    msg['From'] = f'{company_name} <notificaciones@zero.app>'
    msg['Subject'] = subject
    
    token = generate_unsubscribe_token(company_id, to_email)
    unsub_url = f"{base_url}/api/email/unsubscribe?token={token}"
    
    # RFC 8058 One-Click Unsubscribe Headers
    msg['List-Unsubscribe'] = f"<{unsub_url}>"
    msg['List-Unsubscribe-Post'] = "List-Unsubscribe=One-Click"
    
    footer_html = f"""
    <div style="border-top: 1px solid #e2e8f0; margin-top: 28px; padding-top: 14px; font-size: 12px; color: #718096; line-height: 1.5;">
      <p style="margin: 0 0 6px;">Esta es una comunicación oficial de <strong>{company_name}</strong>.</p>
      <p style="margin: 0 0 6px;"><strong>Dirección física registrada:</strong> {physical_address}</p>
      <p style="margin: 0;">
        ¿Desea no recibir más avisos comerciales? 
        <a href="{unsub_url}" style="color: #0f766e; text-decoration: underline;">Desuscribirse en un clic</a>.
      </p>
    </div>
    """
    full_html = f"<div style='font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif; color: #2d3748;'>{body_html}{footer_html}</div>"
    msg.set_content(body_html)
    msg.add_alternative(full_html, subtype='html')
    return msg
