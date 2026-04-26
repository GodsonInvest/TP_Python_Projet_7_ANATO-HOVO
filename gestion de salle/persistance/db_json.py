import json
import os
import sys
from datetime import date, datetime, time
from typing import Optional

_RACINE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _RACINE not in sys.path:
    sys.path.insert(0, _RACINE)

from models.reservation import Reservation, StatutReservation
from models.salle import Salle
from models.utilisateur import Administrateur, Enseignant, Etudiant, Responsable, Utilisateur


class BaseDonneesJSON:
    """Persistance JSON — trois fichiers dans data/ : utilisateurs, salles, reservations."""

    def __init__(self, dossier_data: str = None):
        if dossier_data is None:
            dossier_data = os.path.normpath(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
            )
        os.makedirs(dossier_data, exist_ok=True)
        self._dossier        = dossier_data
        self._f_utilisateurs = os.path.join(dossier_data, "utilisateurs.json")
        self._f_salles       = os.path.join(dossier_data, "salles.json")
        self._f_reservations = os.path.join(dossier_data, "reservations.json")

    def _lire(self, chemin: str) -> list:
        if not os.path.exists(chemin):
            return []
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)

    def _ecrire(self, chemin: str, donnees: list):
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(donnees, f, ensure_ascii=False, indent=2)

    # ── Utilisateurs ─────────────────────────────────────────────────────────────

    def sauvegarder_utilisateur(self, utilisateur: Utilisateur) -> int:
        records = self._lire(self._f_utilisateurs)
        if utilisateur.id is None:
            utilisateur.id = max((r["id"] for r in records), default=0) + 1
        d   = utilisateur.to_dict()
        idx = next((i for i, r in enumerate(records) if r["id"] == d["id"]), None)
        if idx is None:
            records.append(d)
        else:
            records[idx] = d
        self._ecrire(self._f_utilisateurs, records)
        return utilisateur.id

    def charger_utilisateur_par_id(self, user_id: int) -> Optional[Utilisateur]:
        for d in self._lire(self._f_utilisateurs):
            if d["id"] == user_id:
                return self._dict_vers_utilisateur(d)
        return None

    def charger_utilisateur_par_login(self, login: str) -> Optional[Utilisateur]:
        for d in self._lire(self._f_utilisateurs):
            if d["login"] == login:
                return self._dict_vers_utilisateur(d)
        return None

    def charger_tous_utilisateurs(self) -> list[Utilisateur]:
        return [self._dict_vers_utilisateur(d) for d in self._lire(self._f_utilisateurs)]

    def supprimer_utilisateur(self, user_id: int) -> bool:
        records = self._lire(self._f_utilisateurs)
        filtres = [r for r in records if r["id"] != user_id]
        if len(filtres) == len(records):
            return False
        self._ecrire(self._f_utilisateurs, filtres)
        return True

    @staticmethod
    def _dict_vers_utilisateur(d: dict) -> Utilisateur:
        role, mdp = d["role"], d["mot_de_passe"]
        if role == "etudiant":
            u = Etudiant(d["nom"], d["email"], d["login"], mdp,
                         d.get("matricule", ""), d.get("classe", ""))
        elif role == "enseignant":
            u = Enseignant(d["nom"], d["email"], d["login"], mdp, d.get("matiere", ""))
        elif role == "responsable":
            u = Responsable(d["nom"], d["email"], d["login"], mdp, d.get("classe", ""))
        else:
            u = Administrateur(d["nom"], d["email"], d["login"], mdp)
        u.id = d["id"]
        # name-mangling : pas de setter public pour date_inscription
        u._Utilisateur__date_inscription = datetime.fromisoformat(d["date_inscription"])
        return u

    # ── Salles ───────────────────────────────────────────────────────────────────

    def sauvegarder_salle(self, salle: Salle) -> int:
        records = self._lire(self._f_salles)
        if salle.id is None:
            salle.id = max((r["id"] for r in records), default=0) + 1
        d   = salle.to_dict()
        idx = next((i for i, r in enumerate(records) if r["id"] == d["id"]), None)
        if idx is None:
            records.append(d)
        else:
            records[idx] = d
        self._ecrire(self._f_salles, records)
        return salle.id

    def charger_salle_par_id(self, salle_id: int) -> Optional[Salle]:
        for d in self._lire(self._f_salles):
            if d["id"] == salle_id:
                return self._dict_vers_salle(d)
        return None

    def charger_toutes_salles(self) -> list[Salle]:
        return [self._dict_vers_salle(d) for d in self._lire(self._f_salles)]

    def supprimer_salle(self, salle_id: int) -> bool:
        records = self._lire(self._f_salles)
        filtres = [r for r in records if r["id"] != salle_id]
        if len(filtres) == len(records):
            return False
        self._ecrire(self._f_salles, filtres)
        return True

    @staticmethod
    def _dict_vers_salle(d: dict) -> Salle:
        s = Salle(d["nom"], d["capacite"], d.get("equipements", []))
        s.id = d["id"]
        s.disponible = d.get("disponible", True)
        return s

    # ── Réservations ─────────────────────────────────────────────────────────────

    def sauvegarder_reservation(self, reservation: Reservation) -> int:
        records = self._lire(self._f_reservations)
        d   = reservation.to_dict()
        idx = next((i for i, r in enumerate(records) if r["id"] == d["id"]), None)
        if idx is None:
            records.append(d)
        else:
            records[idx] = d
        self._ecrire(self._f_reservations, records)
        return reservation.id

    def charger_reservation_par_id(
        self, reservation_id: int, salles: dict, utilisateurs: dict
    ) -> Optional[Reservation]:
        for d in self._lire(self._f_reservations):
            if d["id"] == reservation_id:
                return self._dict_vers_reservation(d, salles, utilisateurs)
        return None

    def charger_toutes_reservations(self, salles: dict, utilisateurs: dict) -> list[Reservation]:
        return [
            self._dict_vers_reservation(d, salles, utilisateurs)
            for d in self._lire(self._f_reservations)
        ]

    def supprimer_reservation(self, reservation_id: int) -> bool:
        records = self._lire(self._f_reservations)
        filtres = [r for r in records if r["id"] != reservation_id]
        if len(filtres) == len(records):
            return False
        self._ecrire(self._f_reservations, filtres)
        return True

    @staticmethod
    def _dict_vers_reservation(d: dict, salles: dict, utilisateurs: dict) -> Reservation:
        salle       = salles.get(d["salle_id"])
        responsable = utilisateurs.get(d["responsable_id"])
        if salle is None or responsable is None:
            raise ValueError(
                f"Données manquantes pour réservation #{d['id']} — "
                f"salle_id={d['salle_id']}, responsable_id={d['responsable_id']}"
            )
        r = Reservation(
            salle=salle, responsable=responsable, classe=d["classe"],
            date_reservation=date.fromisoformat(d["date"]),
            heure_debut=time.fromisoformat(d["heure_debut"]),
            heure_fin=time.fromisoformat(d["heure_fin"]),
            matiere=d.get("matiere", ""),
        )
        r.id = d["id"]
        # name-mangling : pas de setter public pour statut ni date_creation
        r._Reservation__statut        = StatutReservation(d["statut"])
        r._Reservation__date_creation = datetime.fromisoformat(d["date_creation"])
        return r

    # ── Chargement global ─────────────────────────────────────────────────────────

    def charger_tout(self) -> dict:
        utilisateurs = self.charger_tous_utilisateurs()
        salles       = self.charger_toutes_salles()
        u_dict = {u.id: u for u in utilisateurs}
        s_dict = {s.id: s for s in salles}
        reservations = self.charger_toutes_reservations(s_dict, u_dict)
        # synchronise le compteur pour éviter les collisions d'id après rechargement
        if reservations:
            Reservation._compteur = max(r.id for r in reservations)
        return {"utilisateurs": utilisateurs, "salles": salles, "reservations": reservations}

    def __repr__(self) -> str:
        return f"<BaseDonneesJSON dossier='{self._dossier}'>"
