"""
FinanceDesk v1.1 — backup_service.py
Sauvegarde automatique, export/import config complète, rapports financiers.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

from core.db_manager import (
    get_config, backup_db, export_full_config, import_full_config,
    CFG_BACKUP_DIR, CFG_SMTP_HOST, CFG_SMTP_PORT,
    CFG_SMTP_USER, CFG_SMTP_PASS, CFG_SMTP_FROM, CFG_EMAIL_DEST
)
from services.invoice_service  import get_factures_a_payer, get_factures_payees, get_stats_factures
from services.transfer_service import get_virements, get_stats_virements
from services.cash_service     import get_operations, get_stats_caisse
from services.income_service   import get_recettes, get_stats_recettes
from services.export_service   import export_rapport_pdf, export_factures_excel


def backup_db_auto() -> Path:
    """Sauvegarde vers le dossier configuré (ou dossier par défaut)."""
    dest = get_config(CFG_BACKUP_DIR)
    return backup_db(dest)


def export_config(destination: str) -> Path:
    return export_full_config(destination)


def import_config(source: str, mode: str = "ecraser") -> None:
    import_full_config(source, mode)


def generer_rapport_complet(date_debut: str, date_fin: str,
                             format_: str = "excel") -> str:
    """
    Génère un rapport financier complet sur la période.
    format_ = 'excel' ou 'pdf'
    """
    factures  = get_factures_a_payer(date_debut, date_fin)
    factures += get_factures_payees(date_debut, date_fin)
    virements = get_virements(date_debut, date_fin)
    caisse    = get_operations(date_debut, date_fin)
    recettes  = get_recettes(date_debut, date_fin)

    stats_f = get_stats_factures()
    stats_v = get_stats_virements()
    stats_c = get_stats_caisse()
    stats_r = get_stats_recettes()

    total_depenses = stats_f["total_a_payer"] + stats_v["total_mois"]
    total_recettes = stats_r["total_mois"]
    solde_net      = round(total_recettes - total_depenses, 2)

    stats = {
        "total_a_payer":   stats_f["total_a_payer"],
        "total_virements": stats_v["total_mois"],
        "total_recettes":  total_recettes,
        "solde_caisse":    stats_c["solde"],
        "solde_net":       solde_net,
    }

    data_rapport = {
        "factures":  factures,
        "virements": virements,
        "caisse":    caisse,
        "recettes":  recettes,
        "stats":     stats,
    }

    if format_ == "pdf":
        return export_rapport_pdf(data_rapport, date_debut, date_fin)
    else:
        return export_factures_excel(factures, date_debut, date_fin)


def envoyer_backup_email() -> None:
    """Envoie le fichier de backup par email."""
    backup_path = backup_db_auto()

    host  = get_config(CFG_SMTP_HOST)
    port  = int(get_config(CFG_SMTP_PORT, "587"))
    user  = get_config(CFG_SMTP_USER)
    pwd   = get_config(CFG_SMTP_PASS)
    from_ = get_config(CFG_SMTP_FROM) or user
    dest  = get_config(CFG_EMAIL_DEST)

    if not all([host, user, pwd, dest]):
        raise ValueError("Configuration SMTP incomplète.")

    msg = MIMEMultipart()
    msg["From"]    = from_
    msg["To"]      = dest
    msg["Subject"] = "[FinanceDesk] Sauvegarde automatique"

    msg.attach(MIMEText(
        f"Veuillez trouver ci-joint la sauvegarde FinanceDesk.\n\n"
        f"Fichier : {backup_path.name}", "plain", "utf-8"
    ))

    with open(backup_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition",
                    f'attachment; filename="{backup_path.name}"')
    msg.attach(part)

    with smtplib.SMTP(host, port, timeout=15) as server:
        server.starttls()
        server.login(user, pwd)
        server.sendmail(from_, dest, msg.as_string())
