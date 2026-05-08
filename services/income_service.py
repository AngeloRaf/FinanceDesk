"""
FinanceDesk v1.1 — income_service.py
Réceptions d'argent bancaires.
"""

from core.db_manager import get_connection, rows_to_list, today_iso


def get_recettes(date_debut=None, date_fin=None) -> list[dict]:
    sql = "SELECT * FROM recettes WHERE 1=1"
    params = []
    if date_debut:
        sql += " AND date_reception >= ?"
        params.append(date_debut)
    if date_fin:
        sql += " AND date_reception <= ?"
        params.append(date_fin)
    sql += " ORDER BY date_reception DESC"
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return rows_to_list(rows)


def add_recette(date_reception: str, nom_payeur: str, montant: float,
                numero_facture: str = "", ref_transaction: str = "",
                commentaire: str = "") -> int:
    if montant <= 0:
        raise ValueError("Le montant doit être supérieur à 0.")
    if not nom_payeur.strip():
        raise ValueError("Le nom du payeur est obligatoire.")
    with get_connection() as conn:
        cur = conn.execute("""
            INSERT INTO recettes
                (date_reception, nom_payeur, montant,
                 numero_facture, ref_transaction, commentaire)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (date_reception, nom_payeur, montant,
              numero_facture, ref_transaction, commentaire))
        conn.commit()
        return cur.lastrowid


def delete_recette(recette_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM recettes WHERE id=?", (recette_id,))
        conn.commit()


def get_stats_recettes() -> dict:
    mois = today_iso()[:7]
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(montant),0) FROM recettes "
            "WHERE date_reception LIKE ?", (f"{mois}%",)
        ).fetchone()
    return {"nb_mois": row[0], "total_mois": round(row[1], 2)}
