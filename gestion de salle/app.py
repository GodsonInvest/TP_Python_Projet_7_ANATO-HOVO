import os
import sys
import random
from functools import wraps
from datetime import date, time as dtime, datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, render_template, request, redirect, url_for, session, flash

from models.utilisateur import Administrateur, Etudiant, Enseignant, Responsable
from models.salle import Salle
from models.reservation import Reservation, StatutReservation
from services.authentification import Authentification
from services.gestion_reservation import GestionReservation
from services.notification_email import NotificationEmail
from persistance.db_sqlite import BaseDonneesSQLite

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "reserv_salle_secret_2026")


# ── Helpers ───────────────────────────────────────────────────────────────────────

def get_bd():
    return BaseDonneesSQLite()


def get_data():
    bd  = get_bd()
    tout = bd.charger_tout()
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
    if not (host and user and pwd):
        return None
    return NotificationEmail(host, port, user, pwd)


def _generer_otp() -> str:
    return f"{random.randint(0, 999999):06d}"


def _envoyer_otp(email: str, otp: str) -> bool:
    notif = _get_notif()
    if notif is None:
        return False
    try:
        notif.envoyer_email(
            email,
            "Code de vérification — Inscription",
            f"Bonjour,\n\nVotre code de vérification est : {otp}\n\n"
            f"Ce code expire dans 5 minutes.\n\n"
            f"Si vous n'avez pas demandé ce code, ignorez cet email.\n\n"
            f"Cordialement,\nSystème de réservation universitaire",
        )
        return True
    except Exception:
        return False


def _notifier(reservation, utilisateurs, annulation=False):
    """Envoie les emails aux parties concernées. Échoue silencieusement si SMTP absent."""
    notif = _get_notif()
    if notif is None:
        return
    try:
        etudiants = [
            u for u in utilisateurs.values()
            if isinstance(u, Etudiant) and u.classe == reservation.classe
        ]
        enseignant = next(
            (u for u in utilisateurs.values()
             if isinstance(u, Enseignant) and u.matiere == reservation.matiere),
            None,
        )
        notif.envoyer_responsable(reservation, annulation)
        if enseignant:
            notif.envoyer_enseignant(reservation, enseignant, annulation)
        if etudiants:
            notif.envoyer_etudiants(reservation, etudiants, annulation)
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

    if request.method == "POST":
        nom       = request.form.get("nom", "").strip()
        email     = request.form.get("email", "").strip()
        login_val = request.form.get("login", "").strip()
        mdp       = request.form.get("mot_de_passe", "").strip()
        role      = request.form.get("role", "etudiant")
        classe    = request.form.get("classe", "").strip()
        matricule = request.form.get("matricule", "").strip()
        matiere   = request.form.get("matiere", "").strip()

        if not all([nom, email, login_val, mdp]):
            flash("Tous les champs obligatoires doivent être remplis.", "error")
            return render_template("inscription.html")

        if len(mdp) < 6:
            flash("Le mot de passe doit comporter au moins 6 caractères.", "error")
            return render_template("inscription.html")

        if role not in ("etudiant", "enseignant"):
            flash("Rôle invalide.", "error")
            return render_template("inscription.html")

        bd = get_bd()
        if bd.charger_utilisateur_par_login(login_val):
            flash(f"Le login « {login_val} » est déjà utilisé.", "error")
            return render_template("inscription.html")

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
            },
        }

        envoye = _envoyer_otp(email, otp)
        if envoye:
            flash(f"Un code de vérification a été envoyé à {email}.", "success")
        else:
            flash(
                f"SMTP non configuré — code de test : {otp}  "
                f"(Allez dans Paramètres pour configurer l'email).",
                "warning",
            )
        return redirect(url_for("inscription_verifier"))

    return render_template("inscription.html")


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
            envoye = _envoyer_otp(donnees["user"]["email"], otp)
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
                         u_data["mdp_hash"], u_data["matricule"], u_data["classe"])
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


# ── Dashboard ─────────────────────────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    bd, utilisateurs, salles, reservations = get_data()
    aujourd_hui   = date.today()
    confirmees    = [r for r in reservations if r.statut == StatutReservation.CONFIRMEE]
    res_ce_jour   = [r for r in confirmees if r.date == aujourd_hui]
    recentes      = sorted(reservations, key=lambda r: r.date_creation, reverse=True)[:5]
    return render_template(
        "dashboard.html", active="dashboard",
        nb_salles=len(salles),
        nb_utilisateurs=len(utilisateurs),
        nb_confirmees=len(confirmees),
        nb_ce_jour=len(res_ce_jour),
        reservations_recentes=recentes,
    )


# ── Salles ────────────────────────────────────────────────────────────────────────

@app.route("/salles")
@login_required
def salles():
    _, _, salles_dict, _ = get_data()
    return render_template("salles.html", active="salles",
                           salles=list(salles_dict.values()))


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
    _, _, salles_dict, toutes = get_data()
    filtre_date    = request.args.get("date", "")
    filtre_salle   = request.args.get("salle_id", "")
    filtre_classe  = request.args.get("classe", "").strip()
    filtre_places  = request.args.get("places_min", "").strip()

    resultats = list(toutes)
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
    )


@app.route("/reservations/ajouter", methods=["GET", "POST"])
@login_required
def reservation_ajouter():
    if not peut_gerer_reservations():
        flash("Accès réservé aux responsables et administrateurs.", "error")
        return redirect(url_for("reservations"))

    bd, utilisateurs, salles_dict, reservations_existantes = get_data()

    if request.method == "POST":
        salle_id  = request.form.get("salle_id", "")
        classe    = request.form.get("classe", "").strip()
        date_str  = request.form.get("date", "").strip()
        debut_str = request.form.get("heure_debut", "").strip()
        fin_str   = request.form.get("heure_fin", "").strip()
        matiere   = request.form.get("matiere", "").strip()

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
                bd.sauvegarder_reservation(r)
                _notifier(r, utilisateurs, annulation=False)
                flash(f"Réservation créée — {salle.nom} le {date_str}.", "success")
                return redirect(url_for("reservations"))
            except (ValueError, PermissionError) as e:
                flash(str(e), "error")

    return render_template(
        "reservation_form.html", active="reservations",
        salles=list(salles_dict.values()),
        today=date.today().isoformat(),
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


# ── Utilisateurs (admin) ──────────────────────────────────────────────────────────

@app.route("/utilisateurs")
@login_required
@admin_required
def utilisateurs():
    _, utilisateurs_dict, _, _ = get_data()
    return render_template("utilisateurs.html", active="utilisateurs",
                           utilisateurs=list(utilisateurs_dict.values()))


@app.route("/utilisateurs/inscrire", methods=["GET", "POST"])
@login_required
@admin_required
def utilisateurs_inscrire():
    if request.method == "POST":
        nom       = request.form.get("nom", "").strip()
        email     = request.form.get("email", "").strip()
        login_val = request.form.get("login", "").strip()
        mdp       = request.form.get("mot_de_passe", "").strip()
        role      = request.form.get("role", "etudiant")
        classe    = request.form.get("classe", "").strip()
        matiere   = request.form.get("matiere", "").strip()
        matricule = request.form.get("matricule", "").strip()

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
        matiere = request.form.get("matiere", "").strip()

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
        if matiere and hasattr(u, "matiere"):
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

    cfg = bd.charger_config()
    return render_template("parametres.html", active="parametres", cfg=cfg)


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
        notif.envoyer_email(
            dest,
            "Test SMTP — Réservation de salles",
            "Bonjour,\n\nCeci est un email de test envoyé depuis le système de réservation de salles.\n\nConfiguration SMTP opérationnelle.\n\nCordialement,\nSystème de réservation universitaire",
        )
        flash(f"Email de test envoyé avec succès à {dest}.", "success")
    except Exception as e:
        flash(f"Échec de l'envoi : {e}", "error")

    return redirect(url_for("parametres"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
