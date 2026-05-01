import json
import os
import sys
import random
from functools import wraps
from datetime import date, time as dtime, datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
import csv, io

from models.etablissement import Ecole, UniteFormation
from models.utilisateur import Administrateur, Etudiant, Enseignant, Responsable
from models.salle import Salle
from models.reservation import Reservation, StatutReservation
from services.authentification import Authentification
from services.gestion_reservation import GestionReservation
from services.gestion_cours import GestionCours
from services.gestion_composition import GestionComposition
from services.gestion_evenement import GestionEvenement
from services.notification_email import NotificationEmail
from persistance.db_sqlite import BaseDonneesSQLite

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "reserv_salle_secret_2026")

# Palette de couleurs pour les salles dans le planning (bg, text, border)
COULEURS_SALLES = [
    {"bg": "#e0e7ff", "text": "#3730a3", "border": "#c7d2fe"},
    {"bg": "#d1fae5", "text": "#065f46", "border": "#a7f3d0"},
    {"bg": "#fef3c7", "text": "#92400e", "border": "#fde68a"},
    {"bg": "#ffe4e6", "text": "#9f1239", "border": "#fecdd3"},
    {"bg": "#ede9fe", "text": "#5b21b6", "border": "#ddd6fe"},
    {"bg": "#cffafe", "text": "#164e63", "border": "#a5f3fc"},
    {"bg": "#fce7f3", "text": "#831843", "border": "#fbcfe8"},
    {"bg": "#dcfce7", "text": "#14532d", "border": "#bbf7d0"},
]


# ── Helpers ───────────────────────────────────────────────────────────────────────

def get_bd():
    return BaseDonneesSQLite()


def _get_unites_dict():
    """Cache par requête des unités de formation {id: UniteFormation}."""
    from flask import g
    if not hasattr(g, 'unites_dict'):
        g.unites_dict = {u.id: u for u in get_bd().charger_toutes_unites()}
    return g.unites_dict


def _format_classe(classe: str) -> str:
    """Convertit 'U15,U17' en 'L1-IG, L3-IG'. Supporte aussi les anciens formats texte."""
    if not classe:
        return ''
    unites = _get_unites_dict()
    parts = []
    for c in classe.split(','):
        c = c.strip()
        if c.startswith('U') and c[1:].isdigit():
            u = unites.get(int(c[1:]))
            parts.append(f"{u.niveau}-{u.abreviation or u.nom[:6]}" if u else c)
        else:
            parts.append(c)
    return ', '.join(parts)


@app.context_processor
def inject_format_classe():
    return dict(format_classe=_format_classe)


def get_data():
    bd   = get_bd()
    tout = bd.charger_tout()
    # Marquer automatiquement les réservations dont la fin est passée
    maintenant = datetime.now()
    for r in tout["reservations"]:
        if r.statut in (StatutReservation.CONFIRMEE, StatutReservation.EN_ATTENTE):
            if datetime.combine(r.date, r.heure_fin) < maintenant:
                r._Reservation__statut = StatutReservation.TERMINEE
                bd.sauvegarder_reservation(r)
    return (
        bd,
        {u.id: u for u in tout["utilisateurs"]},
        {s.id: s for s in tout["salles"]},
        tout["reservations"],
    )


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("user_role") != "admin":
            flash("Accès réservé aux administrateurs.", "error")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated


def peut_gerer_reservations():
    return session.get("user_role") in ("admin", "responsable")


def _get_notif():
    """Retourne un NotificationEmail configuré (DB en priorité, puis env vars), ou None."""
    bd   = get_bd()
    host = bd.lire_config("smtp_host") or os.environ.get("SMTP_HOST", "")
    port = int(bd.lire_config("smtp_port") or os.environ.get("SMTP_PORT", "587"))
    user = bd.lire_config("smtp_user") or os.environ.get("SMTP_USER", "")
    pwd  = bd.lire_config("smtp_pass") or os.environ.get("SMTP_PASS", "")
    nom  = bd.lire_config("smtp_nom")  or os.environ.get("SMTP_NOM", "UniRéserv")
    if not (host and user and pwd):
        return None
    return NotificationEmail(host, port, user, pwd, nom)


def _generer_otp() -> str:
    return f"{random.randint(0, 999999):06d}"


def _envoyer_otp(email: str, otp: str, nom: str = "") -> bool:
    notif = _get_notif()
    if notif is None:
        return False
    try:
        notif.envoyer_otp(email, otp, nom)
        return True
    except Exception:
        return False


def _envoyer_otp_reset(email: str, otp: str, nom: str = "") -> bool:
    notif = _get_notif()
    if notif is None:
        return False
    try:
        notif.envoyer_otp_reset(email, otp, nom)
        return True
    except Exception:
        return False


def _niveau(classe: str) -> str:
    """Extrait le niveau (L1/L2/L3/M1/M2) d'une chaîne de classe."""
    import re
    m = re.match(r'^(L[1-3]|M[1-2])', classe.strip().upper())
    return m.group(1) if m else classe.strip().upper()


def _notifier(reservation, utilisateurs, annulation=False):
    """Envoie les emails aux parties concernées. Échoue silencieusement si SMTP absent."""
    notif = _get_notif()
    if notif is None:
        return
    try:
        classe = reservation.classe or ""
        parties = [c.strip() for c in classe.split(",") if c.strip()]

        if any(c.startswith("U") and c[1:].isdigit() for c in parties):
            # Nouveau format : "U15,U17" → match par unite_formation_id
            ids = {int(c[1:]) for c in parties if c.startswith("U") and c[1:].isdigit()}
            etudiants = [
                u for u in utilisateurs.values()
                if isinstance(u, Etudiant) and u.unite_formation_id in ids
            ]
        else:
            # Ancien format texte : "L3" ou "L1,L2" → match par niveau
            niveaux_res = {_niveau(c) for c in parties}
            etudiants = [
                u for u in utilisateurs.values()
                if isinstance(u, Etudiant) and _niveau(u.classe) in niveaux_res
            ]

        ens_id = getattr(reservation, "enseignant_id", None)
        if ens_id:
            enseignant = utilisateurs.get(ens_id) if isinstance(utilisateurs.get(ens_id), Enseignant) else None
        else:
            enseignant = next(
                (u for u in utilisateurs.values()
                 if isinstance(u, Enseignant) and reservation.matiere in u.matieres),
                None,
            )
        notif.envoyer_responsable(reservation, annulation)
        if enseignant:
            notif.envoyer_enseignant(reservation, enseignant, annulation)
        if etudiants:
            notif.envoyer_classe(reservation, etudiants, annulation)
    except Exception:
        pass


# ── Initialisation ────────────────────────────────────────────────────────────────

def seed_admin():
    bd = get_bd()
    if not bd.charger_utilisateur_par_login("admin"):
        admin = Administrateur("Administrateur", "admin@univ.bj", "admin", "Admin@123")
        admin.id = 0
        admin.mot_de_passe = Authentification.hacher_mot_de_passe("Admin@123")
        bd.sauvegarder_utilisateur(admin)


with app.app_context():
    seed_admin()


# ── Auth ──────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return redirect(url_for("dashboard") if "user_id" in session else url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_val = request.form.get("login", "").strip()
        mdp       = request.form.get("mot_de_passe", "")
        u = get_bd().charger_utilisateur_par_login(login_val)
        if u and Authentification.verifier_hash(mdp, u.mot_de_passe):
            session.update({
                "user_id":    u.id,
                "user_role":  u.role,
                "user_nom":   u.nom,
                "user_login": u.login,
            })
            flash(f"Bienvenue, {u.nom} !", "success")
            return redirect(url_for("dashboard"))
        flash("Identifiant ou mot de passe incorrect.", "error")
    return render_template("login.html")


@app.route("/inscription", methods=["GET", "POST"])
def inscription():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    bd = get_bd()
    ecoles = bd.charger_toutes_ecoles()
    unites = bd.charger_toutes_unites()
    unites_json = json.dumps([u.to_dict() for u in unites])

    if request.method == "POST":
        nom                = request.form.get("nom", "").strip()
        email              = request.form.get("email", "").strip()
        login_val          = request.form.get("login", "").strip()
        mdp                = request.form.get("mot_de_passe", "").strip()
        role               = request.form.get("role", "etudiant")
        classe             = request.form.get("classe", "").strip()
        matricule          = request.form.get("matricule", "").strip()
        matieres_list      = request.form.getlist("matiere[]")
        matiere            = ", ".join(m.strip() for m in matieres_list if m.strip())
        ecole_id_str       = request.form.get("ecole_id", "").strip()
        unite_id_str       = request.form.get("unite_formation_id", "").strip()

        if not all([nom, email, login_val, mdp]):
            flash("Tous les champs obligatoires doivent être remplis.", "error")
            return render_template("inscription.html", ecoles=ecoles, unites_json=unites_json)

        if len(mdp) < 6:
            flash("Le mot de passe doit comporter au moins 6 caractères.", "error")
            return render_template("inscription.html", ecoles=ecoles, unites_json=unites_json)

        if role not in ("etudiant", "enseignant"):
            flash("Rôle invalide.", "error")
            return render_template("inscription.html", ecoles=ecoles, unites_json=unites_json)

        # La classe = le niveau choisi (L1, L2, L3, M1, M2)
        if role == "etudiant" and not classe and unite_id_str.isdigit():
            u_obj = next((u for u in unites if u.id == int(unite_id_str)), None)
            if u_obj:
                classe = u_obj.niveau

        if bd.charger_utilisateur_par_login(login_val):
            flash(f"Le login « {login_val} » est déjà utilisé.", "error")
            return render_template("inscription.html", ecoles=ecoles, unites_json=unites_json)

        otp    = _generer_otp()
        expire = (datetime.now() + timedelta(minutes=5)).isoformat()

        session["inscription_pending"] = {
            "code":       otp,
            "expire":     expire,
            "tentatives": 0,
            "user": {
                "nom": nom, "email": email, "login": login_val,
                "mdp_hash": Authentification.hacher_mot_de_passe(mdp),
                "role": role, "classe": classe,
                "matricule": matricule, "matiere": matiere,
                "ecole_id": int(ecole_id_str) if ecole_id_str.isdigit() else None,
                "unite_formation_id": int(unite_id_str) if unite_id_str.isdigit() else None,
            },
        }

        envoye = _envoyer_otp(email, otp, nom)
        if envoye:
            flash(f"Un code de vérification a été envoyé à {email}.", "success")
        else:
            flash(
                f"SMTP non configuré — code de test : {otp}  "
                f"(Allez dans Paramètres pour configurer l'email).",
                "warning",
            )
        return redirect(url_for("inscription_verifier"))

    return render_template("inscription.html", ecoles=ecoles, unites_json=unites_json)


@app.route("/inscription/verifier", methods=["GET", "POST"])
def inscription_verifier():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    donnees = session.get("inscription_pending")
    if not donnees:
        flash("Session expirée. Recommencez l'inscription.", "error")
        return redirect(url_for("inscription"))

    if datetime.now() > datetime.fromisoformat(donnees["expire"]):
        session.pop("inscription_pending", None)
        flash("Le code a expiré. Recommencez l'inscription.", "error")
        return redirect(url_for("inscription"))

    at = donnees["user"]["email"].find("@")
    email_masque = donnees["user"]["email"][:2] + "***" + donnees["user"]["email"][at:]

    if request.method == "POST":
        action = request.form.get("action", "verifier")

        if action == "renvoyer":
            otp = _generer_otp()
            donnees["code"]       = otp
            donnees["expire"]     = (datetime.now() + timedelta(minutes=5)).isoformat()
            donnees["tentatives"] = 0
            session["inscription_pending"] = donnees
            envoye = _envoyer_otp(donnees["user"]["email"], otp, donnees["user"].get("nom",""))
            if envoye:
                flash("Un nouveau code a été envoyé.", "success")
            else:
                flash(f"SMTP non configuré — nouveau code : {otp}", "warning")
            return redirect(url_for("inscription_verifier"))

        otp_saisi = request.form.get("otp", "").strip()
        donnees["tentatives"] = donnees.get("tentatives", 0) + 1
        session["inscription_pending"] = donnees

        if donnees["tentatives"] > 5:
            session.pop("inscription_pending", None)
            flash("Trop de tentatives. Recommencez l'inscription.", "error")
            return redirect(url_for("inscription"))

        if otp_saisi != donnees["code"]:
            restants = 5 - donnees["tentatives"]
            flash(f"Code incorrect. {restants} tentative(s) restante(s).", "error")
            return render_template("otp_verification.html", email_masque=email_masque)

        u_data = donnees["user"]
        bd     = get_bd()
        if bd.charger_utilisateur_par_login(u_data["login"]):
            session.pop("inscription_pending", None)
            flash("Ce login est déjà pris. Recommencez avec un autre login.", "error")
            return redirect(url_for("inscription"))

        if u_data["role"] == "etudiant":
            u = Etudiant(u_data["nom"], u_data["email"], u_data["login"],
                         u_data["mdp_hash"], u_data["matricule"], u_data["classe"],
                         u_data.get("ecole_id"), u_data.get("unite_formation_id"))
        else:
            u = Enseignant(u_data["nom"], u_data["email"], u_data["login"],
                           u_data["mdp_hash"], u_data["matiere"])

        bd.sauvegarder_utilisateur(u)
        session.pop("inscription_pending", None)
        flash("Compte créé avec succès ! Vous pouvez vous connecter.", "success")
        return redirect(url_for("login"))

    return render_template("otp_verification.html", email_masque=email_masque)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/mot-de-passe-oublie", methods=["GET", "POST"])
def mot_de_passe_oublie():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if not email:
            flash("Veuillez saisir votre adresse email.", "error")
            return render_template("mot_de_passe_oublie.html")

        bd = get_bd()
        utilisateur = next(
            (u for u in bd.charger_tous_utilisateurs() if u.email == email),
            None,
        )

        if utilisateur is None:
            flash("Si un compte existe avec cet email, un code vous a été envoyé.", "success")
            return render_template("mot_de_passe_oublie.html")

        otp    = _generer_otp()
        expire = (datetime.now() + timedelta(minutes=10)).isoformat()
        session["reset_pending"] = {
            "code":       otp,
            "expire":     expire,
            "tentatives": 0,
            "user_id":    utilisateur.id,
            "email":      utilisateur.email,
            "nom":        utilisateur.nom,
            "verified":   False,
        }

        envoye = _envoyer_otp_reset(email, otp, utilisateur.nom)
        if envoye:
            flash(f"Un code de réinitialisation a été envoyé à {email}.", "success")
        else:
            flash(
                f"SMTP non configuré — code de test : {otp}  "
                f"(Configurez SMTP dans les Paramètres).",
                "warning",
            )
        return redirect(url_for("mot_de_passe_oublie_verifier"))

    return render_template("mot_de_passe_oublie.html")


@app.route("/mot-de-passe-oublie/verifier", methods=["GET", "POST"])
def mot_de_passe_oublie_verifier():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    donnees = session.get("reset_pending")
    if not donnees:
        flash("Session expirée. Recommencez la réinitialisation.", "error")
        return redirect(url_for("mot_de_passe_oublie"))

    if datetime.now() > datetime.fromisoformat(donnees["expire"]):
        session.pop("reset_pending", None)
        flash("Le code a expiré. Recommencez la réinitialisation.", "error")
        return redirect(url_for("mot_de_passe_oublie"))

    at = donnees["email"].find("@")
    email_masque = donnees["email"][:2] + "***" + donnees["email"][at:]

    if request.method == "POST":
        action = request.form.get("action", "verifier")

        if action == "renvoyer":
            otp = _generer_otp()
            donnees["code"]       = otp
            donnees["expire"]     = (datetime.now() + timedelta(minutes=10)).isoformat()
            donnees["tentatives"] = 0
            donnees["verified"]   = False
            session["reset_pending"] = donnees
            envoye = _envoyer_otp_reset(donnees["email"], otp, donnees.get("nom", ""))
            if envoye:
                flash("Un nouveau code a été envoyé.", "success")
            else:
                flash(f"SMTP non configuré — nouveau code : {otp}", "warning")
            return redirect(url_for("mot_de_passe_oublie_verifier"))

        if action == "verifier":
            otp_saisi = request.form.get("otp", "").strip()
            donnees["tentatives"] = donnees.get("tentatives", 0) + 1
            session["reset_pending"] = donnees

            if donnees["tentatives"] > 5:
                session.pop("reset_pending", None)
                flash("Trop de tentatives. Recommencez la réinitialisation.", "error")
                return redirect(url_for("mot_de_passe_oublie"))

            if otp_saisi != donnees["code"]:
                restants = 5 - donnees["tentatives"]
                flash(f"Code incorrect. {restants} tentative(s) restante(s).", "error")
                return render_template("mot_de_passe_reset.html",
                                       email_masque=email_masque, etape="otp")

            donnees["verified"] = True
            session["reset_pending"] = donnees
            flash("Code vérifié. Choisissez votre nouveau mot de passe.", "success")
            return render_template("mot_de_passe_reset.html",
                                   email_masque=email_masque, etape="password")

        if action == "changer":
            if not donnees.get("verified"):
                flash("Vérification OTP requise.", "error")
                return render_template("mot_de_passe_reset.html",
                                       email_masque=email_masque, etape="otp")

            mdp1 = request.form.get("mot_de_passe", "").strip()
            mdp2 = request.form.get("mot_de_passe_confirm", "").strip()

            if not mdp1 or not mdp2:
                flash("Veuillez remplir les deux champs.", "error")
                return render_template("mot_de_passe_reset.html",
                                       email_masque=email_masque, etape="password")
            if len(mdp1) < 6:
                flash("Le mot de passe doit comporter au moins 6 caractères.", "error")
                return render_template("mot_de_passe_reset.html",
                                       email_masque=email_masque, etape="password")
            if mdp1 != mdp2:
                flash("Les mots de passe ne correspondent pas.", "error")
                return render_template("mot_de_passe_reset.html",
                                       email_masque=email_masque, etape="password")

            bd = get_bd()
            u  = bd.charger_utilisateur_par_id(donnees["user_id"])
            if u is None:
                session.pop("reset_pending", None)
                flash("Utilisateur introuvable.", "error")
                return redirect(url_for("login"))

            u.mot_de_passe = Authentification.hacher_mot_de_passe(mdp1)
            bd.sauvegarder_utilisateur(u)
            session.pop("reset_pending", None)
            flash("Mot de passe mis à jour avec succès. Connectez-vous.", "success")
            return redirect(url_for("login"))

    etape = "password" if donnees.get("verified") else "otp"
    return render_template("mot_de_passe_reset.html",
                           email_masque=email_masque, etape=etape)


# ── Dashboard ─────────────────────────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    bd, utilisateurs, salles, reservations = get_data()
    aujourd_hui = date.today()
    role        = session.get("user_role")
    u_courant   = utilisateurs.get(session["user_id"])

    confirmees  = [r for r in reservations if r.statut == StatutReservation.CONFIRMEE]
    en_attente  = [r for r in reservations if r.statut == StatutReservation.EN_ATTENTE]

    if role == "admin":
        stats = {
            "nb_salles":       len(salles),
            "nb_utilisateurs": len(utilisateurs),
            "nb_confirmees":   len(confirmees),
            "nb_en_attente":   len(en_attente),
        }
        recentes  = sorted(reservations, key=lambda r: r.date_creation, reverse=True)[:5]
        prochaines = []

    elif role == "responsable":
        classe = getattr(u_courant, "classe", "") or ""
        mes_res      = [r for r in reservations if r.responsable.id == session["user_id"]]
        cls_conf     = [r for r in confirmees if r.classe == classe]
        cls_ce_jour  = [r for r in cls_conf if r.date == aujourd_hui]
        prochaines   = sorted(
            [r for r in cls_conf if r.date >= aujourd_hui],
            key=lambda r: (r.date, r.heure_debut))[:8]
        stats = {
            "ma_classe":            classe or "—",
            "nb_mes_reservations":  len(mes_res),
            "nb_confirmees_classe": len(cls_conf),
            "nb_ce_jour_classe":    len(cls_ce_jour),
        }
        recentes = []

    elif role == "enseignant":
        matiere      = getattr(u_courant, "matiere", "") or ""
        ce_jour      = [r for r in confirmees if r.date == aujourd_hui]
        prochaines   = sorted(
            [r for r in confirmees if r.date >= aujourd_hui],
            key=lambda r: (r.date, r.heure_debut))[:8]
        stats = {
            "ma_matiere":    matiere or "—",
            "nb_salles":     len(salles),
            "nb_confirmees": len(confirmees),
            "nb_ce_jour":    len(ce_jour),
        }
        recentes = []

    else:  # etudiant
        classe = getattr(u_courant, "classe", "") or ""
        cls_conf  = [r for r in confirmees if r.classe == classe]
        ce_jour   = [r for r in cls_conf if r.date == aujourd_hui]
        lun = aujourd_hui - timedelta(days=aujourd_hui.weekday())
        dim = lun + timedelta(days=6)
        semaine = [r for r in cls_conf if lun <= r.date <= dim]
        prochaines = sorted(
            [r for r in cls_conf if r.date >= aujourd_hui],
            key=lambda r: (r.date, r.heure_debut))[:8]
        stats = {
            "ma_classe":            classe or "—",
            "nb_confirmees_classe": len(cls_conf),
            "nb_semaine":           len(semaine),
            "nb_ce_jour":           len(ce_jour),
        }
        recentes = []

    # Données pour les nouvelles sections
    toutes_comps = bd.charger_toutes_compositions()
    tous_evts    = bd.charger_tous_evenements()
    unites_dict  = {u.id: u for u in bd.charger_toutes_unites()}

    # Compositions à venir pour l'étudiant
    comps_etudiant = []
    if role == "etudiant" and u_courant:
        uf_id = getattr(u_courant, "unite_formation_id", None)
        comps_etudiant = sorted(
            [c for c in toutes_comps
             if c.get("filiere_id") == uf_id and c["date"] >= aujourd_hui.isoformat()],
            key=lambda c: c["date"],
        )[:5]

    # Événements en attente pour admin
    evts_en_attente = [e for e in tous_evts if e["statut"] == "en_attente"] if role == "admin" else []

    # Événements refusés pour le responsable
    evts_refuses = [
        e for e in tous_evts
        if e["statut"] == "refuse" and e["created_by"] == session["user_id"]
    ] if role == "responsable" else []

    return render_template(
        "dashboard.html", active="dashboard",
        role=role,
        stats=stats,
        reservations_recentes=recentes,
        prochaines=prochaines,
        aujourd_hui=aujourd_hui,
        StatutReservation=StatutReservation,
        comps_etudiant=comps_etudiant,
        evts_en_attente=evts_en_attente,
        evts_refuses=evts_refuses,
        unites_dict=unites_dict,
    )


# ── Salles ────────────────────────────────────────────────────────────────────────

@app.route("/salles")
@login_required
def salles():
    _, _, salles_dict, _ = get_data()
    q = request.args.get("q", "").strip().lower()
    toutes = list(salles_dict.values())
    resultats = [s for s in toutes if q in s.nom.lower()] if q else toutes
    return render_template("salles.html", active="salles",
                           salles=resultats, q=q, nb_total=len(toutes))


@app.route("/salles/<int:salle_id>/detail")
@login_required
def salles_detail(salle_id):
    bd, utilisateurs, salles_dict, toutes = get_data()
    salle = salles_dict.get(salle_id)
    if not salle:
        flash("Salle introuvable.", "error")
        return redirect(url_for("salles"))

    res_salle = sorted(
        [r for r in toutes if r.salle.id == salle_id],
        key=lambda r: (r.date, r.heure_debut),
    )
    aujourd_hui = date.today()
    prochaines  = [r for r in res_salle if r.date >= aujourd_hui
                   and r.statut in (StatutReservation.CONFIRMEE, StatutReservation.EN_ATTENTE)]
    passees     = [r for r in res_salle if r.date < aujourd_hui
                   or r.statut == StatutReservation.TERMINEE]

    il_y_a_30j  = aujourd_hui - timedelta(days=30)
    res_30j     = [r for r in res_salle if il_y_a_30j <= r.date <= aujourd_hui]
    jours_occ   = len(set(r.date for r in res_30j))
    taux        = round(jours_occ / 30 * 100)

    return render_template("salle_detail.html", active="salles",
                           salle=salle,
                           prochaines=prochaines[:10],
                           passees=passees[-5:],
                           taux_occupation=taux,
                           nb_total=len(res_salle),
                           StatutReservation=StatutReservation)


@app.route("/salles/ajouter", methods=["GET", "POST"])
@login_required
@admin_required
def salles_ajouter():
    if request.method == "POST":
        nom      = request.form.get("nom", "").strip()
        capacite = request.form.get("capacite", "").strip()
        eq_raw   = request.form.get("equipements", "").strip()
        equipements = [e.strip() for e in eq_raw.split(",") if e.strip()]

        if not nom or not capacite.isdigit() or int(capacite) <= 0:
            flash("Nom et capacité (entier > 0) sont obligatoires.", "error")
            return render_template("salle_form.html", action="Ajouter", active="salles")

        bd = get_bd()
        s = Salle(nom, int(capacite), equipements)
        bd.sauvegarder_salle(s)
        flash(f"Salle « {nom} » ajoutée.", "success")
        return redirect(url_for("salles"))

    return render_template("salle_form.html", action="Ajouter", active="salles")


@app.route("/salles/<int:salle_id>/modifier", methods=["GET", "POST"])
@login_required
@admin_required
def salles_modifier(salle_id):
    bd = get_bd()
    salle = bd.charger_salle_par_id(salle_id)
    if not salle:
        flash("Salle introuvable.", "error")
        return redirect(url_for("salles"))

    if request.method == "POST":
        nom      = request.form.get("nom", "").strip()
        capacite = request.form.get("capacite", "").strip()
        eq_raw   = request.form.get("equipements", "").strip()
        equipements = [e.strip() for e in eq_raw.split(",") if e.strip()]

        if nom:
            salle.nom = nom
        if capacite.isdigit() and int(capacite) > 0:
            salle.capacite = int(capacite)
        salle._Salle__equipements = equipements
        bd.sauvegarder_salle(salle)
        flash(f"Salle « {salle.nom} » modifiée.", "success")
        return redirect(url_for("salles"))

    return render_template("salle_form.html", action="Modifier",
                           salle=salle, active="salles")


@app.route("/salles/<int:salle_id>/supprimer", methods=["POST"])
@login_required
@admin_required
def salles_supprimer(salle_id):
    bd = get_bd()
    if bd.supprimer_salle(salle_id):
        flash("Salle supprimée.", "success")
    else:
        flash("Salle introuvable.", "error")
    return redirect(url_for("salles"))


# ── Réservations ──────────────────────────────────────────────────────────────────

@app.route("/reservations")
@login_required
def reservations():
    _, utilisateurs, salles_dict, toutes = get_data()
    filtre_date    = request.args.get("date", "")
    filtre_salle   = request.args.get("salle_id", "")
    filtre_classe  = request.args.get("classe", "").strip()
    filtre_places  = request.args.get("places_min", "").strip()

    resultats = list(toutes)

    # Les étudiants ne voient que les réservations de leur classe (passées et futures)
    classe_etudiant = ""
    if session.get("user_role") == "etudiant":
        u_courant = utilisateurs.get(session["user_id"])
        if u_courant and getattr(u_courant, "classe", ""):
            classe_etudiant = u_courant.classe
            resultats = [r for r in resultats if r.classe == classe_etudiant]

    if filtre_date:
        try:
            d = date.fromisoformat(filtre_date)
            resultats = [r for r in resultats if r.date == d]
        except ValueError:
            pass
    if filtre_salle and filtre_salle.isdigit():
        sid = int(filtre_salle)
        resultats = [r for r in resultats if r.salle.id == sid]
    if filtre_classe:
        resultats = [r for r in resultats if filtre_classe.lower() in r.classe.lower()]
    if filtre_places and filtre_places.isdigit():
        min_places = int(filtre_places)
        resultats = [r for r in resultats if r.salle.capacite >= min_places]

    resultats.sort(key=lambda r: (r.date, r.heure_debut))
    return render_template(
        "reservations.html", active="reservations",
        reservations=resultats,
        salles=list(salles_dict.values()),
        filtre_date=filtre_date,
        filtre_salle=filtre_salle,
        filtre_classe=filtre_classe,
        filtre_places=filtre_places,
        peut_gerer=peut_gerer_reservations(),
        StatutReservation=StatutReservation,
        classe_etudiant=classe_etudiant,
    )


@app.route("/reservations/ajouter", methods=["GET", "POST"])
@login_required
def reservation_ajouter():
    if not peut_gerer_reservations():
        flash("Accès réservé aux responsables et administrateurs.", "error")
        return redirect(url_for("reservations"))

    bd, utilisateurs, salles_dict, reservations_existantes = get_data()

    # Classe pré-remplie pour le responsable (depuis son profil)
    u_courant   = utilisateurs.get(session["user_id"])
    pre_classe  = getattr(u_courant, "classe", "") or ""

    # Filières organisées par école pour le sélecteur tronc commun
    ecoles = bd.charger_toutes_ecoles()
    unites = bd.charger_toutes_unites()
    groupes_filieres = {}
    for u in unites:
        groupes_filieres.setdefault(u.ecole_id, []).append(u)
    ecoles_filieres = [
        {"ecole": e, "unites": sorted(groupes_filieres.get(e.id, []),
                                      key=lambda x: (x.nom, x.niveau))}
        for e in ecoles if groupes_filieres.get(e.id)
    ]
    unites_json = json.dumps([u.to_dict() for u in unites])

    # Liste des enseignants pour le sélecteur
    enseignants = [u for u in utilisateurs.values() if isinstance(u, Enseignant)]
    enseignants_json = json.dumps([
        {"id": e.id, "nom": e.nom, "matieres": e.matieres}
        for e in sorted(enseignants, key=lambda x: x.nom)
    ])

    if request.method == "POST":
        salle_id      = request.form.get("salle_id", "")
        # Unités cochées (ex: ["U15","U17"]) ou champ texte de secours
        unites_cb     = request.form.getlist("unites")
        classe        = ",".join(unites_cb) if unites_cb else request.form.get("classe", "").strip()
        date_str      = request.form.get("date", "").strip()
        debut_str     = request.form.get("heure_debut", "").strip()
        fin_str       = request.form.get("heure_fin", "").strip()
        matiere       = request.form.get("matiere", "").strip()
        ens_id_str    = request.form.get("enseignant_id", "").strip()
        enseignant_id = int(ens_id_str) if ens_id_str.isdigit() else None

        salle       = salles_dict.get(int(salle_id)) if salle_id.isdigit() else None
        responsable = utilisateurs.get(session["user_id"])

        if not all([salle, classe, date_str, debut_str, fin_str]):
            flash("Tous les champs obligatoires doivent être remplis.", "error")
        else:
            try:
                gr = GestionReservation()
                gr._GestionReservation__reservations = list(reservations_existantes)
                r = gr.ajouter_reservation(
                    salle=salle,
                    responsable=responsable,
                    classe=classe,
                    date_reservation=date.fromisoformat(date_str),
                    heure_debut=dtime.fromisoformat(debut_str),
                    heure_fin=dtime.fromisoformat(fin_str),
                    matiere=matiere,
                )
                r.enseignant_id = enseignant_id
                bd.sauvegarder_reservation(r)
                _notifier(r, utilisateurs, annulation=False)
                flash(f"Réservation créée — {salle.nom} le {date_str}.", "success")
                return redirect(url_for("reservations"))
            except (ValueError, PermissionError) as e:
                flash(str(e), "error")

    pre_ecole_id = getattr(u_courant, "ecole_id", None)
    return render_template(
        "reservation_form.html", active="reservations",
        salles=list(salles_dict.values()),
        today=date.today().isoformat(),
        pre_classe=pre_classe,
        pre_ecole_id=pre_ecole_id,
        ecoles_filieres=ecoles_filieres,
        unites_json=unites_json,
        enseignants_json=enseignants_json,
        user_role=session.get("user_role"),
    )


@app.route("/reservations/<int:res_id>/modifier", methods=["GET", "POST"])
@login_required
def reservation_modifier(res_id):
    if not peut_gerer_reservations():
        flash("Action non autorisée.", "error")
        return redirect(url_for("reservations"))

    bd, utilisateurs, _, toutes = get_data()
    cible = next((r for r in toutes if r.id == res_id), None)
    if not cible:
        flash("Réservation introuvable.", "error")
        return redirect(url_for("reservations"))

    if cible.statut in (StatutReservation.ANNULEE, StatutReservation.TERMINEE):
        flash("Impossible de modifier une réservation annulée ou terminée.", "error")
        return redirect(url_for("reservations"))

    if request.method == "POST":
        date_str  = request.form.get("date", "").strip()
        debut_str = request.form.get("heure_debut", "").strip()
        fin_str   = request.form.get("heure_fin", "").strip()

        if not all([date_str, debut_str, fin_str]):
            flash("Tous les champs sont obligatoires.", "error")
        else:
            try:
                gr = GestionReservation()
                gr._GestionReservation__reservations = list(toutes)
                gr.modifier_reservation(
                    reservation_id=res_id,
                    nouvelle_date=date.fromisoformat(date_str),
                    nouvel_debut=dtime.fromisoformat(debut_str),
                    nouvelle_fin=dtime.fromisoformat(fin_str),
                )
                bd.sauvegarder_reservation(cible)
                flash("Réservation modifiée.", "success")
                return redirect(url_for("reservations"))
            except (ValueError, PermissionError) as e:
                flash(str(e), "error")

    return render_template(
        "reservation_modifier.html", active="reservations",
        reservation=cible,
    )


@app.route("/reservations/<int:res_id>/annuler", methods=["POST"])
@login_required
def reservation_annuler(res_id):
    if not peut_gerer_reservations():
        flash("Action non autorisée.", "error")
        return redirect(url_for("reservations"))

    bd, utilisateurs, _, toutes = get_data()
    cible = next((r for r in toutes if r.id == res_id), None)
    if cible:
        cible.annuler()
        bd.sauvegarder_reservation(cible)
        _notifier(cible, utilisateurs, annulation=True)
        flash("Réservation annulée.", "success")
    else:
        flash("Réservation introuvable.", "error")
    return redirect(url_for("reservations"))


@app.route("/reservations/<int:res_id>/supprimer", methods=["POST"])
@login_required
@admin_required
def reservation_supprimer(res_id):
    bd, _, _, toutes = get_data()
    cible = next((r for r in toutes if r.id == res_id), None)
    if cible:
        bd.supprimer_reservation(res_id)
        flash("Réservation supprimée définitivement.", "success")
    else:
        flash("Réservation introuvable.", "error")
    return redirect(url_for("reservations"))


@app.route("/reservations/export")
@login_required
def reservations_export_csv():
    _, utilisateurs, _, toutes = get_data()
    role      = session.get("user_role")
    u_courant = utilisateurs.get(session["user_id"])

    resultats = list(toutes)
    if role == "etudiant" and u_courant:
        classe    = getattr(u_courant, "classe", "")
        resultats = [r for r in resultats if r.classe == classe]

    resultats.sort(key=lambda r: (r.date, r.heure_debut))

    out = io.StringIO()
    w   = csv.writer(out, delimiter=";")
    w.writerow(["ID", "Salle", "Classe", "Matière", "Date",
                "Heure début", "Heure fin", "Durée (min)", "Statut", "Responsable"])
    for r in resultats:
        w.writerow([
            r.id, r.salle.nom, r.classe, r.matiere or "",
            r.date.strftime("%d/%m/%Y"),
            r.heure_debut.strftime("%H:%M"),
            r.heure_fin.strftime("%H:%M"),
            r.duree_minutes(),
            r.statut.value,
            r.responsable.nom,
        ])
    out.seek(0)
    nom_fichier = f"reservations_{date.today().isoformat()}.csv"
    return Response(
        "﻿" + out.getvalue(),          # BOM UTF-8 pour Excel
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={nom_fichier}"},
    )


# ── Planning hebdomadaire ─────────────────────────────────────────────────────────

@app.route("/planning")
@login_required
def planning():
    bd, utilisateurs, salles_dict, toutes = get_data()

    debut_str = request.args.get("debut", "")
    try:
        debut_semaine = date.fromisoformat(debut_str)
    except ValueError:
        debut_semaine = date.today()
    debut_semaine -= timedelta(days=debut_semaine.weekday())  # → lundi
    fin_semaine = debut_semaine + timedelta(days=6)

    role      = session.get("user_role")
    u_courant = utilisateurs.get(session["user_id"])

    if role == "etudiant" and u_courant:
        classe    = getattr(u_courant, "classe", "")
        pool      = [r for r in toutes if r.classe == classe]
    else:
        pool = list(toutes)

    pool = [r for r in pool
            if debut_semaine <= r.date <= fin_semaine
            and r.statut in (StatutReservation.CONFIRMEE, StatutReservation.EN_ATTENTE)]

    # Charger cours, compositions, événements pour la semaine
    _JOURS_NOM = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    tous_cours_v2  = bd.charger_tous_cours_v2()
    toutes_comps   = bd.charger_toutes_compositions()
    tous_evts      = [e for e in bd.charger_tous_evenements() if e["statut"] == "valide"]
    unites_dict    = {u.id: u for u in bd.charger_toutes_unites()}

    HEURE_DEBUT   = 7
    HEURE_FIN     = 21
    HAUTEUR_HEURE = 64
    noms_jours    = ["Lun.", "Mar.", "Mer.", "Jeu.", "Ven.", "Sam.", "Dim."]

    C_COURS = {"bg": "#dbeafe", "text": "#1e40af", "border": "#bfdbfe"}
    C_COMP  = {"bg": "#ffedd5", "text": "#9a3412", "border": "#fed7aa"}
    C_EVT   = {"bg": "#dcfce7", "text": "#14532d", "border": "#bbf7d0"}

    def _bloc(heure_debut_str, heure_fin_str, label, sous_label, couleur, type_bloc):
        dh = int(heure_debut_str[:2]) + int(heure_debut_str[3:]) / 60
        fh = int(heure_fin_str[:2])   + int(heure_fin_str[3:]) / 60
        return {
            "top":        round(max(0, (dh - HEURE_DEBUT) * HAUTEUR_HEURE)),
            "height":     round(max(28, (fh - dh) * HAUTEUR_HEURE)),
            "c":          couleur,
            "label":      label,
            "sous_label": sous_label,
            "heure":      f"{heure_debut_str}–{heure_fin_str}",
            "type":       type_bloc,
        }

    jours = []
    for i in range(7):
        d   = debut_semaine + timedelta(days=i)
        blocs = []

        # Réservations classiques
        for r in sorted(pool, key=lambda r: r.heure_debut):
            if r.date != d:
                continue
            dh = r.heure_debut.hour + r.heure_debut.minute / 60
            fh = r.heure_fin.hour   + r.heure_fin.minute   / 60
            blocs.append({
                "r":          r,
                "top":        round(max(0, (dh - HEURE_DEBUT) * HAUTEUR_HEURE)),
                "height":     round(max(28, (fh - dh) * HAUTEUR_HEURE)),
                "c":          COULEURS_SALLES[r.salle.id % len(COULEURS_SALLES)],
                "label":      r.salle.nom,
                "sous_label": _format_classe(r.classe),
                "heure":      f"{r.heure_debut.strftime('%H:%M')}–{r.heure_fin.strftime('%H:%M')}",
                "type":       "reservation",
            })

        # Cours (récurrents)
        jour_nom = _JOURS_NOM[d.weekday()]
        for c in tous_cours_v2:
            if c["date_debut"] <= d.isoformat() <= c["date_fin"]:
                for j in c["jours"]:
                    if j["jour_semaine"] == jour_nom:
                        salle = salles_dict.get(j["salle_id"])
                        filiere = unites_dict.get(c.get("filiere_id"))
                        blocs.append(_bloc(
                            j["heure_debut"], j["heure_fin"],
                            c.get("matiere") or "Cours",
                            filiere.nom if filiere else "",
                            C_COURS, "cours",
                        ))

        # Compositions
        for comp in toutes_comps:
            if comp["date"] == d.isoformat():
                filiere = unites_dict.get(comp.get("filiere_id"))
                blocs.append(_bloc(
                    comp["heure_debut"], comp["heure_fin"],
                    f"Compο — {comp.get('matiere', '')}",
                    filiere.nom if filiere else "",
                    C_COMP, "composition",
                ))

        # Événements validés
        for evt in tous_evts:
            if evt["date_debut"] <= d.isoformat() <= evt["date_fin"]:
                blocs.append(_bloc(
                    evt["heure_debut"], evt["heure_fin"],
                    evt["titre"],
                    "",
                    C_EVT, "evenement",
                ))

        blocs.sort(key=lambda b: b["top"])
        jours.append({
            "date":            d,
            "label":           noms_jours[i],
            "est_aujourd_hui": d == date.today(),
            "blocs":           blocs,
        })

    filtre_type = request.args.get("type", "tout")
    return render_template(
        "planning.html", active="planning",
        jours=jours,
        debut_semaine=debut_semaine,
        fin_semaine=fin_semaine,
        prev_semaine=(debut_semaine - timedelta(weeks=1)).isoformat(),
        next_semaine=(debut_semaine + timedelta(weeks=1)).isoformat(),
        grille_heures=list(range(HEURE_DEBUT, HEURE_FIN + 1)),
        hauteur_grille=(HEURE_FIN - HEURE_DEBUT) * HAUTEUR_HEURE,
        HAUTEUR_HEURE=HAUTEUR_HEURE,
        salles=list(salles_dict.values()),
        COULEURS_SALLES=COULEURS_SALLES,
        peut_gerer=peut_gerer_reservations(),
        StatutReservation=StatutReservation,
        filtre_type=filtre_type,
    )


# ── Utilisateurs (admin) ──────────────────────────────────────────────────────────

@app.route("/utilisateurs")
@login_required
@admin_required
def utilisateurs():
    bd, utilisateurs_dict, _, _ = get_data()
    tous = list(utilisateurs_dict.values())

    ecoles     = bd.charger_toutes_ecoles()
    unites     = bd.charger_toutes_unites()
    ecole_map  = {e.id: e for e in ecoles}
    unite_map  = {u.id: u for u in unites}

    filtre_role   = request.args.get("role", "").strip()
    filtre_search = request.args.get("q", "").strip().lower()
    filtre_ecole  = request.args.get("ecole", "").strip()

    resultats = tous
    if filtre_role:
        resultats = [u for u in resultats if u.role == filtre_role]
    if filtre_ecole and filtre_ecole.isdigit():
        eid = int(filtre_ecole)
        resultats = [u for u in resultats if getattr(u, "ecole_id", None) == eid]
    if filtre_search:
        resultats = [u for u in resultats
                     if filtre_search in u.nom.lower()
                     or filtre_search in u.email.lower()
                     or filtre_search in u.login.lower()
                     or filtre_search in getattr(u, "matricule", "").lower()]

    compteurs = {
        "tous":        len(tous),
        "etudiant":    sum(1 for u in tous if u.role == "etudiant"),
        "enseignant":  sum(1 for u in tous if u.role == "enseignant"),
        "responsable": sum(1 for u in tous if u.role == "responsable"),
        "admin":       sum(1 for u in tous if u.role == "admin"),
    }

    return render_template("utilisateurs.html", active="utilisateurs",
                           utilisateurs=resultats,
                           filtre_role=filtre_role,
                           filtre_search=filtre_search,
                           filtre_ecole=filtre_ecole,
                           compteurs=compteurs,
                           ecoles=ecoles,
                           ecole_map=ecole_map,
                           unite_map=unite_map)


@app.route("/utilisateurs/inscrire", methods=["GET", "POST"])
@login_required
@admin_required
def utilisateurs_inscrire():
    if request.method == "POST":
        nom       = request.form.get("nom", "").strip()
        email     = request.form.get("email", "").strip()
        login_val = request.form.get("login", "").strip()
        mdp       = request.form.get("mot_de_passe", "").strip()
        role          = request.form.get("role", "etudiant")
        classe        = request.form.get("classe", "").strip()
        matieres_list = request.form.getlist("matiere[]")
        matiere       = ", ".join(m.strip() for m in matieres_list if m.strip())
        matricule     = request.form.get("matricule", "").strip()

        if not all([nom, email, login_val, mdp]):
            flash("Tous les champs de base sont obligatoires.", "error")
            return render_template("utilisateur_form.html", active="utilisateurs")

        bd = get_bd()
        if bd.charger_utilisateur_par_login(login_val):
            flash(f"Le login « {login_val} » est déjà utilisé.", "error")
            return render_template("utilisateur_form.html", active="utilisateurs")

        mdp_hash = Authentification.hacher_mot_de_passe(mdp)
        if role == "etudiant":
            u = Etudiant(nom, email, login_val, mdp_hash, matricule, classe)
        elif role == "enseignant":
            u = Enseignant(nom, email, login_val, mdp_hash, matiere)
        else:
            flash("Rôle invalide.", "error")
            return render_template("utilisateur_form.html", active="utilisateurs")

        bd.sauvegarder_utilisateur(u)
        flash(f"Utilisateur « {nom} » créé avec le rôle {role}.", "success")
        return redirect(url_for("utilisateurs"))

    return render_template("utilisateur_form.html", active="utilisateurs")


@app.route("/utilisateurs/<int:user_id>/supprimer", methods=["POST"])
@login_required
@admin_required
def utilisateurs_supprimer(user_id):
    if user_id == session.get("user_id"):
        flash("Vous ne pouvez pas supprimer votre propre compte.", "error")
        return redirect(url_for("utilisateurs"))
    bd = get_bd()
    if bd.supprimer_utilisateur(user_id):
        flash("Utilisateur supprimé.", "success")
    else:
        flash("Utilisateur introuvable.", "error")
    return redirect(url_for("utilisateurs"))


@app.route("/utilisateurs/<int:user_id>/promouvoir", methods=["POST"])
@login_required
@admin_required
def utilisateurs_promouvoir(user_id):
    classe = request.form.get("classe", "").strip()
    if not classe:
        flash("Veuillez indiquer la classe pour la promotion.", "error")
        return redirect(url_for("utilisateurs"))

    bd = get_bd()
    u  = bd.charger_utilisateur_par_id(user_id)
    if not u:
        flash("Utilisateur introuvable.", "error")
        return redirect(url_for("utilisateurs"))

    nouveau = Responsable(u.nom, u.email, u.login, u.mot_de_passe, classe)
    nouveau.id = u.id
    nouveau._Utilisateur__date_inscription = u.date_inscription
    bd.sauvegarder_utilisateur(nouveau)
    flash(f"« {u.nom} » promu Responsable de {classe}.", "success")
    return redirect(url_for("utilisateurs"))


@app.route("/utilisateurs/<int:user_id>/revoquer", methods=["POST"])
@login_required
@admin_required
def utilisateurs_revoquer(user_id):
    nouveau_role = request.form.get("nouveau_role", "etudiant")
    bd = get_bd()
    u  = bd.charger_utilisateur_par_id(user_id)
    if not u or not isinstance(u, Responsable):
        flash("Cet utilisateur n'est pas Responsable.", "error")
        return redirect(url_for("utilisateurs"))

    if nouveau_role == "etudiant":
        revoque = Etudiant(u.nom, u.email, u.login, u.mot_de_passe, "", u.classe)
    else:
        revoque = Enseignant(u.nom, u.email, u.login, u.mot_de_passe, "")
    revoque.id = u.id
    revoque._Utilisateur__date_inscription = u.date_inscription
    bd.sauvegarder_utilisateur(revoque)
    flash(f"Rôle Responsable révoqué pour « {u.nom} ».", "success")
    return redirect(url_for("utilisateurs"))


# ── Profil utilisateur ────────────────────────────────────────────────────────────

@app.route("/profil", methods=["GET", "POST"])
@login_required
def profil():
    bd = get_bd()
    u  = bd.charger_utilisateur_par_id(session["user_id"])
    if not u:
        flash("Utilisateur introuvable.", "error")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        nom        = request.form.get("nom", "").strip()
        email      = request.form.get("email", "").strip()
        mdp_actuel = request.form.get("mot_de_passe_actuel", "")
        nouveau    = request.form.get("nouveau_mot_de_passe", "").strip()

        if not Authentification.verifier_hash(mdp_actuel, u.mot_de_passe):
            flash("Mot de passe actuel incorrect.", "error")
            return render_template("profil.html", active="profil", u=u)

        if nom:
            u.nom = nom
        if email:
            try:
                u.email = email
            except ValueError as e:
                flash(str(e), "error")
                return render_template("profil.html", active="profil", u=u)
        if nouveau:
            if len(nouveau) < 6:
                flash("Le nouveau mot de passe doit comporter au moins 6 caractères.", "error")
                return render_template("profil.html", active="profil", u=u)
            u.mot_de_passe = Authentification.hacher_mot_de_passe(nouveau)

        bd.sauvegarder_utilisateur(u)
        session["user_nom"] = u.nom
        flash("Profil mis à jour avec succès.", "success")
        return redirect(url_for("profil"))

    return render_template("profil.html", active="profil", u=u)


@app.route("/profil/matieres/ajouter", methods=["POST"])
@login_required
def profil_ajouter_matiere():
    bd = get_bd()
    u  = bd.charger_utilisateur_par_id(session["user_id"])
    if not isinstance(u, Enseignant):
        flash("Accès réservé aux enseignants.", "error")
        return redirect(url_for("profil"))

    nouvelle = request.form.get("nouvelle_matiere", "").strip()
    if not nouvelle:
        flash("Nom de matière requis.", "error")
        return redirect(url_for("profil"))

    matieres = u.matieres
    if nouvelle.lower() in [m.lower() for m in matieres]:
        flash(f"La matière « {nouvelle} » est déjà dans votre liste.", "warning")
        return redirect(url_for("profil"))

    matieres.append(nouvelle)
    u.matiere = ", ".join(matieres)
    bd.sauvegarder_utilisateur(u)
    flash(f"Matière « {nouvelle} » ajoutée.", "success")
    return redirect(url_for("profil"))


@app.route("/profil/matieres/supprimer", methods=["POST"])
@login_required
def profil_supprimer_matiere():
    bd = get_bd()
    u  = bd.charger_utilisateur_par_id(session["user_id"])
    if not isinstance(u, Enseignant):
        flash("Accès réservé aux enseignants.", "error")
        return redirect(url_for("profil"))

    a_supprimer = request.form.get("matiere", "").strip()
    matieres    = [m for m in u.matieres if m != a_supprimer]
    u.matiere   = ", ".join(matieres)
    bd.sauvegarder_utilisateur(u)
    flash(f"Matière « {a_supprimer} » supprimée.", "success")
    return redirect(url_for("profil"))


@app.route("/utilisateurs/<int:user_id>/modifier", methods=["GET", "POST"])
@login_required
@admin_required
def utilisateurs_modifier(user_id):
    bd = get_bd()
    u  = bd.charger_utilisateur_par_id(user_id)
    if not u:
        flash("Utilisateur introuvable.", "error")
        return redirect(url_for("utilisateurs"))

    if request.method == "POST":
        nom     = request.form.get("nom", "").strip()
        email   = request.form.get("email", "").strip()
        nouveau = request.form.get("nouveau_mot_de_passe", "").strip()
        classe  = request.form.get("classe", "").strip()
        matieres_list = request.form.getlist("matiere[]")
        matiere       = ", ".join(m.strip() for m in matieres_list if m.strip())

        if nom:
            u.nom = nom
        if email:
            try:
                u.email = email
            except ValueError as e:
                flash(str(e), "error")
                return render_template("utilisateur_modifier.html", active="utilisateurs", u=u)
        if nouveau:
            if len(nouveau) < 6:
                flash("Le mot de passe doit comporter au moins 6 caractères.", "error")
                return render_template("utilisateur_modifier.html", active="utilisateurs", u=u)
            u.mot_de_passe = Authentification.hacher_mot_de_passe(nouveau)
        if classe and hasattr(u, "classe"):
            u.classe = classe
        if hasattr(u, "matiere"):
            u.matiere = matiere

        bd.sauvegarder_utilisateur(u)
        if user_id == session.get("user_id"):
            session["user_nom"] = u.nom
        flash(f"Compte de « {u.nom} » mis à jour.", "success")
        return redirect(url_for("utilisateurs"))

    return render_template("utilisateur_modifier.html", active="utilisateurs", u=u)


# ── Paramètres SMTP (admin) ───────────────────────────────────────────────────────

@app.route("/parametres", methods=["GET", "POST"])
@login_required
@admin_required
def parametres():
    bd = get_bd()
    if request.method == "POST":
        bd.ecrire_config("smtp_host", request.form.get("smtp_host", "").strip())
        bd.ecrire_config("smtp_port", request.form.get("smtp_port", "587").strip())
        bd.ecrire_config("smtp_user", request.form.get("smtp_user", "").strip())
        mdp = request.form.get("smtp_pass", "").strip()
        if mdp:
            bd.ecrire_config("smtp_pass", mdp)
        bd.ecrire_config("smtp_nom",  request.form.get("smtp_nom", "").strip())
        flash("Configuration SMTP sauvegardée.", "success")
        return redirect(url_for("parametres"))

    cfg   = bd.charger_config()
    admin = bd.charger_utilisateur_par_id(session["user_id"])
    return render_template("parametres.html", active="parametres", cfg=cfg,
                           admin_email=admin.email if admin else "")


@app.route("/parametres/email", methods=["POST"])
@login_required
@admin_required
def parametres_email():
    bd          = get_bd()
    u           = bd.charger_utilisateur_par_id(session["user_id"])
    nouvel_email = request.form.get("nouvel_email", "").strip()
    mdp_actuel  = request.form.get("mot_de_passe_actuel", "")

    if not nouvel_email or not mdp_actuel:
        flash("Email et mot de passe requis.", "error")
        return redirect(url_for("parametres"))
    if not Authentification.verifier_hash(mdp_actuel, u.mot_de_passe):
        flash("Mot de passe incorrect.", "error")
        return redirect(url_for("parametres"))
    try:
        u.email = nouvel_email
        bd.sauvegarder_utilisateur(u)
        flash(f"Email mis à jour : {nouvel_email}", "success")
    except Exception as e:
        flash(str(e), "error")
    return redirect(url_for("parametres"))


@app.route("/parametres/tester", methods=["POST"])
@login_required
@admin_required
def parametres_tester():
    dest = request.form.get("email_test", "").strip()
    if not dest:
        flash("Veuillez saisir une adresse de destination.", "error")
        return redirect(url_for("parametres"))

    notif = _get_notif()
    if notif is None:
        flash("Configuration SMTP incomplète. Remplissez hôte, utilisateur et mot de passe.", "error")
        return redirect(url_for("parametres"))

    try:
        notif.envoyer_test(dest)
        flash(f"Email de test envoyé avec succès à {dest}.", "success")
    except Exception as e:
        flash(f"Échec de l'envoi : {e}", "error")

    return redirect(url_for("parametres"))


# ── Écoles & Facultés (admin) ─────────────────────────────────────────────────────

@app.route("/ecoles")
@login_required
@admin_required
def ecoles():
    bd = get_bd()
    toutes_ecoles = bd.charger_toutes_ecoles()
    toutes_unites = bd.charger_toutes_unites()

    filieres_par_ecole = {}
    for e in toutes_ecoles:
        groupes = {}
        for u in toutes_unites:
            if u.ecole_id != e.id:
                continue
            if u.nom not in groupes:
                groupes[u.nom] = {"nom": u.nom, "abreviation": u.abreviation, "niveaux": []}
            groupes[u.nom]["niveaux"].append(u.niveau)
        for g in groupes.values():
            g["niveaux"].sort()
            g["cycle"] = "Licence" if g["niveaux"][0].startswith("L") else "Master"
        filieres_par_ecole[e.id] = sorted(groupes.values(), key=lambda f: f["nom"])

    return render_template("ecoles.html", active="ecoles",
                           ecoles=toutes_ecoles, filieres_par_ecole=filieres_par_ecole)


@app.route("/ecoles/ajouter", methods=["GET", "POST"])
@login_required
@admin_required
def ecoles_ajouter():
    if request.method == "POST":
        nom    = request.form.get("nom", "").strip()
        type_e = request.form.get("type", "ecole")
        desc   = request.form.get("description", "").strip()
        abr    = request.form.get("abreviation", "").strip().upper()
        if not nom:
            flash("Le nom est obligatoire.", "error")
            return render_template("ecole_form.html", action="Ajouter", active="ecoles")
        if type_e not in ("ecole", "faculte"):
            type_e = "ecole"
        e = Ecole(nom, type_e, desc, abr)
        get_bd().sauvegarder_ecole(e)
        flash(f"« {nom} » ajouté(e) avec succès.", "success")
        return redirect(url_for("ecoles"))
    return render_template("ecole_form.html", action="Ajouter", active="ecoles")


@app.route("/ecoles/<int:ecole_id>/modifier", methods=["GET", "POST"])
@login_required
@admin_required
def ecoles_modifier(ecole_id):
    bd = get_bd()
    e  = bd.charger_ecole_par_id(ecole_id)
    if not e:
        flash("École introuvable.", "error")
        return redirect(url_for("ecoles"))
    if request.method == "POST":
        nom    = request.form.get("nom", "").strip()
        type_e = request.form.get("type", "ecole")
        desc   = request.form.get("description", "").strip()
        abr    = request.form.get("abreviation", "").strip().upper()
        if nom:
            e.nom = nom
        if type_e in ("ecole", "faculte"):
            e.type = type_e
        e.description = desc
        e.abreviation = abr
        bd.sauvegarder_ecole(e)
        flash(f"« {e.nom} » modifié(e).", "success")
        return redirect(url_for("ecoles"))
    return render_template("ecole_form.html", action="Modifier", ecole=e, active="ecoles")


@app.route("/ecoles/<int:ecole_id>/supprimer", methods=["POST"])
@login_required
@admin_required
def ecoles_supprimer(ecole_id):
    bd = get_bd()
    e  = bd.charger_ecole_par_id(ecole_id)
    if bd.supprimer_ecole(ecole_id):
        flash(f"« {e.nom if e else '—'} » supprimé(e).", "success")
    else:
        flash("École introuvable.", "error")
    return redirect(url_for("ecoles"))


@app.route("/ecoles/<int:ecole_id>/unites/ajouter", methods=["GET", "POST"])
@login_required
@admin_required
def unites_ajouter(ecole_id):
    bd = get_bd()
    e  = bd.charger_ecole_par_id(ecole_id)
    if not e:
        flash("École introuvable.", "error")
        return redirect(url_for("ecoles"))
    if request.method == "POST":
        nom   = request.form.get("nom", "").strip()
        cycle = request.form.get("cycle", "licence")
        abr   = request.form.get("abreviation", "").strip().upper()
        if not nom:
            flash("Le nom de la filière est obligatoire.", "error")
            return render_template("unite_form.html", mode="ajouter", ecole=e, active="ecoles")
        niveaux = ["L1", "L2", "L3"] if cycle == "licence" else ["M1", "M2"]
        for niveau in niveaux:
            bd.sauvegarder_unite(UniteFormation(nom, niveau, ecole_id, abr))
        flash(f"Filière « {nom} » créée avec {len(niveaux)} niveaux ({', '.join(niveaux)}).", "success")
        return redirect(url_for("ecoles"))
    return render_template("unite_form.html", mode="ajouter", ecole=e, active="ecoles")


@app.route("/ecoles/<int:ecole_id>/filieres/modifier", methods=["GET", "POST"])
@login_required
@admin_required
def filieres_modifier(ecole_id):
    bd          = get_bd()
    e           = bd.charger_ecole_par_id(ecole_id)
    ancien_nom  = request.args.get("nom") or request.form.get("ancien_nom", "")
    if not e or not ancien_nom:
        flash("Filière introuvable.", "error")
        return redirect(url_for("ecoles"))

    if request.method == "POST":
        nouveau_nom = request.form.get("nom", "").strip()
        abr         = request.form.get("abreviation", "").strip().upper()
        if not nouveau_nom:
            flash("Le nom est obligatoire.", "error")
        else:
            bd.modifier_filiere(ecole_id, ancien_nom, nouveau_nom, abr)
            flash(f"Filière « {nouveau_nom} » mise à jour.", "success")
            return redirect(url_for("ecoles"))

    unites_filiere = [u for u in bd.charger_unites_par_ecole(ecole_id) if u.nom == ancien_nom]
    if not unites_filiere:
        flash("Filière introuvable.", "error")
        return redirect(url_for("ecoles"))

    filiere = {
        "nom":         ancien_nom,
        "abreviation": unites_filiere[0].abreviation,
        "niveaux":     sorted(u.niveau for u in unites_filiere),
        "cycle":       "Licence" if unites_filiere[0].niveau.startswith("L") else "Master",
    }
    return render_template("unite_form.html", mode="modifier",
                           ecole=e, filiere=filiere, active="ecoles")


@app.route("/ecoles/<int:ecole_id>/filieres/supprimer", methods=["POST"])
@login_required
@admin_required
def filieres_supprimer(ecole_id):
    nom = request.form.get("nom", "")
    bd  = get_bd()
    n   = bd.supprimer_filiere(ecole_id, nom)
    if n > 0:
        flash(f"Filière « {nom} » supprimée ({n} niveau(x)).", "success")
    else:
        flash("Filière introuvable.", "error")
    return redirect(url_for("ecoles"))


# ── Cours multi-jours ────────────────────────────────────────────────────────────────

def _parser_cours_form(form, salles_dict):
    """Parse le formulaire cours. Retourne (cours_data, erreur|None)."""
    unites_cb = form.getlist("unites")
    classe    = ",".join(unites_cb) if unites_cb else form.get("classe", "").strip()
    matiere       = form.get("matiere", "").strip()
    ens_id_str    = form.get("enseignant_id", "").strip()
    enseignant_id = int(ens_id_str) if ens_id_str.isdigit() else None
    date_debut_str = form.get("date_debut", "").strip()
    date_fin_str   = form.get("date_fin", "").strip()

    if not all([classe, date_debut_str, date_fin_str]):
        return None, "Classe et période obligatoires."
    try:
        date_debut = date.fromisoformat(date_debut_str)
        date_fin   = date.fromisoformat(date_fin_str)
    except ValueError:
        return None, "Dates invalides."
    if date_debut >= date_fin:
        return None, "La date de fin doit être après la date de début."

    JOURS_NOMS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi"]
    jours_config = []
    for jour in JOURS_NOMS:
        if form.get(f"jour_{jour}"):
            sid  = form.get(f"salle_{jour}", "")
            hdeb = form.get(f"debut_{jour}", "")
            hfin = form.get(f"fin_{jour}", "")
            if sid.isdigit() and hdeb and hfin:
                try:
                    jours_config.append({
                        "jour": jour,
                        "salle_id": int(sid),
                        "heure_debut": dtime.fromisoformat(hdeb),
                        "heure_fin":   dtime.fromisoformat(hfin),
                    })
                except ValueError:
                    pass

    if not jours_config:
        return None, "Au moins un jour doit être configuré avec salle et horaires."

    return {
        "enseignant_id": enseignant_id,
        "classe":        classe,
        "matiere":       matiere,
        "date_debut":    date_debut,
        "date_fin":      date_fin,
        "jours":         jours_config,
    }, None


@app.route("/cours")
@login_required
def cours_liste():
    if not peut_gerer_reservations():
        flash("Accès réservé aux responsables et administrateurs.", "error")
        return redirect(url_for("dashboard"))
    bd, utilisateurs, salles_dict, _ = get_data()
    tous_cours = bd.charger_tous_cours()
    return render_template(
        "cours.html", active="cours",
        cours_liste=tous_cours,
        utilisateurs=utilisateurs,
        salles_dict=salles_dict,
        today=date.today().isoformat(),
    )


@app.route("/cours/nouveau", methods=["GET", "POST"])
@login_required
def cours_nouveau():
    if not peut_gerer_reservations():
        flash("Accès réservé aux responsables et administrateurs.", "error")
        return redirect(url_for("dashboard"))

    bd, utilisateurs, salles_dict, reservations_existantes = get_data()
    ecoles  = bd.charger_toutes_ecoles()
    unites  = bd.charger_toutes_unites()
    groupes = {}
    for u in unites:
        groupes.setdefault(u.ecole_id, []).append(u)
    ecoles_filieres = [
        {"ecole": e, "unites": sorted(groupes.get(e.id, []), key=lambda x: (x.nom, x.niveau))}
        for e in ecoles if groupes.get(e.id)
    ]
    unites_json = json.dumps([u.to_dict() for u in unites])
    enseignants = [u for u in utilisateurs.values() if isinstance(u, Enseignant)]
    enseignants_json = json.dumps([
        {"id": e.id, "nom": e.nom, "matieres": e.matieres}
        for e in sorted(enseignants, key=lambda x: x.nom)
    ])

    if request.method == "POST":
        cours_data, erreur = _parser_cours_form(request.form, salles_dict)
        if erreur:
            flash(erreur, "error")
        else:
            ignorer    = request.form.get("ignorer_conflits") == "1"
            responsable = utilisateurs.get(session["user_id"])
            gr = GestionReservation()
            gr._GestionReservation__reservations = list(reservations_existantes)
            conflits, reservations_creees = gr.creer_cours(
                cours_data, salles_dict, responsable, ignorer_conflits=ignorer
            )
            if conflits:
                flash(
                    f"{len(conflits)} conflit(s) détecté(s). "
                    "Vérifiez les dates ou cochez « Ignorer les conflits ».",
                    "error",
                )
            else:
                cours_db = {
                    "id":            None,
                    "enseignant_id": cours_data["enseignant_id"],
                    "classe":        cours_data["classe"],
                    "matiere":       cours_data["matiere"],
                    "date_debut":    cours_data["date_debut"].isoformat(),
                    "date_fin":      cours_data["date_fin"].isoformat(),
                    "created_by":    session["user_id"],
                    "created_at":    datetime.now().isoformat(),
                    "jours": [
                        {
                            "jour_semaine": j["jour"],
                            "salle_id":    j["salle_id"],
                            "heure_debut": j["heure_debut"].strftime("%H:%M"),
                            "heure_fin":   j["heure_fin"].strftime("%H:%M"),
                        }
                        for j in cours_data["jours"]
                    ],
                }
                cours_id = bd.sauvegarder_cours(cours_db)
                for r in reservations_creees:
                    r.cours_id = cours_id
                    bd.sauvegarder_reservation(r)
                flash(
                    f"Cours créé — {len(reservations_creees)} séance(s) planifiée(s).",
                    "success",
                )
                return redirect(url_for("cours_liste"))

    u_courant    = utilisateurs.get(session["user_id"])
    pre_classe   = getattr(u_courant, "classe", "") or ""
    pre_ecole_id = getattr(u_courant, "ecole_id", None)
    return render_template(
        "cours_form.html", active="cours",
        salles=list(salles_dict.values()),
        ecoles_filieres=ecoles_filieres,
        unites_json=unites_json,
        enseignants_json=enseignants_json,
        pre_classe=pre_classe,
        pre_ecole_id=pre_ecole_id,
        user_role=session.get("user_role"),
        today=date.today().isoformat(),
    )


@app.route("/cours/verifier-conflits", methods=["POST"])
@login_required
def cours_verifier_conflits():
    bd, utilisateurs, salles_dict, reservations_existantes = get_data()
    cours_data, erreur = _parser_cours_form(request.form, salles_dict)
    if erreur:
        return Response(json.dumps({"erreur": erreur}), content_type="application/json"), 400
    responsable = utilisateurs.get(session["user_id"])
    gr = GestionReservation()
    gr._GestionReservation__reservations = list(reservations_existantes)
    conflits, _ = gr.creer_cours(cours_data, salles_dict, responsable, ignorer_conflits=False)
    return Response(json.dumps({
        "nb_conflits": len(conflits),
        "conflits": [
            {
                "date":                c["date"].strftime("%d/%m/%Y"),
                "jour":                c["jour"].capitalize(),
                "salle":               c["salle"].nom,
                "heure_debut":         c["heure_debut"].strftime("%H:%M"),
                "heure_fin":           c["heure_fin"].strftime("%H:%M"),
                "conflit_avec_id":     c["conflit_avec_id"],
                "conflit_avec_classe": c["conflit_avec_classe"],
            }
            for c in conflits
        ],
    }), content_type="application/json")


@app.route("/cours/<int:cours_id>/annuler", methods=["POST"])
@login_required
def cours_annuler(cours_id):
    if not peut_gerer_reservations():
        flash("Accès réservé.", "error")
        return redirect(url_for("dashboard"))
    bd, utilisateurs, salles_dict, reservations_existantes = get_data()
    cours = bd.charger_cours_par_id(cours_id)
    if not cours:
        flash("Cours introuvable.", "error")
        return redirect(url_for("cours_liste"))
    gr = GestionReservation()
    gr._GestionReservation__reservations = list(reservations_existantes)
    annulees = gr.annuler_cours(cours_id)
    for r in annulees:
        bd.sauvegarder_reservation(r)
    flash(f"{len(annulees)} séance(s) future(s) annulée(s).", "success")
    return redirect(url_for("cours_liste"))


# ── API AJAX ──────────────────────────────────────────────────────────────────────

@app.route("/api/enseignants/recherche")
@login_required
def api_enseignants_recherche():
    from flask import jsonify
    q = request.args.get("q", "").strip().lower()
    _, utilisateurs, _, _ = get_data()
    resultats = [
        {"id": u.id, "nom": u.nom, "email": u.email,
         "matieres": getattr(u, "matieres", [])}
        for u in utilisateurs.values()
        if u.role == "enseignant" and (q in u.nom.lower() or q in u.email.lower())
    ]
    return jsonify(resultats[:10])


# ── Cours v2 (nouveau système avec filière) ───────────────────────────────────────

def _parser_cours_v2(form, salles_dict):
    """Parse le formulaire cours v2 (filiere_id + vacataire). Retourne (data, erreur|None)."""
    filiere_id_str = form.get("filiere_id", "").strip()
    filiere_id     = int(filiere_id_str) if filiere_id_str.isdigit() else None
    if not filiere_id:
        return None, "La filière est obligatoire."

    ens_id_str    = form.get("enseignant_id", "").strip()
    enseignant_id = int(ens_id_str) if ens_id_str.isdigit() else None
    ens_nom_ext   = form.get("enseignant_nom_ext", "").strip()
    ens_email_ext = form.get("enseignant_email_ext", "").strip()
    matiere       = form.get("matiere", "").strip()

    date_debut_str = form.get("date_debut", "").strip()
    date_fin_str   = form.get("date_fin", "").strip()
    if not all([date_debut_str, date_fin_str]):
        return None, "Les dates de début et fin sont obligatoires."
    try:
        date_debut = date.fromisoformat(date_debut_str)
        date_fin   = date.fromisoformat(date_fin_str)
    except ValueError:
        return None, "Dates invalides."
    if date_debut >= date_fin:
        return None, "La date de fin doit être après la date de début."

    JOURS_NOMS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi"]
    jours_config = []
    for jour in JOURS_NOMS:
        if form.get(f"jour_{jour}"):
            sid  = form.get(f"salle_{jour}", "")
            hdeb = form.get(f"debut_{jour}", "")
            hfin = form.get(f"fin_{jour}", "")
            if sid.isdigit() and hdeb and hfin:
                try:
                    jours_config.append({
                        "jour_semaine": jour,
                        "salle_id":     int(sid),
                        "heure_debut":  dtime.fromisoformat(hdeb).strftime("%H:%M"),
                        "heure_fin":    dtime.fromisoformat(hfin).strftime("%H:%M"),
                    })
                except ValueError:
                    pass

    if not jours_config:
        return None, "Au moins un jour doit être configuré avec salle et horaires."

    return {
        "filiere_id":           filiere_id,
        "enseignant_id":        enseignant_id,
        "enseignant_nom_ext":   ens_nom_ext,
        "enseignant_email_ext": ens_email_ext,
        "matiere":              matiere,
        "date_debut":           date_debut,
        "date_fin":             date_fin,
        "jours":                jours_config,
        "created_by":           session["user_id"],
    }, None


@app.route("/cours/v2")
@login_required
def cours_v2_liste():
    if not peut_gerer_reservations():
        flash("Accès réservé aux responsables et administrateurs.", "error")
        return redirect(url_for("dashboard"))
    bd, utilisateurs, salles_dict, _ = get_data()
    tous_cours = bd.charger_tous_cours_v2()
    unites     = {u.id: u for u in bd.charger_toutes_unites()}
    return render_template(
        "cours_v2.html", active="cours",
        cours_liste=tous_cours,
        utilisateurs=utilisateurs,
        salles_dict=salles_dict,
        unites=unites,
        today=date.today().isoformat(),
    )


@app.route("/cours/v2/nouveau", methods=["GET", "POST"])
@login_required
def cours_v2_nouveau():
    if not peut_gerer_reservations():
        flash("Accès réservé aux responsables et administrateurs.", "error")
        return redirect(url_for("dashboard"))

    bd, utilisateurs, salles_dict, _ = get_data()
    ecoles  = bd.charger_toutes_ecoles()
    unites  = bd.charger_toutes_unites()
    groupes = {}
    for u in unites:
        groupes.setdefault(u.ecole_id, []).append(u)
    ecoles_filieres = [
        {"ecole": e, "unites": sorted(groupes.get(e.id, []), key=lambda x: (x.nom, x.niveau))}
        for e in ecoles if groupes.get(e.id)
    ]
    unites_json = json.dumps([u.to_dict() for u in unites])

    if request.method == "POST":
        cours_data, erreur = _parser_cours_v2(request.form, salles_dict)
        if erreur:
            flash(erreur, "error")
        else:
            gc      = GestionCours(bd)
            notif   = _get_notif()
            resultat = gc.creer_cours(cours_data, notif=notif, utilisateurs=utilisateurs)
            if resultat["conflits"]:
                flash(f"{len(resultat['conflits'])} conflit(s) détecté(s). Vérifiez les dates.", "error")
                return render_template(
                    "cours_v2_form.html", active="cours",
                    ecoles_filieres=ecoles_filieres, unites_json=unites_json,
                    salles=list(salles_dict.values()),
                    conflits=resultat["conflits"],
                    today=date.today().isoformat(),
                )
            flash(f"Cours créé avec succès.", "success")
            return redirect(url_for("cours_v2_liste"))

    return render_template(
        "cours_v2_form.html", active="cours",
        ecoles_filieres=ecoles_filieres, unites_json=unites_json,
        salles=list(salles_dict.values()),
        conflits=[],
        today=date.today().isoformat(),
    )


@app.route("/cours/v2/<int:cours_id>/modifier", methods=["GET", "POST"])
@login_required
def cours_v2_modifier(cours_id):
    if not peut_gerer_reservations():
        flash("Accès réservé.", "error")
        return redirect(url_for("dashboard"))

    bd, utilisateurs, salles_dict, _ = get_data()
    cours = bd.charger_cours_v2_par_id(cours_id)
    if not cours:
        flash("Cours introuvable.", "error")
        return redirect(url_for("cours_v2_liste"))

    ecoles  = bd.charger_toutes_ecoles()
    unites  = bd.charger_toutes_unites()
    groupes = {}
    for u in unites:
        groupes.setdefault(u.ecole_id, []).append(u)
    ecoles_filieres = [
        {"ecole": e, "unites": sorted(groupes.get(e.id, []), key=lambda x: (x.nom, x.niveau))}
        for e in ecoles if groupes.get(e.id)
    ]
    unites_json = json.dumps([u.to_dict() for u in unites])

    if request.method == "POST":
        cours_data, erreur = _parser_cours_v2(request.form, salles_dict)
        if erreur:
            flash(erreur, "error")
        else:
            gc       = GestionCours(bd)
            notif    = _get_notif()
            resultat = gc.modifier_cours(cours_id, cours_data, notif=notif, utilisateurs=utilisateurs)
            if resultat.get("conflits"):
                flash(f"{len(resultat['conflits'])} conflit(s) après modification.", "error")
            else:
                flash("Cours modifié.", "success")
                return redirect(url_for("cours_v2_liste"))

    return render_template(
        "cours_v2_form.html", active="cours",
        ecoles_filieres=ecoles_filieres, unites_json=unites_json,
        salles=list(salles_dict.values()),
        cours=cours, conflits=[],
        today=date.today().isoformat(),
    )


@app.route("/cours/v2/<int:cours_id>/annuler", methods=["POST"])
@login_required
def cours_v2_annuler(cours_id):
    if not peut_gerer_reservations():
        flash("Accès réservé.", "error")
        return redirect(url_for("dashboard"))
    bd, utilisateurs, _, _ = get_data()
    gc    = GestionCours(bd)
    notif = _get_notif()
    if gc.annuler_cours(cours_id, notif=notif, utilisateurs=utilisateurs):
        flash("Cours annulé.", "success")
    else:
        flash("Cours introuvable.", "error")
    return redirect(url_for("cours_v2_liste"))


@app.route("/cours/v2/verifier-conflits", methods=["POST"])
@login_required
def cours_v2_verifier_conflits():
    from flask import jsonify
    bd, _, salles_dict, _ = get_data()
    cours_data, erreur = _parser_cours_v2(request.form, salles_dict)
    if erreur:
        return jsonify({"erreur": erreur, "conflits": []}), 400
    gc = GestionCours(bd)
    conflits = gc.verifier_conflits(cours_data)
    return jsonify({
        "nb_conflits": len(conflits),
        "conflits": [
            {
                "date": c["date"], "jour": c["jour"],
                "heure_debut": c["heure_debut"], "heure_fin": c["heure_fin"],
                "conflit_type": c["conflit"]["type"],
                "conflit_label": c["conflit"]["label"],
            }
            for c in conflits
        ],
    })


# ── Compositions ──────────────────────────────────────────────────────────────────

def _peut_gerer_compositions():
    return session.get("user_role") in ("admin", "responsable", "enseignant")


@app.route("/compositions")
@login_required
def compositions_liste():
    if not _peut_gerer_compositions():
        flash("Accès non autorisé.", "error")
        return redirect(url_for("dashboard"))
    bd, utilisateurs, salles_dict, _ = get_data()
    toutes   = bd.charger_toutes_compositions()
    unites   = {u.id: u for u in bd.charger_toutes_unites()}
    return render_template(
        "compositions.html", active="compositions",
        compositions=toutes,
        utilisateurs=utilisateurs,
        salles_dict=salles_dict,
        unites=unites,
        today=date.today().isoformat(),
    )


@app.route("/compositions/nouvelle", methods=["GET", "POST"])
@login_required
def compositions_nouvelle():
    if not _peut_gerer_compositions():
        flash("Accès non autorisé.", "error")
        return redirect(url_for("dashboard"))

    bd, utilisateurs, salles_dict, _ = get_data()
    ecoles  = bd.charger_toutes_ecoles()
    unites  = bd.charger_toutes_unites()
    groupes = {}
    for u in unites:
        groupes.setdefault(u.ecole_id, []).append(u)
    ecoles_filieres = [
        {"ecole": e, "unites": sorted(groupes.get(e.id, []), key=lambda x: (x.nom, x.niveau))}
        for e in ecoles if groupes.get(e.id)
    ]
    unites_json = json.dumps([u.to_dict() for u in unites])

    if request.method == "POST":
        filiere_id_str = request.form.get("filiere_id", "").strip()
        filiere_id     = int(filiere_id_str) if filiere_id_str.isdigit() else None
        ens_id_str     = request.form.get("enseignant_id", "").strip()
        enseignant_id  = int(ens_id_str) if ens_id_str.isdigit() else None
        salle_id_str   = request.form.get("salle_id", "").strip()
        salle_id       = int(salle_id_str) if salle_id_str.isdigit() else None
        date_str       = request.form.get("date", "").strip()
        hdeb           = request.form.get("heure_debut", "").strip()
        hfin           = request.form.get("heure_fin", "").strip()
        matiere        = request.form.get("matiere", "").strip()
        ens_nom_ext    = request.form.get("enseignant_nom_ext", "").strip()
        ens_email_ext  = request.form.get("enseignant_email_ext", "").strip()

        if not all([filiere_id, salle_id, date_str, hdeb, hfin]):
            flash("Tous les champs obligatoires doivent être remplis.", "error")
        else:
            try:
                comp_data = {
                    "filiere_id":           filiere_id,
                    "enseignant_id":        enseignant_id,
                    "enseignant_nom_ext":   ens_nom_ext,
                    "enseignant_email_ext": ens_email_ext,
                    "matiere":              matiere,
                    "salle_id":             salle_id,
                    "date":                 date.fromisoformat(date_str),
                    "heure_debut":          hdeb,
                    "heure_fin":            hfin,
                    "created_by":           session["user_id"],
                }
                gc    = GestionComposition(bd)
                notif = _get_notif()
                res   = gc.creer_composition(comp_data, notif=notif, utilisateurs=utilisateurs)
                if res["conflit"]:
                    c = res["conflit"]
                    flash(f"Conflit avec {c['type']} « {c['label']} » ({c['heure_debut']}–{c['heure_fin']}).", "error")
                else:
                    mention = " (sur cours existant)" if res["sur_cours_existant"] else ""
                    flash(f"Composition créée{mention}.", "success")
                    return redirect(url_for("compositions_liste"))
            except ValueError as e:
                flash(str(e), "error")

    return render_template(
        "composition_form.html", active="compositions",
        ecoles_filieres=ecoles_filieres, unites_json=unites_json,
        salles=list(salles_dict.values()),
        today=date.today().isoformat(),
    )


@app.route("/compositions/<int:comp_id>/annuler", methods=["POST"])
@login_required
def compositions_annuler(comp_id):
    if not _peut_gerer_compositions():
        flash("Accès non autorisé.", "error")
        return redirect(url_for("dashboard"))
    bd, utilisateurs, _, _ = get_data()
    gc    = GestionComposition(bd)
    notif = _get_notif()
    if gc.annuler_composition(comp_id, notif=notif, utilisateurs=utilisateurs):
        flash("Composition annulée.", "success")
    else:
        flash("Composition introuvable.", "error")
    return redirect(url_for("compositions_liste"))


# ── Événements ────────────────────────────────────────────────────────────────────

@app.route("/evenements")
@login_required
def evenements_liste():
    if not peut_gerer_reservations():
        flash("Accès non autorisé.", "error")
        return redirect(url_for("dashboard"))
    bd, utilisateurs, salles_dict, _ = get_data()
    tous  = bd.charger_tous_evenements()
    en_attente = [e for e in tous if e["statut"] == "en_attente"]
    return render_template(
        "evenements.html", active="evenements",
        evenements=tous,
        nb_en_attente=len(en_attente),
        utilisateurs=utilisateurs,
        salles_dict=salles_dict,
        today=date.today().isoformat(),
        role=session.get("user_role"),
    )


@app.route("/evenements/nouveau", methods=["GET", "POST"])
@login_required
def evenements_nouveau():
    if not peut_gerer_reservations():
        flash("Accès non autorisé.", "error")
        return redirect(url_for("dashboard"))

    bd, utilisateurs, salles_dict, _ = get_data()

    ecoles  = bd.charger_toutes_ecoles()
    unites  = bd.charger_toutes_unites()
    groupes = {}
    for u in unites:
        groupes.setdefault(u.ecole_id, []).append(u)
    ecoles_filieres = [
        {"ecole": e, "unites": sorted(groupes.get(e.id, []), key=lambda x: (x.nom, x.niveau))}
        for e in ecoles if groupes.get(e.id)
    ]
    unites_json = json.dumps([u.to_dict() for u in unites])

    if request.method == "POST":
        titre       = request.form.get("titre", "").strip()
        description = request.form.get("description", "").strip()
        salle_id_str = request.form.get("salle_id", "").strip()
        salle_id    = int(salle_id_str) if salle_id_str.isdigit() else None
        date_debut_str = request.form.get("date_debut", "").strip()
        date_fin_str   = request.form.get("date_fin", "").strip()
        hdeb = request.form.get("heure_debut", "").strip()
        hfin = request.form.get("heure_fin", "").strip()
        pc_type = request.form.get("public_cible_type", "universite")
        pc_id_str = request.form.get("public_cible_id", "").strip()
        pc_id = int(pc_id_str) if pc_id_str.isdigit() else None
        pc_ids_raw = request.form.getlist("public_cible_ids[]")
        pc_ids = [int(x) for x in pc_ids_raw if x.isdigit()]

        if not all([titre, description, salle_id, date_debut_str, date_fin_str, hdeb, hfin]):
            flash("Tous les champs obligatoires doivent être remplis.", "error")
        else:
            try:
                evt_data = {
                    "titre":              titre,
                    "description":        description,
                    "salle_id":           salle_id,
                    "date_debut":         date.fromisoformat(date_debut_str),
                    "date_fin":           date.fromisoformat(date_fin_str),
                    "heure_debut":        hdeb,
                    "heure_fin":          hfin,
                    "created_by":         session["user_id"],
                    "public_cible_type":  pc_type,
                    "public_cible_id":    pc_id,
                    "public_cible_ids":   pc_ids,
                }
                ge    = GestionEvenement(bd)
                notif = _get_notif()
                role  = session.get("user_role")
                res   = ge.creer_evenement(evt_data, role, notif=notif, utilisateurs=utilisateurs)
                if res["conflit"]:
                    c = res["conflit"]
                    flash(f"Conflit salle avec {c['type']} « {c['label']} ».", "error")
                elif res["statut"] == "valide":
                    flash("Événement créé et validé.", "success")
                    return redirect(url_for("evenements_liste"))
                else:
                    flash("Événement soumis — en attente de validation par un administrateur.", "info")
                    return redirect(url_for("evenements_liste"))
            except ValueError as e:
                flash(str(e), "error")

    return render_template(
        "evenement_form.html", active="evenements",
        salles=list(salles_dict.values()),
        ecoles_filieres=ecoles_filieres,
        unites_json=unites_json,
        today=date.today().isoformat(),
        role=session.get("user_role"),
    )


@app.route("/evenements/<int:evt_id>/modifier", methods=["GET", "POST"])
@login_required
def evenements_modifier(evt_id):
    if not peut_gerer_reservations():
        flash("Accès non autorisé.", "error")
        return redirect(url_for("dashboard"))
    bd, _, salles_dict, _ = get_data()
    evt = bd.charger_evenement_par_id(evt_id)
    if not evt:
        flash("Événement introuvable.", "error")
        return redirect(url_for("evenements_liste"))
    if isinstance(evt.get("public_cible_ids"), str):
        try:
            evt["public_cible_ids"] = json.loads(evt["public_cible_ids"])
        except Exception:
            evt["public_cible_ids"] = []

    ecoles  = bd.charger_toutes_ecoles()
    unites  = bd.charger_toutes_unites()
    groupes = {}
    for u in unites:
        groupes.setdefault(u.ecole_id, []).append(u)
    ecoles_filieres = [
        {"ecole": e, "unites": sorted(groupes.get(e.id, []), key=lambda x: (x.nom, x.niveau))}
        for e in ecoles if groupes.get(e.id)
    ]
    unites_json = json.dumps([u.to_dict() for u in unites])

    if request.method == "POST":
        titre       = request.form.get("titre", "").strip()
        description = request.form.get("description", "").strip()
        salle_id_str = request.form.get("salle_id", "").strip()
        salle_id    = int(salle_id_str) if salle_id_str.isdigit() else None
        date_debut_str = request.form.get("date_debut", "").strip()
        date_fin_str   = request.form.get("date_fin", "").strip()
        hdeb = request.form.get("heure_debut", "").strip()
        hfin = request.form.get("heure_fin", "").strip()
        pc_type = request.form.get("public_cible_type", "universite")
        pc_id_str = request.form.get("public_cible_id", "").strip()
        pc_id = int(pc_id_str) if pc_id_str.isdigit() else None
        pc_ids_raw = request.form.getlist("public_cible_ids[]")
        pc_ids = [int(x) for x in pc_ids_raw if x.isdigit()]
        if all([titre, description, salle_id, date_debut_str, date_fin_str, hdeb, hfin]):
            ge = GestionEvenement(bd)
            ge.modifier_evenement(evt_id, {
                "titre": titre, "description": description, "salle_id": salle_id,
                "date_debut": date.fromisoformat(date_debut_str),
                "date_fin":   date.fromisoformat(date_fin_str),
                "heure_debut": hdeb, "heure_fin": hfin,
                "public_cible_type": pc_type,
                "public_cible_id":   pc_id,
                "public_cible_ids":  pc_ids,
            })
            flash("Événement modifié.", "success")
            return redirect(url_for("evenements_liste"))
        flash("Tous les champs sont obligatoires.", "error")

    return render_template(
        "evenement_form.html", active="evenements",
        salles=list(salles_dict.values()),
        ecoles_filieres=ecoles_filieres,
        unites_json=unites_json,
        evt=evt,
        today=date.today().isoformat(),
        role=session.get("user_role"),
    )


@app.route("/evenements/<int:evt_id>/valider", methods=["POST"])
@login_required
@admin_required
def evenements_valider(evt_id):
    bd, utilisateurs, _, _ = get_data()
    ge    = GestionEvenement(bd)
    notif = _get_notif()
    if ge.valider_evenement(evt_id, session["user_id"], notif=notif, utilisateurs=utilisateurs):
        flash("Événement validé.", "success")
    else:
        flash("Impossible de valider cet événement.", "error")
    return redirect(url_for("evenements_liste"))


@app.route("/evenements/<int:evt_id>/refuser", methods=["POST"])
@login_required
@admin_required
def evenements_refuser(evt_id):
    motif = request.form.get("motif", "").strip()
    bd, utilisateurs, _, _ = get_data()
    ge = GestionEvenement(bd)
    if ge.refuser_evenement(evt_id, session["user_id"], motif):
        flash("Événement refusé.", "success")
    else:
        flash("Événement introuvable.", "error")
    return redirect(url_for("evenements_liste"))


@app.errorhandler(404)
def page_non_trouvee(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def erreur_serveur(e):
    return render_template("404.html", erreur_500=True), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
