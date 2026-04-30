from abc import ABC, abstractmethod
from datetime import datetime


class Utilisateur(ABC):

    def __init__(self, nom: str, email: str, login: str, mot_de_passe: str):
        self.__id: int = None                     # assigné par la couche persistance
        self.__nom: str = nom
        self.__email: str = email
        self.__login: str = login
        self.__mot_de_passe: str = mot_de_passe  # stocké haché en pratique
        self.__date_inscription: datetime = datetime.now()

    @property
    def id(self) -> int:
        return self.__id

    @id.setter
    def id(self, valeur: int):
        if self.__id is None:
            self.__id = valeur

    @property
    def nom(self) -> str:
        return self.__nom

    @nom.setter
    def nom(self, valeur: str):
        if valeur.strip():
            self.__nom = valeur.strip()

    @property
    def email(self) -> str:
        return self.__email

    @email.setter
    def email(self, valeur: str):
        if "@" in valeur:
            self.__email = valeur
        else:
            raise ValueError("Email invalide.")

    @property
    def login(self) -> str:
        return self.__login

    @property
    def mot_de_passe(self) -> str:
        return self.__mot_de_passe

    @mot_de_passe.setter
    def mot_de_passe(self, nouveau: str):
        if len(nouveau) >= 6:
            self.__mot_de_passe = nouveau
        else:
            raise ValueError("Le mot de passe doit comporter au moins 6 caractères.")

    @property
    def date_inscription(self) -> datetime:
        return self.__date_inscription

    @property
    @abstractmethod
    def role(self) -> str:
        pass

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} id={self.__id} "
            f"login='{self.__login}' role='{self.role}'>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.__id,
            "nom": self.__nom,
            "email": self.__email,
            "login": self.__login,
            "mot_de_passe": self.__mot_de_passe,
            "role": self.role,
            "date_inscription": self.__date_inscription.isoformat(),
        }


class Etudiant(Utilisateur):

    def __init__(self, nom: str, email: str, login: str, mot_de_passe: str,
                 matricule: str, classe: str,
                 ecole_id: int = None, unite_formation_id: int = None):
        super().__init__(nom, email, login, mot_de_passe)
        self.__matricule: str = matricule
        self.__classe: str = classe
        self.__ecole_id: int = ecole_id
        self.__unite_formation_id: int = unite_formation_id

    @property
    def role(self) -> str:
        return "etudiant"

    @property
    def matricule(self) -> str:
        return self.__matricule

    @property
    def classe(self) -> str:
        return self.__classe

    @classe.setter
    def classe(self, valeur: str):
        self.__classe = valeur

    @property
    def ecole_id(self) -> int:
        return self.__ecole_id

    @ecole_id.setter
    def ecole_id(self, v: int):
        self.__ecole_id = v

    @property
    def unite_formation_id(self) -> int:
        return self.__unite_formation_id

    @unite_formation_id.setter
    def unite_formation_id(self, v: int):
        self.__unite_formation_id = v

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({
            "matricule": self.__matricule,
            "classe": self.__classe,
            "ecole_id": self.__ecole_id,
            "unite_formation_id": self.__unite_formation_id,
        })
        return d


class Enseignant(Utilisateur):

    def __init__(self, nom: str, email: str, login: str, mot_de_passe: str,
                 matiere: str):
        super().__init__(nom, email, login, mot_de_passe)
        self.__matiere: str = matiere

    @property
    def role(self) -> str:
        return "enseignant"

    @property
    def matiere(self) -> str:
        return self.__matiere

    @matiere.setter
    def matiere(self, valeur: str):
        self.__matiere = valeur

    @property
    def matieres(self) -> list:
        return [m.strip() for m in self.__matiere.split(",") if m.strip()]

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({"matiere": self.__matiere})
        return d


class Responsable(Utilisateur):
    """Rôle attribué par l'admin uniquement — non disponible à l'inscription directe."""

    def __init__(self, nom: str, email: str, login: str, mot_de_passe: str,
                 classe: str):
        super().__init__(nom, email, login, mot_de_passe)
        self.__classe: str = classe

    @property
    def role(self) -> str:
        return "responsable"

    @property
    def classe(self) -> str:
        return self.__classe

    @classe.setter
    def classe(self, valeur: str):
        self.__classe = valeur

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({"classe": self.__classe})
        return d


class Administrateur(Utilisateur):

    def __init__(self, nom: str, email: str, login: str, mot_de_passe: str):
        super().__init__(nom, email, login, mot_de_passe)

    @property
    def role(self) -> str:
        return "admin"

    def attribuer_role_responsable(self, utilisateur: Utilisateur,
                                   classe: str) -> "Responsable":
        return Responsable(
            nom=utilisateur.nom,
            email=utilisateur.email,
            login=utilisateur.login,
            mot_de_passe=utilisateur.mot_de_passe,
            classe=classe,
        )

    def revoquer_role_responsable(self, responsable: "Responsable",
                                  nouveau_role: str = "etudiant") -> Utilisateur:
        """nouveau_role : 'etudiant' | 'enseignant'"""
        if nouveau_role == "etudiant":
            return Etudiant(
                nom=responsable.nom,
                email=responsable.email,
                login=responsable.login,
                mot_de_passe=responsable.mot_de_passe,
                matricule="",
                classe=responsable.classe,
            )
        elif nouveau_role == "enseignant":
            return Enseignant(
                nom=responsable.nom,
                email=responsable.email,
                login=responsable.login,
                mot_de_passe=responsable.mot_de_passe,
                matiere="",
            )
        else:
            raise ValueError(f"Rôle inconnu : {nouveau_role}")
