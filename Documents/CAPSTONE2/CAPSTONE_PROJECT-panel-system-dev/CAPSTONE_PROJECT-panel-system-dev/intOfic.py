import os
import django
import hashlib
from datetime import date

# 1. Setup Django environment settings
# Replace 'myproject' with your actual project root directory folder name
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "caufa_portal.settings")
django.setup()

from core_system.models import OfficerUser


def generate_sha256_hash(password_string):
    """
    Computes a standard, raw SHA-256 hexadecimal hash string.
    """
    encoded_bytes = password_string.encode("utf-8")
    sha256_engine = hashlib.sha256(encoded_bytes)
    return sha256_engine.hexdigest()


def create_initial_officers():
    print("--- Initializing CAUFA Portal Officer Accounts (SHA-256 Mode) ---")

    # Define our three core system roles with default baseline credentials
    initial_users = [
        {
            "full_name": "Madam President",
            "username": "president_admin",
            "password": "SecurePresidentPass2026!",
            "role": "President",
        },
        {
            "full_name": "Chief Auditor",
            "username": "auditor_admin",
            "password": "SecureAuditorPass2026!",
            "role": "Auditor",
        },
        {
            "full_name": "Head Treasurer",
            "username": "treasurer_admin",
            "password": "SecureTreasurerPass2026!",
            "role": "Treasurer",
        },
    ]

    for user_data in initial_users:
        # Check if username already exists to prevent duplication crashes
        if OfficerUser.objects.filter(username=user_data["username"]).exists():
            print(f"[!] User '{user_data['username']}' already exists. Skipping.")
            continue

        # Cryptographically hash the plaintext using SHA-256
        hashed_password = generate_sha256_hash(user_data["password"])

        # Instantiate and commit row parameters to the database
        officer = OfficerUser(
            full_name=user_data["full_name"],
            username=user_data["username"],
            password_hash=hashed_password,
            role=user_data["role"],
            account_status="Active",
            term_start=date(2026, 6, 1),
            term_end=date(2027, 6, 1),
            mfa_secret=None,
        )
        officer.save()
        print(
            f"[✓] Created {user_data['role']} Account | Username: {user_data['username']}"
        )

    print("-----------------------------------------------------------------")


if __name__ == "__main__":
    create_initial_officers()
