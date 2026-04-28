"""
Tests du service Authentification (Bloc 5).
Couvre : hachage, vérification, login/logout, rôles, état de connexion.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.utilisateur import Administrateur, Enseignant, Etudiant, Responsable
from services.authentification import Authentification


# ── Stub gestionnaire utilisateurs ─────────────────────────────────────────────

class GestionnaireStub:
    """Remplace le vrai GestionUtilisateurs pour les tests unitaires."""

    def __init__(self, utilisateurs: list):
        self._users = {u.login: u for u in utilisateurs}

    def trouver_par_login(self, login: str):
        return self._users.get(login)


# ── Fixtures ────────────────────────────────────────────────────────────────────

MDL_PASS = "monMotDePasse"


@pytest.fixture
def mdp_hash():
    return Authentification.hacher_mot_de_passe(MDL_PASS)


@pytest.fixture
def utilisateurs(mdp_hash):
    admin = Administrateur("Admin", "admin@univ.bj", "admin", mdp_hash)
    admin.id = 1
    ens = Enseignant("Prof X", "x@univ.bj", "profx", mdp_hash, "Maths")
    ens.id = 2
    etud = Etudiant("Bob", "bob@etud.bj", "bob", mdp_hash, "ET001", "L1")
    etud.id = 3
    resp = Responsable("Chef", "chef@univ.bj", "chef", mdp_hash, "M2")
    resp.id = 4
    return [admin, ens, etud, resp]


@pytest.fixture
def auth(utilisateurs):
    gestionnaire = GestionnaireStub(utilisateurs)
    return Authentification(gestionnaire)


# ── Hachage SHA-256 ─────────────────────────────────────────────────────────────

class TestHachage:

    def test_hacher_retourne_string_non_vide(self):
        h = Authentification.hacher_mot_de_passe("test")
        assert isinstance(h, str) and len(h) > 0

    def test_meme_mdp_meme_hash(self):
        assert (
            Authentification.hacher_mot_de_passe("abc")
            == Authentification.hacher_mot_de_passe("abc")
        )

    def test_mdp_differents_hash_differents(self):
        assert (
            Authentification.hacher_mot_de_passe("abc")
            != Authentification.hacher_mot_de_passe("ABC")
        )

    def test_hash_sha256_longueur(self):
        h = Authentification.hacher_mot_de_passe("quelconque")
        assert len(h) == 64  # SHA-256 hex = 64 chars

    def test_verifier_hash_correct(self, mdp_hash):
        assert Authentification.verifier_hash(MDL_PASS, mdp_hash) is True

    def test_verifier_hash_incorrect(self, mdp_hash):
        assert Authentification.verifier_hash("mauvais", mdp_hash) is False

    def test_verifier_hash_vide(self, mdp_hash):
        assert Authentification.verifier_hash("", mdp_hash) is False


# ── Login ───────────────────────────────────────────────────────────────────────

class TestLogin:

    def test_login_valide(self, auth):
        u = auth.login("admin", MDL_PASS)
        assert u is not None
        assert u.login == "admin"

    def test_login_met_a_jour_etat(self, auth):
        auth.login("admin", MDL_PASS)
        assert auth.est_connecte is True
        assert auth.utilisateur_courant is not None

    def test_login_login_inconnu(self, auth):
        with pytest.raises(ValueError, match="[Ii]ntrouvable"):
            auth.login("inconnu", MDL_PASS)

    def test_login_mauvais_mot_de_passe(self, auth):
        with pytest.raises(ValueError, match="[Mm]ot de passe"):
            auth.login("admin", "mauvaismdp")

    def test_login_etat_initial_deconnecte(self, auth):
        assert auth.est_connecte is False
        assert auth.utilisateur_courant is None

    def test_login_enseignant(self, auth):
        u = auth.login("profx", MDL_PASS)
        assert u.role == "enseignant"

    def test_login_etudiant(self, auth):
        u = auth.login("bob", MDL_PASS)
        assert u.role == "etudiant"

    def test_login_responsable(self, auth):
        u = auth.login("chef", MDL_PASS)
        assert u.role == "responsable"


# ── Logout ──────────────────────────────────────────────────────────────────────

class TestLogout:

    def test_logout_reinitialise_etat(self, auth):
        auth.login("admin", MDL_PASS)
        auth.logout()
        assert auth.est_connecte is False
        assert auth.utilisateur_courant is None

    def test_logout_sans_login_ne_plante_pas(self, auth):
        auth.logout()
        assert auth.est_connecte is False


# ── Rôles ────────────────────────────────────────────────────────────────────────

class TestVerificationRole:

    def test_verifier_role_correct(self, auth):
        auth.login("admin", MDL_PASS)
        assert auth.verifier_role("admin") is True

    def test_verifier_role_incorrect(self, auth):
        auth.login("admin", MDL_PASS)
        assert auth.verifier_role("etudiant") is False

    def test_verifier_role_sans_connexion(self, auth):
        assert auth.verifier_role("admin") is False

    def test_verifier_role_inconnu_leve_erreur(self, auth):
        auth.login("admin", MDL_PASS)
        with pytest.raises(ValueError, match="inconnu"):
            auth.verifier_role("directeur")

    def test_exiger_role_ok(self, auth):
        auth.login("admin", MDL_PASS)
        auth.exiger_role("admin")   # ne doit pas lever d'exception

    def test_exiger_role_mauvais_role(self, auth):
        auth.login("bob", MDL_PASS)
        with pytest.raises(PermissionError, match="[Rr]efusé"):
            auth.exiger_role("admin")

    def test_exiger_role_deconnecte(self, auth):
        with pytest.raises(PermissionError):
            auth.exiger_role("etudiant")

    def test_roles_valides_connus(self):
        for role in ("admin", "responsable", "enseignant", "etudiant"):
            assert role in Authentification.ROLES_VALIDES


# ── Repr ─────────────────────────────────────────────────────────────────────────

class TestRepr:

    def test_repr_deconnecte(self, auth):
        assert "False" in repr(auth)

    def test_repr_connecte(self, auth):
        auth.login("admin", MDL_PASS)
        assert "admin" in repr(auth)
