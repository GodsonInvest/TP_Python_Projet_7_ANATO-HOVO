from datetime import date, time
from typing import Optional
from models.reservation import Reservation, StatutReservation
from models.salle import Salle
from models.utilisateur import Responsable


class GestionReservation:
    

    def __init__(self):
        self.__reservations: list[Reservation] = []

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def ajouter_reservation(
        self,
        salle: Salle,
        responsable: Responsable,
        classe: str,
        date_reservation: date,
        heure_debut: time,
        heure_fin: time,
        matiere: str = "",
    ) -> Reservation:
        
        nouvelle = Reservation(
            salle=salle,
            responsable=responsable,
            classe=classe,
            date_reservation=date_reservation,
            heure_debut=heure_debut,
            heure_fin=heure_fin,
            matiere=matiere,
        )

        conflit = self.verifier_conflit(nouvelle)
        if conflit:
            raise ValueError(
                f"Conflit horaire détecté avec la réservation #{conflit.id} "
                f"(classe '{conflit.classe}', "
                f"{conflit.heure_debut.strftime('%H:%M')}–"
                f"{conflit.heure_fin.strftime('%H:%M')})."
            )

        nouvelle.confirmer()
        self.__reservations.append(nouvelle)
        return nouvelle

    def supprimer_reservation(self, reservation_id: int) -> bool:
        """
        Annule et retire la réservation identifiée.
        Retourne True si trouvée, False sinon.
        """
        for r in self.__reservations:
            if r.id == reservation_id:
                r.annuler()
                self.__reservations.remove(r)
                return True
        return False

    def modifier_reservation(
        self,
        reservation_id: int,
        nouvelle_date: date,
        nouvel_debut: time,
        nouvelle_fin: time,
    ) -> Reservation:
        """
        Modifie les horaires d'une réservation existante
        après vérification des conflits (hors elle-même).
        """
        cible = self._trouver_par_id(reservation_id)
        if cible is None:
            raise ValueError(f"Réservation #{reservation_id} introuvable.")

        # Sauvegarde temporaire
        ancienne_date  = cible.date
        ancien_debut   = cible.heure_debut
        ancienne_fin   = cible.heure_fin

        # Modification provisoire pour tester les conflits
        cible.modifier_horaires(nouvelle_date, nouvel_debut, nouvelle_fin)

        conflit = self.verifier_conflit(cible, exclure_id=reservation_id)
        if conflit:
            # Rollback
            cible.modifier_horaires(ancienne_date, ancien_debut, ancienne_fin)
            raise ValueError(
                f"Conflit avec la réservation #{conflit.id} après modification."
            )

        return cible

    # ── Détection de conflits ─────────────────────────────────────────────────

    def verifier_conflit(
        self,
        nouvelle: Reservation,
        exclure_id: Optional[int] = None,
    ) -> Optional[Reservation]:
        
        for existante in self.__reservations:
            if existante.id == exclure_id:
                continue
            if existante.statut not in (
                StatutReservation.CONFIRMEE, StatutReservation.EN_ATTENTE
            ):
                continue
            if nouvelle.chevauche(existante):
                return existante
        return None

    # ── Consultation du planning ───────────────────────────────────────────────

    def afficher_planning(
        self,
        filtre_date: Optional[date] = None,
        filtre_salle_nom: Optional[str] = None,
        filtre_classe: Optional[str] = None,
    ) -> list[Reservation]:
    
        resultats = [
            r for r in self.__reservations
            if r.statut == StatutReservation.CONFIRMEE
        ]

        if filtre_date:
            resultats = [r for r in resultats if r.date == filtre_date]

        if filtre_salle_nom:
            resultats = [
                r for r in resultats
                if filtre_salle_nom.lower() in r.salle.nom.lower()
            ]

        if filtre_classe:
            resultats = [
                r for r in resultats
                if filtre_classe.lower() in r.classe.lower()
            ]

        # Tri par date puis heure de début
        return sorted(resultats, key=lambda r: (r.date, r.heure_debut))

    def reservations_par_salle(self, salle_id: int) -> list[Reservation]:
        """Retourne toutes les réservations actives d'une salle donnée."""
        return [
            r for r in self.__reservations
            if r.salle.id == salle_id
            and r.statut == StatutReservation.CONFIRMEE
        ]

    def reservations_par_responsable(self, responsable_id: int) -> list[Reservation]:
        """Retourne les réservations d'un responsable donné."""
        return [
            r for r in self.__reservations
            if r.responsable.id == responsable_id
        ]

    # ── Helpers privés ────────────────────────────────────────────────────────

    def _trouver_par_id(self, reservation_id: int) -> Optional[Reservation]:
        for r in self.__reservations:
            if r.id == reservation_id:
                return r
        return None

    @property
    def toutes_les_reservations(self) -> list[Reservation]:
        """Accès lecture seule à la liste complète (admin)."""
        return list(self.__reservations)

    def __repr__(self) -> str:
        return f"<GestionReservation {len(self.__reservations)} réservation(s)>"
