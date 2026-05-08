"""
FinanceDesk v1.1 — build.py
Script de build automatisé : PyInstaller + NSIS
Exécuter avec : python build.py
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

BASE_DIR  = Path(__file__).parent
DIST_DIR  = BASE_DIR / "dist" / "FinanceDesk"
BUILD_DIR = BASE_DIR / "build"


def etape(msg):
    print(f"\n{'─'*50}")
    print(f"  {msg}")
    print(f"{'─'*50}")


def verifier_prerequis():
    etape("Vérification des prérequis")

    # Vérifier PyInstaller
    try:
        import PyInstaller
        print(f"  ✓ PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("  ✗ PyInstaller manquant — pip install pyinstaller")
        sys.exit(1)

    # Vérifier le fichier .spec
    spec = BASE_DIR / "financedesk.spec"
    if not spec.exists():
        print("  ✗ financedesk.spec introuvable")
        sys.exit(1)
    print("  ✓ financedesk.spec trouvé")

    # Vérifier les fichiers UI
    for f in ["ui/FinanceDesk_v1_1.html", "ui/login.html", "ui/app.js"]:
        p = BASE_DIR / f
        if not p.exists():
            print(f"  ✗ Fichier manquant : {f}")
            sys.exit(1)
        print(f"  ✓ {f}")

    # Vérifier l'icône (non bloquant)
    ico = BASE_DIR / "assets" / "logo.ico"
    if not ico.exists():
        print("  ⚠ assets/logo.ico manquant — icône par défaut utilisée")
        _creer_ico_defaut()
    else:
        print("  ✓ logo.ico")


def _creer_ico_defaut():
    """Crée un logo.ico minimal si absent."""
    ico_path = BASE_DIR / "assets" / "logo.ico"
    ico_path.parent.mkdir(parents=True, exist_ok=True)
    # ICO 16x16 minimal (fichier binaire valide)
    ico_data = bytes([
        0,0,1,0,1,0,16,16,0,0,1,0,32,0,104,4,
        0,0,22,0,0,0,40,0,0,0,16,0,0,0,32,0,
        0,0,1,0,32,0,0,0,0,0,0,4,0,0,0,0,
        0,0,0,0,0,0,0,0,0,0,0,0,0,0
    ] + [26,58,107,255] * 256 + [0]*128)
    ico_path.write_bytes(ico_data)
    print("  ✓ logo.ico créé (défaut bleu FinanceDesk)")


def nettoyer():
    etape("Nettoyage des builds précédents")
    for d in [DIST_DIR.parent, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)
            print(f"  ✓ Supprimé : {d}")


def build_exe():
    etape("Build PyInstaller → .exe")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller",
         "financedesk.spec", "--noconfirm"],
        cwd=str(BASE_DIR)
    )
    if result.returncode != 0:
        print("  ✗ PyInstaller a échoué")
        sys.exit(1)

    exe = DIST_DIR / "FinanceDesk.exe"
    if exe.exists():
        size_mb = exe.stat().st_size / (1024 * 1024)
        print(f"  ✓ FinanceDesk.exe créé ({size_mb:.1f} MB)")
    else:
        print("  ✗ FinanceDesk.exe introuvable après build")
        sys.exit(1)


def build_installer():
    etape("Build NSIS → installateur .exe")

    # Chercher makensis
    nsis_paths = [
        r"C:\Program Files (x86)\NSIS\makensis.exe",
        r"C:\Program Files\NSIS\makensis.exe",
        "makensis",
    ]

    makensis = None
    for p in nsis_paths:
        if Path(p).exists() or p == "makensis":
            try:
                subprocess.run([p, "/VERSION"],
                               capture_output=True, check=True)
                makensis = p
                break
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue

    if not makensis:
        print("  ⚠ NSIS non trouvé — ignoré")
        print("  → Téléchargez NSIS sur https://nsis.sourceforge.io/")
        print("  → Puis relancez : makensis installer.nsi")
        return

    result = subprocess.run(
        [makensis, "installer.nsi"],
        cwd=str(BASE_DIR)
    )
    if result.returncode == 0:
        setup = BASE_DIR / "FinanceDesk_v1.1_Setup.exe"
        if setup.exists():
            size_mb = setup.stat().st_size / (1024 * 1024)
            print(f"  ✓ FinanceDesk_v1.1_Setup.exe créé ({size_mb:.1f} MB)")
    else:
        print("  ✗ NSIS a échoué — vérifiez installer.nsi")


def afficher_resultat():
    etape("Résultat final")
    print(f"  Dossier dist/ : {DIST_DIR}")

    setup = BASE_DIR / "FinanceDesk_v1.1_Setup.exe"
    if setup.exists():
        print(f"\n  ┌─────────────────────────────────────────┐")
        print(f"  │  FinanceDesk_v1.1_Setup.exe  — PRÊT ✓  │")
        print(f"  └─────────────────────────────────────────┘")
        print(f"\n  Testez sur une machine vierge :")
        print(f"  1. Copiez FinanceDesk_v1.1_Setup.exe")
        print(f"  2. Double-cliquez pour installer")
        print(f"  3. Lancez depuis le Bureau")
    else:
        print(f"\n  FinanceDesk.exe disponible dans :")
        print(f"  {DIST_DIR / 'FinanceDesk.exe'}")
        print(f"\n  Pour créer l'installateur :")
        print(f"  1. Installez NSIS : https://nsis.sourceforge.io/")
        print(f"  2. Lancez : makensis installer.nsi")


if __name__ == "__main__":
    print("\n" + "═"*50)
    print("  FinanceDesk v1.1 — Build Script")
    print("═"*50)

    verifier_prerequis()
    nettoyer()
    build_exe()
    build_installer()
    afficher_resultat()

    print("\n" + "═"*50 + "\n")
