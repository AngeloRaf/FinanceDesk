"""
FinanceDesk v1.1 — test_couche2.py
Tests de validation de la Couche 2 : tous les services métier.
"""

import sys, os, tempfile
os.environ["APPDATA"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(__file__))

from core.db_manager import init_db, set_config, CFG_SEUIL_CAISSE, CFG_RAPPEL_JOURS
from core.security import set_master_password

from services.invoice_service  import (add_facture, add_facture_payee, get_factures_a_payer,
                                        get_factures_payees, marquer_payee, get_stats_factures,
                                        delete_facture)
from services.cash_service     import (add_operation, get_solde_caisse, get_operations,
                                        rapprocher_caisse, get_stats_caisse, is_sous_seuil)
from services.transfer_service import (add_virement, get_virements, get_stats_virements,
                                        delete_virement)
from services.income_service   import (add_recette, get_recettes, get_stats_recettes)
from services.budget_service   import (add_budget, get_budgets, get_budget_by_id,
                                        update_budget, delete_budget, get_liste_budgets_select)
from services.reminder_service import (add_rappel, get_rappels, delete_rappel,
                                        tester_smtp, get_stats_rappels)

PASS_COUNT = FAIL_COUNT = 0

def test(name, condition):
    global PASS_COUNT, FAIL_COUNT
    if condition:
        print(f"  ✓  {name}"); PASS_COUNT += 1
    else:
        print(f"  ✗  {name}  ← ÉCHEC"); FAIL_COUNT += 1

def err(name, fn):
    global PASS_COUNT, FAIL_COUNT
    try:
        fn(); print(f"  ✗  {name}  ← ÉCHEC (pas d'erreur)"); FAIL_COUNT += 1
    except (ValueError, Exception):
        print(f"  ✓  {name}"); PASS_COUNT += 1

# ── Init ──────────────────────────────────────────────────────────────────────
init_db()
set_master_password("Test2025!")
set_config(CFG_SEUIL_CAISSE, "500")
set_config(CFG_RAPPEL_JOURS, "7")

# ══════════════════════════════════════════════════════════════════════════════
print("\n─── Couche 2A : Budgets ───")

bid1 = add_budget("Marketing", 20000)
bid2 = add_budget("Infrastructure IT", 30000)
test("Budget créé", bid1 > 0)
test("Deux budgets", len(get_budgets()) == 2)

update_budget(bid1, montant_alloue=25000)
b = get_budget_by_id(bid1)
test("Budget mis à jour", b["montant_alloue"] == 25000)
test("Consommé initial = 0", b["montant_consomme"] == 0)
test("Progression 0%", b["progression_pct"] == 0)
test("Statut ok", b["statut"] == "ok")

sel = get_liste_budgets_select()
test("Liste select non vide", len(sel) >= 2)
test("Liste select a 'id' et 'nom'", "id" in sel[0] and "nom" in sel[0])

err("Budget montant négatif", lambda: add_budget("Test", -100))
err("Budget nom vide", lambda: add_budget("", 1000))

# ══════════════════════════════════════════════════════════════════════════════
print("\n─── Couche 2B : Factures ───")

fid1 = add_facture("FAC-001", "Orange Pro", 1240.00, "2025-05-10",
                   budget_id=bid1)
fid2 = add_facture("FAC-002", "AWS Cloud", 2150.00, "2025-04-30")
fid3 = add_facture_payee("FAC-003", "Sodexo", 800.00, "2025-03-15",
                          "2025-03-14", "VIR-XYZ", "virement", budget_id=bid2)

test("Facture ajoutée", fid1 > 0)
a_payer = get_factures_a_payer()
test("2 factures en attente", len(a_payer) == 2)
payees = get_factures_payees()
test("1 facture payée directement", len(payees) == 1)

# Marquer comme payée par virement
marquer_payee(fid1, "VIR-001", "virement", "2025-05-09")
test("Facture marquée payée", len(get_factures_payees()) == 2)
test("Virement auto créé", len(get_virements()) == 2)

# Marquer comme payée en espèces
marquer_payee(fid2, "CAISSE-001", "especes", "2025-04-29")
test("Facture espèces marquée payée", len(get_factures_payees()) == 3)

stats = get_stats_factures()
test("Stats factures dict", "nb_a_payer" in stats)
test("0 facture restante en attente", stats["nb_a_payer"] == 0)

err("Marquer payée 2 fois", lambda: marquer_payee(fid1, "X", "virement"))
err("Montant négatif facture", lambda: add_facture("X", "Y", -10, "2025-01-01"))

# ══════════════════════════════════════════════════════════════════════════════
print("\n─── Couche 2C : Petite Caisse ───")

# Réappro initiale — on part du solde actuel
solde_avant = get_solde_caisse()
add_operation("2025-04-01", "Réappro initiale", "Réapprovisionnement caisse",
              "entree", 1000.00)
test("Solde augmenté de 1000 après réappro",
     abs(get_solde_caisse() - (solde_avant + 1000.00)) < 0.01)

solde_base = get_solde_caisse()
r1 = add_operation("2025-04-05", "Achat fournitures", "Fournitures",
                   "sortie", 87.50)
test("solde_apres = solde_base - 87.50",
     abs(r1["solde_apres"] - (solde_base - 87.50)) < 0.01)

solde_base2 = get_solde_caisse()
r2 = add_operation("2025-04-10", "Repas équipe", "Repas",
                   "sortie", 150.00)
test("solde_apres = solde_base2 - 150",
     abs(r2["solde_apres"] - (solde_base2 - 150.00)) < 0.01)

# Solde temps réel
solde = get_solde_caisse()
test("Solde temps réel correct (moins sortie caisse FAC-002)", solde < 762.50)

ops = get_operations()
test("Opérations listées", len(ops) >= 3)

# Rapprochement
rapport = rapprocher_caisse(solde)
test("Rapprochement sans écart", rapport["ecart"] == 0 and rapport["statut"] == "ok")
rapport2 = rapprocher_caisse(solde + 50)
test("Rapprochement surplus détecté", rapport2["statut"] == "surplus")
rapport3 = rapprocher_caisse(solde - 30)
test("Rapprochement déficit détecté", rapport3["statut"] == "deficit")

# Alerte seuil (seuil=500, solde ~600 → pas d'alerte encore)
alerte, s = is_sous_seuil()
test("Alerte seuil correcte", isinstance(alerte, bool))

stats_c = get_stats_caisse()
test("Stats caisse dict complet", all(k in stats_c for k in
     ["solde","entrees_mois","sorties_mois","alerte_seuil","seuil_configure"]))

err("Catégorie invalide", lambda: add_operation(
    "2025-04-01","Test","MauvaiseCateg","sortie",10))
err("Montant zéro", lambda: add_operation(
    "2025-04-01","Test","Divers","sortie",0))
err("Description vide", lambda: add_operation(
    "2025-04-01","","Divers","sortie",10))

# ══════════════════════════════════════════════════════════════════════════════
print("\n─── Couche 2D : Virements ───")

nb_vir_avant = len(get_virements())
vid = add_virement("2025-04-20", "Fournisseur Test", 500.00, "VIR-TEST", "Test")
test("Virement ajouté", vid > 0)
virements = get_virements()
test("Virements listables", len(virements) == nb_vir_avant + 1)

# Filtre par période
v_filtre = get_virements("2025-04-01", "2025-04-30")
test("Filtre période virements", all(
    v["date_virement"] >= "2025-04-01" for v in v_filtre
))

stats_v = get_stats_virements()
test("Stats virements dict", "nb_mois" in stats_v)
err("Virement montant zéro", lambda: add_virement("2025-01-01","Test",0))
err("Virement bénéficiaire vide", lambda: add_virement("2025-01-01","",100))

# ══════════════════════════════════════════════════════════════════════════════
print("\n─── Couche 2E : Recettes ───")

rid = add_recette("2025-04-15", "Client Dupont", 5000.00,
                  "FAC-CLI-001", "VIR-CLI-001")
test("Recette ajoutée", rid > 0)
test("Recettes listables", len(get_recettes()) >= 1)

r_filtre = get_recettes("2025-04-01", "2025-04-30")
test("Filtre période recettes", len(r_filtre) >= 1)

stats_r = get_stats_recettes()
test("Stats recettes dict", "nb_mois" in stats_r)
err("Recette montant zéro", lambda: add_recette("2025-01-01","Test",0))
err("Recette payeur vide", lambda: add_recette("2025-01-01","",100))

# ══════════════════════════════════════════════════════════════════════════════
print("\n─── Couche 2F : Budgets — consommation automatique ───")

b_marketing = get_budget_by_id(bid1)
test("Budget Marketing a consommé (factures payées)",
     b_marketing["montant_consomme"] > 0)
test("Progression > 0%", b_marketing["progression_pct"] > 0)

b_infra = get_budget_by_id(bid2)
test("Budget Infra a consommé (facture + virement)",
     b_infra["montant_consomme"] > 0)

# Test statut critique
add_budget("Petit Budget", 100)
bids = {b["nom"]: b["id"] for b in get_budgets()}
add_virement("2025-04-01", "Test", 95, budget_id=bids["Petit Budget"])
b_petit = get_budget_by_id(bids["Petit Budget"])
test("Statut critique à 95%", b_petit["statut"] == "critique")

# ══════════════════════════════════════════════════════════════════════════════
print("\n─── Couche 2G : Rappels ───")

rpid = add_rappel("Orange Pro", 1240.00, "2025-05-10", "finance@test.com")
test("Rappel ajouté", rpid > 0)
rappels = get_rappels()
test("Rappels listables", len(rappels) >= 1)
test("Rappel a jours_restants", "jours_restants" in rappels[0])
test("Rappel a urgence", "urgence" in rappels[0])

stats_rap = get_stats_rappels()
test("Stats rappels dict", "nb_urgents" in stats_rap)

# Test SMTP sans config → erreur propre
result = tester_smtp()
test("Test SMTP sans config retourne erreur propre",
     result["ok"] == False and "erreur" in result)

err("Rappel fournisseur vide", lambda: add_rappel("", 100, "2025-01-01", "a@b.com"))
err("Rappel email vide", lambda: add_rappel("Test", 100, "2025-01-01", ""))

delete_rappel(rpid)
test("Rappel supprimé", len(get_rappels()) == 0)

# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{'═'*52}")
total = PASS_COUNT + FAIL_COUNT
print(f"  Résultat : {PASS_COUNT}/{total} tests passés", end="")
if FAIL_COUNT == 0:
    print("  — COUCHE 2 VALIDÉE ✓")
else:
    print(f"  — {FAIL_COUNT} ÉCHEC(S) ✗")
print(f"{'═'*52}\n")
sys.exit(0 if FAIL_COUNT == 0 else 1)
