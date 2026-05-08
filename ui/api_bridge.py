"""
FinanceDesk v1.1 — api_bridge.py
Bridge entre Python et l'interface HTML via PyWebView.
Toutes les méthodes de cette classe sont accessibles depuis JS via :
    window.pywebview.api.nom_methode(args)
"""

import json
from core.db_manager import init_db, get_all_config, set_config
from core.security   import check_master_password, set_master_password, is_password_set

from services.invoice_service  import (
    get_factures_a_payer, get_factures_payees, add_facture,
    add_facture_payee, marquer_payee, update_facture,
    delete_facture, get_stats_factures
)
from services.transfer_service import (
    get_virements, add_virement, delete_virement, get_stats_virements
)
from services.cash_service import (
    get_operations, add_operation, delete_operation,
    get_solde_caisse, rapprocher_caisse, get_stats_caisse,
    is_sous_seuil, CATEGORIES
)
from services.income_service import (
    get_recettes, add_recette, delete_recette, get_stats_recettes
)
from services.budget_service import (
    get_budgets, get_budget_by_id, add_budget, update_budget,
    delete_budget, get_liste_budgets_select
)
from services.reminder_service import (
    get_rappels, add_rappel, delete_rappel, desactiver_rappel,
    verifier_et_envoyer_rappels, tester_smtp, get_stats_rappels
)
from services.export_service import (
    export_factures_excel, export_virements_excel,
    export_caisse_excel, export_recettes_excel, export_rapport_pdf
)
from services.backup_service import (
    backup_db_auto, export_config, import_config,
    generer_rapport_complet, envoyer_backup_email
)


def _ok(data=None) -> str:
    """Réponse succès sérialisée JSON."""
    return json.dumps({"ok": True, "data": data})


def _err(message: str) -> str:
    """Réponse erreur sérialisée JSON."""
    return json.dumps({"ok": False, "erreur": message})


class ApiBridge:
    """
    Classe exposée à PyWebView.
    Chaque méthode retourne une chaîne JSON : {"ok": true, "data": ...}
    ou {"ok": false, "erreur": "..."}.
    """

    # ══════════════════════════════════════════════════════════════════════
    #  DÉMARRAGE & AUTH
    # ══════════════════════════════════════════════════════════════════════

    def demarrage(self) -> str:
        """Appelé au chargement de l'app : init DB + vérification rappels."""
        try:
            init_db()
            rappels_envoyes = verifier_et_envoyer_rappels()
            alerte, solde   = is_sous_seuil()
            return _ok({
                "premier_lancement":  not is_password_set(),
                "rappels_envoyes":    len(rappels_envoyes),
                "alerte_caisse":      alerte,
                "solde_caisse":       solde,
            })
        except Exception as e:
            return _err(str(e))

    def verifier_password(self, password: str) -> str:
        try:
            ok = check_master_password(password)
            return _ok({"valide": ok})
        except Exception as e:
            return _err(str(e))

    def definir_password(self, password: str) -> str:
        try:
            set_master_password(password)
            return _ok()
        except Exception as e:
            return _err(str(e))

    def changer_password(self, ancien: str, nouveau: str) -> str:
        try:
            if not check_master_password(ancien):
                return _err("Mot de passe actuel incorrect.")
            set_master_password(nouveau)
            return _ok()
        except Exception as e:
            return _err(str(e))

    # ══════════════════════════════════════════════════════════════════════
    #  DASHBOARD
    # ══════════════════════════════════════════════════════════════════════

    def get_dashboard(self) -> str:
        try:
            return _ok({
                "factures":  get_stats_factures(),
                "virements": get_stats_virements(),
                "caisse":    get_stats_caisse(),
                "recettes":  get_stats_recettes(),
                "rappels":   get_stats_rappels(),
                "budgets":   get_budgets(),
            })
        except Exception as e:
            return _err(str(e))

    # ══════════════════════════════════════════════════════════════════════
    #  FACTURES
    # ══════════════════════════════════════════════════════════════════════

    def get_factures_a_payer(self, date_debut="", date_fin="") -> str:
        try:
            return _ok(get_factures_a_payer(
                date_debut or None, date_fin or None
            ))
        except Exception as e:
            return _err(str(e))

    def get_factures_payees(self, date_debut="", date_fin="") -> str:
        try:
            return _ok(get_factures_payees(
                date_debut or None, date_fin or None
            ))
        except Exception as e:
            return _err(str(e))

    def ajouter_facture(self, numero: str, fournisseur: str, montant: float,
                        date_echeance: str, commentaire: str = "",
                        budget_id=None) -> str:
        try:
            fid = add_facture(numero, fournisseur, float(montant),
                              date_echeance, commentaire,
                              int(budget_id) if budget_id else None)
            return _ok({"id": fid})
        except Exception as e:
            return _err(str(e))

    def ajouter_facture_payee(self, numero, fournisseur, montant,
                               date_echeance, date_paiement,
                               ref_transaction, mode_reglement,
                               commentaire="", budget_id=None) -> str:
        try:
            fid = add_facture_payee(
                numero, fournisseur, float(montant), date_echeance,
                date_paiement, ref_transaction, mode_reglement,
                commentaire, int(budget_id) if budget_id else None
            )
            return _ok({"id": fid})
        except Exception as e:
            return _err(str(e))

    def marquer_facture_payee(self, facture_id: int, ref_transaction: str,
                               mode_reglement: str, date_paiement: str = "") -> str:
        try:
            marquer_payee(int(facture_id), ref_transaction, mode_reglement,
                          date_paiement or None)
            return _ok()
        except Exception as e:
            return _err(str(e))

    def modifier_facture(self, facture_id: int, **kwargs) -> str:
        try:
            update_facture(int(facture_id), **kwargs)
            return _ok()
        except Exception as e:
            return _err(str(e))

    def supprimer_facture(self, facture_id: int) -> str:
        try:
            delete_facture(int(facture_id))
            return _ok()
        except Exception as e:
            return _err(str(e))

    def exporter_factures(self, date_debut="", date_fin="") -> str:
        try:
            toutes = get_factures_a_payer(date_debut or None, date_fin or None)
            toutes += get_factures_payees(date_debut or None, date_fin or None)
            path = export_factures_excel(toutes, date_debut, date_fin)
            return _ok({"chemin": path})
        except Exception as e:
            return _err(str(e))

    # ══════════════════════════════════════════════════════════════════════
    #  VIREMENTS
    # ══════════════════════════════════════════════════════════════════════

    def get_virements(self, date_debut="", date_fin="") -> str:
        try:
            return _ok(get_virements(date_debut or None, date_fin or None))
        except Exception as e:
            return _err(str(e))

    def ajouter_virement(self, date_virement, beneficiaire, montant,
                          ref_transaction="", commentaire="", budget_id=None) -> str:
        try:
            vid = add_virement(date_virement, beneficiaire, float(montant),
                               ref_transaction, commentaire,
                               int(budget_id) if budget_id else None)
            return _ok({"id": vid})
        except Exception as e:
            return _err(str(e))

    def supprimer_virement(self, virement_id: int) -> str:
        try:
            delete_virement(int(virement_id))
            return _ok()
        except Exception as e:
            return _err(str(e))

    def exporter_virements(self, date_debut="", date_fin="") -> str:
        try:
            path = export_virements_excel(
                get_virements(date_debut or None, date_fin or None),
                date_debut, date_fin
            )
            return _ok({"chemin": path})
        except Exception as e:
            return _err(str(e))

    # ══════════════════════════════════════════════════════════════════════
    #  PETITE CAISSE
    # ══════════════════════════════════════════════════════════════════════

    def get_operations_caisse(self, date_debut="", date_fin="") -> str:
        try:
            return _ok(get_operations(date_debut or None, date_fin or None))
        except Exception as e:
            return _err(str(e))

    def get_solde_caisse(self) -> str:
        try:
            return _ok({"solde": get_solde_caisse()})
        except Exception as e:
            return _err(str(e))

    def get_categories_caisse(self) -> str:
        return _ok(CATEGORIES)

    def ajouter_operation_caisse(self, date_operation, description, categorie,
                                  type_operation, montant,
                                  justificatif="", budget_id=None) -> str:
        try:
            result = add_operation(
                date_operation, description, categorie, type_operation,
                float(montant), justificatif,
                int(budget_id) if budget_id else None
            )
            return _ok(result)
        except Exception as e:
            return _err(str(e))

    def supprimer_operation_caisse(self, op_id: int) -> str:
        try:
            delete_operation(int(op_id))
            return _ok()
        except Exception as e:
            return _err(str(e))

    def rapprocher_caisse(self, montant_physique: float) -> str:
        try:
            return _ok(rapprocher_caisse(float(montant_physique)))
        except Exception as e:
            return _err(str(e))

    def exporter_caisse(self, date_debut="", date_fin="") -> str:
        try:
            path = export_caisse_excel(
                get_operations(date_debut or None, date_fin or None),
                date_debut, date_fin
            )
            return _ok({"chemin": path})
        except Exception as e:
            return _err(str(e))

    # ══════════════════════════════════════════════════════════════════════
    #  RECETTES
    # ══════════════════════════════════════════════════════════════════════

    def get_recettes(self, date_debut="", date_fin="") -> str:
        try:
            return _ok(get_recettes(date_debut or None, date_fin or None))
        except Exception as e:
            return _err(str(e))

    def ajouter_recette(self, date_reception, nom_payeur, montant,
                         numero_facture="", ref_transaction="",
                         commentaire="") -> str:
        try:
            rid = add_recette(date_reception, nom_payeur, float(montant),
                              numero_facture, ref_transaction, commentaire)
            return _ok({"id": rid})
        except Exception as e:
            return _err(str(e))

    def supprimer_recette(self, recette_id: int) -> str:
        try:
            delete_recette(int(recette_id))
            return _ok()
        except Exception as e:
            return _err(str(e))

    def exporter_recettes(self, date_debut="", date_fin="") -> str:
        try:
            path = export_recettes_excel(
                get_recettes(date_debut or None, date_fin or None),
                date_debut, date_fin
            )
            return _ok({"chemin": path})
        except Exception as e:
            return _err(str(e))

    # ══════════════════════════════════════════════════════════════════════
    #  BUDGETS
    # ══════════════════════════════════════════════════════════════════════

    def get_budgets(self) -> str:
        try:
            return _ok(get_budgets())
        except Exception as e:
            return _err(str(e))

    def get_budgets_select(self) -> str:
        try:
            return _ok(get_liste_budgets_select())
        except Exception as e:
            return _err(str(e))

    def ajouter_budget(self, nom: str, montant_alloue: float) -> str:
        try:
            bid = add_budget(nom, float(montant_alloue))
            return _ok({"id": bid})
        except Exception as e:
            return _err(str(e))

    def modifier_budget(self, budget_id: int, nom=None,
                         montant_alloue=None) -> str:
        try:
            update_budget(int(budget_id), nom,
                          float(montant_alloue) if montant_alloue else None)
            return _ok()
        except Exception as e:
            return _err(str(e))

    def supprimer_budget(self, budget_id: int) -> str:
        try:
            delete_budget(int(budget_id))
            return _ok()
        except Exception as e:
            return _err(str(e))

    # ══════════════════════════════════════════════════════════════════════
    #  RAPPELS
    # ══════════════════════════════════════════════════════════════════════

    def get_rappels(self) -> str:
        try:
            return _ok(get_rappels())
        except Exception as e:
            return _err(str(e))

    def ajouter_rappel(self, fournisseur, montant,
                        date_echeance, email_dest) -> str:
        try:
            rid = add_rappel(fournisseur, float(montant),
                             date_echeance, email_dest)
            return _ok({"id": rid})
        except Exception as e:
            return _err(str(e))

    def supprimer_rappel(self, rappel_id: int) -> str:
        try:
            delete_rappel(int(rappel_id))
            return _ok()
        except Exception as e:
            return _err(str(e))

    def envoyer_rappel_manuel(self, rappel_id: int) -> str:
        try:
            from services.reminder_service import envoyer_email_rappel
            from core.db_manager import get_connection, rows_to_list
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM rappels WHERE id=?", (rappel_id,)
                ).fetchone()
            if not row:
                return _err("Rappel introuvable.")
            envoyer_email_rappel(dict(row))
            return _ok()
        except Exception as e:
            return _err(str(e))

    def tester_smtp(self) -> str:
        try:
            return _ok(tester_smtp())
        except Exception as e:
            return _err(str(e))

    # ══════════════════════════════════════════════════════════════════════
    #  PARAMÈTRES & CONFIG
    # ══════════════════════════════════════════════════════════════════════

    def get_config(self) -> str:
        try:
            cfg = get_all_config()
            # Ne jamais renvoyer le hash du mot de passe au front
            cfg.pop("master_password_hash", None)
            cfg.pop("smtp_password", None)
            return _ok(cfg)
        except Exception as e:
            return _err(str(e))

    def sauvegarder_config(self, config: dict) -> str:
        try:
            for key, value in config.items():
                if key not in ("master_password_hash",):
                    set_config(key, str(value))
            return _ok()
        except Exception as e:
            return _err(str(e))

    # ══════════════════════════════════════════════════════════════════════
    #  SAUVEGARDE & RAPPORTS
    # ══════════════════════════════════════════════════════════════════════

    def backup_maintenant(self) -> str:
        try:
            path = backup_db_auto()
            return _ok({"chemin": str(path)})
        except Exception as e:
            return _err(str(e))

    def exporter_config(self, destination: str) -> str:
        try:
            path = export_config(destination)
            return _ok({"chemin": str(path)})
        except Exception as e:
            return _err(str(e))

    def importer_config(self, source: str, mode: str = "ecraser") -> str:
        try:
            import_config(source, mode)
            return _ok()
        except Exception as e:
            return _err(str(e))

    def generer_rapport(self, date_debut: str, date_fin: str,
                         format_: str = "excel") -> str:
        try:
            path = generer_rapport_complet(date_debut, date_fin, format_)
            return _ok({"chemin": str(path)})
        except Exception as e:
            return _err(str(e))

    def envoyer_backup_email(self) -> str:
        try:
            envoyer_backup_email()
            return _ok()
        except Exception as e:
            return _err(str(e))

    # ══════════════════════════════════════════════════════════════════════
    #  UTILITAIRES UI
    # ══════════════════════════════════════════════════════════════════════

    def ouvrir_fichier(self, chemin: str) -> str:
        """Ouvre un fichier (Excel, PDF) avec l'application par défaut Windows."""
        try:
            import os
            os.startfile(chemin)
            return _ok()
        except Exception as e:
            return _err(str(e))

    def ouvrir_dossier(self, chemin: str) -> str:
        """Ouvre un dossier dans l'explorateur Windows."""
        try:
            import subprocess
            subprocess.Popen(f'explorer "{chemin}"')
            return _ok()
        except Exception as e:
            return _err(str(e))
