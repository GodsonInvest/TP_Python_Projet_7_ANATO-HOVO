"""
Tests des modèles utilisateur (Bloc 5 — modèles).
Couvre : Utilisateur (ABC), Etudiant, Enseignant, Responsable, Administrateur.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.utilisateur import (
    Utilisateur, Etudiant, Enseignant, Responsable, Administrateur
)
from services.authentification import Authentification


# ── Fixtures locales ────────────────────────────────────────────────────────────

@pytest.fixture
def hash_mdp():
    return Authentification.hacher_mot_de_passe("secret123")


@pytest.fixture
def etudiant(hash_mdp):
    return Etudiant(
        "Alice Dupont", "alice@etud.bj", "alice", hash_mdp,
        matricule="ET2024001", classe="L2",
        ecole_id=1, unite_formation_id=3,
    )


@pytest.fixture
def enseignant(hash_mdp):
    return Enseignant("Prof Martin", "martin@univ.bj", "martin", hash_mdp, "Bases de données")


@pytest.fixture
def responsable(hash_mdp):
    return Responsable("Mme Kola", "kola@univ.bj", "kola", hash_mdp, "M1")


@pytest.fixture
def admin(hash_mdp):
    return Administrateur("Super Admin", "admin@univ.bj", "admin", hash_mdp)


# ── Utilisateur est abstrait ────────────────────────────────────────────────────

class TestUtilisateurABC:

    def test_instanciation_directe_impossible(self):
        with pytest.raises(TypeError):
            Utilisateur("Nom", "a@b.fr", "login", "hash")  # type: ignore

    def test_role_abstrait_force_implementation(self):
        """Chaque sous-classe doit définir role."""
        assert Etudiant.role is not None
        assert Enseignant.role is not None


# ── Propriétés communes ─────────────────────────────────────────────────────────

class TestPropriétésCommunes:

    def test_id_initial_none(self, etudiant):
        assert etudiant.id is None

    def test_id_setter_une_seule_fois(self, etudiant):
        etudiant.id = 5
        assert etudiant.id == 5
        etudiant.id = 99          # doit être ignoré
        assert etudiant.id == 5   # inchangé

    def test_nom_getter(self, etudiant):
        assert etudiant.nom == "Alice Dupont"

    def test_nom_setter_valide(self, etudiant):
        etudiant.nom = "  Alice M.  "
        assert etudiant.nom == "Alice M."

    def test_email_getter(self, etudiant):
        assert etudiant.email == "alice@etud.bj"

    def test_email_setter_valide(self, etudiant):
        etudiant.email = "nouvelle@email.bj"
        assert etudiant.email == "nouvelle@email.bj"

    def test_email_setter_invalide(self, etudiant):
        with pytest.raises(ValueError, match="invalide"):
            etudiant.email = "pasdearobase"

    def test_login_immuable(self, etudiant):
        assert etudiant.login == "alice"
        assert not hasattr(type(etudiant).login, "fset") or type(etudiant).login.fset is None

    def test_mot_de_passe_setter_valide(self, etudiant):
        nouveau_hash = Authentification.hacher_mot_de_passe("nouveaumdp")
        etudiant.mot_de_passe = nouveau_hash
        assert etudiant.mot_de_passe == nouveau_hash

    def test_mot_de_passe_trop_court(self, etudiant):
        with pytest.raises(ValueError, match="6"):
            etudiant.mot_de_passe = "abc"

    def test_date_inscription_non_nulle(self, etudiant):
        assert etudiant.date_inscription is not None

    def test_repr_contient_login(self, etudiant):
        r = repr(etudiant)
        assert "alice" in r


# ── Etudiant ────────────────────────────────────────────────────────────────────

class TestEtudiant:

    def test_role(self, etudiant):
        assert etudiant.role == "etudiant"

    def test_matricule(self, etudiant):
        assert etudiant.matricule == "ET2024001"

    def test_classe(self, etudiant):
        assert etudiant.classe == "L2"

    def test_classe_setter(self, etudiant):
        etudiant.classe = "L3"
        assert etudiant.classe == "L3"

    def test_ecole_id(self, etudiant):
        assert etudiant.ecole_id == 1

    def test_ecole_id_setter(self, etudiant):
        etudiant.ecole_id = 7
        assert etudiant.ecole_id == 7

    def test_unite_formation_id(self, etudiant):
        assert etudiant.unite_formation_id == 3

    def test_unite_formation_id_setter(self, etudiant):
        etudiant.unite_formation_id = 99
        assert etudiant.unite_formation_id == 99

    def test_to_dict_contient_champs_etudiant(self, etudiant):
        d = etudiant.to_dict()
        assert d["role"] == "etudiant"
        assert d["matricule"] == "ET2024001"
        assert d["classe"] == "L2"
        assert d["ecole_id"] == 1
        assert d["unite_formation_id"] == 3

    def test_to_dict_contient_champs_communs(self, etudiant):
        d = etudiant.to_dict()
        for champ in ("id", "nom", "email", "login", "mot_de_passe", "date_inscription"):
            assert champ in d

    def test_etudiant_sans_ecole(self, hash_mdp):
        e = Etudiant("Bob", "bob@x.bj", "bob", hash_mdp, "ET002", "L1")
        assert e.ecole_id is None
        assert e.unite_formation_id is None


# ── Enseignant ──────────────────────────────────────────────────────────────────

class TestEnseignant:

    def test_role(self, enseignant):
        assert enseignant.role == "enseignant"

    def test_matiere(self, enseignant):
        assert enseignant.matiere == "Bases de données"

    def test_matiere_setter(self, enseignant):
        enseignant.matiere = "Réseaux"
        assert enseignant.matiere == "Réseaux"

    def test_to_dict_contient_matiere(self, enseignant):
        d = enseignant.to_dict()
        assert d["role"] == "enseignant"
        assert d["matiere"] == "Bases de données"


# ── Responsable ─────────────────────────────────────────────────────────────────

class TestResponsable:

    def test_role(self, responsable):
        assert responsable.role == "responsable"

    def test_classe(self, responsable):
        assert responsable.classe == "M1"

    def test_classe_setter(self, responsable):
        responsable.classe = "M2"
        assert responsable.classe == "M2"

    def test_to_dict_contient_classe(self, responsable):
        d = responsable.to_dict()
        assert d["role"] == "responsable"
        assert d["classe"] == "M1"


# ── Administrateur ──────────────────────────────────────────────────────────────

class TestAdministrateur:

    def test_role(self, admin):
        assert admin.role == "admin"

    def test_to_dict_role_admin(self, admin):
        assert admin.to_dict()["role"] == "admin"

    def test_attribuer_role_responsable(self, admin, enseignant):
        resp = admin.attribuer_role_responsable(enseignant, "L1")
        assert isinstance(resp, Responsable)
        assert resp.role == "responsable"
        assert resp.classe == "L1"
        assert resp.nom == enseignant.nom
        assert resp.email == enseignant.email
        assert resp.login == enseignant.login

    def test_revoquer_vers_etudiant(self, admin, responsable):
        etud = admin.revoquer_role_responsable(responsable, "etudiant")
        assert isinstance(etud, Etudiant)
        assert etud.role == "etudiant"
        assert etud.nom == responsable.nom

    def test_revoquer_vers_enseignant(self, admin, responsable):
        ens = admin.revoquer_role_responsable(responsable, "enseignant")
        assert isinstance(ens, Enseignant)
        assert ens.role == "enseignant"

    def test_revoquer_role_inconnu(self, admin, responsable):
        with pytest.raises(ValueError, match="inconnu"):
            admin.revoquer_role_responsable(responsable, "directeur")

    def test_attribuer_preserve_mot_de_passe(self, admin, enseignant):
        resp = admin.attribuer_role_responsable(enseignant, "L2")
        assert resp.mot_de_passe == enseignant.mot_de_passe
