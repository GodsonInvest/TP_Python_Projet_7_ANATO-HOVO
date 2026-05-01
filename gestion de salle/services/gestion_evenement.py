import json as _json
from datetime import date, timedelta, datetime
from typing import Optional


def _str_heure(h) -> str:
    return h.strftime("%H:%M") if hasattr(h, "strftime") else str(h)


def _str_date(d) -> str:
    return d.isoformat() if hasattr(d, "isoformat") else str(d)


def _as_date(d) -> date:
    return d if isinstance(d, date) else date.fromisoformat(d)


class GestionEvenement:

    def __init__(self, bd):
        self.bd = bd

    # ── Création ──────────────────────────────────────────────────────────────

    def creer_evenement(
        self,
        data: dict,
        role_createur: str,
        notif=None,
        utilisateurs: dict = None,
    ) -> dict:
        """
        data : {titre, description, salle_id, date_debut, date_fin,
                heure_debut, heure_fin, created_by,
                public_cible_type, public_cible_id}
        role_createur : 'admin' → statut='valide' immédiatement ; sinon 'en_attente'
        Retourne : {evt_id, conflit, statut}
        """
        h_debut = _str_heure(data["heure_debut"])
        h_fin   = _str_heure(data["heure_fin"])
        d_debut = _as_date(data["date_debut"])
        d_fin   = _as_date(data["date_fin"])

        if role_createur == "admin":
            d = d_debut
            while d <= d_fin:
                conflit = self.bd.verifier_conflit_planning(data["salle_id"], d, h_debut, h_fin)
                if conflit:
                    return {"evt_id": None, "conflit": conflit, "statut": None}
                d += timedelta(days=1)

        statut = "valide" if role_createur == "admin" else "en_attente"

        evt = {
            "titre":              data["titre"],
            "description":        data.get("description", ""),
            "salle_id":           data["salle_id"],
            "date_debut":         _str_date(d_debut),
            "date_fin":           _str_date(d_fin),
            "heure_debut":        h_debut,
            "heure_fin":          h_fin,
            "statut":             statut,
            "motif_refus":        "",
            "created_by":         data["created_by"],
            "validated_by":       data["created_by"] if role_createur == "admin" else None,
            "created_at":         datetime.now().isoformat(),
            "public_cible_type":  data.get("public_cible_type", "universite"),
            "public_cible_id":    data.get("public_cible_id"),
            "public_cible_ids":   data.get("public_cible_ids") or [],
        }
        evt_id = self.bd.sauvegarder_evenement(evt)

        if statut == "valide" and notif and utilisateurs:
            self._notifier(evt, utilisateurs, notif, annulation=False)

        return {"evt_id": evt_id, "conflit": None, "statut": statut}

    # ── Validation / Refus ────────────────────────────────────────────────────

    def valider_evenement(
        self,
        evt_id: int,
        admin_id: int,
        notif=None,
        utilisateurs: dict = None,
    ) -> bool:
        evt = self.bd.charger_evenement_par_id(evt_id)
        if not evt or evt["statut"] != "en_attente":
            return False
        evt["statut"]       = "valide"
        evt["validated_by"] = admin_id
        self.bd.sauvegarder_evenement(evt)
        if notif and utilisateurs:
            self._notifier(evt, utilisateurs, notif, annulation=False)
        return True

    def refuser_evenement(
        self,
        evt_id: int,
        admin_id: int,
        motif: str,
        notif=None,
        utilisateurs: dict = None,
    ) -> bool:
        evt = self.bd.charger_evenement_par_id(evt_id)
        if not evt:
            return False
        evt["statut"]       = "refuse"
        evt["validated_by"] = admin_id
        evt["motif_refus"]  = motif
        self.bd.sauvegarder_evenement(evt)
        return True

    def modifier_evenement(self, evt_id: int, data: dict) -> bool:
        evt = self.bd.charger_evenement_par_id(evt_id)
        if not evt:
            return False
        h_debut = _str_heure(data["heure_debut"])
        h_fin   = _str_heure(data["heure_fin"])
        d_debut = _as_date(data["date_debut"])
        d_fin   = _as_date(data["date_fin"])
        evt.update({
            "titre":             data["titre"],
            "description":       data.get("description", ""),
            "salle_id":          data["salle_id"],
            "date_debut":        _str_date(d_debut),
            "date_fin":          _str_date(d_fin),
            "heure_debut":       h_debut,
            "heure_fin":         h_fin,
            "public_cible_type": data.get("public_cible_type", evt.get("public_cible_type", "universite")),
            "public_cible_id":   data.get("public_cible_id", evt.get("public_cible_id")),
            "public_cible_ids":  data.get("public_cible_ids") or evt.get("public_cible_ids") or [],
        })
        self.bd.sauvegarder_evenement(evt)
        return True

    # ── Notifications ─────────────────────────────────────────────────────────

    def _filtrer_destinataires(self, utilisateurs: dict, evt: dict) -> list:
        """Retourne la liste des utilisateurs concernés selon le public cible."""
        cible_type = evt.get("public_cible_type", "universite")

        if cible_type == "universite":
            return list(utilisateurs.values())

        if cible_type == "ecole":
            # public_cible_ids : liste d'ecole_id (stockée en JSON string dans la DB)
            raw = evt.get("public_cible_ids") or []
            if isinstance(raw, str):
                try:
                    raw = _json.loads(raw)
                except Exception:
                    raw = []
            ecole_ids = set(int(x) for x in raw if x)
            if not ecole_ids:
                return list(utilisateurs.values())
            return [u for u in utilisateurs.values() if getattr(u, "ecole_id", None) in ecole_ids]

        if cible_type == "filiere":
            cible_id = evt.get("public_cible_id")
            if not cible_id:
                return list(utilisateurs.values())
            return [u for u in utilisateurs.values()
                    if getattr(u, "unite_formation_id", None) == int(cible_id)]

        return list(utilisateurs.values())

    def _notifier(self, evt: dict, utilisateurs: dict, notif, annulation: bool):
        try:
            dest = self._filtrer_destinataires(utilisateurs, evt)
            notif.notifier_evenement(evt, dest, annulation)
        except Exception:
            pass
