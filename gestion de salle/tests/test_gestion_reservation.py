"""
Tests du service GestionReservation et du modèle Reservation (Bloc 5).
Couvre : création, conflits, modification avec rollback, annulation,
         filtres du planning, durée, et format de classe multi-unités.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, time
from models.salle import Salle
from models.utilisateur import Responsable
from models.reservation import Reservation, StatutReservation
from services.gestion_reservation import GestionReservation
from services.authentification import Authentification


# ── Fixtures locales ────────────────────────────────────────────────────────────

@pytest.fixture
def hash_mdp():
    return Authentification.hacher_mot_de_passe("pass")


@pytest.fixture
def salle1():
    s = Salle("Amphi 200", 200, ["vidéoprojecteur"])
    s.id = 1
    return s


@pytest.fixture
def salle2():
    s = Salle("Salle TD", 30)
    s.id = 2
    return s


@pytest.fixture
def resp(hash_mdp):
    r = Responsable("Dupont", "dupont@univ.bj", "dupont", hash_mdp, "L3")
    r.id = 1
    return r


@pytest.fixture
def gest():
    return GestionReservation()


JOUR = date(2026, 9, 15)


def ajouter(gest, salle, resp, classe, debut_h, fin_h, matiere=""):
    return gest.ajouter_reservation(
        salle=salle,
        responsable=resp,
        classe=classe,
        date_reservation=JOUR,
        heure_debut=time(debut_h, 0),
        heure_fin=time(fin_h, 0),
        matiere=matiere,
    )


# ── Modèle Reservation ──────────────────────────────────────────────────────────

class TestReservationModele:

    def test_creation_valide(self, salle1, resp):
        r = Reservation(salle1, resp, "L3", JOUR, time(8, 0), time(10, 0))
        assert r.salle is salle1
        assert r.classe == "L3"
        assert r.statut == StatutReservation.EN_ATTENTE

    def test_heure_debut_superieure_fin_interdit(self, salle1, resp):
        with pytest.raises(ValueError):
            Reservation(salle1, resp, "L3", JOUR, time(10, 0), time(8, 0))

    def test_heures_egales_interdites(self, salle1, resp):
        with pytest.raises(ValueError):
            Reservation(salle1, resp, "L3", JOUR, time(9, 0), time(9, 0))

    def test_duree_minutes(self, salle1, resp):
        r = Reservation(salle1, resp, "L3", JOUR, time(8, 0), time(10, 30))
        assert r.duree_minutes() == 150

    def test_confirmer(self, salle1, resp):
        r = Reservation(salle1, resp, "L3", JOUR, time(8, 0), time(10, 0))
        r.confirmer()
        assert r.statut == StatutReservation.CONFIRMEE

    def test_annuler(self, salle1, resp):
        r = Reservation(salle1, resp, "L3", JOUR, time(8, 0), time(10, 0))
        r.annuler()
        assert r.statut == StatutReservation.ANNULEE

    def test_to_dict_champs(self, salle1, resp):
        r = Reservation(salle1, resp, "L3", JOUR, time(8, 0), time(10, 0), "Algo")
        d = r.to_dict()
        assert d["classe"] == "L3"
        assert d["matiere"] == "Algo"
        assert d["heure_debut"] == "08:00"
        assert d["heure_fin"] == "10:00"
        assert d["statut"] == "en_attente"

    def test_repr_contient_salle(self, salle1, resp):
        r = Reservation(salle1, resp, "L3", JOUR, time(8, 0), time(10, 0))
        assert "Amphi 200" in repr(r)


# ── Chevauchement ───────────────────────────────────────────────────────────────

class TestChevauchement:

    def test_meme_salle_meme_plage_chevauche(self, salle1, resp):
        r1 = Reservation(salle1, resp, "L1", JOUR, time(8, 0), time(10, 0))
        r2 = Reservation(salle1, resp, "L2", JOUR, time(8, 0), time(10, 0))
        assert r1.chevauche(r2)

    def test_plages_qui_se_chevauchent_partiellement(self, salle1, resp):
        r1 = Reservation(salle1, resp, "L1", JOUR, time(8, 0), time(10, 0))
        r2 = Reservation(salle1, resp, "L2", JOUR, time(9, 0), time(11, 0))
        assert r1.chevauche(r2)

    def test_plages_adjacentes_ne_chevauchent_pas(self, salle1, resp):
        r1 = Reservation(salle1, resp, "L1", JOUR, time(8, 0), time(10, 0))
        r2 = Reservation(salle1, resp, "L2", JOUR, time(10, 0), time(12, 0))
        assert not r1.chevauche(r2)

    def test_salles_differentes_pas_de_conflit(self, salle1, salle2, resp):
        r1 = Reservation(salle1, resp, "L1", JOUR, time(8, 0), time(10, 0))
        r2 = Reservation(salle2, resp, "L2", JOUR, time(8, 0), time(10, 0))
        assert not r1.chevauche(r2)

    def test_dates_differentes_pas_de_conflit(self, salle1, resp):
        r1 = Reservation(salle1, resp, "L1", date(2026, 9, 15), time(8, 0), time(10, 0))
        r2 = Reservation(salle1, resp, "L2", date(2026, 9, 16), time(8, 0), time(10, 0))
        assert not r1.chevauche(r2)

    def test_r1_inclus_dans_r2(self, salle1, resp):
        r1 = Reservation(salle1, resp, "L1", JOUR, time(9, 0), time(10, 0))
        r2 = Reservation(salle1, resp, "L2", JOUR, time(8, 0), time(12, 0))
        assert r1.chevauche(r2)


# ── GestionReservation ──────────────────────────────────────────────────────────

class TestAjoutReservation:

    def test_ajout_simple(self, gest, salle1, resp):
        r = ajouter(gest, salle1, resp, "L3", 8, 10)
        assert r is not None
        assert r.statut == StatutReservation.CONFIRMEE

    def test_ajout_retourne_reservation_avec_id(self, gest, salle1, resp):
        r = ajouter(gest, salle1, resp, "L3", 8, 10)
        assert r.id is not None

    def test_conflit_leve_erreur(self, gest, salle1, resp):
        ajouter(gest, salle1, resp, "L3", 8, 10)
        with pytest.raises(ValueError, match="[Cc]onflit"):
            ajouter(gest, salle1, resp, "L2", 9, 11)

    def test_salles_differentes_pas_de_conflit(self, gest, salle1, salle2, resp):
        ajouter(gest, salle1, resp, "L3", 8, 10)
        r2 = ajouter(gest, salle2, resp, "L3", 8, 10)
        assert r2 is not None

    def test_plages_consecutives_acceptees(self, gest, salle1, resp):
        ajouter(gest, salle1, resp, "L1", 8, 10)
        r2 = ajouter(gest, salle1, resp, "L2", 10, 12)
        assert r2 is not None

    def test_nombre_reservations_incremente(self, gest, salle1, resp):
        ajouter(gest, salle1, resp, "L1", 8, 10)
        ajouter(gest, salle1, resp, "L2", 10, 12)
        assert len(gest.toutes_les_reservations) == 2


class TestModificationReservation:

    def test_modification_valide(self, gest, salle1, resp):
        r = ajouter(gest, salle1, resp, "L3", 8, 10)
        modifiee = gest.modifier_reservation(r.id, JOUR, time(14, 0), time(16, 0))
        assert modifiee.heure_debut == time(14, 0)
        assert modifiee.heure_fin == time(16, 0)

    def test_modification_avec_conflit_rollback(self, gest, salle1, resp):
        r1 = ajouter(gest, salle1, resp, "L1", 8, 10)
        r2 = ajouter(gest, salle1, resp, "L2", 10, 12)
        with pytest.raises(ValueError, match="[Cc]onflit"):
            gest.modifier_reservation(r2.id, JOUR, time(9, 0), time(11, 0))
        # rollback : r2 doit avoir ses horaires d'origine
        assert r2.heure_debut == time(10, 0)
        assert r2.heure_fin == time(12, 0)

    def test_modification_id_inconnu(self, gest):
        with pytest.raises(ValueError, match="introuvable"):
            gest.modifier_reservation(9999, JOUR, time(8, 0), time(10, 0))

    def test_modification_peut_garder_meme_plage(self, gest, salle1, resp):
        r = ajouter(gest, salle1, resp, "L3", 8, 10)
        modifiee = gest.modifier_reservation(r.id, JOUR, time(8, 0), time(10, 0))
        assert modifiee.id == r.id


class TestSuppressionReservation:

    def test_suppression_existante(self, gest, salle1, resp):
        r = ajouter(gest, salle1, resp, "L3", 8, 10)
        ok = gest.supprimer_reservation(r.id)
        assert ok is True

    def test_reservation_supprimee_libere_creneau(self, gest, salle1, resp):
        r1 = ajouter(gest, salle1, resp, "L3", 8, 10)
        gest.supprimer_reservation(r1.id)
        r2 = ajouter(gest, salle1, resp, "L2", 8, 10)
        assert r2 is not None

    def test_suppression_id_inconnu(self, gest):
        ok = gest.supprimer_reservation(9999)
        assert ok is False


class TestFiltresPlanning:

    def test_planning_filtre_par_date(self, gest, salle1, resp):
        ajouter(gest, salle1, resp, "L3", 8, 10)
        resultats = gest.afficher_planning(filtre_date=JOUR)
        assert len(resultats) == 1

    def test_planning_date_differente_vide(self, gest, salle1, resp):
        ajouter(gest, salle1, resp, "L3", 8, 10)
        autre_jour = date(2026, 12, 31)
        assert gest.afficher_planning(filtre_date=autre_jour) == []

    def test_planning_filtre_salle(self, gest, salle1, salle2, resp):
        ajouter(gest, salle1, resp, "L3", 8, 10)
        ajouter(gest, salle2, resp, "L3", 8, 10)
        resultats = gest.afficher_planning(filtre_salle_nom="Amphi")
        assert all("Amphi" in r.salle.nom for r in resultats)

    def test_planning_filtre_classe(self, gest, salle1, resp):
        ajouter(gest, salle1, resp, "L3", 8, 10)
        ajouter(gest, salle1, resp, "L1", 10, 12)
        resultats = gest.afficher_planning(filtre_classe="L3")
        assert len(resultats) == 1
        assert resultats[0].classe == "L3"

    def test_planning_tri_par_horaire(self, gest, salle1, resp):
        ajouter(gest, salle1, resp, "L2", 12, 14)
        ajouter(gest, salle1, resp, "L1", 8, 10)
        resultats = gest.afficher_planning()
        assert resultats[0].heure_debut < resultats[1].heure_debut

    def test_reservations_par_salle(self, gest, salle1, salle2, resp):
        ajouter(gest, salle1, resp, "L3", 8, 10)
        ajouter(gest, salle2, resp, "L3", 8, 10)
        resultats = gest.reservations_par_salle(salle1.id)
        assert all(r.salle.id == salle1.id for r in resultats)

    def test_reservations_par_responsable(self, gest, salle1, resp, hash_mdp):
        ajouter(gest, salle1, resp, "L3", 8, 10)
        autre_resp = Responsable("Autre", "autre@univ.bj", "autre", hash_mdp, "L1")
        autre_resp.id = 99
        gest.ajouter_reservation(salle1, autre_resp, "L1", date(2026, 10, 1), time(8, 0), time(10, 0))
        assert len(gest.reservations_par_responsable(resp.id)) == 1
