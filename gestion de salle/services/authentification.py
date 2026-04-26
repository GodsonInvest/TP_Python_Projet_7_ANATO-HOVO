import hashlib
import hmac
from typing import Optional
from models.utilisateur import Utilisateur


class Authentification:

    ROLES_VALIDES = {"admin", "responsable", "enseignant", "etudiant"}

    def __init__(self, gestionnaire_utilisateurs):
        self.__gestionnaire = gestionnaire_utilisateurs
        self.__utilisateur_courant: Optional[Utilisateur] = None
        self.__connecte: bool = False

    @staticmethod
    def hacher_mot_de_passe(mot_de_passe: str) -> str:
        """SHA-256 du mot de passe (en production : bcrypt)."""
        return hashlib.sha256(mot_de_passe.encode("utf-8")).hexdigest()

    @staticmethod
    def verifier_hash(mot_de_passe: str, hash_stocke: str) -> bool:
        """Comparaison sécurisée contre les attaques timing."""
        hash_saisi = hashlib.sha256(mot_de_passe.encode("utf-8")).hexdigest()
        return hmac.compare_digest(hash_saisi, hash_stocke)

    def login(self, login: str, mot_de_passe: str) -> Utilisateur:
        utilisateur = self.__gestionnaire.trouver_par_login(login)
        if utilisateur is None:
            raise ValueError("Identifiant introuvable.")
        if not self.verifier_hash(mot_de_passe, utilisateur.mot_de_passe):
            raise ValueError("Mot de passe incorrect.")
        self.__utilisateur_courant = utilisateur
        self.__connecte = True
        return utilisateur

    def logout(self):
        self.__utilisateur_courant = None
        self.__connecte = False

    def verifier_role(self, role_requis: str) -> bool:
        if not self.__connecte or self.__utilisateur_courant is None:
            return False
        if role_requis not in self.ROLES_VALIDES:
            raise ValueError(f"Rôle inconnu : {role_requis}")
        return self.__utilisateur_courant.role == role_requis

    def exiger_role(self, role_requis: str):
        if not self.verifier_role(role_requis):
            role_actuel = (
                self.__utilisateur_courant.role
                if self.__utilisateur_courant else "non connecté"
            )
            raise PermissionError(
                f"Accès refusé. Rôle requis : '{role_requis}', "
                f"rôle actuel : '{role_actuel}'."
            )

    @property
    def est_connecte(self) -> bool:
        return self.__connecte

    @property
    def utilisateur_courant(self) -> Optional[Utilisateur]:
        return self.__utilisateur_courant

    def __repr__(self) -> str:
        u = self.__utilisateur_courant
        return (
            f"<Authentification connecte={self.__connecte} "
            f"utilisateur={u.login if u else None}>"
        )
