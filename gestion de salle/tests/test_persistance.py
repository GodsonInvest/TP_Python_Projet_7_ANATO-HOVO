"""
Tests de la couche de persistance (Bloc 4).
Couvre BaseDonneesSQLite et BaseDonneesJSON avec les memes scenarios.

Usage :
    python tests/test_persistance.py
"""

import os
import sys
import tempfile

# Racine du projet dans sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, time

from models.salle import Salle
from models.utilisateur import Administrateur, Enseignant, Etudiant, Responsable
from models.reservation import Reservation, StatutReservation
from services.authentification import Authentification
from persistance.db_sqlite import BaseDonneesSQLite
from persistance.db_json import BaseDonneesJSON


# ─────────────────────────── Utilitaires ───────────────────────────────────────

def sep(titre: str):
    print(f"\n{'-'*55}")
    print(f"  {titre}")
    print('-'*55)


def ok(msg: str):
    print(f"  [OK] {msg}")


def echec(msg: str):
    print(f"  [ECHEC] {msg}")
    raise AssertionError(msg)


# ─────────────────────────── Scenario de test ──────────────────────────────────

def tester_backend(bd, nom_backend: str):
    """Execute tous les tests sur un backend (SQLite ou JSON)."""

    print(f"\n{'='*55}")
    print(f"  BACKEND : {nom_backend}")
    print('='*55)

    # ── 1. Utilisateurs ──────────────────────────────────────────────────────────
    sep("1. Sauvegarde et chargement des utilisateurs")

    admin = Administrateur("Dr. Admin", "admin@univ.bj", "admin_test", "Admin@123")
    admin.id = 0
    admin.mot_de_passe = Authentification.hacher_mot_de_passe("Admin@123")
    bd.sauvegarder_utilisateur(admin)
    ok(f"Admin sauvegarde — id={admin.id}")

    etudiant = Etudiant("Alice", "alice@univ.bj", "alice_test", "Pass@123",
                        "ETU001", "L3-INFO")
    etudiant.mot_de_passe = Authentification.hacher_mot_de_passe("Pass@123")
    etudiant.id = 1
    bd.sauvegarder_utilisateur(etudiant)
    ok(f"Etudiant sauvegarde — id={etudiant.id}")

    enseignant = Enseignant("Prof. Martin", "martin@univ.bj", "martin_test",
                            "Pass@123", "Algorithmique")
    enseignant.mot_de_passe = Authentification.hacher_mot_de_passe("Pass@123")
    enseignant.id = 2
    bd.sauvegarder_utilisateur(enseignant)
    ok(f"Enseignant sauvegarde — id={enseignant.id}")

    responsable = Responsable("Alice (resp)", "alice@univ.bj", "alice_test",
                              etudiant.mot_de_passe, "L3-INFO")
    responsable.id = 1
    bd.sauvegarder_utilisateur(responsable)
    ok(f"Responsable sauvegarde (ecrase etudiant) — id={responsable.id}")

    # Chargement par id
    u = bd.charger_utilisateur_par_id(2)
    assert u is not None, "Enseignant non trouve par id"
    assert u.role == "enseignant", f"Role attendu 'enseignant', obtenu '{u.role}'"
    assert u.nom == "Prof. Martin"
    ok(f"Chargement par id OK — {u}")

    # Chargement par login
    u2 = bd.charger_utilisateur_par_login("martin_test")
    assert u2 is not None, "Enseignant non trouve par login"
    assert u2.id == 2
    ok("Chargement par login OK")

    # Chargement de tous
    tous = bd.charger_tous_utilisateurs()
    assert len(tous) >= 2, f"Attendu >= 2 utilisateurs, obtenu {len(tous)}"
    ok(f"charger_tous_utilisateurs : {len(tous)} utilisateur(s)")

    # ── 2. Salles ────────────────────────────────────────────────────────────────
    sep("2. Sauvegarde et chargement des salles")

    s1 = Salle("Salle-A-Test", 40, ["Projecteur", "Tableau blanc"])
    s1.id = 10
    bd.sauvegarder_salle(s1)
    ok(f"Salle sauvegardee — id={s1.id}")

    s2 = Salle("Salle-B-Test", 25, ["Climatisation"])
    s2.id = 11
    bd.sauvegarder_salle(s2)
    ok(f"Salle 2 sauvegardee — id={s2.id}")

    # Modification + mise a jour
    s1.capacite = 50
    bd.sauvegarder_salle(s1)
    reloaded = bd.charger_salle_par_id(10)
    assert reloaded is not None, "Salle non trouvee apres update"
    assert reloaded.capacite == 50, f"Capacite attendue 50, obtenue {reloaded.capacite}"
    ok("Mise a jour de la capacite — OK")

    salles = bd.charger_toutes_salles()
    assert len(salles) >= 2
    ok(f"charger_toutes_salles : {len(salles)} salle(s)")

    # Equipements conserves
    s_recharge = bd.charger_salle_par_id(10)
    assert "Projecteur" in s_recharge.equipements, "Equipements perdus apres rechargement"
    ok("Equipements conserves apres rechargement")

    # ── 3. Reservations ──────────────────────────────────────────────────────────
    sep("3. Sauvegarde et chargement des reservations")

    # Reconstruit les dicts attendus par charger_toutes_reservations
    u_dict = {u.id: u for u in bd.charger_tous_utilisateurs()}
    s_dict = {s.id: s for s in bd.charger_toutes_salles()}

    resp = u_dict.get(1)  # responsable id=1
    salle = s_dict.get(10)

    assert resp is not None, "Responsable id=1 introuvable pour la reservation"
    assert salle is not None, "Salle id=10 introuvable pour la reservation"

    r1 = Reservation(
        salle=salle,
        responsable=resp,
        classe="L3-INFO",
        date_reservation=date(2026, 6, 1),
        heure_debut=time(8, 0),
        heure_fin=time(10, 0),
        matiere="Algorithmique",
    )
    r1.confirmer()
    bd.sauvegarder_reservation(r1)
    ok(f"Reservation sauvegardee — id={r1.id}")

    r2 = Reservation(
        salle=salle,
        responsable=resp,
        classe="L2-MATH",
        date_reservation=date(2026, 6, 1),
        heure_debut=time(10, 30),
        heure_fin=time(12, 0),
        matiere="Mathematiques",
    )
    bd.sauvegarder_reservation(r2)
    ok(f"Reservation 2 sauvegardee — id={r2.id}")

    # Modification du statut + mise a jour
    r2.annuler()
    bd.sauvegarder_reservation(r2)

    # Rechargement
    u_dict2 = {u.id: u for u in bd.charger_tous_utilisateurs()}
    s_dict2 = {s.id: s for s in bd.charger_toutes_salles()}
    toutes  = bd.charger_toutes_reservations(s_dict2, u_dict2)
    assert len(toutes) >= 2, f"Attendu >= 2 reservations, obtenu {len(toutes)}"
    ok(f"charger_toutes_reservations : {len(toutes)} reservation(s)")

    r2_rechargee = next((r for r in toutes if r.id == r2.id), None)
    assert r2_rechargee is not None, "Reservation 2 introuvable apres rechargement"
    assert r2_rechargee.statut == StatutReservation.ANNULEE, \
        f"Statut attendu ANNULEE, obtenu {r2_rechargee.statut}"
    ok("Statut ANNULEE conserve apres rechargement")

    r1_rechargee = next((r for r in toutes if r.id == r1.id), None)
    assert r1_rechargee.statut == StatutReservation.CONFIRMEE
    assert r1_rechargee.matiere == "Algorithmique"
    assert r1_rechargee.salle.nom == "Salle-A-Test"
    ok("Reservation 1 : statut, matiere et salle corrects")

    # ── 4. charger_tout() ────────────────────────────────────────────────────────
    sep("4. charger_tout() — integration complete")

    tout = bd.charger_tout()
    assert "utilisateurs"  in tout
    assert "salles"        in tout
    assert "reservations"  in tout
    assert len(tout["utilisateurs"]) >= 2
    assert len(tout["salles"])       >= 2
    assert len(tout["reservations"]) >= 2
    ok(f"charger_tout : {len(tout['utilisateurs'])} user(s), "
       f"{len(tout['salles'])} salle(s), "
       f"{len(tout['reservations'])} res.")

    # ── 5. Suppressions ──────────────────────────────────────────────────────────
    sep("5. Suppressions")

    assert bd.supprimer_reservation(r2.id), "Suppression reservation 2 echouee"
    ok(f"Reservation #{r2.id} supprimee")

    assert not bd.supprimer_reservation(9999), "Suppression d'un id inexistant doit retourner False"
    ok("Suppression id inexistant : retourne False — OK")

    assert bd.supprimer_salle(11), "Suppression salle 2 echouee"
    ok("Salle #11 supprimee")

    assert bd.supprimer_utilisateur(2), "Suppression enseignant echouee"
    ok("Utilisateur #2 supprime")

    print(f"\n  Tous les tests {nom_backend} ont passe. \n")


# ─────────────────────────── Point d'entree ────────────────────────────────────

def main():
    # Dossier temporaire isole pour ne pas polluer data/
    with tempfile.TemporaryDirectory() as tmp:
        print(f"Dossier temporaire : {tmp}")

        # --- SQLite ---
        chemin_db = os.path.join(tmp, "test.db")
        bd_sqlite = BaseDonneesSQLite(chemin_db=chemin_db)
        tester_backend(bd_sqlite, "SQLite")

        # --- JSON ---
        dossier_json = os.path.join(tmp, "json")
        bd_json = BaseDonneesJSON(dossier_data=dossier_json)
        tester_backend(bd_json, "JSON")

    print("\n" + "="*55)
    print("  Tous les tests de persistance sont passes !")
    print("="*55 + "\n")


if __name__ == "__main__":
    main()
