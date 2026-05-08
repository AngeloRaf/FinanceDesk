"""
FinanceDesk v1.1 — db_manager.py
Gestion complète de la base de données SQLite locale.
Responsabilités : initialisation, migrations, accès centralisé.
"""

import sqlite3
import os
import shutil
from datetime import datetime
from pathlib import Path

# ── Chemin de la base de données ──────────────────────────────────────────────
BASE_DIR = Path(os.getenv("APPDATA", Path.home())) / "FinanceDesk"
DB_PATH  = BASE_DIR / "financedesk.db"

# Version courante du schéma — incrémenter à chaque migration
SCHEMA_VERSION = 1


def get_db_path() -> Path:
    return DB_PATH


def get_connection() -> sqlite3.Connection:
    """Retourne une connexion SQLite avec row_factory dict-like."""
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row          # accès par colonne : row["montant"]
    conn.execute("PRAGMA journal_mode=WAL") # écriture concurrente sûre
    conn.execute("PRAGMA foreign_keys=ON")  # intégrité référentielle
    return conn


# ══════════════════════════════════════════════════════════════════════════════
#  INITIALISATION & MIGRATIONS
# ══════════════════════════════════════════════════════════════════════════════

def init_db() -> None:
    """Crée toutes les tables si elles n'existent pas et applique les migrations."""
    conn = get_connection()
    try:
        _create_all_tables(conn)
        _apply_migrations(conn)
        conn.commit()
    finally:
        conn.close()


def _create_all_tables(conn: sqlite3.Connection) -> None:
    """Définit le schéma complet de l'application."""

    conn.executescript("""

    -- ── Version du schéma ─────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS schema_version (
        version     INTEGER NOT NULL DEFAULT 1,
        updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    -- ── Sécurité ──────────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS config (
        key         TEXT PRIMARY KEY,
        value       TEXT
    );

    -- ── Factures ──────────────────────────────────────────────────────────
    -- Factures fournisseurs (à payer et payées)
    CREATE TABLE IF NOT EXISTS factures (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        numero              TEXT    NOT NULL,            -- ex. FAC-2025-0001
        fournisseur         TEXT    NOT NULL,
        montant             REAL    NOT NULL CHECK(montant >= 0),
        date_echeance       TEXT    NOT NULL,            -- ISO 8601 : YYYY-MM-DD
        commentaire         TEXT,
        statut              TEXT    NOT NULL DEFAULT 'en_attente'
                                    CHECK(statut IN ('en_attente','payee')),
        -- Rempli lors du marquage "payée"
        date_paiement       TEXT,
        ref_transaction     TEXT,
        mode_reglement      TEXT    CHECK(mode_reglement IN ('virement','especes', NULL)),
        budget_id           INTEGER REFERENCES budgets(id) ON DELETE SET NULL,
        created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
        updated_at          TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    -- ── Virements bancaires ────────────────────────────────────────────────
    -- Transactions bancaires sortantes uniquement
    CREATE TABLE IF NOT EXISTS virements (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        date_virement   TEXT    NOT NULL,
        beneficiaire    TEXT    NOT NULL,
        montant         REAL    NOT NULL CHECK(montant >= 0),
        ref_transaction TEXT,
        commentaire     TEXT,                           -- numéro de facture lié
        budget_id       INTEGER REFERENCES budgets(id) ON DELETE SET NULL,
        created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    -- ── Petite caisse ─────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS petite_caisse (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        date_operation  TEXT    NOT NULL,
        description     TEXT    NOT NULL,
        categorie       TEXT    NOT NULL
                                CHECK(categorie IN (
                                    'Fournitures','Transport','Repas',
                                    'Remboursement employé',
                                    'Réapprovisionnement caisse','Divers'
                                )),
        type_operation  TEXT    NOT NULL CHECK(type_operation IN ('entree','sortie')),
        montant         REAL    NOT NULL CHECK(montant > 0),
        -- solde_apres calculé dynamiquement, stocké pour audit
        solde_apres     REAL,
        justificatif    TEXT,                           -- n° reçu ou référence
        budget_id       INTEGER REFERENCES budgets(id) ON DELETE SET NULL,
        created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    -- ── Réceptions d'argent ───────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS recettes (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        date_reception  TEXT    NOT NULL,
        nom_payeur      TEXT    NOT NULL,
        numero_facture  TEXT,
        ref_transaction TEXT,
        montant         REAL    NOT NULL CHECK(montant >= 0),
        commentaire     TEXT,
        created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    -- ── Budgets ───────────────────────────────────────────────────────────
    -- montant_consomme = calculé depuis factures + virements + petite_caisse
    CREATE TABLE IF NOT EXISTS budgets (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        nom             TEXT    NOT NULL UNIQUE,
        montant_alloue  REAL    NOT NULL CHECK(montant_alloue >= 0),
        created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
        updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    -- ── Rappels de paiement ───────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS rappels (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        fournisseur     TEXT    NOT NULL,
        montant         REAL    NOT NULL CHECK(montant >= 0),
        date_echeance   TEXT    NOT NULL,
        email_dest      TEXT    NOT NULL,
        statut          TEXT    NOT NULL DEFAULT 'actif'
                                CHECK(statut IN ('actif','envoye','desactive')),
        dernier_envoi   TEXT,
        created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    """)


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Système de migrations simple basé sur schema_version."""
    rows = conn.execute("SELECT version FROM schema_version").fetchone()
    current = rows["version"] if rows else 0

    if current == 0:
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,)
        )
        return

    # Migration vers v2 (exemple futur) :
    # if current < 2:
    #     conn.execute("ALTER TABLE factures ADD COLUMN tva REAL DEFAULT 0")
    #     conn.execute("UPDATE schema_version SET version=2, updated_at=datetime('now')")


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG & SÉCURITÉ
# ══════════════════════════════════════════════════════════════════════════════

def get_config(key: str, default=None):
    """Lit une valeur de configuration."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM config WHERE key=?", (key,)
        ).fetchone()
    return row["value"] if row else default


def set_config(key: str, value: str) -> None:
    """Écrit ou met à jour une valeur de configuration."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO config (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value)
        )
        conn.commit()


def get_all_config() -> dict:
    """Retourne toute la config sous forme de dict."""
    with get_connection() as conn:
        rows = conn.execute("SELECT key, value FROM config").fetchall()
    return {r["key"]: r["value"] for r in rows}


# ── Clés de config standard ──────────────────────────────────────────────────
CFG_PASSWORD_HASH   = "master_password_hash"
CFG_SMTP_HOST       = "smtp_host"
CFG_SMTP_PORT       = "smtp_port"
CFG_SMTP_USER       = "smtp_user"
CFG_SMTP_PASS       = "smtp_password"         # stocké chiffré
CFG_SMTP_FROM       = "smtp_from"
CFG_EMAIL_DEST      = "email_destinataire"
CFG_RAPPEL_JOURS    = "rappel_jours"          # délai avant échéance
CFG_SEUIL_CAISSE    = "seuil_alerte_caisse"   # ex. "200"
CFG_BACKUP_DIR      = "backup_directory"
CFG_BACKUP_EMAIL    = "backup_email_auto"     # "1" ou "0"


# ══════════════════════════════════════════════════════════════════════════════
#  SAUVEGARDE & RESTAURATION
# ══════════════════════════════════════════════════════════════════════════════

def backup_db(destination_dir: str | None = None) -> Path:
    """
    Copie la base vers le dossier de sauvegarde.
    Retourne le chemin du fichier de sauvegarde créé.
    """
    dest = Path(destination_dir) if destination_dir else BASE_DIR / "backups"
    dest.mkdir(parents=True, exist_ok=True)

    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = dest / f"financedesk_backup_{timestamp}.db"
    shutil.copy2(str(DB_PATH), str(backup_file))
    return backup_file


def export_full_config(destination: str) -> Path:
    """
    Export complet : copie la base de données vers un fichier unique.
    Utilisé pour Import/Export configuration complète.
    """
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(DB_PATH), str(dest))
    return dest


def import_full_config(source: str, mode: str = "ecraser") -> None:
    """
    Importe une configuration depuis un fichier .db.
    mode = 'ecraser' : remplace la base entièrement.
    mode = 'fusionner' : fusionne (non implémenté ici, voir merge_service).
    """
    src = Path(source)
    if not src.exists():
        raise FileNotFoundError(f"Fichier source introuvable : {source}")

    if mode == "ecraser":
        backup_db()                          # sauvegarde avant écrasement
        shutil.copy2(str(src), str(DB_PATH))
    elif mode == "fusionner":
        _merge_db(src)
    else:
        raise ValueError(f"Mode inconnu : {mode}")


def _merge_db(source: Path) -> None:
    """
    Fusion simple : insère les enregistrements manquants depuis la source.
    Les conflits (même id) sont ignorés (INSERT OR IGNORE).
    """
    tables = [
        "factures", "virements", "petite_caisse",
        "recettes", "budgets", "rappels", "config"
    ]
    src_conn  = sqlite3.connect(str(source))
    dest_conn = get_connection()
    try:
        for table in tables:
            rows = src_conn.execute(f"SELECT * FROM {table}").fetchall()
            if not rows:
                continue
            cols   = [d[0] for d in src_conn.execute(
                f"SELECT * FROM {table} LIMIT 0"
            ).description]
            placeholders = ", ".join(["?"] * len(cols))
            col_names    = ", ".join(cols)
            dest_conn.executemany(
                f"INSERT OR IGNORE INTO {table} ({col_names}) VALUES ({placeholders})",
                [tuple(r) for r in rows]
            )
        dest_conn.commit()
    finally:
        src_conn.close()
        dest_conn.close()


# ══════════════════════════════════════════════════════════════════════════════
#  UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def rows_to_list(rows) -> list[dict]:
    """Convertit une liste de sqlite3.Row en liste de dict sérialisable."""
    return [dict(r) for r in rows]


def today_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def db_exists() -> bool:
    return DB_PATH.exists()
