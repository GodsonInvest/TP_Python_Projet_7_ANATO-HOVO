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

from models.etablissement import Ecole, UniteFormation
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
        CREATE TABLE IF NOT EXISTS ecoles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nom         TEXT    NOT NULL UNIQUE,
            type        TEXT    NOT NULL DEFAULT 'ecole',
            description TEXT    NOT NULL DEFAULT '',
            abreviation TEXT    NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS unites_formation (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nom         TEXT    NOT NULL,
            niveau      TEXT    NOT NULL,
            ecole_id    INTEGER NOT NULL,
            abreviation TEXT    NOT NULL DEFAULT '',
            FOREIGN KEY (ecole_id) REFERENCES ecoles(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS utilisateurs (
            id                  INTEGER PRIMARY KEY,
            nom                 TEXT    NOT NULL,
            email               TEXT    NOT NULL UNIQUE,
            login               TEXT    NOT NULL UNIQUE,
            mot_de_passe        TEXT    NOT NULL,
            role                TEXT    NOT NULL,
            date_inscription    TEXT    NOT NULL,
            matricule           TEXT,
            classe              TEXT,
            matiere             TEXT,
            ecole_id            INTEGER,
            unite_formation_id  INTEGER
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

        CREATE TABLE IF NOT EXISTS config (
            cle    TEXT PRIMARY KEY,
            valeur TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS reservation_cours (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            enseignant_id   INTEGER,
            classe          TEXT    NOT NULL DEFAULT '',
            matiere         TEXT    NOT NULL DEFAULT '',
            date_debut      TEXT    NOT NULL,
            date_fin        TEXT    NOT NULL,
            created_by      INTEGER NOT NULL,
            created_at      TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reservation_cours_jours (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cours_id        INTEGER NOT NULL,
            jour_semaine    TEXT    NOT NULL,
            salle_id        INTEGER NOT NULL,
            heure_debut     TEXT    NOT NULL,
            heure_fin       TEXT    NOT NULL,
            FOREIGN KEY (cours_id) REFERENCES reservation_cours(id) ON DELETE CASCADE
        );
        """
        with self._connexion() as conn:
            conn.executescript(ddl)
        self._migrer_tables()

    def _migrer_tables(self):
        """Ajoute les colonnes manquantes pour les bases de données existantes."""
        migrations = [
            ("utilisateurs",    "ecole_id",           "INTEGER"),
            ("utilisateurs",    "unite_formation_id",  "INTEGER"),
            ("ecoles",          "abreviation",         "TEXT NOT NULL DEFAULT ''"),
            ("unites_formation","abreviation",         "TEXT NOT NULL DEFAULT ''"),
            ("reservations",    "enseignant_id",       "INTEGER"),
            ("reservations",    "cours_id",            "INTEGER"),
        ]
        with self._connexion() as conn:
            for table, col, typ in migrations:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
                except sqlite3.OperationalError:
                    pass

    # ── Utilisateurs ─────────────────────────────────────────────────────────────

    def sauvegarder_utilisateur(self, utilisateur: Utilisateur) -> int:
        d = utilisateur.to_dict()
        params = (
            d["nom"], d["email"], d["login"], d["mot_de_passe"],
            d["role"], d["date_inscription"],
            d.get("matricule"), d.get("classe"), d.get("matiere"),
            d.get("ecole_id"), d.get("unite_formation_id"),
        )
        with self._connexion() as conn:
            if utilisateur.id is None:
                cur = conn.execute(
                    "INSERT INTO utilisateurs "
                    "(nom, email, login, mot_de_passe, role, date_inscription, "
                    " matricule, classe, matiere, ecole_id, unite_formation_id) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    params,
                )
                utilisateur.id = cur.lastrowid
            else:
                try:
                    conn.execute(
                        "INSERT INTO utilisateurs "
                        "(id, nom, email, login, mot_de_passe, role, "
                        " date_inscription, matricule, classe, matiere, "
                        " ecole_id, unite_formation_id) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (utilisateur.id, *params),
                    )
                except sqlite3.IntegrityError:
                    conn.execute(
                        "UPDATE utilisateurs "
                        "SET nom=?, email=?, login=?, mot_de_passe=?, role=?, "
                        "    date_inscription=?, matricule=?, classe=?, matiere=?, "
                        "    ecole_id=?, unite_formation_id=? "
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
        keys = row.keys()
        ecole_id = row["ecole_id"] if "ecole_id" in keys else None
        uf_id    = row["unite_formation_id"] if "unite_formation_id" in keys else None
        if role == "etudiant":
            u = Etudiant(row["nom"], row["email"], row["login"], mdp,
                         row["matricule"] or "", row["classe"] or "",
                         ecole_id, uf_id)
        elif role == "enseignant":
            u = Enseignant(row["nom"], row["email"], row["login"], mdp, row["matiere"] or "")
        elif role == "responsable":
            u = Responsable(row["nom"], row["email"], row["login"], mdp, row["classe"] or "")
        else:
            u = Administrateur(row["nom"], row["email"], row["login"], mdp)
        u.id = row["id"]
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
            d["matiere"], d.get("enseignant_id"), d.get("cours_id"), d["statut"], d["date_creation"],
        )
        with self._connexion() as conn:
            try:
                conn.execute(
                    "INSERT INTO reservations "
                    "(id, salle_id, responsable_id, classe, date, "
                    " heure_debut, heure_fin, matiere, enseignant_id, cours_id, statut, date_creation) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (d["id"], *params),
                )
            except sqlite3.IntegrityError:
                conn.execute(
                    "UPDATE reservations "
                    "SET salle_id=?, responsable_id=?, classe=?, date=?, "
                    "    heure_debut=?, heure_fin=?, matiere=?, enseignant_id=?, "
                    "    cours_id=?, statut=?, date_creation=? "
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
        keys = row.keys()
        ens_id   = row["enseignant_id"] if "enseignant_id" in keys else None
        cours_id = row["cours_id"]      if "cours_id"      in keys else None
        r = Reservation(
            salle=salle, responsable=responsable, classe=row["classe"],
            date_reservation=date.fromisoformat(row["date"]),
            heure_debut=time.fromisoformat(row["heure_debut"]),
            heure_fin=time.fromisoformat(row["heure_fin"]),
            matiere=row["matiere"] or "",
            enseignant_id=ens_id,
            cours_id=cours_id,
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

    # ── Écoles ───────────────────────────────────────────────────────────────────

    def sauvegarder_ecole(self, ecole: Ecole) -> int:
        d = ecole.to_dict()
        params = (d["nom"], d["type"], d["description"], d["abreviation"])
        with self._connexion() as conn:
            if ecole.id is None:
                cur = conn.execute(
                    "INSERT INTO ecoles (nom, type, description, abreviation) VALUES (?,?,?,?)",
                    params,
                )
                ecole.id = cur.lastrowid
            else:
                try:
                    conn.execute(
                        "INSERT INTO ecoles (id, nom, type, description, abreviation) VALUES (?,?,?,?,?)",
                        (ecole.id, *params),
                    )
                except sqlite3.IntegrityError:
                    conn.execute(
                        "UPDATE ecoles SET nom=?, type=?, description=?, abreviation=? WHERE id=?",
                        (*params, ecole.id),
                    )
        return ecole.id

    def charger_ecole_par_id(self, ecole_id: int) -> Optional[Ecole]:
        with self._connexion() as conn:
            row = conn.execute("SELECT * FROM ecoles WHERE id = ?", (ecole_id,)).fetchone()
        return self._ligne_vers_ecole(row) if row else None

    def charger_toutes_ecoles(self) -> list:
        with self._connexion() as conn:
            rows = conn.execute("SELECT * FROM ecoles ORDER BY nom").fetchall()
        return [self._ligne_vers_ecole(r) for r in rows]

    def supprimer_ecole(self, ecole_id: int) -> bool:
        with self._connexion() as conn:
            cur = conn.execute("DELETE FROM ecoles WHERE id = ?", (ecole_id,))
        return cur.rowcount > 0

    @staticmethod
    def _ligne_vers_ecole(row: sqlite3.Row) -> Ecole:
        keys = row.keys()
        abr  = row["abreviation"] if "abreviation" in keys else ""
        e = Ecole(row["nom"], row["type"], row["description"], abr)
        e.id = row["id"]
        return e

    # ── Unités de formation ───────────────────────────────────────────────────────

    def sauvegarder_unite(self, unite: UniteFormation) -> int:
        d = unite.to_dict()
        params = (d["nom"], d["niveau"], d["ecole_id"], d["abreviation"])
        with self._connexion() as conn:
            if unite.id is None:
                cur = conn.execute(
                    "INSERT INTO unites_formation (nom, niveau, ecole_id, abreviation) VALUES (?,?,?,?)",
                    params,
                )
                unite.id = cur.lastrowid
            else:
                try:
                    conn.execute(
                        "INSERT INTO unites_formation (id, nom, niveau, ecole_id, abreviation) VALUES (?,?,?,?,?)",
                        (unite.id, *params),
                    )
                except sqlite3.IntegrityError:
                    conn.execute(
                        "UPDATE unites_formation SET nom=?, niveau=?, ecole_id=?, abreviation=? WHERE id=?",
                        (*params, unite.id),
                    )
        return unite.id

    def charger_unite_par_id(self, unite_id: int) -> Optional[UniteFormation]:
        with self._connexion() as conn:
            row = conn.execute("SELECT * FROM unites_formation WHERE id = ?", (unite_id,)).fetchone()
        return self._ligne_vers_unite(row) if row else None

    def charger_unites_par_ecole(self, ecole_id: int) -> list:
        with self._connexion() as conn:
            rows = conn.execute(
                "SELECT * FROM unites_formation WHERE ecole_id = ? ORDER BY niveau, nom",
                (ecole_id,),
            ).fetchall()
        return [self._ligne_vers_unite(r) for r in rows]

    def charger_toutes_unites(self) -> list:
        with self._connexion() as conn:
            rows = conn.execute(
                "SELECT * FROM unites_formation ORDER BY ecole_id, niveau, nom"
            ).fetchall()
        return [self._ligne_vers_unite(r) for r in rows]

    def supprimer_unite(self, unite_id: int) -> bool:
        with self._connexion() as conn:
            cur = conn.execute("DELETE FROM unites_formation WHERE id = ?", (unite_id,))
        return cur.rowcount > 0

    def supprimer_filiere(self, ecole_id: int, nom: str) -> int:
        """Supprime tous les niveaux d'une filière (même nom, même école)."""
        with self._connexion() as conn:
            cur = conn.execute(
                "DELETE FROM unites_formation WHERE ecole_id = ? AND nom = ?",
                (ecole_id, nom),
            )
        return cur.rowcount

    def modifier_filiere(self, ecole_id: int, ancien_nom: str,
                         nouveau_nom: str, abreviation: str):
        """Met à jour le nom et l'abréviation de tous les niveaux d'une filière."""
        with self._connexion() as conn:
            conn.execute(
                "UPDATE unites_formation SET nom = ?, abreviation = ? "
                "WHERE ecole_id = ? AND nom = ?",
                (nouveau_nom, abreviation, ecole_id, ancien_nom),
            )

    @staticmethod
    def _ligne_vers_unite(row: sqlite3.Row) -> UniteFormation:
        keys = row.keys()
        abr  = row["abreviation"] if "abreviation" in keys else ""
        u = UniteFormation(row["nom"], row["niveau"], row["ecole_id"], abr)
        u.id = row["id"]
        return u

    # ── Cours multi-jours ─────────────────────────────────────────────────────────

    def sauvegarder_cours(self, cours: dict) -> int:
        jours = cours.get("jours", [])
        params = (
            cours.get("enseignant_id"),
            cours.get("classe", ""),
            cours.get("matiere", ""),
            cours.get("date_debut", ""),
            cours.get("date_fin", ""),
            cours.get("created_by"),
            cours.get("created_at", ""),
        )
        with self._connexion() as conn:
            if cours.get("id") is None:
                cur = conn.execute(
                    "INSERT INTO reservation_cours "
                    "(enseignant_id, classe, matiere, date_debut, date_fin, created_by, created_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    params,
                )
                cours["id"] = cur.lastrowid
            else:
                conn.execute(
                    "UPDATE reservation_cours "
                    "SET enseignant_id=?, classe=?, matiere=?, date_debut=?, date_fin=?, "
                    "    created_by=?, created_at=? WHERE id=?",
                    (*params, cours["id"]),
                )
                conn.execute("DELETE FROM reservation_cours_jours WHERE cours_id=?", (cours["id"],))
            for j in jours:
                conn.execute(
                    "INSERT INTO reservation_cours_jours "
                    "(cours_id, jour_semaine, salle_id, heure_debut, heure_fin) "
                    "VALUES (?,?,?,?,?)",
                    (cours["id"], j["jour_semaine"], j["salle_id"], j["heure_debut"], j["heure_fin"]),
                )
        return cours["id"]

    def charger_cours_par_id(self, cours_id: int) -> Optional[dict]:
        with self._connexion() as conn:
            row = conn.execute("SELECT * FROM reservation_cours WHERE id=?", (cours_id,)).fetchone()
            if not row:
                return None
            c = dict(row)
            jours = conn.execute(
                "SELECT * FROM reservation_cours_jours WHERE cours_id=? ORDER BY id",
                (cours_id,),
            ).fetchall()
            c["jours"] = [dict(j) for j in jours]
        return c

    def charger_tous_cours(self) -> list:
        with self._connexion() as conn:
            rows = conn.execute(
                "SELECT * FROM reservation_cours ORDER BY date_debut DESC"
            ).fetchall()
            result = []
            for row in rows:
                c = dict(row)
                jours = conn.execute(
                    "SELECT * FROM reservation_cours_jours WHERE cours_id=? ORDER BY id",
                    (c["id"],),
                ).fetchall()
                c["jours"] = [dict(j) for j in jours]
                result.append(c)
        return result

    def supprimer_cours(self, cours_id: int) -> bool:
        with self._connexion() as conn:
            cur = conn.execute("DELETE FROM reservation_cours WHERE id=?", (cours_id,))
        return cur.rowcount > 0

    # ── Configuration SMTP ────────────────────────────────────────────────────────

    def lire_config(self, cle: str, defaut: str = "") -> str:
        with self._connexion() as conn:
            row = conn.execute("SELECT valeur FROM config WHERE cle = ?", (cle,)).fetchone()
        return row["valeur"] if row else defaut

    def ecrire_config(self, cle: str, valeur: str):
        with self._connexion() as conn:
            conn.execute(
                "INSERT INTO config (cle, valeur) VALUES (?, ?) "
                "ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur",
                (cle, valeur),
            )

    def charger_config(self) -> dict:
        with self._connexion() as conn:
            rows = conn.execute("SELECT cle, valeur FROM config").fetchall()
        return {r["cle"]: r["valeur"] for r in rows}

    def __repr__(self) -> str:
        return f"<BaseDonneesSQLite '{self._chemin_db}'>"
