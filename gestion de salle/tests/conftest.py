"""
Fixtures partagées pour la suite de tests pytest (Bloc 5).
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, time

from models.salle import Salle
from models.utilisateur import (
    Administrateur, Enseignant, Etudiant, Responsable
)
from models.reservation import Reservation
from services.authentification import Authentification
from services.gestion_reservation import GestionReservation


# ── Salles ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def salle_a():
    s = Salle("Amphi A", 200, ["vidéoprojecteur", "micro"])
    s.id = 1
    return s


@pytest.fixture
def salle_b():
    s = Salle("Salle B", 30, ["tableau"])
    s.id = 2
    return s


# ── Utilisateurs ───────────────────────────────────────────────────────────────

@pytest.fixture
def mdp_hash():
    return Authentification.hacher_mot_de_passe("motdepasse")


@pytest.fixture
def admin(mdp_hash):
    a = Administrateur("Admin Test", "admin@univ.bj", "admin", mdp_hash)
    a.id = 10
    return a


@pytest.fixture
def responsable(mdp_hash):
    r = Responsable("Prof Dupont", "dupont@univ.bj", "dupont", mdp_hash, "L3")
    r.id = 20
    return r


@pytest.fixture
def enseignant(mdp_hash):
    e = Enseignant("Dr Martin", "martin@univ.bj", "martin", mdp_hash, "Algorithmique")
    e.id = 30
    return e


@pytest.fixture
def etudiant(mdp_hash):
    et = Etudiant(
        "Alice", "alice@etud.bj", "alice", mdp_hash,
        matricule="ET001", classe="L3",
        ecole_id=1, unite_formation_id=5,
    )
    et.id = 40
    return et


# ── Réservations ───────────────────────────────────────────────────────────────

@pytest.fixture
def reservation_base(salle_a, responsable):
    """Réservation simple du 2026-06-01 de 08h00 à 10h00."""
    r = Reservation(
        salle=salle_a,
        responsable=responsable,
        classe="L3",
        date_reservation=date(2026, 6, 1),
        heure_debut=time(8, 0),
        heure_fin=time(10, 0),
        matiere="Algorithmique",
    )
    return r


@pytest.fixture
def gestionnaire():
    return GestionReservation()
