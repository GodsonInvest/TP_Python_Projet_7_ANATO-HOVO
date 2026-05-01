from datetime import date, datetime
from typing import Optional


def _str_heure(h) -> str:
    return h.strftime("%H:%M") if hasattr(h, "strftime") else str(h)


def _as_date(d) -> date:
    return d if isinstance(d, date) else date.fromisoformat(d)


class GestionComposition:

    def __init__(self, bd):
        self.bd = bd

    # ── Détection cours même enseignant même créneau ──────────────────────────

    def _sur_cours_enseignant(
        self,
        enseignant_id: Optional[int],
        enseignant_email_ext: str,
        d: date,
        heure_debut: str,
        heure_fin: str,
    ) -> bool:
        """Retourne True si l'enseignant a un cours sur ce créneau (composition en salle de cours)."""
        if not enseignant_id and not enseignant_email_ext:
            return False
        _JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        jour_sem = _JOURS[d.weekday()]
        d_str = d.isoformat()
        with self.bd._connexion() as conn:
            if enseignant_id:
                row = conn.execute(
                    "SELECT 1 FROM cours_jours cj JOIN cours c ON cj.cours_id = c.id "
                    "WHERE c.enseignant_id=? AND cj.jour_semaine=? "
                    "AND c.date_debut<=? AND c.date_fin>=? "
                    "AND cj.heure_debut<? AND cj.heure_fin>?",
                    [enseignant_id, jour_sem, d_str, d_str, heure_fin, heure_debut],
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT 1 FROM cours_jours cj JOIN cours c ON cj.cours_id = c.id "
                    "WHERE c.enseignant_email_ext=? AND cj.jour_semaine=? "
                    "AND c.date_debut<=? AND c.date_fin>=? "
                    "AND cj.heure_debut<? AND cj.heure_fin>?",
                    [enseignant_email_ext, jour_sem, d_str, d_str, heure_fin, heure_debut],
                ).fetchone()
        return row is not None

    # ── Création ──────────────────────────────────────────────────────────────

    def creer_composition(self, data: dict, notif=None, utilisateurs: dict = None) -> dict:
        """
        data : {filiere_id, enseignant_id?, enseignant_nom_ext, enseignant_email_ext,
                matiere, salle_id, date, heure_debut, heure_fin, created_by}
        Retourne : {comp_id, sur_cours_existant, conflit}
        """
        d       = _as_date(data["date"])
        h_debut = _str_heure(data["heure_debut"])
        h_fin   = _str_heure(data["heure_fin"])

        sur_cours = self._sur_cours_enseignant(
            data.get("enseignant_id"),
            data.get("enseignant_email_ext", ""),
            d, h_debut, h_fin,
        )

        if not sur_cours:
            conflit = self.bd.verifier_conflit_planning(data["salle_id"], d, h_debut, h_fin)
            if conflit:
                return {"comp_id": None, "sur_cours_existant": False, "conflit": conflit}

        comp = {
            "filiere_id":           data["filiere_id"],
            "enseignant_id":        data.get("enseignant_id"),
            "enseignant_nom_ext":   data.get("enseignant_nom_ext", ""),
            "enseignant_email_ext": data.get("enseignant_email_ext", ""),
            "matiere":              data.get("matiere", ""),
            "salle_id":             data["salle_id"],
            "date":                 d.isoformat(),
            "heure_debut":          h_debut,
            "heure_fin":            h_fin,
            "sur_cours_existant":   int(sur_cours),
            "created_by":           data["created_by"],
            "created_at":           datetime.now().isoformat(),
        }
        comp_id = self.bd.sauvegarder_composition(comp)

        if notif and utilisateurs:
            self._notifier(comp, utilisateurs, notif, annulation=False)

        return {"comp_id": comp_id, "sur_cours_existant": sur_cours, "conflit": None}

    def annuler_composition(self, comp_id: int, notif=None, utilisateurs: dict = None) -> bool:
        comp = self.bd.charger_composition_par_id(comp_id)
        if not comp:
            return False

        if notif and utilisateurs:
            self._notifier(comp, utilisateurs, notif, annulation=True)

        return self.bd.supprimer_composition(comp_id)

    # ── Notifications ─────────────────────────────────────────────────────────

    def _notifier(self, comp: dict, utilisateurs: dict, notif, annulation: bool):
        try:
            from models.utilisateur import Etudiant
            filiere_id = comp.get("filiere_id")
            etudiants = [
                u for u in utilisateurs.values()
                if isinstance(u, Etudiant) and u.unite_formation_id == filiere_id
            ]
            ens_email = comp.get("enseignant_email_ext", "")
            ens_nom   = comp.get("enseignant_nom_ext", "")
            ens_id    = comp.get("enseignant_id")
            if ens_id and ens_id in utilisateurs:
                ens_email = utilisateurs[ens_id].email
                ens_nom   = utilisateurs[ens_id].nom
            notif.notifier_composition(comp, etudiants, ens_email, ens_nom, annulation)
        except Exception:
            pass
