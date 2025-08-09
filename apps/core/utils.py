from cryptography.fernet import Fernet
from django.conf import settings
import base64
from urllib.parse import quote, unquote


def get_encryption_key():
    """Obtiene la clave de encriptación desde settings"""
    if not hasattr(settings, 'EMAIL_ENCRYPTION_KEY'):
        raise ValueError("EMAIL_ENCRYPTION_KEY no está configurado en settings")
    return settings.EMAIL_ENCRYPTION_KEY


def encrypt_email(email: str) -> str:
    """Encripta un email para uso en URLs"""
    cipher = Fernet(get_encryption_key())
    encrypted = cipher.encrypt(email.encode())
    # Hacer URL-safe
    return quote(base64.urlsafe_b64encode(encrypted).decode())


def decrypt_email(encrypted_email: str) -> str:
    """Desencripta un email desde URL"""
    cipher = Fernet(get_encryption_key())
    # Decodificar desde URL-safe
    encrypted_bytes = base64.urlsafe_b64decode(unquote(encrypted_email))
    return cipher.decrypt(encrypted_bytes).decode()