"""
Exceptions metier du systeme de reservation de salles.
"""


class ErreurSysteme(Exception):
    """Exception racine du systeme — toutes les exceptions heritent d'elle."""


class UtilisateurIntrouvable(ErreurSysteme):
    """Aucun utilisateur ne correspond aux criteres fournis."""


class SalleIntrouvable(ErreurSysteme):
    """Aucune salle ne correspond aux criteres fournis."""


class ReservationIntrouvable(ErreurSysteme):
    """Aucune reservation ne correspond aux criteres fournis."""


class ConflitReservation(ErreurSysteme):
    """Un creneau est deja occupe par une reservation existante."""


class AccesRefuse(ErreurSysteme):
    """L'utilisateur ne dispose pas des droits necessaires pour cette action."""


class DonneesInvalides(ErreurSysteme):
    """Les donnees fournies ne respectent pas les contraintes metier."""


class ErreurPersistance(ErreurSysteme):
    """Erreur lors de la lecture ou de l'ecriture des donnees persistantes."""
