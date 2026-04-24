import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import date, time

from models.utilisateur import Administrateur, Etudiant, Enseignant
from models.salle import Salle
from services.gestion_utilisateurs import GestionUtilisateurs
from services.gestion_salles import GestionSalles
from services.gestion_reservation import GestionReservation
from services.authentification import Authentification


def separator(titre: str):
    print(f"\n{'═'*55}")
    print(f"  {titre}")
    print('═'*55)


def demo():
    # ── 1. Initialisation des services ──────────────────────────────────────
    separator("1. Initialisation des services")
    gest_users   = GestionUtilisateurs()
    gest_salles  = GestionSalles()
    gest_res     = GestionReservation()
    auth         = Authentification(gest_users)
    print("✔ Services instanciés avec succès.")

    # ── 2. Création de l'administrateur (directement en base) ───────────────
    separator("2. Création de l'administrateur")
    admin = Administrateur("Dr. Admin", "admin@univ.bj", "admin", "Admin@123")
    admin.id = 0
    admin.mot_de_passe = Authentification.hacher_mot_de_passe("Admin@123")
    # L'admin est stocké manuellement (contournement de la règle d'inscription)
    gest_users._GestionUtilisateurs__utilisateurs[0] = admin
    print(f"✔ {admin}")

    # ── 3. Inscription d'un étudiant et d'un enseignant ─────────────────────
    separator("3. Inscription des utilisateurs")
    etudiant   = Etudiant("Alice Dupont", "alice@univ.bj",
                          "alice", "Pass@123", "ETU001", "L3-INFO")
    enseignant = Enseignant("Prof. Martin", "martin@univ.bj",
                            "martin", "Pass@123", "Algorithmique")

    gest_users.inscrire(etudiant)
    gest_users.inscrire(enseignant)
    print(f"✔ {etudiant}")
    print(f"✔ {enseignant}")

    # Tentative d'inscription en double → erreur attendue
    try:
        gest_users.inscrire(Etudiant("Bob", "b@b.com", "alice", "xxx", "E2", "L1"))
    except ValueError as e:
        print(f"✔ Doublon bloqué : {e}")

    # ── 4. Promotion au rôle Responsable ────────────────────────────────────
    separator("4. Attribution du rôle Responsable (par l'admin)")
    responsable = gest_users.promouvoir_responsable(admin, etudiant.id, "L3-INFO")
    print(f"✔ Promu : {responsable}")

    # Tentative par un non-admin → erreur attendue
    try:
        gest_users.promouvoir_responsable(enseignant, enseignant.id, "L1")
    except PermissionError as e:
        print(f"✔ Promotion bloquée : {e}")

    # ── 5. Ajout de salles ──────────────────────────────────────────────────
    separator("5. Gestion des salles")
    s1 = Salle("Salle A", 40, ["Projecteur", "Tableau blanc"])
    s2 = Salle("Salle B", 30, ["Projecteur"])
    gest_salles.ajouter_salle(admin, s1)
    gest_salles.ajouter_salle(admin, s2)
    print(f"✔ {s1}")
    print(f"✔ {s2}")

    # ── 6. Connexion utilisateur ─────────────────────────────────────────────
    separator("6. Authentification")
    u = auth.login("alice", "Pass@123")
    print(f"✔ Connexion réussie : {u.login} (rôle: {u.role})")
    print(f"  Est connecté : {auth.est_connecte}")

    # ── 7. Réservation de salle ──────────────────────────────────────────────
    separator("7. Réservation de salle")
    r1 = gest_res.ajouter_reservation(
        salle=s1,
        responsable=responsable,
        classe="L3-INFO",
        date_reservation=date(2026, 5, 10),
        heure_debut=time(10, 0),
        heure_fin=time(12, 0),
        matiere="Algorithmique",
    )
    print(f"✔ Réservation créée : {r1}")

    # ── 8. Détection de conflit ──────────────────────────────────────────────
    separator("8. Détection de conflit")
    try:
        gest_res.ajouter_reservation(
            salle=s1,
            responsable=responsable,
            classe="L2-MATH",
            date_reservation=date(2026, 5, 10),
            heure_debut=time(11, 0),   # ← chevauche 10h–12h
            heure_fin=time(13, 0),
            matiere="Maths",
        )
    except ValueError as e:
        print(f"✔ Conflit détecté et bloqué : {e}")

    # Réservation sans conflit (autre créneau)
    r2 = gest_res.ajouter_reservation(
        salle=s1,
        responsable=responsable,
        classe="L2-MATH",
        date_reservation=date(2026, 5, 10),
        heure_debut=time(14, 0),
        heure_fin=time(16, 0),
        matiere="Maths",
    )
    print(f"✔ Deuxième réservation (sans conflit) : {r2}")

    # ── 9. Consultation du planning ──────────────────────────────────────────
    separator("9. Planning du 10/05/2026")
    planning = gest_res.afficher_planning(filtre_date=date(2026, 5, 10))
    for r in planning:
        print(
            f"  [{r.salle.nom}] {r.heure_debut.strftime('%H:%M')}–"
            f"{r.heure_fin.strftime('%H:%M')} | {r.classe} | {r.matiere}"
        )

    # ── 10. Révocation du rôle ────────────────────────────────────────────────
    separator("10. Révocation du rôle Responsable")
    revoque = gest_users.revoquer_responsable(admin, responsable.id, "etudiant")
    print(f"✔ Rôle révoqué → {revoque}")

    # ── 11. Déconnexion ──────────────────────────────────────────────────────
    separator("11. Déconnexion")
    auth.logout()
    print(f"✔ Déconnecté. Est connecté : {auth.est_connecte}")

    separator("Démonstration terminée avec succès ✅")


if __name__ == "__main__":
    demo()
