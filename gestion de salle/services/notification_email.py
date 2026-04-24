import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from models.reservation import Reservation
from models.utilisateur import Enseignant, Etudiant


class NotificationEmail:

    def __init__(self, smtp_host: str, smtp_port: int,
                 expediteur: str, mot_de_passe: str):
        self.__smtp_host: str = smtp_host
        self.__smtp_port: int = smtp_port
        self.__expediteur: str = expediteur
        self.__mot_de_passe: str = mot_de_passe

    # ── Envoi générique ───────────────────────────────────────────────────────

    def envoyer_email(self, destinataire: str, sujet: str, corps: str):
        """
        Envoie un email via SMTP (TLS).
        Lève une exception en cas d'échec réseau.
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = sujet
        msg["From"]    = self.__expediteur
        msg["To"]      = destinataire
        msg.attach(MIMEText(corps, "plain", "utf-8"))

        with smtplib.SMTP(self.__smtp_host, self.__smtp_port) as serveur:
            serveur.ehlo()
            serveur.starttls()
            serveur.login(self.__expediteur, self.__mot_de_passe)
            serveur.sendmail(self.__expediteur, destinataire, msg.as_string())

    # ── Templates de messages ─────────────────────────────────────────────────

    @staticmethod
    def _corps_confirmation(reservation: Reservation) -> str:
        r = reservation
        return (
            f"Bonjour,\n\n"
            f"Une réservation a été confirmée :\n\n"
            f"  Matière     : {r.matiere or 'N/A'}\n"
            f"  Salle       : {r.salle.nom} (capacité : {r.salle.capacite} places)\n"
            f"  Classe      : {r.classe}\n"
            f"  Date        : {r.date.strftime('%d/%m/%Y')}\n"
            f"  Horaire     : {r.heure_debut.strftime('%H:%M')} — "
            f"{r.heure_fin.strftime('%H:%M')}\n"
            f"  Responsable : {r.responsable.nom}\n\n"
            f"Cordialement,\nSystème de réservation universitaire"
        )

    @staticmethod
    def _corps_annulation(reservation: Reservation) -> str:
        r = reservation
        return (
            f"Bonjour,\n\n"
            f"La réservation suivante a été annulée :\n\n"
            f"  Salle  : {r.salle.nom}\n"
            f"  Classe : {r.classe}\n"
            f"  Date   : {r.date.strftime('%d/%m/%Y')}\n"
            f"  Heure  : {r.heure_debut.strftime('%H:%M')} — "
            f"{r.heure_fin.strftime('%H:%M')}\n\n"
            f"Cordialement,\nSystème de réservation universitaire"
        )

    # ── Notifications ciblées ─────────────────────────────────────────────────

    def envoyer_responsable(self, reservation: Reservation, annulation: bool = False):
        """Notifie le responsable de la réservation."""
        sujet = (
            "❌ Annulation de réservation" if annulation
            else "✅ Confirmation de réservation"
        )
        corps = (
            self._corps_annulation(reservation) if annulation
            else self._corps_confirmation(reservation)
        )
        self.envoyer_email(reservation.responsable.email, sujet, corps)

    def envoyer_enseignant(self, reservation: Reservation,
                           enseignant: Enseignant, annulation: bool = False):
        """Notifie l'enseignant concerné par la réservation."""
        sujet = (
            f"❌ Annulation — {reservation.salle.nom}" if annulation
            else f"📅 Réservation — {reservation.salle.nom}"
        )
        corps = (
            self._corps_annulation(reservation) if annulation
            else self._corps_confirmation(reservation)
        )
        self.envoyer_email(enseignant.email, sujet, corps)

    def envoyer_etudiants(self, reservation: Reservation,
                          etudiants: list[Etudiant], annulation: bool = False):
        """Notifie chaque étudiant de la classe."""
        sujet = (
            f"❌ Annulation cours — {reservation.classe}" if annulation
            else f"📅 Cours planifié — {reservation.classe}"
        )
        corps = (
            self._corps_annulation(reservation) if annulation
            else self._corps_confirmation(reservation)
        )
        for etudiant in etudiants:
            self.envoyer_email(etudiant.email, sujet, corps)

    def notifier_tous(self, reservation: Reservation,
                      enseignant: Enseignant,
                      etudiants: list[Etudiant],
                      annulation: bool = False):
        """
        Envoie les notifications à toutes les parties concernées :
        responsable, enseignant et étudiants.
        """
        self.envoyer_responsable(reservation, annulation)
        self.envoyer_enseignant(reservation, enseignant, annulation)
        self.envoyer_etudiants(reservation, etudiants, annulation)

    def __repr__(self) -> str:
        return (
            f"<NotificationEmail host='{self.__smtp_host}' "
            f"port={self.__smtp_port} from='{self.__expediteur}'>"
        )
