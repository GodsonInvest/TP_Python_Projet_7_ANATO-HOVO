"""
Couche de persistance SQLite — module sqlite3 (bibliothèque standard Python).

Entités gérées : Utilisateur (et sous-classes), Salle, Reservation.
Fichier de base de données : data/reservation_salles.db
"""

import json
import os
import sqlite3
import sys
from contextlib import contextmanager
from datetime import date, datetime, time
from typing import Optional

# Garantit que « gestion de salle/ » est dans sys.path quel que soit le CWD.
_RACINE = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _RACINE not in sys.path:
    sys.path.insert(0, _RACINE)

from models.reservation import Reservation, StatutReservation
from models.salle import Salle
from models.utilisateur import (
    Administrateur,
    Enseignant,
    Etudiant,
    Responsable,
    Utilisateur,
)


class BaseDonneesSQLite:
    """
    Gestionnaire de persistance SQLite.

    Chaque méthode ouvre une connexion courte, exécute l'opération,
    puis la connexion est libérée (garbage-collected).
    Les clés étrangères sont activées à chaque connexion (PRAGMA).
    """

    _CHEMIN_PAR_DEFAUT = os.path.normpath(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "data",
            "reservation_salles.db",
        )
    )

    def __init__(self, chemin_db: str = None):
        if chemin_db is None:
            chemin_db = self._CHEMIN_PAR_DEFAUT
        chemin_db = os.path.normpath(chemin_db)
        os.makedirs(os.path.dirname(chemin_db), exist_ok=True)
        self._chemin_db = chemin_db
        self._initialiser_tables()

    # ── Connexion ────────────────────────────────────────────────────────────────

    @contextmanager
    def _connexion(self):
        """Ouvre une connexion SQLite, la configure, commit/rollback puis la ferme."""
        conn = sqlite3.connect(self._chemin_db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Schéma ───────────────────────────────────────────────────────────────────

    def _initialiser_tables(self):
        ddl = """
        CREATE TABLE IF NOT EXISTS utilisateurs (
            id               INTEGER PRIMARY KEY,
            nom              TEXT    NOT NULL,
            email            TEXT    NOT NULL UNIQUE,
            login            TEXT    NOT NULL UNIQUE,
            mot_de_passe     TEXT    NOT NULL,
            role             TEXT    NOT NULL,
            date_inscription TEXT    NOT NULL,
            matricule        TEXT,
            classe           TEXT,
            matiere          TEXT
        );

        CREATE TABLE IF NOT EXISTS salles (
            id          INTEGER PRIMARY KEY,
            nom         TEXT    NOT NULL UNIQUE,
            capacite    INTEGER NOT NULL,
            equipements TEXT    NOT NULL DEFAULT '[]',
            disponible  INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS reservations (
            id              INTEGER PRIMARY KEY,
            salle_id        INTEGER NOT NULL,
            responsable_id  INTEGER NOT NULL,
            classe          TEXT    NOT NULL,
            date            TEXT    NOT NULL,
            heure_debut     TEXT    NOT NULL,
            heure_fin       TEXT    NOT NULL,
            matiere         TEXT    DEFAULT '',
            statut          TEXT    NOT NULL DEFAULT 'en_attente',
            date_creation   TEXT    NOT NULL,
            FOREIGN KEY (salle_id)       REFERENCES salles(id),
            FOREIGN KEY (responsable_id) REFERENCES utilisateurs(id)
        );
        """
        with self._connexion() as conn:
            conn.executescript(ddl)

    # ════════════════════════════════ Utilisateurs ════════════════════════════════

    def sauvegarder_utilisateur(self, utilisateur: Utilisateur) -> int:
        """
        INSERT si l'utilisateur est nouveau (id None ou absent de la base).
        UPDATE sinon.  Retourne l'id affecté.
        """
        d = utilisateur.to_dict()
        params = (
            d["nom"], d["email"], d["login"], d["mot_de_passe"],
            d["role"], d["date_inscription"],
            d.get("matricule"), d.get("classe"), d.get("matiere"),
        )
        with self._connexion() as conn:
            if utilisateur.id is None:
                cur = conn.execute(
                    "INSERT INTO utilisateurs "
                    "(nom, email, login, mot_de_passe, role, date_inscription, "
                    " matricule, classe, matiere) VALUES (?,?,?,?,?,?,?,?,?)",
                    params,
                )
                utilisateur.id = cur.lastrowid
            else:
                # L'id vient de GestionUtilisateurs ou d'un chargement precedent.
                # On tente un INSERT explicite ; si l'id ou le login/email
                # existent deja on fait un UPDATE.
                try:
                    conn.execute(
                        "INSERT INTO utilisateurs "
                        "(id, nom, email, login, mot_de_passe, role, "
                        " date_inscription, matricule, classe, matiere) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (utilisateur.id, *params),
                    )
                except sqlite3.IntegrityError:
                    conn.execute(
                        "UPDATE utilisateurs "
                        "SET nom=?, email=?, login=?, mot_de_passe=?, role=?, "
                        "    date_inscription=?, matricule=?, classe=?, matiere=? "
                        "WHERE id=?",
                        (*params, utilisateur.id),
                    )
        return utilisateur.id

    def charger_utilisateur_par_id(self, user_id: int) -> Optional[Utilisateur]:
        with self._connexion() as conn:
            row = conn.execute(
                "SELECT * FROM utilisateurs WHERE id = ?", (user_id,)
            ).fetchone()
        return self._ligne_vers_utilisateur(row) if row else None

    def charger_utilisateur_par_login(self, login: str) -> Optional[Utilisateur]:
        with self._connexion() as conn:
            row = conn.execute(
                "SELECT * FROM utilisateurs WHERE login = ?", (login,)
            ).fetchone()
        return self._ligne_vers_utilisateur(row) if row else None

    def charger_tous_utilisateurs(self) -> list[Utilisateur]:
        with self._connexion() as conn:
            rows = conn.execute("SELECT * FROM utilisateurs").fetchall()
        return [self._ligne_vers_utilisateur(r) for r in rows]

    def supprimer_utilisateur(self, user_id: int) -> bool:
        with self._connexion() as conn:
            cur = conn.execute(
                "DELETE FROM utilisateurs WHERE id = ?", (user_id,)
            )
        return cur.rowcount > 0

    @staticmethod
    def _ligne_vers_utilisateur(row: sqlite3.Row) -> Utilisateur:
        """Reconstruit un objet Utilisateur (ou sous-classe) depuis une ligne SQLite."""
        role = row["role"]
        mdp  = row["mot_de_passe"]

        if role == "etudiant":
            u = Etudiant(
                row["nom"], row["email"], row["login"], mdp,
                row["matricule"] or "", row["classe"] or "",
            )
        elif role == "enseignant":
            u = Enseignant(
                row["nom"], row["email"], row["login"], mdp,
                row["matiere"] or "",
            )
        elif role == "responsable":
            u = Responsable(
                row["nom"], row["email"], row["login"], mdp,
                row["classe"] or "",
            )
        else:  # admin
            u = Administrateur(row["nom"], row["email"], row["login"], mdp)

        u.id = row["id"]
        # Restaure la date d'inscription originale (pas de setter public).
        u._Utilisateur__date_inscription = datetime.fromisoformat(
            row["date_inscription"]
        )
        return u

    # ════════════════════════════════════ Salles ══════════════════════════════════

    def sauvegarder_salle(self, salle: Salle) -> int:
        """INSERT ou UPDATE selon la presence de l'id en base. Retourne l'id."""
        d  = salle.to_dict()
        eq = json.dumps(d["equipements"], ensure_ascii=False)
        params = (d["nom"], d["capacite"], eq, int(d["disponible"]))

        with self._connexion() as conn:
            if salle.id is None:
                cur = conn.execute(
                    "INSERT INTO salles (nom, capacite, equipements, disponible) "
                    "VALUES (?,?,?,?)",
                    params,
                )
                salle.id = cur.lastrowid
            else:
                try:
                    conn.execute(
                        "INSERT INTO salles "
                        "(id, nom, capacite, equipements, disponible) "
                        "VALUES (?,?,?,?,?)",
                        (salle.id, *params),
                    )
                except sqlite3.IntegrityError:
                    conn.execute(
                        "UPDATE salles "
                        "SET nom=?, capacite=?, equipements=?, disponible=? "
                        "WHERE id=?",
                        (*params, salle.id),
                    )
        return salle.id

    def charger_salle_par_id(self, salle_id: int) -> Optional[Salle]:
        with self._connexion() as conn:
            row = conn.execute(
                "SELECT * FROM salles WHERE id = ?", (salle_id,)
            ).fetchone()
        return self._ligne_vers_salle(row) if row else None

    def charger_toutes_salles(self) -> list[Salle]:
        with self._connexion() as conn:
            rows = conn.execute("SELECT * FROM salles").fetchall()
        return [self._ligne_vers_salle(r) for r in rows]

    def supprimer_salle(self, salle_id: int) -> bool:
        with self._connexion() as conn:
            cur = conn.execute("DELETE FROM salles WHERE id = ?", (salle_id,))
        return cur.rowcount > 0

    @staticmethod
    def _ligne_vers_salle(row: sqlite3.Row) -> Salle:
        s = Salle(row["nom"], row["capacite"], json.loads(row["equipements"]))
        s.id = row["id"]
        s.disponible = bool(row["disponible"])
        return s

    # ═══════════════════════════════════ Reservations ═════════════════════════════

    def sauvegarder_reservation(self, reservation: Reservation) -> int:
        """
        INSERT avec l'id Python (attribue par Reservation._compteur).
        Bascule sur UPDATE si l'id existe deja en base (session rechargee).
        """
        d = reservation.to_dict()
        params = (
            d["salle_id"], d["responsable_id"], d["classe"],
            d["date"], d["heure_debut"], d["heure_fin"],
            d["matiere"], d["statut"], d["date_creation"],
        )
        with self._connexion() as conn:
            try:
                conn.execute(
                    "INSERT INTO reservations "
                    "(id, salle_id, responsable_id, classe, date, "
                    " heure_debut, heure_fin, matiere, statut, date_creation) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (d["id"], *params),
                )
            except sqlite3.IntegrityError:
                conn.execute(
                    "UPDATE reservations "
                    "SET salle_id=?, responsable_id=?, classe=?, date=?, "
                    "    heure_debut=?, heure_fin=?, matiere=?, statut=?, "
                    "    date_creation=? "
                    "WHERE id=?",
                    (*params, d["id"]),
                )
        return reservation.id

    def charger_reservation_par_id(
        self,
        reservation_id: int,
        salles: dict,
        utilisateurs: dict,
    ) -> Optional[Reservation]:
        with self._connexion() as conn:
            row = conn.execute(
                "SELECT * FROM reservations WHERE id = ?", (reservation_id,)
            ).fetchone()
        return (
            self._ligne_vers_reservation(row, salles, utilisateurs) if row else None
        )

    def charger_toutes_reservations(
        self,
        salles: dict,
        utilisateurs: dict,
    ) -> list[Reservation]:
        with self._connexion() as conn:
            rows = conn.execute("SELECT * FROM reservations").fetchall()
        return [self._ligne_vers_reservation(r, salles, utilisateurs) for r in rows]

    def supprimer_reservation(self, reservation_id: int) -> bool:
        with self._connexion() as conn:
            cur = conn.execute(
                "DELETE FROM reservations WHERE id = ?", (reservation_id,)
            )
        return cur.rowcount > 0

    @staticmethod
    def _ligne_vers_reservation(
        row: sqlite3.Row,
        salles: dict,
        utilisateurs: dict,
    ) -> Reservation:
        salle       = salles.get(row["salle_id"])
        responsable = utilisateurs.get(row["responsable_id"])
        if salle is None or responsable is None:
            raise ValueError(
                f"Donnees manquantes pour reservation #{row['id']} — "
                f"salle_id={row['salle_id']}, "
                f"responsable_id={row['responsable_id']}"
            )
        r = Reservation(
            salle=salle,
            responsable=responsable,
            classe=row["classe"],
            date_reservation=date.fromisoformat(row["date"]),
            heure_debut=time.fromisoformat(row["heure_debut"]),
            heure_fin=time.fromisoformat(row["heure_fin"]),
            matiere=row["matiere"] or "",
        )
        r.id = row["id"]
        # Restaure statut et date de creation (pas de setter public).
        r._Reservation__statut        = StatutReservation(row["statut"])
        r._Reservation__date_creation = datetime.fromisoformat(row["date_creation"])
        return r

    # ══════════════════════════════ Chargement global ══════════════════════════════

    def charger_tout(self) -> dict:
        """
        Charge toutes les entites depuis la base.
        Retourne {'utilisateurs': [...], 'salles': [...], 'reservations': [...]}.

        Met a jour Reservation._compteur pour que les nouvelles reservations
        creees en memoire aient des ids superieurs au max enregistre en base.
        """
        utilisateurs = self.charger_tous_utilisateurs()
        salles       = self.charger_toutes_salles()

        u_dict = {u.id: u for u in utilisateurs}
        s_dict = {s.id: s for s in salles}

        reservations = self.charger_toutes_reservations(s_dict, u_dict)

        if reservations:
            Reservation._compteur = max(r.id for r in reservations)

        return {
            "utilisateurs": utilisateurs,
            "salles":        salles,
            "reservations":  reservations,
        }

    def __repr__(self) -> str:
        return f"<BaseDonneesSQLite '{self._chemin_db}'>"
