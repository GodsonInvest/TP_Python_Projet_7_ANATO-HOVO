from abc import ABC, abstractmethod
from datetime import datetime


class Utilisateur(ABC):
    

    def __init__(self, nom: str, email: str, login: str, mot_de_passe: str):
        self.__id: int = None                        # Clé primaire (assignée par la BDD)
        self.__nom: str = nom
        self.__email: str = email
        self.__login: str = login
        self.__mot_de_passe: str = mot_de_passe      # Stocké haché en pratique
        self.__date_inscription: datetime = datetime.now()

    # ── Propriétés (getters / setters) ──────────────────────────────────────

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

    # ── Méthode abstraite (rôle polymorphique) ───────────────────────────────

    @property
    @abstractmethod
    def role(self) -> str:
        """Retourne le rôle de l'utilisateur (polymorphisme)."""

    # ── Représentation ───────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} id={self.__id} "
            f"login='{self.__login}' role='{self.role}'>"
        )

    def to_dict(self) -> dict:
        """Sérialise l'objet en dictionnaire (utile pour la persistance)."""
        return {
            "id": self.__id,
            "nom": self.__nom,
            "email": self.__email,
            "login": self.__login,
            "mot_de_passe": self.__mot_de_passe,
            "role": self.role,
            "date_inscription": self.__date_inscription.isoformat(),
        }


# ────────────────────────Sous-classes concrètes───────────────────────────────────────────────────

class Etudiant(Utilisateur):
    """Utilisateur de type Étudiant. Peut consulter le planning."""

    def __init__(self, nom: str, email: str, login: str, mot_de_passe: str,
                 matricule: str, classe: str):
        super().__init__(nom, email, login, mot_de_passe)
        self.__matricule: str = matricule
        self.__classe: str = classe

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

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({"matricule": self.__matricule, "classe": self.__classe})
        return d


class Enseignant(Utilisateur):
    """Utilisateur de type Enseignant. Peut consulter le planning."""

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

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({"matiere": self.__matiere})
        return d


class Responsable(Utilisateur):
    """
    Utilisateur promu Responsable de classe par l'admin.
    Hérite de Utilisateur — rôle non disponible à l'inscription directe.
    """

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
    """Super utilisateur du système."""

    def __init__(self, nom: str, email: str, login: str, mot_de_passe: str):
        super().__init__(nom, email, login, mot_de_passe)

    @property
    def role(self) -> str:
        return "admin"

    # ── Actions spécifiques admin ────────────────────────────────────────────

    def attribuer_role_responsable(self, utilisateur: Utilisateur,
                                   classe: str) -> "Responsable":
        """
        Crée un Responsable à partir d'un Etudiant ou Enseignant existant.
        Retourne la nouvelle instance Responsable.
        """
        return Responsable(
            nom=utilisateur.nom,
            email=utilisateur.email,
            login=utilisateur.login,
            mot_de_passe=utilisateur.mot_de_passe,
            classe=classe,
        )

    def revoquer_role_responsable(self, responsable: "Responsable",
                                  nouveau_role: str = "etudiant") -> Utilisateur:
        """
        Révoque le rôle Responsable et retourne l'utilisateur avec le rôle souhaité.
        nouveau_role : 'etudiant' | 'enseignant'
        """
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
