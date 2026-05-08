"""
FinanceDesk v1.1 — cash_service.py
Petite caisse : entrées/sorties, solde temps réel, alerte seuil, rapprochement.
"""

from core.db_manager import (
    get_connection, rows_to_list, get_config,
    today_iso, now_iso, CFG_SEUIL_CAISSE
)

CATEGORIES = [
    "Fournitures", "Transport", "Repas",
    "Remboursement employé", "Réapprovisionnement caisse", "Divers"
]


# ══════════════════════════════════════════════════════════════════════════════
#  SOLDE
# ══════════════════════════════════════════════════════════════════════════════

def get_solde_caisse() -> float:
    """Calcule le solde en temps réel depuis toutes les opérations."""
    with get_connection() as conn:
        row = conn.execute("""
            SELECT COALESCE(
                SUM(CASE WHEN type_operation='entree' THEN montant ELSE -montant END), 0
            ) FROM petite_caisse
        """).fetchone()
    return round(row[0], 2)


def is_sous_seuil() -> tuple[bool, float]:
    """
    Vérifie si le solde est sous le seuil d'alerte configuré.
    Retourne (True, solde) si alerte, (False, solde) sinon.
    """
    solde  = get_solde_caisse()
    seuil  = float(get_config(CFG_SEUIL_CAISSE, "200"))
    return (solde < seuil, solde)


# ══════════════════════════════════════════════════════════════════════════════
#  LECTURE
# ══════════════════════════════════════════════════════════════════════════════

def get_operations(date_debut=None, date_fin=None) -> list[dict]:
    sql = """
        SELECT pc.*, b.nom as budget_nom
        FROM petite_caisse pc
        LEFT JOIN budgets b ON pc.budget_id = b.id
        WHERE 1=1
    """
    params = []
    if date_debut:
        sql += " AND pc.date_operation >= ?"
        params.append(date_debut)
    if date_fin:
        sql += " AND pc.date_operation <= ?"
        params.append(date_fin)
    sql += " ORDER BY pc.date_operation DESC, pc.id DESC"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return rows_to_list(rows)


def get_operation_by_id(op_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM petite_caisse WHERE id=?", (op_id,)
        ).fetchone()
    return dict(row) if row else None


# ══════════════════════════════════════════════════════════════════════════════
#  ÉCRITURE
# ══════════════════════════════════════════════════════════════════════════════

def add_operation(date_operation: str, description: str, categorie: str,
                  type_operation: str, montant: float,
                  justificatif: str = "", budget_id: int = None) -> dict:
    """
    Ajoute une opération caisse.
    Retourne {'id': ..., 'solde_apres': ..., 'alerte': bool}.
    """
    if type_operation not in ("entree", "sortie"):
        raise ValueError("type_operation doit être 'entree' ou 'sortie'.")
    if categorie not in CATEGORIES:
        raise ValueError(f"Catégorie invalide. Choisir parmi : {CATEGORIES}")
    if not description.strip():
        raise ValueError("La description est obligatoire.")
    if montant <= 0:
        raise ValueError("Le montant doit être supérieur à 0.")

    solde_actuel = get_solde_caisse()
    if type_operation == "sortie":
        solde_apres = round(solde_actuel - montant, 2)
    else:
        solde_apres = round(solde_actuel + montant, 2)

    with get_connection() as conn:
        cur = conn.execute("""
            INSERT INTO petite_caisse
                (date_operation, description, categorie, type_operation,
                 montant, solde_apres, justificatif, budget_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (date_operation, description, categorie, type_operation,
              montant, solde_apres, justificatif, budget_id))
        conn.commit()

    seuil      = float(get_config(CFG_SEUIL_CAISSE, "200"))
    alerte     = solde_apres < seuil
    return {"id": cur.lastrowid, "solde_apres": solde_apres, "alerte": alerte}


def delete_operation(op_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM petite_caisse WHERE id=?", (op_id,))
        conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
#  RAPPROCHEMENT
# ══════════════════════════════════════════════════════════════════════════════

def rapprocher_caisse(montant_physique: float) -> dict:
    """
    Compare le solde théorique (calculé) avec le montant physiquement compté.
    Retourne un rapport d'écart.
    """
    solde_theorique = get_solde_caisse()
    ecart           = round(montant_physique - solde_theorique, 2)
    return {
        "solde_theorique": solde_theorique,
        "montant_physique": round(montant_physique, 2),
        "ecart":           ecart,
        "statut":          "ok" if ecart == 0 else ("surplus" if ecart > 0 else "deficit"),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  KPI DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

def get_stats_caisse() -> dict:
    mois = today_iso()[:7]
    with get_connection() as conn:
        entrees = conn.execute(
            "SELECT COALESCE(SUM(montant),0) FROM petite_caisse "
            "WHERE type_operation='entree' AND date_operation LIKE ?",
            (f"{mois}%",)
        ).fetchone()[0]
        sorties = conn.execute(
            "SELECT COALESCE(SUM(montant),0) FROM petite_caisse "
            "WHERE type_operation='sortie' AND date_operation LIKE ?",
            (f"{mois}%",)
        ).fetchone()[0]
    alerte, solde = is_sous_seuil()
    return {
        "solde":           solde,
        "entrees_mois":    round(entrees, 2),
        "sorties_mois":    round(sorties, 2),
        "alerte_seuil":    alerte,
        "seuil_configure": float(get_config(CFG_SEUIL_CAISSE, "200")),
    }
