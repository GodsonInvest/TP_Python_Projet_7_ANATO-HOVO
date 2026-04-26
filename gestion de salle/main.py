import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import date, time

from models.utilisateur import Administrateur, Etudiant, Enseignant
from models.salle import Salle
from services.gestion_utilisateurs import GestionUtilisateurs
from services.gestion_salles import GestionSalles
from services.gestion_reservation import GestionReservation
from services.authentification import Authentification
from persistance.db_sqlite import BaseDonneesSQLite
from persistance.db_json import BaseDonneesJSON


def separator(titre: str):
    print(f"\n{'='*55}")
    print(f"  {titre}")
    print('='*55)


def demo_poo():
    separator("BLOC 3 — Architecture POO")

    separator("1. Initialisation des services")
    gest_users  = GestionUtilisateurs()
    gest_salles = GestionSalles()
    gest_res    = GestionReservation()
    auth        = Authentification(gest_users)
    print("  Services instancies avec succes.")

    separator("2. Creation de l'administrateur")
    admin = Administrateur("Dr. Admin", "admin@univ.bj", "admin", "Admin@123")
    admin.id = 0
    admin.mot_de_passe = Authentification.hacher_mot_de_passe("Admin@123")
    gest_users._GestionUtilisateurs__utilisateurs[0] = admin
    print(f"  {admin}")

    separator("3. Inscription des utilisateurs")
    etudiant   = Etudiant("Alice Dupont", "alice@univ.bj", "alice", "Pass@123", "ETU001", "L3-INFO")
    enseignant = Enseignant("Prof. Martin", "martin@univ.bj", "martin", "Pass@123", "Algorithmique")
    gest_users.inscrire(etudiant)
    gest_users.inscrire(enseignant)
    print(f"  {etudiant}")
    print(f"  {enseignant}")
    try:
        gest_users.inscrire(Etudiant("Bob", "b@b.com", "alice", "xxx", "E2", "L1"))
    except ValueError as e:
        print(f"  Doublon bloque : {e}")

    separator("4. Attribution du role Responsable")
    responsable = gest_users.promouvoir_responsable(admin, etudiant.id, "L3-INFO")
    print(f"  Promu : {responsable}")
    try:
        gest_users.promouvoir_responsable(enseignant, enseignant.id, "L1")
    except PermissionError as e:
        print(f"  Promotion bloquee : {e}")

    separator("5. Gestion des salles")
    s1 = Salle("Salle A", 40, ["Projecteur", "Tableau blanc"])
    s2 = Salle("Salle B", 30, ["Projecteur"])
    gest_salles.ajouter_salle(admin, s1)
    gest_salles.ajouter_salle(admin, s2)
    print(f"  {s1}")
    print(f"  {s2}")

    separator("6. Authentification")
    u = auth.login("alice", "Pass@123")
    print(f"  Connexion reussie : {u.login} (role: {u.role})")

    separator("7. Reservation de salle")
    r1 = gest_res.ajouter_reservation(
        salle=s1, responsable=responsable, classe="L3-INFO",
        date_reservation=date(2026, 5, 10),
        heure_debut=time(10, 0), heure_fin=time(12, 0),
        matiere="Algorithmique",
    )
    print(f"  Reservation creee : {r1}")

    separator("8. Detection de conflit")
    try:
        gest_res.ajouter_reservation(
            salle=s1, responsable=responsable, classe="L2-MATH",
            date_reservation=date(2026, 5, 10),
            heure_debut=time(11, 0), heure_fin=time(13, 0),
            matiere="Maths",
        )
    except ValueError as e:
        print(f"  Conflit detecte et bloque : {e}")
    r2 = gest_res.ajouter_reservation(
        salle=s1, responsable=responsable, classe="L2-MATH",
        date_reservation=date(2026, 5, 10),
        heure_debut=time(14, 0), heure_fin=time(16, 0),
        matiere="Maths",
    )
    print(f"  Deuxieme reservation (sans conflit) : {r2}")

    separator("9. Planning du 10/05/2026")
    for r in gest_res.afficher_planning(filtre_date=date(2026, 5, 10)):
        print(
            f"  [{r.salle.nom}] {r.heure_debut.strftime('%H:%M')}-"
            f"{r.heure_fin.strftime('%H:%M')} | {r.classe} | {r.matiere}"
        )

    separator("10. Revocation du role Responsable")
    revoque = gest_users.revoquer_responsable(admin, responsable.id, "etudiant")
    print(f"  Role revoque -> {revoque}")

    separator("11. Deconnexion")
    auth.logout()
    print(f"  Deconnecte. Est connecte : {auth.est_connecte}")

    separator("Demonstration POO terminee avec succes")
    return gest_users, gest_salles, gest_res


def demo_persistance(gest_users, gest_salles, gest_res):
    separator("BLOC 4 — Persistance des donnees")

    separator("SQLite — Sauvegarde")
    bd = BaseDonneesSQLite()
    print(f"  Base de donnees : {bd}")
    tous_users = gest_users.tous_les_utilisateurs()
    for u in tous_users:
        bd.sauvegarder_utilisateur(u)
    for s in gest_salles.toutes_les_salles():
        bd.sauvegarder_salle(s)
    for r in gest_res.toutes_les_reservations:
        bd.sauvegarder_reservation(r)
    print(f"  {len(tous_users)} utilisateur(s), "
          f"{len(gest_salles.toutes_les_salles())} salle(s), "
          f"{len(gest_res.toutes_les_reservations)} reservation(s) sauvegardes.")

    separator("SQLite — Rechargement depuis la base")
    tout = bd.charger_tout()
    print(f"  Utilisateurs : {len(tout['utilisateurs'])}  "
          f"Salles : {len(tout['salles'])}  "
          f"Reservations : {len(tout['reservations'])}")
    for r in tout['reservations']:
        print(
            f"    [{r.salle.nom}] {r.heure_debut.strftime('%H:%M')}-"
            f"{r.heure_fin.strftime('%H:%M')} | {r.classe} | statut={r.statut.value}"
        )

    separator("JSON — Sauvegarde")
    bd_json = BaseDonneesJSON()
    print(f"  Dossier JSON : {bd_json}")
    for u in gest_users.tous_les_utilisateurs():
        bd_json.sauvegarder_utilisateur(u)
    for s in gest_salles.toutes_les_salles():
        bd_json.sauvegarder_salle(s)
    for r in gest_res.toutes_les_reservations:
        bd_json.sauvegarder_reservation(r)
    print("  Donnees exportees dans data/ (utilisateurs.json, salles.json, reservations.json)")

    separator("JSON — Rechargement depuis les fichiers")
    tout_json = bd_json.charger_tout()
    print(f"  Utilisateurs : {len(tout_json['utilisateurs'])}  "
          f"Salles : {len(tout_json['salles'])}  "
          f"Reservations : {len(tout_json['reservations'])}")

    separator("Demonstration persistance terminee avec succes")


if __name__ == "__main__":
    demo_persistance(*demo_poo())
