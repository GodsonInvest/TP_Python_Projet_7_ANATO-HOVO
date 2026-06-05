"""
Validateur de formulaires — UniRéserv
Toutes les méthodes retournent (ok: bool, message: str).
"""

import re
from datetime import date, time, datetime


class Validateur:

    # ── Champs texte ──────────────────────────────────────────────────────────

    @staticmethod
    def valider_champ_requis(valeur, nom_champ: str) -> tuple[bool, str]:
        if not valeur or (isinstance(valeur, str) and not valeur.strip()):
            return False, f"Le champ « {nom_champ} » est obligatoire."
        return True, ""

    @staticmethod
    def valider_nom(nom: str) -> tuple[bool, str]:
        nom = nom.strip() if nom else ""
        if len(nom) < 2:
            return False, "Le nom doit comporter au moins 2 caractères."
        if any(c.isdigit() for c in nom):
            return False, "Le nom ne doit pas contenir de chiffres."
        return True, ""

    @staticmethod
    def valider_login(login: str) -> tuple[bool, str]:
        login = login.strip() if login else ""
        if len(login) < 3:
            return False, "Le login doit comporter au moins 3 caractères."
        if " " in login:
            return False, "Le login ne doit pas contenir d'espaces."
        if not re.fullmatch(r"[a-zA-Z0-9_\-]+", login):
            return False, "Le login ne peut contenir que des lettres, chiffres, tirets et underscores."
        return True, ""

    @staticmethod
    def valider_email(email: str) -> tuple[bool, str]:
        email = email.strip() if email else ""
        if len(email) < 6:
            return False, "L'adresse email est trop courte (minimum 6 caractères)."
        if " " in email:
            return False, "L'adresse email ne doit pas contenir d'espaces."
        if "@" not in email:
            return False, "L'adresse email doit contenir le symbole @."
        parts = email.split("@")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            return False, "L'adresse email n'est pas valide."
        if "." not in parts[1]:
            return False, "L'adresse email doit contenir un domaine valide (ex: nom@email.com)."
        return True, ""

    @staticmethod
    def valider_mot_de_passe(mot_de_passe: str) -> tuple[bool, str]:
        mdp = mot_de_passe or ""
        if len(mdp) < 6:
            return False, "Le mot de passe doit comporter au moins 6 caractères."
        if not any(c.isupper() for c in mdp):
            return False, "Le mot de passe doit contenir au moins une majuscule."
        if not any(c.isdigit() for c in mdp):
            return False, "Le mot de passe doit contenir au moins un chiffre."
        return True, ""

    # ── Capacité ──────────────────────────────────────────────────────────────

    @staticmethod
    def valider_capacite(capacite) -> tuple[bool, str]:
        try:
            val = int(capacite)
        except (ValueError, TypeError):
            return False, "La capacité doit être un nombre entier."
        if val < 1:
            return False, "La capacité doit être d'au moins 1 place."
        if val > 2000:
            return False, "La capacité ne peut pas dépasser 2 000 places."
        return True, ""

    # ── Dates ────────────────────────────────────────────────────────────────

    @staticmethod
    def valider_dates(date_debut, date_fin, autoriser_passe: bool = False) -> tuple[bool, str]:
        try:
            if isinstance(date_debut, str):
                date_debut = date.fromisoformat(date_debut)
            if isinstance(date_fin, str):
                date_fin = date.fromisoformat(date_fin)
        except (ValueError, TypeError):
            return False, "Les dates saisies ne sont pas valides."

        if not autoriser_passe and date_debut < date.today():
            return False, "La date de début ne peut pas être dans le passé."
        if date_fin < date_debut:
            return False, "La date de fin doit être après la date de début."
        return True, ""

    # ── Horaires ─────────────────────────────────────────────────────────────

    @staticmethod
    def valider_horaires(heure_debut, heure_fin) -> tuple[bool, str]:
        try:
            if isinstance(heure_debut, str):
                heure_debut = time.fromisoformat(heure_debut)
            if isinstance(heure_fin, str):
                heure_fin = time.fromisoformat(heure_fin)
        except (ValueError, TypeError):
            return False, "Les horaires saisis ne sont pas valides."

        debut_min = heure_debut.hour * 60 + heure_debut.minute
        fin_min   = heure_fin.hour * 60 + heure_fin.minute

        if fin_min <= debut_min:
            return False, "L'heure de fin doit être après l'heure de début."
        duree = fin_min - debut_min
        if duree < 30:
            return False, "La durée minimale est de 30 minutes."
        if duree > 480:
            return False, "La durée maximale est de 8 heures."
        return True, ""

    # ── Collecteur d'erreurs multiples ────────────────────────────────────────

    @classmethod
    def valider_tout(cls, checks: list[tuple]) -> dict[str, str]:
        """
        checks : [(champ, bool_ok, message), ...]
        Retourne un dict {champ: message_erreur} — vide si tout est valide.
        """
        errors = {}
        for champ, ok, msg in checks:
            if not ok and champ not in errors:
                errors[champ] = msg
        return errors
