"""
FinanceDesk v1.1 — invoice_service.py
CRUD complet des factures : ajout, modification, filtres, marquer comme payée.
"""

from core.db_manager import get_connection, rows_to_list, today_iso, now_iso


# ══════════════════════════════════════════════════════════════════════════════
#  LECTURE
# ══════════════════════════════════════════════════════════════════════════════

def get_factures_a_payer(date_debut=None, date_fin=None) -> list[dict]:
    """Retourne toutes les factures en attente, avec filtre période optionnel."""
    sql = """
        SELECT f.*, b.nom as budget_nom
        FROM factures f
        LEFT JOIN budgets b ON f.budget_id = b.id
        WHERE f.statut = 'en_attente'
    """
    params = []
    if date_debut:
        sql += " AND f.date_echeance >= ?"
        params.append(date_debut)
    if date_fin:
        sql += " AND f.date_echeance <= ?"
        params.append(date_fin)
    sql += " ORDER BY f.date_echeance ASC"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return rows_to_list(rows)


def get_factures_payees(date_debut=None, date_fin=None) -> list[dict]:
    """Retourne toutes les factures payées, avec filtre période optionnel."""
    sql = """
        SELECT f.*, b.nom as budget_nom
        FROM factures f
        LEFT JOIN budgets b ON f.budget_id = b.id
        WHERE f.statut = 'payee'
    """
    params = []
    if date_debut:
        sql += " AND f.date_paiement >= ?"
        params.append(date_debut)
    if date_fin:
        sql += " AND f.date_paiement <= ?"
        params.append(date_fin)
    sql += " ORDER BY f.date_paiement DESC"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return rows_to_list(rows)


def get_facture_by_id(facture_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM factures WHERE id=?", (facture_id,)
        ).fetchone()
    return dict(row) if row else None


# ══════════════════════════════════════════════════════════════════════════════
#  ÉCRITURE
# ══════════════════════════════════════════════════════════════════════════════

def add_facture(numero: str, fournisseur: str, montant: float,
                date_echeance: str, commentaire: str = "",
                budget_id: int = None) -> int:
    """Ajoute une facture en attente. Retourne l'id créé."""
    if montant < 0:
        raise ValueError("Le montant ne peut pas être négatif.")
    if not numero or not fournisseur:
        raise ValueError("Numéro et fournisseur sont obligatoires.")

    with get_connection() as conn:
        cur = conn.execute("""
            INSERT INTO factures
                (numero, fournisseur, montant, date_echeance, commentaire, budget_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (numero, fournisseur, montant, date_echeance, commentaire, budget_id))
        conn.commit()
        return cur.lastrowid


def add_facture_payee(numero: str, fournisseur: str, montant: float,
                      date_echeance: str, date_paiement: str,
                      ref_transaction: str, mode_reglement: str,
                      commentaire: str = "", budget_id: int = None) -> int:
    """Ajoute directement une facture déjà payée + crée virement ou sortie caisse."""
    if mode_reglement not in ("virement", "especes"):
        raise ValueError("Mode de règlement invalide.")

    with get_connection() as conn:
        cur = conn.execute("""
            INSERT INTO factures
                (numero, fournisseur, montant, date_echeance, commentaire,
                 statut, date_paiement, ref_transaction, mode_reglement, budget_id)
            VALUES (?, ?, ?, ?, ?, 'payee', ?, ?, ?, ?)
        """, (numero, fournisseur, montant, date_echeance, commentaire,
              date_paiement, ref_transaction, mode_reglement, budget_id))

        if mode_reglement == "virement":
            conn.execute("""
                INSERT INTO virements
                    (date_virement, beneficiaire, montant, ref_transaction,
                     commentaire, budget_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (date_paiement, fournisseur, montant, ref_transaction,
                  numero, budget_id))
        else:
            solde = _get_solde_caisse(conn) - montant
            conn.execute("""
                INSERT INTO petite_caisse
                    (date_operation, description, categorie, type_operation,
                     montant, solde_apres, justificatif, budget_id)
                VALUES (?, ?, 'Divers', 'sortie', ?, ?, ?, ?)
            """, (date_paiement,
                  f"Paiement facture {numero} — {fournisseur}",
                  montant, solde, ref_transaction, budget_id))

        conn.commit()
        return cur.lastrowid


def marquer_payee(facture_id: int, ref_transaction: str,
                  mode_reglement: str, date_paiement: str = None) -> None:
    """
    Marque une facture comme payée.
    Si mode_reglement == 'virement', crée aussi l'entrée dans virements.
    Si mode_reglement == 'especes', crée la sortie en petite caisse.
    """
    if mode_reglement not in ("virement", "especes"):
        raise ValueError("Mode de règlement invalide : 'virement' ou 'especes'.")

    date_paiement = date_paiement or today_iso()
    facture = get_facture_by_id(facture_id)
    if not facture:
        raise ValueError(f"Facture {facture_id} introuvable.")
    if facture["statut"] == "payee":
        raise ValueError("Cette facture est déjà marquée comme payée.")

    with get_connection() as conn:
        conn.execute("""
            UPDATE factures SET
                statut          = 'payee',
                date_paiement   = ?,
                ref_transaction = ?,
                mode_reglement  = ?,
                updated_at      = ?
            WHERE id = ?
        """, (date_paiement, ref_transaction, mode_reglement, now_iso(), facture_id))

        # Création automatique du virement ou de la sortie caisse
        if mode_reglement == "virement":
            conn.execute("""
                INSERT INTO virements
                    (date_virement, beneficiaire, montant, ref_transaction,
                     commentaire, budget_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (date_paiement, facture["fournisseur"], facture["montant"],
                  ref_transaction, facture["numero"], facture["budget_id"]))
        else:
            # Calcul du nouveau solde caisse
            solde = _get_solde_caisse(conn) - facture["montant"]
            conn.execute("""
                INSERT INTO petite_caisse
                    (date_operation, description, categorie, type_operation,
                     montant, solde_apres, justificatif, budget_id)
                VALUES (?, ?, 'Divers', 'sortie', ?, ?, ?, ?)
            """, (date_paiement,
                  f"Paiement facture {facture['numero']} — {facture['fournisseur']}",
                  facture["montant"], solde, ref_transaction,
                  facture["budget_id"]))

        conn.commit()


def update_facture(facture_id: int, **kwargs) -> None:
    """Met à jour les champs d'une facture en attente."""
    allowed = {"numero", "fournisseur", "montant", "date_echeance",
               "commentaire", "budget_id"}
    fields  = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    fields["updated_at"] = now_iso()
    sql = "UPDATE factures SET " + ", ".join(f"{k}=?" for k in fields) + " WHERE id=?"
    with get_connection() as conn:
        conn.execute(sql, list(fields.values()) + [facture_id])
        conn.commit()


def delete_facture(facture_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM factures WHERE id=?", (facture_id,))
        conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
#  KPI DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

def get_stats_factures() -> dict:
    """Retourne les KPI : total à payer, en retard, payées ce mois."""
    today = today_iso()
    with get_connection() as conn:
        a_payer = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(montant),0) FROM factures WHERE statut='en_attente'"
        ).fetchone()
        en_retard = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(montant),0) FROM factures "
            "WHERE statut='en_attente' AND date_echeance < ?", (today,)
        ).fetchone()
        mois = today[:7]  # YYYY-MM
        payees_mois = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(montant),0) FROM factures "
            "WHERE statut='payee' AND date_paiement LIKE ?", (f"{mois}%",)
        ).fetchone()

    return {
        "nb_a_payer":      a_payer[0],
        "total_a_payer":   a_payer[1],
        "nb_en_retard":    en_retard[0],
        "total_en_retard": en_retard[1],
        "nb_payees_mois":  payees_mois[0],
        "total_payees_mois": payees_mois[1],
    }


# ── Utilitaire interne ────────────────────────────────────────────────────────
def _get_solde_caisse(conn) -> float:
    row = conn.execute("""
        SELECT COALESCE(
            SUM(CASE WHEN type_operation='entree' THEN montant ELSE -montant END), 0
        ) FROM petite_caisse
    """).fetchone()
    return row[0]
