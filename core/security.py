"""
FinanceDesk v1.1 — security.py
Gestion du mot de passe maître : hash bcrypt, vérification, première config.
"""

import bcrypt
from core.db_manager import get_config, set_config, CFG_PASSWORD_HASH


# ══════════════════════════════════════════════════════════════════════════════
#  MOT DE PASSE MAÎTRE
# ══════════════════════════════════════════════════════════════════════════════

def hash_password(password: str) -> str:
    """Retourne le hash bcrypt du mot de passe (str)."""
    salt   = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Vérifie un mot de passe contre son hash stocké."""
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            hashed.encode("utf-8")
        )
    except Exception:
        return False


def is_password_set() -> bool:
    """True si un mot de passe maître a déjà été configuré."""
    return get_config(CFG_PASSWORD_HASH) is not None


def set_master_password(password: str) -> None:
    """Définit ou change le mot de passe maître (stocke le hash)."""
    if len(password) < 4:
        raise ValueError("Le mot de passe doit contenir au moins 4 caractères.")
    hashed = hash_password(password)
    set_config(CFG_PASSWORD_HASH, hashed)


def check_master_password(password: str) -> bool:
    """
    Vérifie le mot de passe saisi au démarrage.
    Retourne True si correct, False sinon.
    """
    stored = get_config(CFG_PASSWORD_HASH)
    if not stored:
        return False
    return verify_password(password, stored)
