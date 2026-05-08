"""
FinanceDesk v1.1 — test_couche1.py
Tests de validation de la Couche 1 : DB + sécurité.
Exécuter avec : python test_couche1.py
"""

import sys
import os
import tempfile
import sqlite3
from pathlib import Path

# ── Patch du chemin DB pour les tests (évite d'écrire dans AppData) ──────────
os.environ["APPDATA"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).parent))

from core.db_manager import (
    init_db, get_connection, get_config, set_config,
    backup_db, rows_to_list, db_exists, DB_PATH,
    CFG_PASSWORD_HASH, CFG_SMTP_HOST, CFG_SEUIL_CAISSE
)
from core.security import (
    hash_password, verify_password, set_master_password,
    check_master_password, is_password_set
)

PASS_COUNT = 0
FAIL_COUNT = 0


def test(name: str, condition: bool) -> None:
    global PASS_COUNT, FAIL_COUNT
    if condition:
        print(f"  ✓  {name}")
        PASS_COUNT += 1
    else:
        print(f"  ✗  {name}  ← ÉCHEC")
        FAIL_COUNT += 1


# ══════════════════════════════════════════════════════════════════════════════
print("\n─── Couche 1A : Initialisation base de données ───")

init_db()
test("Fichier .db créé", db_exists())

conn = get_connection()
tables = {r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
).fetchall()}
conn.close()

for tbl in ["factures","virements","petite_caisse","recettes","budgets","rappels","config","schema_version"]:
    test(f"Table '{tbl}' existe", tbl in tables)

# ══════════════════════════════════════════════════════════════════════════════
print("\n─── Couche 1B : Contraintes & intégrité ───")

conn = get_connection()
# Test montant >= 0
try:
    conn.execute("INSERT INTO factures (numero,fournisseur,montant,date_echeance) VALUES ('X','Y',-1,'2025-01-01')")
    conn.commit()
    test("Montant négatif refusé", False)
except sqlite3.IntegrityError:
    test("Montant négatif refusé", True)

# Test statut invalide
try:
    conn.execute("INSERT INTO factures (numero,fournisseur,montant,date_echeance,statut) VALUES ('X','Y',100,'2025-01-01','invalide')")
    conn.commit()
    test("Statut invalide refusé", False)
except sqlite3.IntegrityError:
    test("Statut invalide refusé", True)

# Test categorie caisse invalide
try:
    conn.execute("""INSERT INTO petite_caisse
        (date_operation,description,categorie,type_operation,montant)
        VALUES ('2025-01-01','test','MauvaiseCat','sortie',50)""")
    conn.commit()
    test("Catégorie caisse invalide refusée", False)
except sqlite3.IntegrityError:
    test("Catégorie caisse invalide refusée", True)

conn.close()

# ══════════════════════════════════════════════════════════════════════════════
print("\n─── Couche 1C : Config clé-valeur ───")

set_config(CFG_SMTP_HOST, "smtp.gmail.com")
test("set_config fonctionne", get_config(CFG_SMTP_HOST) == "smtp.gmail.com")

set_config(CFG_SMTP_HOST, "smtp.outlook.com")
test("set_config écrase la valeur", get_config(CFG_SMTP_HOST) == "smtp.outlook.com")

set_config(CFG_SEUIL_CAISSE, "200")
test("set_config seuil caisse", get_config(CFG_SEUIL_CAISSE) == "200")

test("get_config clé inexistante retourne None", get_config("inexistant") is None)
test("get_config avec default", get_config("inexistant", "def") == "def")

# ══════════════════════════════════════════════════════════════════════════════
print("\n─── Couche 1D : Sécurité (bcrypt) ───")

# Hash & verify
hashed = hash_password("MonMotDePasse123")
test("Hash n'est pas le mot de passe en clair", hashed != "MonMotDePasse123")
test("Hash commence par $2b$", hashed.startswith("$2b$"))
test("Vérification correcte", verify_password("MonMotDePasse123", hashed))
test("Vérification incorrecte", not verify_password("mauvais", hashed))
test("Deux hashs différents pour même mdp", hash_password("abc") != hash_password("abc"))

# Mot de passe maître
test("Pas de mdp configuré au départ", not is_password_set())
set_master_password("Admin2025!")
test("Mdp maître configuré après set", is_password_set())
test("check_master_password correct", check_master_password("Admin2025!"))
test("check_master_password incorrect", not check_master_password("mauvais"))

# Longueur minimale
try:
    set_master_password("ab")
    test("Mdp trop court refusé", False)
except ValueError:
    test("Mdp trop court refusé", True)

# ══════════════════════════════════════════════════════════════════════════════
print("\n─── Couche 1E : Sauvegarde ───")

backup_path = backup_db()
test("Backup créé", backup_path.exists())
test("Backup est une DB valide", sqlite3.connect(str(backup_path)).execute("SELECT 1").fetchone() is not None)

# ══════════════════════════════════════════════════════════════════════════════
print("\n─── Couche 1F : Insert données réelles + rows_to_list ───")

conn = get_connection()
conn.execute("""
    INSERT INTO budgets (nom, montant_alloue) VALUES ('Marketing', 20000)
""")
conn.execute("""
    INSERT INTO factures (numero, fournisseur, montant, date_echeance, budget_id)
    VALUES ('FAC-2025-001', 'Orange Pro', 1240.00, '2025-04-24',
        (SELECT id FROM budgets WHERE nom='Marketing'))
""")
conn.execute("""
    INSERT INTO petite_caisse (date_operation, description, categorie, type_operation, montant, solde_apres)
    VALUES ('2025-04-20', 'Achat fournitures bureau', 'Fournitures', 'sortie', 87.50, 412.50)
""")
conn.execute("""
    INSERT INTO recettes (date_reception, nom_payeur, numero_facture, ref_transaction, montant)
    VALUES ('2025-04-18', 'Client Dupont', 'FAC-CLI-001', 'VIR-ABC-123', 5000.00)
""")
conn.execute("""
    INSERT INTO rappels (fournisseur, montant, date_echeance, email_dest)
    VALUES ('AWS Cloud', 2150.00, '2025-05-05', 'finance@entreprise.com')
""")
conn.commit()

factures  = rows_to_list(conn.execute("SELECT * FROM factures").fetchall())
caisse    = rows_to_list(conn.execute("SELECT * FROM petite_caisse").fetchall())
recettes  = rows_to_list(conn.execute("SELECT * FROM recettes").fetchall())
budgets   = rows_to_list(conn.execute("SELECT * FROM budgets").fetchall())
rappels   = rows_to_list(conn.execute("SELECT * FROM rappels").fetchall())
conn.close()

test("Facture insérée et lisible comme dict", len(factures) == 1 and factures[0]["fournisseur"] == "Orange Pro")
test("Petite caisse insérée", caisse[0]["montant"] == 87.50)
test("Recette insérée", recettes[0]["montant"] == 5000.00)
test("Budget inséré", budgets[0]["nom"] == "Marketing")
test("Rappel inséré", rappels[0]["fournisseur"] == "AWS Cloud")
test("Budget lié à facture via FK", factures[0]["budget_id"] == budgets[0]["id"])

# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{'═'*50}")
total = PASS_COUNT + FAIL_COUNT
print(f"  Résultat : {PASS_COUNT}/{total} tests passés", end="")
if FAIL_COUNT == 0:
    print("  — COUCHE 1 VALIDÉE ✓")
else:
    print(f"  — {FAIL_COUNT} ÉCHEC(S) ✗")
print(f"{'═'*50}\n")
sys.exit(0 if FAIL_COUNT == 0 else 1)
