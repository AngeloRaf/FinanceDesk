"""
FinanceDesk v1.1 — budget_service.py
Budgets : création, calcul automatique consommé, solde restant, progression.
"""

from core.db_manager import get_connection, rows_to_list, now_iso


def get_budgets() -> list[dict]:
    """
    Retourne tous les budgets avec montant_consomme calculé automatiquement
    depuis factures payées + virements + sorties petite caisse.
    """
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM budgets ORDER BY nom").fetchall()
        budgets = rows_to_list(rows)
        for b in budgets:
            b["montant_consomme"] = _calcul_consomme(conn, b["id"])
            b["solde_restant"]    = round(b["montant_alloue"] - b["montant_consomme"], 2)
            alloue = b["montant_alloue"]
            b["progression_pct"]  = round(
                (b["montant_consomme"] / alloue * 100) if alloue > 0 else 0, 1
            )
            b["statut"] = _statut_budget(b["progression_pct"])
    return budgets


def get_budget_by_id(budget_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM budgets WHERE id=?", (budget_id,)
        ).fetchone()
        if not row:
            return None
        b = dict(row)
        b["montant_consomme"] = _calcul_consomme(conn, budget_id)
        b["solde_restant"]    = round(b["montant_alloue"] - b["montant_consomme"], 2)
        alloue = b["montant_alloue"]
        b["progression_pct"]  = round(
            (b["montant_consomme"] / alloue * 100) if alloue > 0 else 0, 1
        )
        b["statut"] = _statut_budget(b["progression_pct"])
    return b


def add_budget(nom: str, montant_alloue: float) -> int:
    if not nom.strip():
        raise ValueError("Le nom du budget est obligatoire.")
    if montant_alloue < 0:
        raise ValueError("Le montant alloué ne peut pas être négatif.")
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO budgets (nom, montant_alloue) VALUES (?, ?)",
            (nom.strip(), montant_alloue)
        )
        conn.commit()
        return cur.lastrowid


def update_budget(budget_id: int, nom: str = None,
                  montant_alloue: float = None) -> None:
    fields = {}
    if nom is not None:
        fields["nom"] = nom.strip()
    if montant_alloue is not None:
        if montant_alloue < 0:
            raise ValueError("Le montant alloué ne peut pas être négatif.")
        fields["montant_alloue"] = montant_alloue
    if not fields:
        return
    fields["updated_at"] = now_iso()
    sql = "UPDATE budgets SET " + ", ".join(f"{k}=?" for k in fields) + " WHERE id=?"
    with get_connection() as conn:
        conn.execute(sql, list(fields.values()) + [budget_id])
        conn.commit()


def delete_budget(budget_id: int) -> None:
    """Supprime un budget — les dépenses liées passent à budget_id=NULL."""
    with get_connection() as conn:
        conn.execute("DELETE FROM budgets WHERE id=?", (budget_id,))
        conn.commit()


def get_liste_budgets_select() -> list[dict]:
    """Retourne id + nom pour remplir les menus déroulants."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, nom FROM budgets ORDER BY nom"
        ).fetchall()
    return rows_to_list(rows)


# ── Utilitaires internes ──────────────────────────────────────────────────────

def _calcul_consomme(conn, budget_id: int) -> float:
    """
    Somme des dépenses associées à ce budget :
    factures payées + virements + sorties petite caisse.
    """
    fac = conn.execute(
        "SELECT COALESCE(SUM(montant),0) FROM factures "
        "WHERE budget_id=? AND statut='payee'", (budget_id,)
    ).fetchone()[0]

    vir = conn.execute(
        "SELECT COALESCE(SUM(montant),0) FROM virements "
        "WHERE budget_id=?", (budget_id,)
    ).fetchone()[0]

    cai = conn.execute(
        "SELECT COALESCE(SUM(montant),0) FROM petite_caisse "
        "WHERE budget_id=? AND type_operation='sortie'", (budget_id,)
    ).fetchone()[0]

    return round(fac + vir + cai, 2)


def _statut_budget(pct: float) -> str:
    if pct >= 90:
        return "critique"
    if pct >= 70:
        return "attention"
    return "ok"
