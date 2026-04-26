class Ecole:

    def __init__(self, nom: str, type_etablissement: str = "ecole",
                 description: str = "", abreviation: str = ""):
        self.__id: int = None
        self.__nom: str = nom
        self.__type: str = type_etablissement  # "ecole" | "faculte"
        self.__description: str = description
        self.__abreviation: str = abreviation

    @property
    def id(self) -> int: return self.__id

    @id.setter
    def id(self, v: int):
        if self.__id is None: self.__id = v

    @property
    def nom(self) -> str: return self.__nom

    @nom.setter
    def nom(self, v: str): self.__nom = v.strip()

    @property
    def type(self) -> str: return self.__type

    @type.setter
    def type(self, v: str): self.__type = v

    @property
    def description(self) -> str: return self.__description

    @description.setter
    def description(self, v: str): self.__description = v

    @property
    def abreviation(self) -> str: return self.__abreviation

    @abreviation.setter
    def abreviation(self, v: str): self.__abreviation = v.strip().upper()

    def to_dict(self) -> dict:
        return {
            "id": self.__id,
            "nom": self.__nom,
            "type": self.__type,
            "description": self.__description,
            "abreviation": self.__abreviation,
        }

    def __repr__(self) -> str:
        return f"<Ecole id={self.__id} nom='{self.__nom}' type='{self.__type}'>"


class UniteFormation:

    NIVEAUX_LICENCE = ["L1", "L2", "L3"]
    NIVEAUX_MASTER  = ["M1", "M2"]
    NIVEAUX         = NIVEAUX_LICENCE + NIVEAUX_MASTER

    def __init__(self, nom: str, niveau: str, ecole_id: int, abreviation: str = ""):
        if niveau not in self.NIVEAUX:
            raise ValueError(f"Niveau '{niveau}' invalide. Attendu : {self.NIVEAUX}")
        self.__id: int        = None
        self.__nom: str       = nom
        self.__niveau: str    = niveau
        self.__ecole_id: int  = ecole_id
        self.__abreviation: str = abreviation

    @property
    def id(self) -> int: return self.__id

    @id.setter
    def id(self, v: int):
        if self.__id is None: self.__id = v

    @property
    def nom(self) -> str: return self.__nom

    @nom.setter
    def nom(self, v: str): self.__nom = v.strip()

    @property
    def niveau(self) -> str: return self.__niveau

    @niveau.setter
    def niveau(self, v: str):
        if v in self.NIVEAUX: self.__niveau = v

    @property
    def ecole_id(self) -> int: return self.__ecole_id

    @property
    def abreviation(self) -> str: return self.__abreviation

    @abreviation.setter
    def abreviation(self, v: str): self.__abreviation = v.strip().upper()

    @property
    def cycle(self) -> str:
        return "Licence" if self.__niveau in self.NIVEAUX_LICENCE else "Master"

    def to_dict(self) -> dict:
        return {
            "id": self.__id,
            "nom": self.__nom,
            "niveau": self.__niveau,
            "ecole_id": self.__ecole_id,
            "abreviation": self.__abreviation,
        }

    def __repr__(self) -> str:
        return f"<UniteFormation id={self.__id} '{self.__nom}' {self.__niveau}>"
