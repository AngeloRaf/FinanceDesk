"""
FinanceDesk v1.1 — reminder_service.py
Rappels de paiement : vérification au démarrage, envoi SMTP automatique.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date, timedelta

from core.db_manager import (
    get_connection, rows_to_list, get_config, today_iso,
    CFG_SMTP_HOST, CFG_SMTP_PORT, CFG_SMTP_USER,
    CFG_SMTP_PASS, CFG_SMTP_FROM, CFG_EMAIL_DEST, CFG_RAPPEL_JOURS
)


# ══════════════════════════════════════════════════════════════════════════════
#  LECTURE
# ══════════════════════════════════════════════════════════════════════════════

def get_rappels() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM rappels ORDER BY date_echeance ASC"
        ).fetchall()
    rappels = rows_to_list(rows)
    today   = date.today()
    for r in rappels:
        echeance    = date.fromisoformat(r["date_echeance"])
        jours_reste = (echeance - today).days
        r["jours_restants"] = jours_reste
        r["urgence"] = _urgence(jours_reste)
    return rappels


def add_rappel(fournisseur: str, montant: float, date_echeance: str,
               email_dest: str) -> int:
    if not fournisseur.strip():
        raise ValueError("Le fournisseur est obligatoire.")
    if montant <= 0:
        raise ValueError("Le montant doit être supérieur à 0.")
    if not email_dest.strip():
        raise ValueError("L'email destinataire est obligatoire.")

    with get_connection() as conn:
        cur = conn.execute("""
            INSERT INTO rappels (fournisseur, montant, date_echeance, email_dest)
            VALUES (?, ?, ?, ?)
        """, (fournisseur.strip(), montant, date_echeance, email_dest.strip()))
        conn.commit()
        return cur.lastrowid


def delete_rappel(rappel_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM rappels WHERE id=?", (rappel_id,))
        conn.commit()


def desactiver_rappel(rappel_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE rappels SET statut='desactive' WHERE id=?", (rappel_id,)
        )
        conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
#  VÉRIFICATION AU DÉMARRAGE
# ══════════════════════════════════════════════════════════════════════════════

def verifier_et_envoyer_rappels() -> list[dict]:
    """
    Appelé au démarrage de l'application.
    Envoie les emails pour les rappels dont l'échéance approche.
    Retourne la liste des rappels traités.
    """
    delai_jours = int(get_config(CFG_RAPPEL_JOURS, "7"))
    today       = date.today()
    limite      = today + timedelta(days=delai_jours)
    traites     = []

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM rappels
            WHERE statut = 'actif'
            AND date_echeance <= ?
        """, (str(limite),)).fetchall()
        rappels = rows_to_list(rows)

    for r in rappels:
        try:
            envoyer_email_rappel(r)
            with get_connection() as conn:
                conn.execute("""
                    UPDATE rappels
                    SET statut='envoye', dernier_envoi=?
                    WHERE id=?
                """, (today_iso(), r["id"]))
                conn.commit()
            r["email_envoye"] = True
        except Exception as e:
            r["email_envoye"] = False
            r["erreur"]       = str(e)
        traites.append(r)

    return traites


# ══════════════════════════════════════════════════════════════════════════════
#  ENVOI EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def envoyer_email_rappel(rappel: dict) -> None:
    """Envoie un email de rappel pour une échéance."""
    _send_email(
        destinataire=rappel["email_dest"],
        sujet=f"[FinanceDesk] Rappel échéance — {rappel['fournisseur']}",
        corps=_corps_rappel(rappel)
    )


def tester_smtp() -> dict:
    """
    Teste la configuration SMTP en envoyant un email de test.
    Retourne {'ok': True} ou {'ok': False, 'erreur': '...'}.
    """
    dest = get_config(CFG_EMAIL_DEST, "")
    if not dest:
        return {"ok": False, "erreur": "Email destinataire non configuré."}
    try:
        _send_email(
            destinataire=dest,
            sujet="[FinanceDesk] Test de configuration SMTP",
            corps="Votre configuration SMTP fonctionne correctement."
        )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


def _send_email(destinataire: str, sujet: str, corps: str) -> None:
    host = get_config(CFG_SMTP_HOST)
    port = int(get_config(CFG_SMTP_PORT, "587"))
    user = get_config(CFG_SMTP_USER)
    pwd  = get_config(CFG_SMTP_PASS)
    from_ = get_config(CFG_SMTP_FROM) or user

    if not all([host, user, pwd]):
        raise ValueError("Configuration SMTP incomplète (host, user, password requis).")

    msg = MIMEMultipart()
    msg["From"]    = from_
    msg["To"]      = destinataire
    msg["Subject"] = sujet
    msg.attach(MIMEText(corps, "plain", "utf-8"))

    with smtplib.SMTP(host, port, timeout=10) as server:
        server.starttls()
        server.login(user, pwd)
        server.sendmail(from_, destinataire, msg.as_string())


def _corps_rappel(r: dict) -> str:
    return (
        f"Bonjour,\n\n"
        f"Rappel de paiement FinanceDesk :\n\n"
        f"  Fournisseur : {r['fournisseur']}\n"
        f"  Montant     : {r['montant']:,.2f} €\n"
        f"  Échéance    : {r['date_echeance']}\n\n"
        f"Merci de procéder au règlement avant la date d'échéance.\n\n"
        f"— FinanceDesk"
    )


def _urgence(jours: int) -> str:
    if jours < 0:
        return "retard"
    if jours <= 3:
        return "urgent"
    if jours <= 7:
        return "bientot"
    return "normal"


def get_stats_rappels() -> dict:
    rappels = get_rappels()
    return {
        "nb_urgents":   sum(1 for r in rappels if r["urgence"] == "urgent"),
        "nb_semaine":   sum(1 for r in rappels if r["urgence"] in ("urgent","bientot")),
        "nb_total":     len(rappels),
    }
