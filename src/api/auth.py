"""
auth.py — Simple admin authentication with JWT tokens
"""
import jwt
import time
import bcrypt
from src.config import ADMIN_USERNAME, ADMIN_PASSWORD, SECRET_KEY


def get_password_hash():
    return bcrypt.hashpw(ADMIN_PASSWORD.encode('utf-8'), bcrypt.gensalt())

_admin_hash = get_password_hash()


def verify_admin(username, password):
    if username != ADMIN_USERNAME:
        return False
    return bcrypt.checkpw(password.encode('utf-8'), _admin_hash)


def create_token(username):
    payload = {
        'sub': username,
        'iat': int(time.time()),
        'exp': int(time.time()) + 86400  # 24h
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')


def verify_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload.get('sub')
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
