#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import secrets
import hashlib
import os

def custom_generate_password_hash(password):
    """Genera un hash sicuro della password usando SHA-256"""
    salt = secrets.token_hex(8)
    pwdhash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"sha256${salt}${pwdhash}"

# Credenziali admin
admin_username = "admin"
admin_password = "admin123"

# Genera hash della password
password_hash = custom_generate_password_hash(admin_password)

# Crea oggetto admin
admin_user = {
    "id": "1",
    "username": admin_username,
    "password": password_hash,
    "is_admin": True
}

# Salva nel file admin_users.json
admin_users = [admin_user]
with open('admin_users.json', 'w', encoding='utf-8') as file:
    json.dump(admin_users, file, indent=2)

print(f"File admin_users.json creato con successo!")
print(f"Username: {admin_username}")
print(f"Password: {admin_password}")
print(f"Hash generato: {password_hash}")