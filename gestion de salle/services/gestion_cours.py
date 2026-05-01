from datetime import date, timedelta, datetime
from typing import Optional

JOURS_SEMAINE = {
    "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4,
}


def _str_heure(h) -> str:
    return h.strftime("%H:%M") if hasattr(h, "strftime") else str(h)


def _str_date(d) -> str:
    return d.isoformat() if hasattr(d, "isoformat") else str(d)


def _as_date(d) -> date:
    return d if isinstance(d, date) else date.fromisoformat(d)


class GestionCours:

    def __init__(self, bd):
        self.bd = bd

    # ── Génération d'occurrences ──────────────────────────────────────────────

    def _occurrences(self, date_debut: date, date_fin: date, jours_config: list) -> list:
        result = []
        for config in jours_config:
            num = JOURS_SEMAINE.get(config["jour_semaine"], -1)
            if num < 0:
                continue
            d = date_debut
            delta = (num - d.weekday()) % 7
            d = d + timedelta(days=delta)
            while d <= date_fin:
                result.append({**config, "_date": d})
                d += timedelta(weeks=1)
        return result

    # ── Vérification des conflits ─────────────────────────────────────────────

    def verifier_conflits(self, data: dict, exclure_cours_id: Optional[int] = None) -> list:
        date_debut = _as_date(data["date_debut"])
        date_fin   = _as_date(data["date_fin"])
        occurrences = self._occurrences(date_debut, date_fin, data.get("jours", []))

        conflits = []
        for occ in occurrences:
            c = self.bd.verifier_conflit_planning(
                occ["salle_id"],
                occ["_date"],
                _str_heure(occ["heure_debut"]),
                _str_heure(occ["heure_fin"]),
                exclure_cours_id=exclure_cours_id,
            )
            if c:
                conflits.append({
                    "date":        _str_date(occ["_date"]),
                    "jour":        occ["jour_semaine"],
                    "salle_id":    occ["salle_id"],
                    "heure_debut": _str_heure(occ["heure_debut"]),
                    "heure_fin":   _str_heure(occ["heure_fin"]),
                    "conflit":     c,
                })
        return conflits

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def creer_cours(self, data: dict, notif=None, utilisateurs: dict = None) -> dict:
        """
        data : {filiere_id, enseignant_id?, enseignant_nom_ext, enseignant_email_ext,
                matiere, date_debut, date_fin, created_by,
                jours: [{jour_semaine, salle_id, heure_debut, heure_fin}]}
        Retourne : {cours_id, conflits}
        """
        conflits = self.verifier_conflits(data)
        if conflits:
            return {"cours_id": None, "conflits": conflits}

        cours = {
            "filiere_id":           data["filiere_id"],
            "enseignant_id":        data.get("enseignant_id"),
            "enseignant_nom_ext":   data.get("enseignant_nom_ext", ""),
            "enseignant_email_ext": data.get("enseignant_email_ext", ""),
            "matiere":              data.get("matiere", ""),
            "date_debut":           _str_date(data["date_debut"]),
            "date_fin":             _str_date(data["date_fin"]),
            "created_by":           data["created_by"],
            "created_at":           datetime.now().isoformat(),
            "jours": [
                {
                    "jour_semaine": j["jour_semaine"],
                    "salle_id":     j["salle_id"],
                    "heure_debut":  _str_heure(j["heure_debut"]),
                    "heure_fin":    _str_heure(j["heure_fin"]),
                }
                for j in data.get("jours", [])
            ],
        }
        cours_id = self.bd.sauvegarder_cours_v2(cours)

        if notif and utilisateurs:
            self._notifier(cours, utilisateurs, notif, annulation=False)

        return {"cours_id": cours_id, "conflits": []}

    def modifier_cours(self, cours_id: int, data: dict, notif=None, utilisateurs: dict = None) -> dict:
        conflits = self.verifier_conflits(data, exclure_cours_id=cours_id)
        if conflits:
            return {"cours_id": None, "conflits": conflits}

        cours = self.bd.charger_cours_v2_par_id(cours_id)
        if not cours:
            return {"cours_id": None, "conflits": [], "erreur": "Cours introuvable."}

        cours.update({
            "filiere_id":           data["filiere_id"],
            "enseignant_id":        data.get("enseignant_id"),
            "enseignant_nom_ext":   data.get("enseignant_nom_ext", ""),
            "enseignant_email_ext": data.get("enseignant_email_ext", ""),
            "matiere":              data.get("matiere", ""),
            "date_debut":           _str_date(data["date_debut"]),
            "date_fin":             _str_date(data["date_fin"]),
            "jours": [
                {
                    "jour_semaine": j["jour_semaine"],
                    "salle_id":     j["salle_id"],
                    "heure_debut":  _str_heure(j["heure_debut"]),
                    "heure_fin":    _str_heure(j["heure_fin"]),
                }
                for j in data.get("jours", [])
            ],
        })
        self.bd.sauvegarder_cours_v2(cours)

        if notif and utilisateurs:
            self._notifier(cours, utilisateurs, notif, annulation=False)

        return {"cours_id": cours_id, "conflits": []}

    def annuler_cours(self, cours_id: int, notif=None, utilisateurs: dict = None) -> bool:
        cours = self.bd.charger_cours_v2_par_id(cours_id)
        if not cours:
            return False

        if notif and utilisateurs:
            self._notifier(cours, utilisateurs, notif, annulation=True)

        return self.bd.supprimer_cours_v2(cours_id)

    # ── Notifications ─────────────────────────────────────────────────────────

    def _notifier(self, cours: dict, utilisateurs: dict, notif, annulation: bool):
        try:
            from models.utilisateur import Etudiant
            filiere_id = cours.get("filiere_id")
            etudiants = [
                u for u in utilisateurs.values()
                if isinstance(u, Etudiant) and u.unite_formation_id == filiere_id
            ]
            ens_email = cours.get("enseignant_email_ext", "")
            ens_nom   = cours.get("enseignant_nom_ext", "")
            ens_id    = cours.get("enseignant_id")
            if ens_id and ens_id in utilisateurs:
                ens_email = utilisateurs[ens_id].email
                ens_nom   = utilisateurs[ens_id].nom
            notif.notifier_cours(cours, etudiants, ens_email, ens_nom, annulation)
        except Exception:
            pass
