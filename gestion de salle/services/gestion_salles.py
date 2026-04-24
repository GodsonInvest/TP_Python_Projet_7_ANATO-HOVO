
from typing import Optional
from models.salle import Salle
from models.utilisateur import Administrateur


class GestionSalles:
    def __init__(self):
        self.__salles: dict[int, Salle] = {}
        self.__prochain_id: int = 1

    def ajouter_salle(self, admin: Administrateur, salle: Salle) -> Salle:
        if not isinstance(admin, Administrateur):
            raise PermissionError("Seul un Administrateur peut ajouter une salle.")
        salle.id = self.__prochain_id
        self.__salles[self.__prochain_id] = salle
        self.__prochain_id += 1
        return salle

    def modifier_salle(self, admin: Administrateur, salle_id: int,
                       nom: str = None, capacite: int = None) -> Salle:
        if not isinstance(admin, Administrateur):
            raise PermissionError("Seul un Administrateur peut modifier une salle.")
        salle = self.trouver_par_id(salle_id)
        if salle is None:
            raise ValueError(f"Salle #{salle_id} introuvable.")
        if nom:
            salle.nom = nom
        if capacite:
            salle.capacite = capacite
        return salle

    def supprimer_salle(self, admin: Administrateur, salle_id: int) -> bool:
        if not isinstance(admin, Administrateur):
            raise PermissionError("Seul un Administrateur peut supprimer une salle.")
        if salle_id in self.__salles:
            del self.__salles[salle_id]
            return True
        return False

    def trouver_par_id(self, salle_id: int) -> Optional[Salle]:
        return self.__salles.get(salle_id)

    def trouver_par_nom(self, nom: str) -> Optional[Salle]:
        for s in self.__salles.values():
            if s.nom.lower() == nom.lower():
                return s
        return None

    def salles_disponibles(self, capacite_min: int = 0) -> list[Salle]:
        """Retourne les salles disponibles avec capacité >= capacite_min."""
        return [
            s for s in self.__salles.values()
            if s.disponible and s.capacite >= capacite_min
        ]

    def toutes_les_salles(self) -> list[Salle]:
        return list(self.__salles.values())

    def __repr__(self) -> str:
        return f"<GestionSalles {len(self.__salles)} salle(s)>"
