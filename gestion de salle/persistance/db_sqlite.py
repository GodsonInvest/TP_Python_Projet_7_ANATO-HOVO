import json
import os
import sqlite3
import sys
from contextlib import contextmanager
from datetime import date, datetime, time
from typing import Optional

_RACINE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _RACINE not in sys.path:
    sys.path.insert(0, _RACINE)

from models.reservation import Reservation, StatutReservation
from models.salle import Salle
from models.utilisateur import Administrateur, Enseignant, Etudiant, Responsable, Utilisateur


class BaseDonneesSQLite:

    _CHEMIN_PAR_DEFAUT = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "reservation_salles.db")
    )

    def __init__(self, chemin_db: str = None):
        if chemin_db is None:
            chemin_db = self._CHEMIN_PAR_DEFAUT
        chemin_db = os.path.normpath(chemin_db)
        os.makedirs(os.path.dirname(chemin_db), exist_ok=True)
        self._chemin_db = chemin_db
        self._initialiser_tables()

    @contextmanager
    def _connexion(self):
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

    # ── Utilisateurs ─────────────────────────────────────────────────────────────

    def sauvegarder_utilisateur(self, utilisateur: Utilisateur) -> int:
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
                # id fourni par GestionUtilisateurs ou rechargement : INSERT d'abord,
                # UPDATE si l'id ou le login/email existent déjà.
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
            row = conn.execute("SELECT * FROM utilisateurs WHERE id = ?", (user_id,)).fetchone()
        return self._ligne_vers_utilisateur(row) if row else None

    def charger_utilisateur_par_login(self, login: str) -> Optional[Utilisateur]:
        with self._connexion() as conn:
            row = conn.execute("SELECT * FROM utilisateurs WHERE login = ?", (login,)).fetchone()
        return self._ligne_vers_utilisateur(row) if row else None

    def charger_tous_utilisateurs(self) -> list[Utilisateur]:
        with self._connexion() as conn:
            rows = conn.execute("SELECT * FROM utilisateurs").fetchall()
        return [self._ligne_vers_utilisateur(r) for r in rows]

    def supprimer_utilisateur(self, user_id: int) -> bool:
        with self._connexion() as conn:
            cur = conn.execute("DELETE FROM utilisateurs WHERE id = ?", (user_id,))
        return cur.rowcount > 0

    @staticmethod
    def _ligne_vers_utilisateur(row: sqlite3.Row) -> Utilisateur:
        role, mdp = row["role"], row["mot_de_passe"]
        if role == "etudiant":
            u = Etudiant(row["nom"], row["email"], row["login"], mdp,
                         row["matricule"] or "", row["classe"] or "")
        elif role == "enseignant":
            u = Enseignant(row["nom"], row["email"], row["login"], mdp, row["matiere"] or "")
        elif role == "responsable":
            u = Responsable(row["nom"], row["email"], row["login"], mdp, row["classe"] or "")
        else:
            u = Administrateur(row["nom"], row["email"], row["login"], mdp)
        u.id = row["id"]
        # name-mangling : pas de setter public pour date_inscription
        u._Utilisateur__date_inscription = datetime.fromisoformat(row["date_inscription"])
        return u

    # ── Salles ───────────────────────────────────────────────────────────────────

    def sauvegarder_salle(self, salle: Salle) -> int:
        d  = salle.to_dict()
        eq = json.dumps(d["equipements"], ensure_ascii=False)
        params = (d["nom"], d["capacite"], eq, int(d["disponible"]))
        with self._connexion() as conn:
            if salle.id is None:
                cur = conn.execute(
                    "INSERT INTO salles (nom, capacite, equipements, disponible) VALUES (?,?,?,?)",
                    params,
                )
                salle.id = cur.lastrowid
            else:
                try:
                    conn.execute(
                        "INSERT INTO salles (id, nom, capacite, equipements, disponible) VALUES (?,?,?,?,?)",
                        (salle.id, *params),
                    )
                except sqlite3.IntegrityError:
                    conn.execute(
                        "UPDATE salles SET nom=?, capacite=?, equipements=?, disponible=? WHERE id=?",
                        (*params, salle.id),
                    )
        return salle.id

    def charger_salle_par_id(self, salle_id: int) -> Optional[Salle]:
        with self._connexion() as conn:
            row = conn.execute("SELECT * FROM salles WHERE id = ?", (salle_id,)).fetchone()
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

    # ── Réservations ─────────────────────────────────────────────────────────────

    def sauvegarder_reservation(self, reservation: Reservation) -> int:
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
                    "    heure_debut=?, heure_fin=?, matiere=?, statut=?, date_creation=? "
                    "WHERE id=?",
                    (*params, d["id"]),
                )
        return reservation.id

    def charger_reservation_par_id(
        self, reservation_id: int, salles: dict, utilisateurs: dict
    ) -> Optional[Reservation]:
        with self._connexion() as conn:
            row = conn.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,)).fetchone()
        return self._ligne_vers_reservation(row, salles, utilisateurs) if row else None

    def charger_toutes_reservations(self, salles: dict, utilisateurs: dict) -> list[Reservation]:
        with self._connexion() as conn:
            rows = conn.execute("SELECT * FROM reservations").fetchall()
        return [self._ligne_vers_reservation(r, salles, utilisateurs) for r in rows]

    def supprimer_reservation(self, reservation_id: int) -> bool:
        with self._connexion() as conn:
            cur = conn.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
        return cur.rowcount > 0

    @staticmethod
    def _ligne_vers_reservation(row: sqlite3.Row, salles: dict, utilisateurs: dict) -> Reservation:
        salle       = salles.get(row["salle_id"])
        responsable = utilisateurs.get(row["responsable_id"])
        if salle is None or responsable is None:
            raise ValueError(
                f"Données manquantes pour réservation #{row['id']} — "
                f"salle_id={row['salle_id']}, responsable_id={row['responsable_id']}"
            )
        r = Reservation(
            salle=salle, responsable=responsable, classe=row["classe"],
            date_reservation=date.fromisoformat(row["date"]),
            heure_debut=time.fromisoformat(row["heure_debut"]),
            heure_fin=time.fromisoformat(row["heure_fin"]),
            matiere=row["matiere"] or "",
        )
        r.id = row["id"]
        # name-mangling : pas de setter public pour statut ni date_creation
        r._Reservation__statut        = StatutReservation(row["statut"])
        r._Reservation__date_creation = datetime.fromisoformat(row["date_creation"])
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
        return f"<BaseDonneesSQLite '{self._chemin_db}'>"
