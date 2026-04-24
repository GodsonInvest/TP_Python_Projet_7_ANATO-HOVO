
class Salle:

    def __init__(self, nom: str, capacite: int, equipements: list[str] = None):
        self.__id: int = None
        self.__nom: str = nom
        self.__capacite: int = capacite
        self.__equipements: list[str] = equipements or []
        self.__disponible: bool = True

    # ── Propriétés ───────────────────────────────────────────────────────────

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
    def capacite(self) -> int:
        return self.__capacite

    @capacite.setter
    def capacite(self, valeur: int):
        if valeur > 0:
            self.__capacite = valeur
        else:
            raise ValueError("La capacité doit être supérieure à 0.")

    @property
    def equipements(self) -> list[str]:
        return list(self.__equipements)          

    @property
    def disponible(self) -> bool:
        return self.__disponible

    @disponible.setter
    def disponible(self, valeur: bool):
        self.__disponible = valeur

    # ── Méthodes ─────────────────────────────────────────────────────────────

    def ajouter_equipement(self, equipement: str):
        if equipement not in self.__equipements:
            self.__equipements.append(equipement)

    def retirer_equipement(self, equipement: str):
        self.__equipements = [e for e in self.__equipements if e != equipement]

    def to_dict(self) -> dict:
        return {
            "id": self.__id,
            "nom": self.__nom,
            "capacite": self.__capacite,
            "equipements": self.__equipements,
            "disponible": self.__disponible,
        }

    def __repr__(self) -> str:
        return (
            f"<Salle id={self.__id} nom='{self.__nom}' "
            f"capacite={self.__capacite} dispo={self.__disponible}>"
        )
