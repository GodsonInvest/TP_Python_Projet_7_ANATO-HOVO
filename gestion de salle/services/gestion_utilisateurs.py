from typing import Optional
from models.utilisateur import Utilisateur, Responsable, Administrateur
from services.authentification import Authentification


class GestionUtilisateurs:

    def __init__(self):
        self.__utilisateurs: dict[int, Utilisateur] = {}
        self.__prochain_id: int = 1

    def inscrire(self, utilisateur: Utilisateur) -> Utilisateur:
        if utilisateur.role in ("admin", "responsable"):
            raise PermissionError(
                f"Le rôle '{utilisateur.role}' ne peut pas être inscrit directement."
            )
        if self.trouver_par_login(utilisateur.login):
            raise ValueError(f"Le login '{utilisateur.login}' est déjà utilisé.")

        # hachage avant stockage
        utilisateur.mot_de_passe = Authentification.hacher_mot_de_passe(
            utilisateur.mot_de_passe
        )
        utilisateur.id = self.__prochain_id
        self.__utilisateurs[self.__prochain_id] = utilisateur
        self.__prochain_id += 1
        return utilisateur

    def trouver_par_id(self, user_id: int) -> Optional[Utilisateur]:
        return self.__utilisateurs.get(user_id)

    def trouver_par_login(self, login: str) -> Optional[Utilisateur]:
        for u in self.__utilisateurs.values():
            if u.login == login:
                return u
        return None

    def lister_par_role(self, role: str) -> list[Utilisateur]:
        return [u for u in self.__utilisateurs.values() if u.role == role]

    def tous_les_utilisateurs(self) -> list[Utilisateur]:
        return list(self.__utilisateurs.values())

    def promouvoir_responsable(
        self,
        admin: Administrateur,
        user_id: int,
        classe: str,
    ) -> Responsable:
        if not isinstance(admin, Administrateur):
            raise PermissionError("Seul un Administrateur peut attribuer le rôle Responsable.")
        utilisateur = self.trouver_par_id(user_id)
        if utilisateur is None:
            raise ValueError(f"Utilisateur #{user_id} introuvable.")
        if isinstance(utilisateur, Responsable):
            raise ValueError(f"L'utilisateur #{user_id} est déjà Responsable.")
        nouveau = admin.attribuer_role_responsable(utilisateur, classe)
        nouveau.id = utilisateur.id
        nouveau.mot_de_passe = utilisateur.mot_de_passe  # hash déjà stocké
        self.__utilisateurs[user_id] = nouveau
        return nouveau

    def revoquer_responsable(
        self,
        admin: Administrateur,
        user_id: int,
        nouveau_role: str = "etudiant",
    ) -> Utilisateur:
        if not isinstance(admin, Administrateur):
            raise PermissionError("Seul un Administrateur peut révoquer le rôle Responsable.")
        utilisateur = self.trouver_par_id(user_id)
        if not isinstance(utilisateur, Responsable):
            raise ValueError(f"L'utilisateur #{user_id} n'est pas Responsable.")
        revoque = admin.revoquer_role_responsable(utilisateur, nouveau_role)
        revoque.id = utilisateur.id
        revoque.mot_de_passe = utilisateur.mot_de_passe  # hash déjà stocké
        self.__utilisateurs[user_id] = revoque
        return revoque

    def supprimer_utilisateur(self, admin: Administrateur, user_id: int) -> bool:
        if not isinstance(admin, Administrateur):
            raise PermissionError("Seul un Administrateur peut supprimer un utilisateur.")
        if user_id in self.__utilisateurs:
            del self.__utilisateurs[user_id]
            return True
        return False

    def __repr__(self) -> str:
        return f"<GestionUtilisateurs {len(self.__utilisateurs)} utilisateur(s)>"
