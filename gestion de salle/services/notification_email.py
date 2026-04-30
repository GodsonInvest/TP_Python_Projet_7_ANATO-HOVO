import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from models.reservation import Reservation
from models.utilisateur import Enseignant


# ── Templates HTML ─────────────────────────────────────────────────────────────

_HEADER = """
<tr>
  <td style="background:linear-gradient(135deg,#0f172a 0%,#1e1b4b 60%,#312e81 100%);
             padding:32px 40px;border-radius:12px 12px 0 0;text-align:center;">
    <div style="display:inline-flex;align-items:center;gap:10px;">
      <div style="width:36px;height:36px;background:#4f46e5;border-radius:8px;
                  display:inline-flex;align-items:center;justify-content:center;">
        <span style="color:#fff;font-size:18px;font-weight:900;line-height:1;">U</span>
      </div>
      <span style="color:#fff;font-size:20px;font-weight:700;letter-spacing:-0.5px;">UniRéserv</span>
    </div>
  </td>
</tr>
"""

_FOOTER = """
<tr>
  <td style="background:#f8fafc;padding:24px 40px;border-top:1px solid #e2e8f0;
             border-radius:0 0 12px 12px;text-align:center;">
    <p style="margin:0;color:#94a3b8;font-size:12px;line-height:1.6;">
      Système de réservation de salles universitaire · UniRéserv<br/>
      <span style="color:#cbd5e1;">Cet email est généré automatiquement, merci de ne pas y répondre.</span>
    </p>
  </td>
</tr>
"""

_WRAP_START = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width"/></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 20px;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0"
           style="background:#fff;border-radius:12px;border:1px solid #e2e8f0;
                  box-shadow:0 4px 24px rgba(0,0,0,.07);overflow:hidden;">
"""

_WRAP_END = """    </table>
  </td></tr>
</table>
</body></html>"""


def _badge(texte, bg, couleur):
    return (
        f'<span style="display:inline-block;padding:4px 14px;border-radius:999px;'
        f'background:{bg};color:{couleur};font-size:12px;font-weight:700;">{texte}</span>'
    )


def _info_row(label, valeur):
    return f"""
      <tr>
        <td style="padding:10px 0;border-bottom:1px solid #f1f5f9;
                   color:#64748b;font-size:13px;width:40%;vertical-align:top;">{label}</td>
        <td style="padding:10px 0;border-bottom:1px solid #f1f5f9;
                   color:#1e293b;font-size:13px;font-weight:600;">{valeur}</td>
      </tr>"""


def _html_otp(otp: str, nom: str = "") -> str:
    salut = f"Bonjour{' ' + nom if nom else ''},"
    return _WRAP_START + _HEADER + f"""
      <tr>
        <td style="padding:40px 40px 16px;">
          <p style="margin:0 0 8px;color:#1e293b;font-size:22px;font-weight:700;">{salut}</p>
          <p style="margin:0;color:#64748b;font-size:15px;line-height:1.6;">
            Voici votre code de vérification pour finaliser votre inscription sur <strong>UniRéserv</strong>.
          </p>
        </td>
      </tr>
      <tr>
        <td style="padding:24px 40px;">
          <div style="background:#f0f4ff;border:2px dashed #c7d2fe;border-radius:12px;
                      padding:28px;text-align:center;">
            <p style="margin:0 0 6px;color:#6366f1;font-size:12px;font-weight:600;
                      letter-spacing:2px;text-transform:uppercase;">Code de vérification</p>
            <p style="margin:0;font-size:48px;font-weight:800;letter-spacing:12px;
                      color:#3730a3;font-family:'Courier New',monospace;">{otp}</p>
          </div>
          <div style="margin-top:20px;background:#fef9c3;border-left:4px solid #eab308;
                      border-radius:6px;padding:12px 16px;">
            <p style="margin:0;color:#854d0e;font-size:13px;line-height:1.6;">
              ⏱ Ce code expire dans <strong>5 minutes</strong>.<br/>
              Si vous n'avez pas demandé ce code, ignorez cet email.
            </p>
          </div>
        </td>
      </tr>
""" + _FOOTER + _WRAP_END


def _html_reset_otp(otp: str, nom: str = "") -> str:
    salut = f"Bonjour{' ' + nom if nom else ''},"
    return _WRAP_START + _HEADER + f"""
      <tr>
        <td style="padding:40px 40px 16px;">
          <p style="margin:0 0 8px;color:#1e293b;font-size:22px;font-weight:700;">{salut}</p>
          <p style="margin:0;color:#64748b;font-size:15px;line-height:1.6;">
            Vous avez demandé la réinitialisation de votre mot de passe sur <strong>UniRéserv</strong>.<br/>
            Utilisez le code ci-dessous pour créer un nouveau mot de passe.
          </p>
        </td>
      </tr>
      <tr>
        <td style="padding:24px 40px;">
          <div style="background:#fff7ed;border:2px dashed #fed7aa;border-radius:12px;
                      padding:28px;text-align:center;">
            <p style="margin:0 0 6px;color:#ea580c;font-size:12px;font-weight:600;
                      letter-spacing:2px;text-transform:uppercase;">Code de réinitialisation</p>
            <p style="margin:0;font-size:48px;font-weight:800;letter-spacing:12px;
                      color:#c2410c;font-family:'Courier New',monospace;">{otp}</p>
          </div>
          <div style="margin-top:20px;background:#fef9c3;border-left:4px solid #eab308;
                      border-radius:6px;padding:12px 16px;">
            <p style="margin:0;color:#854d0e;font-size:13px;line-height:1.6;">
              ⏱ Ce code expire dans <strong>10 minutes</strong>.<br/>
              Si vous n'avez pas demandé cette réinitialisation, ignorez cet email.
            </p>
          </div>
        </td>
      </tr>
""" + _FOOTER + _WRAP_END


def _html_reservation(reservation: Reservation, annulation: bool = False) -> str:
    r = reservation
    if annulation:
        titre    = "Réservation annulée"
        sous_titre = "La réservation suivante a été annulée."
        badge    = _badge("❌ Annulée", "#fee2e2", "#b91c1c")
        couleur_barre = "#ef4444"
    else:
        titre    = "Réservation confirmée"
        sous_titre = "Une salle a été réservée pour votre classe."
        badge    = _badge("✅ Confirmée", "#dcfce7", "#15803d")
        couleur_barre = "#22c55e"

    rows = (
        _info_row("Salle", f"{r.salle.nom} <span style='color:#94a3b8;font-weight:400;'>(capacité : {r.salle.capacite} places)</span>")
        + _info_row("Classe", r.classe)
        + _info_row("Date", r.date.strftime("%A %d %B %Y").capitalize())
        + _info_row("Horaire", f"{r.heure_debut.strftime('%H:%M')} → {r.heure_fin.strftime('%H:%M')} <span style='color:#94a3b8;font-weight:400;'>({r.duree_minutes()} min)</span>")
        + (_info_row("Matière", r.matiere) if r.matiere else "")
        + _info_row("Responsable", r.responsable.nom)
    )

    return _WRAP_START + _HEADER + f"""
      <tr>
        <td>
          <div style="height:4px;background:{couleur_barre};"></div>
        </td>
      </tr>
      <tr>
        <td style="padding:36px 40px 20px;">
          <div style="margin-bottom:12px;">{badge}</div>
          <p style="margin:8px 0 4px;color:#1e293b;font-size:22px;font-weight:700;">{titre}</p>
          <p style="margin:0;color:#64748b;font-size:14px;">{sous_titre}</p>
        </td>
      </tr>
      <tr>
        <td style="padding:0 40px 36px;">
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;">
            <tr>
              <td style="padding:0 20px;">
                <table width="100%" cellpadding="0" cellspacing="0">
                  {rows}
                </table>
              </td>
            </tr>
          </table>
        </td>
      </tr>
""" + _FOOTER + _WRAP_END


def _html_test() -> str:
    return _WRAP_START + _HEADER + """
      <tr>
        <td style="padding:40px 40px 20px;text-align:center;">
          <div style="width:64px;height:64px;background:#dcfce7;border-radius:16px;
                      margin:0 auto 16px;display:flex;align-items:center;justify-content:center;">
            <span style="font-size:32px;">✅</span>
          </div>
          <p style="margin:0 0 8px;color:#1e293b;font-size:22px;font-weight:700;">Configuration SMTP opérationnelle</p>
          <p style="margin:0;color:#64748b;font-size:14px;line-height:1.6;">
            Cet email confirme que votre configuration SMTP fonctionne correctement.<br/>
            Les notifications de réservation seront bien envoyées.
          </p>
        </td>
      </tr>
      <tr>
        <td style="padding:0 40px 40px;">
          <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;
                      padding:20px;text-align:center;">
            <p style="margin:0;color:#94a3b8;font-size:13px;">
              Envoyé depuis le panneau d'administration <strong style="color:#6366f1;">UniRéserv</strong>
            </p>
          </div>
        </td>
      </tr>
""" + _FOOTER + _WRAP_END


# ── Classe principale ──────────────────────────────────────────────────────────

class NotificationEmail:

    def __init__(self, smtp_host: str, smtp_port: int,
                 expediteur: str, mot_de_passe: str, nom_affichage: str = "UniRéserv"):
        self.__smtp_host       = smtp_host
        self.__smtp_port       = smtp_port
        self.__expediteur      = expediteur
        self.__mot_de_passe    = mot_de_passe
        self.__nom_affichage   = nom_affichage

    def envoyer_email(self, destinataire: str, sujet: str, html: str, texte: str = ""):
        msg = MIMEMultipart("alternative")
        msg["Subject"] = sujet
        msg["From"]    = f"{self.__nom_affichage} <{self.__expediteur}>"
        msg["To"]      = destinataire

        if texte:
            msg.attach(MIMEText(texte, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(self.__smtp_host, self.__smtp_port) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(self.__expediteur, self.__mot_de_passe)
            srv.sendmail(self.__expediteur, destinataire, msg.as_string())

    # ── Notifications ciblées ──────────────────────────────────────────────────

    def envoyer_responsable(self, reservation: Reservation, annulation: bool = False):
        sujet = "❌ Annulation de réservation" if annulation else "✅ Réservation confirmée — " + reservation.salle.nom
        self.envoyer_email(
            reservation.responsable.email, sujet,
            _html_reservation(reservation, annulation),
        )

    def envoyer_enseignant(self, reservation: Reservation,
                           enseignant: Enseignant, annulation: bool = False):
        sujet = f"❌ Annulation — {reservation.salle.nom}" if annulation else f"📅 Cours planifié — {reservation.salle.nom}"
        self.envoyer_email(
            enseignant.email, sujet,
            _html_reservation(reservation, annulation),
        )

    def envoyer_classe(self, reservation: Reservation,
                       etudiants: list, annulation: bool = False):
        sujet = f"❌ Cours annulé — {reservation.classe}" if annulation else f"📅 Nouveau cours — {reservation.classe}"
        html  = _html_reservation(reservation, annulation)
        for etudiant in etudiants:
            self.envoyer_email(etudiant.email, sujet, html)

    def envoyer_otp(self, destinataire: str, otp: str, nom: str = ""):
        self.envoyer_email(
            destinataire,
            "🔐 Code de vérification — UniRéserv",
            _html_otp(otp, nom),
        )

    def envoyer_otp_reset(self, destinataire: str, otp: str, nom: str = ""):
        self.envoyer_email(
            destinataire,
            "🔑 Réinitialisation de mot de passe — UniRéserv",
            _html_reset_otp(otp, nom),
        )

    def envoyer_test(self, destinataire: str):
        self.envoyer_email(
            destinataire,
            "✅ Test SMTP — UniRéserv",
            _html_test(),
        )

    def notifier_tous(self, reservation: Reservation,
                      enseignant, etudiants: list, annulation: bool = False):
        self.envoyer_responsable(reservation, annulation)
        if enseignant:
            self.envoyer_enseignant(reservation, enseignant, annulation)
        if etudiants:
            self.envoyer_classe(reservation, etudiants, annulation)

    def __repr__(self):
        return f"<NotificationEmail host='{self.__smtp_host}' port={self.__smtp_port} from='{self.__expediteur}'>"
