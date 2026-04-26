from datetime import date, time, datetime
from enum import Enum


class StatutReservation(Enum):
    EN_ATTENTE = "en_attente"
    CONFIRMEE  = "confirmee"
    ANNULEE    = "annulee"
    TERMINEE   = "terminee"


class Reservation:

    _compteur: int = 0

    def __init__(
        self,
        salle,
        responsable,
        classe: str,
        date_reservation: date,
        heure_debut: time,
        heure_fin: time,
        matiere: str = "",
    ):
        Reservation._compteur += 1
        self.__id: int = Reservation._compteur
        self.__salle = salle
        self.__responsable = responsable
        self.__classe: str = classe
        self.__date: date = date_reservation
        self.__heure_debut: time = heure_debut
        self.__heure_fin: time = heure_fin
        self.__matiere: str = matiere
        self.__statut: StatutReservation = StatutReservation.EN_ATTENTE
        self.__date_creation: datetime = datetime.now()
        self._valider_horaires()

    def _valider_horaires(self):
        if self.__heure_debut >= self.__heure_fin:
            raise ValueError(
                f"L'heure de début ({self.__heure_debut}) "
                f"doit être avant l'heure de fin ({self.__heure_fin})."
            )

    @property
    def id(self) -> int:
        return self.__id

    @id.setter
    def id(self, valeur: int):
        self.__id = valeur

    @property
    def salle(self):
        return self.__salle

    @property
    def responsable(self):
        return self.__responsable

    @property
    def classe(self) -> str:
        return self.__classe

    @property
    def date(self) -> date:
        return self.__date

    @property
    def heure_debut(self) -> time:
        return self.__heure_debut

    @property
    def heure_fin(self) -> time:
        return self.__heure_fin

    @property
    def matiere(self) -> str:
        return self.__matiere

    @property
    def statut(self) -> StatutReservation:
        return self.__statut

    @property
    def date_creation(self) -> datetime:
        return self.__date_creation

    def confirmer(self):
        if self.__statut == StatutReservation.EN_ATTENTE:
            self.__statut = StatutReservation.CONFIRMEE

    def annuler(self):
        if self.__statut not in (StatutReservation.ANNULEE, StatutReservation.TERMINEE):
            self.__statut = StatutReservation.ANNULEE

    def modifier_horaires(self, nouvelle_date: date,
                          nouvel_debut: time, nouvelle_fin: time):
        if self.__statut in (StatutReservation.ANNULEE, StatutReservation.TERMINEE):
            raise PermissionError("Impossible de modifier une réservation annulée ou terminée.")
        self.__date = nouvelle_date
        self.__heure_debut = nouvel_debut
        self.__heure_fin = nouvelle_fin
        self._valider_horaires()

    def chevauche(self, autre: "Reservation") -> bool:
        if self.__salle.id != autre.__salle.id:
            return False
        if self.__date != autre.__date:
            return False
        # début1 < fin2  ET  fin1 > début2
        return self.__heure_debut < autre.__heure_fin and self.__heure_fin > autre.__heure_debut

    def duree_minutes(self) -> int:
        debut = datetime.combine(self.__date, self.__heure_debut)
        fin   = datetime.combine(self.__date, self.__heure_fin)
        return int((fin - debut).total_seconds() // 60)

    def to_dict(self) -> dict:
        return {
            "id": self.__id,
            "salle_id": self.__salle.id,
            "salle_nom": self.__salle.nom,
            "responsable_id": self.__responsable.id,
            "responsable_nom": self.__responsable.nom,
            "classe": self.__classe,
            "date": self.__date.isoformat(),
            "heure_debut": self.__heure_debut.strftime("%H:%M"),
            "heure_fin": self.__heure_fin.strftime("%H:%M"),
            "matiere": self.__matiere,
            "statut": self.__statut.value,
            "date_creation": self.__date_creation.isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"<Reservation id={self.__id} salle='{self.__salle.nom}' "
            f"classe='{self.__classe}' {self.__date} "
            f"{self.__heure_debut}→{self.__heure_fin} [{self.__statut.value}]>"
        )
