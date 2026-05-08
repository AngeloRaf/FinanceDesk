"""
FinanceDesk v1.1 — transfer_service.py
Virements bancaires sortants : historique, filtres, export.
"""

from core.db_manager import get_connection, rows_to_list, today_iso


def get_virements(date_debut=None, date_fin=None) -> list[dict]:
    sql = """
        SELECT v.*, b.nom as budget_nom
        FROM virements v
        LEFT JOIN budgets b ON v.budget_id = b.id
        WHERE 1=1
    """
    params = []
    if date_debut:
        sql += " AND v.date_virement >= ?"
        params.append(date_debut)
    if date_fin:
        sql += " AND v.date_virement <= ?"
        params.append(date_fin)
    sql += " ORDER BY v.date_virement DESC"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return rows_to_list(rows)


def add_virement(date_virement: str, beneficiaire: str, montant: float,
                 ref_transaction: str = "", commentaire: str = "",
                 budget_id: int = None) -> int:
    if montant <= 0:
        raise ValueError("Le montant doit être supérieur à 0.")
    if not beneficiaire.strip():
        raise ValueError("Le bénéficiaire est obligatoire.")

    with get_connection() as conn:
        cur = conn.execute("""
            INSERT INTO virements
                (date_virement, beneficiaire, montant, ref_transaction,
                 commentaire, budget_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (date_virement, beneficiaire, montant,
              ref_transaction, commentaire, budget_id))
        conn.commit()
        return cur.lastrowid


def delete_virement(virement_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM virements WHERE id=?", (virement_id,))
        conn.commit()


def get_stats_virements() -> dict:
    mois = today_iso()[:7]
    with get_connection() as conn:
        total = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(montant),0) FROM virements "
            "WHERE date_virement LIKE ?", (f"{mois}%",)
        ).fetchone()
    return {"nb_mois": total[0], "total_mois": round(total[1], 2)}
