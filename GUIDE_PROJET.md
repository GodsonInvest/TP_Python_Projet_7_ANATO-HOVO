# GUIDE COMPLET DU PROJET — UniRéserv
**Auteur : ANATO Amen Godson Cossi / HOVO**

---

## TABLE DES MATIÈRES

1. [Architecture du projet](#1-architecture-du-projet)
2. [Explication fichier par fichier](#2-explication-fichier-par-fichier)
3. [50 Questions d'examen avec réponses](#3-50-questions-dexamen-avec-réponses)
4. [Glossaire des 40 termes clés](#4-glossaire-des-40-termes-clés)
5. [5 Scénarios de démonstration](#5-5-scénarios-de-démonstration)

---

# 1. ARCHITECTURE DU PROJET

```
TP_Python_Projet_7_ANATO&HOVO/
│
├── GUIDE_PROJET.md              ← Ce document
├── README.md                    ← Documentation générale du projet
├── render.yaml                  ← Configuration de déploiement (Render.com)
│
└── gestion de salle/            ← Dossier principal de l'application
    │
    ├── app.py                   ← Application Flask : toutes les routes HTTP (point d'entrée web)
    ├── main.py                  ← Script de démonstration en console (POO + persistance)
    ├── wsgi.py                  ← Point d'entrée WSGI pour déploiement en production
    │
    ├── models/                  ← Modèles métier (les "entités" du système)
    │   ├── utilisateur.py       ← Hiérarchie des utilisateurs (ABC → Etudiant, Enseignant, Responsable, Admin)
    │   ├── salle.py             ← Modèle Salle avec équipements
    │   ├── reservation.py       ← Modèle Reservation + StatutReservation (Enum) + détection chevauchement
    │   └── etablissement.py     ← Modèles Ecole et UniteFormation (filières)
    │
    ├── services/                ← Logique métier (traitement des opérations)
    │   ├── authentification.py  ← Hachage SHA-256, login/logout, vérification de rôle
    │   ├── gestion_utilisateurs.py ← Inscription, promotion Responsable, révocation
    │   ├── gestion_salles.py    ← CRUD salles, filtrage par disponibilité/capacité
    │   ├── gestion_reservation.py  ← Réservations ponctuelles + génération récurrente (cours)
    │   ├── gestion_cours.py     ← Cours multi-jours liés à une filière
    │   ├── gestion_composition.py  ← Compositions (examens) avec règle "sur cours existant"
    │   ├── gestion_evenement.py ← Événements avec workflow de validation + public cible
    │   └── notification_email.py   ← Envoi d'emails HTML via SMTP (OTP, réservation, cours, etc.)
    │
    ├── persistance/             ← Couche de persistance des données
    │   ├── db_sqlite.py         ← Base SQLite : 10 tables, migration automatique, CRUD complet
    │   └── db_json.py           ← Base JSON alternative (3 fichiers dans data/)
    │
    ├── exceptions/              ← Hiérarchie d'exceptions personnalisées
    │   └── exceptions.py        ← ErreurSysteme → ErreurAuthentification, ErreurReservation, etc.
    │
    ├── data/                    ← Données persistées (ignoré par git)
    │   └── reservation_salles.db  ← Fichier SQLite (créé automatiquement au démarrage)
    │
    ├── tests/                   ← Suite de tests pytest (Bloc 5)
    │   ├── conftest.py          ← Fixtures partagées (salle_a, responsable, gestionnaire…)
    │   ├── test_utilisateur.py  ← Tests modèles utilisateurs (ABC, propriétés, rôles)
    │   ├── test_authentification.py ← Tests hachage, login, logout, rôles
    │   ├── test_gestion_reservation.py ← Tests réservations, conflits, rollback, planning
    │   └── test_persistance.py  ← Tests sauvegarder/charger SQLite et JSON
    │
    ├── static/                  ← Fichiers statiques CSS/JS
    │   └── css/
    │       └── style.css        ← Styles globaux (complète Tailwind CSS)
    │
    └── templates/               ← Templates Jinja2 HTML (31 fichiers)
        ├── base.html            ← Template parent : navigation, flash messages, layout
        ├── login.html           ← Formulaire de connexion
        ├── inscription.html     ← Formulaire d'inscription avec cascade école→filière
        ├── otp_verification.html ← Vérification du code OTP à 6 chiffres
        ├── mot_de_passe_oublie.html ← Demande de réinitialisation
        ├── reset_mot_de_passe.html  ← Formulaire nouveau mot de passe
        ├── dashboard.html       ← Tableau de bord selon le rôle
        ├── profil.html          ← Page profil utilisateur
        ├── parametres.html      ← Configuration SMTP (admin)
        ├── planning.html        ← Planning hebdomadaire unifié (réservations, cours, compositions, événements)
        ├── salles.html          ← Liste des salles avec filtres
        ├── salle_form.html      ← Formulaire ajout/modification de salle
        ├── reservations.html    ← Liste des réservations
        ├── reservation_form.html ← Formulaire de réservation
        ├── reservation_detail.html ← Détail d'une réservation
        ├── cours_liste.html     ← Liste des cours planifiés
        ├── cours_form.html      ← Formulaire cours multi-jours
        ├── cours_detail.html    ← Détail d'un cours
        ├── compositions.html    ← Liste des compositions
        ├── composition_form.html ← Formulaire composition
        ├── evenements.html      ← Liste des événements avec workflow validation
        ├── evenement_form.html  ← Formulaire événement + public cible multi-sélection
        ├── utilisateurs.html    ← Liste utilisateurs (admin)
        ├── utilisateur_form.html ← Formulaire ajout/modification utilisateur
        ├── ecoles.html          ← Liste des écoles et facultés
        ├── ecole_form.html      ← Formulaire école
        ├── filieres.html        ← Liste des filières par école
        ├── filiere_form.html    ← Formulaire filière
        ├── 404.html             ← Page d'erreur 404
        └── 500.html             ← Page d'erreur 500
```

---

# 2. EXPLICATION FICHIER PAR FICHIER

---

## 2.1 `models/utilisateur.py` — Hiérarchie des utilisateurs

### Concept central : Classe Abstraite (ABC)

```python
from abc import ABC, abstractmethod

class Utilisateur(ABC):
    def __init__(self, nom, email, login, mot_de_passe):
        self.__id               = None
        self.__nom              = nom.strip()
        self.__email            = email.strip()
        self.__login            = login.strip()
        self.__mot_de_passe     = mot_de_passe
        self.__date_inscription = datetime.now()

    @property
    @abstractmethod
    def role(self) -> str: ...
```

**Ce que fait chaque ligne :**

- `ABC` = Abstract Base Class. On importe ça depuis le module `abc` de Python. Cela rend la classe **abstraite** : on ne peut pas faire `Utilisateur("Alice", ...)` directement — Python lèvera une `TypeError`.
- `@abstractmethod` = décorateur qui force chaque sous-classe à implémenter la méthode `role`. Si une sous-classe oublie, Python refuse de l'instancier.
- `self.__id` (double underscore) = **name mangling**. Python transforme `__id` en `_Utilisateur__id` en interne. Résultat : aucune sous-classe ne peut accéder à `self.__id` directement. C'est de l'**encapsulation forte**.

### Propriétés avec `@property`

```python
@property
def id(self):
    return self.__id

@id.setter
def id(self, valeur):
    if self.__id is None:       # on ne peut définir l'id qu'une seule fois
        self.__id = valeur
```

**Pourquoi cette règle ?** L'id est assigné par la base de données. Une fois donné, on ne doit plus pouvoir le changer accidentellement depuis le code. Le setter vérifie `if self.__id is None` avant d'accepter la valeur.

### Validation dans le setter email

```python
@email.setter
def email(self, valeur):
    if "@" not in valeur:
        raise ValueError(f"Email invalide : {valeur}")
    self.__email = valeur.strip()
```

Un setter peut contenir de la logique de validation. Si l'email ne contient pas `@`, on lève une `ValueError` immédiatement.

### Les 4 sous-classes

```python
class Etudiant(Utilisateur):
    role = "etudiant"           # constante de classe (pas besoin d'@abstractmethod)

    def __init__(self, nom, email, login, mdp, matricule, classe,
                 ecole_id=None, unite_formation_id=None):
        super().__init__(nom, email, login, mdp)
        self.__matricule          = matricule
        self.__classe             = classe
        self.__ecole_id           = ecole_id
        self.__unite_formation_id = unite_formation_id
```

- `super().__init__(...)` = appelle le constructeur de la classe parente `Utilisateur` pour initialiser les attributs communs (nom, email, etc.)
- `ecole_id` et `unite_formation_id` permettent de savoir à quelle école/filière appartient l'étudiant pour les notifications ciblées.

```python
class Enseignant(Utilisateur):
    role = "enseignant"

    @property
    def matieres(self) -> list[str]:
        return [m.strip() for m in self.__matiere.split(",") if m.strip()]
```

Un enseignant peut avoir plusieurs matières séparées par des virgules : `"Algo, Maths, Python"`. La propriété `matieres` retourne une **liste** en découpant avec `split(",")` et en nettoyant avec `strip()`.

```python
class Administrateur(Utilisateur):
    role = "admin"

    def attribuer_role_responsable(self, utilisateur, classe):
        return Responsable(utilisateur.nom, utilisateur.email,
                           utilisateur.login, utilisateur.mot_de_passe, classe)

    def revoquer_role_responsable(self, responsable, nouveau_role):
        if nouveau_role == "etudiant":
            return Etudiant(responsable.nom, ...)
        elif nouveau_role == "enseignant":
            return Enseignant(responsable.nom, ...)
        else:
            raise ValueError(f"Rôle inconnu : {nouveau_role}")
```

L'admin peut **changer le rôle** d'un utilisateur. En Python, on crée un nouvel objet du bon type — on ne peut pas changer la classe d'un objet existant.

---

## 2.2 `models/salle.py` — La salle de classe

```python
class Salle:
    def __init__(self, nom: str, capacite: int, equipements: list = None):
        self.__nom         = nom.strip()
        self.__capacite    = capacite
        self.__equipements = equipements or []
        self.__disponible  = True
        self.__id          = None
```

- `equipements: list = None` + `equipements or []` = valeur par défaut mutable. En Python, mettre `[]` comme valeur par défaut de paramètre est un **piège classique** (la liste est partagée entre tous les appels). On met `None` et on initialise ensuite avec `or []`.

```python
    def to_dict(self) -> dict:
        return {
            "id":          self.__id,
            "nom":         self.__nom,
            "capacite":    self.__capacite,
            "equipements": self.__equipements,
            "disponible":  self.__disponible,
        }
```

`to_dict()` est un pattern de **sérialisation** : convertir un objet Python en dictionnaire pour pouvoir le stocker en JSON ou SQLite.

---

## 2.3 `models/reservation.py` — La réservation et la détection de conflit

### L'Énumération (Enum)

```python
from enum import Enum

class StatutReservation(Enum):
    EN_ATTENTE = "en_attente"
    CONFIRMEE  = "confirmee"
    ANNULEE    = "annulee"
    TERMINEE   = "terminee"
```

Un `Enum` définit un ensemble de **valeurs constantes nommées**. Avantage : impossible d'écrire `r.statut = "confirmé"` (avec accent) par erreur — on utilise toujours `StatutReservation.CONFIRMEE`.

### Variable de classe et compteur automatique d'ID

```python
class Reservation:
    _compteur = 0               # variable de CLASSE, partagée par toutes les instances

    def __init__(self, salle, responsable, classe, date_reservation, heure_debut, heure_fin, matiere="", ...):
        if heure_debut >= heure_fin:
            raise ValueError("L'heure de début doit être avant l'heure de fin.")
        Reservation._compteur += 1
        self.__id              = Reservation._compteur
        ...
        self.__statut          = StatutReservation.EN_ATTENTE
```

- `_compteur` (underscore simple) = convention Python pour "semi-privé". Ce n'est pas du name-mangling, mais ça signale "n'utilise pas directement".
- Chaque nouvelle réservation incrémente le compteur de classe → ID unique automatique.
- La validation `if heure_debut >= heure_fin` est dans le constructeur pour garantir qu'un objet Reservation invalide ne peut pas exister.

### L'algorithme de chevauchement

```python
def chevauche(self, autre: "Reservation") -> bool:
    if self.__salle.id != autre.__salle.id:   # pas la même salle
        return False
    if self.__date != autre.__date:           # pas le même jour
        return False
    # chevauchement temporel : début1 < fin2 ET fin1 > début2
    return self.__heure_debut < autre.__heure_fin and self.__heure_fin > autre.__heure_debut
```

**L'algorithme de base des intervalles :** deux intervalles [A, B] et [C, D] se chevauchent si et seulement si `A < D ET B > C`. C'est la condition **inverse** de "pas de chevauchement" (B ≤ C OU A ≥ D). Cas concret :
- Réservation 1 : 08h00–10h00
- Réservation 2 : 09h00–11h00
- `08:00 < 11:00` ✓ ET `10:00 > 09:00` ✓ → chevauchement détecté

---

## 2.4 `models/etablissement.py` — Écoles et filières

```python
class UniteFormation:
    NIVEAUX = ['L1', 'L2', 'L3', 'M1', 'M2']   # constante de classe

    def __init__(self, nom: str, niveau: str, ecole_id: int, abreviation: str = ""):
        if niveau not in self.NIVEAUX:
            raise ValueError(f"Niveau invalide : {niveau}. Attendu : {self.NIVEAUX}")
        ...
```

`NIVEAUX` est une constante de classe en **MAJUSCULES** (convention Python pour les constantes). La validation dans `__init__` garantit qu'on ne peut pas créer une `UniteFormation` avec un niveau `"Bac+5"` par exemple.

---

## 2.5 `exceptions/exceptions.py` — Exceptions personnalisées

```python
class ErreurSysteme(Exception):
    """Exception de base du système."""
    pass

class ErreurAuthentification(ErreurSysteme):
    pass

class ErreurReservation(ErreurSysteme):
    pass

class ErreurSalle(ErreurSysteme):
    pass
```

**Hiérarchie d'exceptions :** On hérite d'`Exception` (classe de base Python). L'avantage d'avoir `ErreurSysteme` comme racine : on peut faire `except ErreurSysteme` pour attraper toutes les erreurs de l'application, ou `except ErreurAuthentification` pour n'attraper qu'un type précis.

---

## 2.6 `services/authentification.py` — Sécurité des mots de passe

```python
import hashlib
import hmac

class Authentification:
    ROLES_VALIDES = {"admin", "responsable", "enseignant", "etudiant"}

    @staticmethod
    def hacher_mot_de_passe(mot_de_passe: str) -> str:
        return hashlib.sha256(mot_de_passe.encode("utf-8")).hexdigest()

    @staticmethod
    def verifier_hash(mot_de_passe_saisi: str, hash_stocke: str) -> bool:
        hash_saisi = Authentification.hacher_mot_de_passe(mot_de_passe_saisi)
        return hmac.compare_digest(hash_saisi, hash_stocke)
```

**Pourquoi `@staticmethod` ?** Ces méthodes n'utilisent pas `self` ni la classe — elles font un calcul pur. Le `@staticmethod` indique clairement qu'elles n'ont pas besoin d'une instance.

**Pourquoi SHA-256 ?** SHA-256 est une **fonction de hachage cryptographique** : irréversible (on ne peut pas retrouver le mot de passe depuis le hash) et déterministe (même entrée → même sortie). On stocke uniquement le hash dans la base, jamais le mot de passe en clair.

**Pourquoi `hmac.compare_digest` et pas `==` ?** Pour éviter les **attaques temporelles** : la comparaison `==` s'arrête au premier caractère différent → un attaquant pourrait mesurer le temps de réponse pour deviner le hash caractère par caractère. `hmac.compare_digest` compare **toujours les deux chaînes en entier** quel que soit leur contenu.

### Login / Logout

```python
def __init__(self, gestionnaire_utilisateurs):
    self.__gestionnaire      = gestionnaire_utilisateurs
    self.__utilisateur_courant = None
    self.__est_connecte      = False

def login(self, login: str, mot_de_passe: str):
    u = self.__gestionnaire.trouver_par_login(login)
    if u is None:
        raise ValueError(f"Utilisateur introuvable : {login}")
    if not self.verifier_hash(mot_de_passe, u.mot_de_passe):
        raise ValueError("Mot de passe incorrect.")
    self.__utilisateur_courant = u
    self.__est_connecte        = True
    return u

def logout(self):
    self.__utilisateur_courant = None
    self.__est_connecte        = False
```

---

## 2.7 `services/gestion_utilisateurs.py` — Gestion des comptes

```python
class GestionUtilisateurs:
    def __init__(self):
        self.__utilisateurs: dict[int, Utilisateur] = {}

    def inscrire(self, utilisateur: Utilisateur) -> Utilisateur:
        for u in self.__utilisateurs.values():
            if u.login == utilisateur.login:
                raise ValueError(f"Login déjà utilisé : {utilisateur.login}")
        utilisateur.mot_de_passe = Authentification.hacher_mot_de_passe(utilisateur.mot_de_passe)
        ...
```

- `dict[int, Utilisateur]` = annotation de type (type hint). Pas obligatoire en Python, mais aide à comprendre que ce dictionnaire mappe `id → Utilisateur`.
- Le mot de passe est haché **avant** stockage. Règle de sécurité fondamentale.

```python
    def promouvoir_responsable(self, admin, user_id: int, classe: str) -> Responsable:
        if not isinstance(admin, Administrateur):
            raise PermissionError("Seul un administrateur peut promouvoir.")
        ...
```

`isinstance(admin, Administrateur)` vérifie le **type dynamique** de l'objet. C'est le mécanisme de contrôle d'accès en mémoire (pour le mode console).

---

## 2.8 `services/gestion_salles.py` — Gestion des salles

```python
def salles_disponibles(self, capacite_min: int = 0) -> list[Salle]:
    return [
        s for s in self.__salles.values()
        if s.disponible and s.capacite >= capacite_min
    ]
```

**List comprehension avec condition :** `[expression for élément in itérable if condition]`. Équivalent à une boucle `for` avec un `if`, mais en une seule ligne. Plus lisible et plus rapide en Python.

---

## 2.9 `services/gestion_reservation.py` — Réservations et cours récurrents

### Réservation ponctuelle

```python
def ajouter_reservation(self, salle, responsable, classe, date_reservation,
                         heure_debut, heure_fin, matiere="") -> Reservation:
    nouvelle = Reservation(salle=salle, responsable=responsable, classe=classe,
                           date_reservation=date_reservation,
                           heure_debut=heure_debut, heure_fin=heure_fin,
                           matiere=matiere)
    conflit = self.verifier_conflit(nouvelle)
    if conflit:
        raise ValueError(f"Conflit horaire détecté avec la réservation #{conflit.id}...")
    nouvelle.confirmer()
    self.__reservations.append(nouvelle)
    return nouvelle
```

Ordre des opérations : créer l'objet → vérifier les conflits → confirmer → ajouter à la liste. Si un conflit est trouvé, on lève une exception avant de confirmer.

### Génération des occurrences récurrentes pour un cours

```python
JOURS_SEMAINE = {'lundi': 0, 'mardi': 1, 'mercredi': 2, 'jeudi': 3,
                  'vendredi': 4, 'samedi': 5, 'dimanche': 6}

def creer_cours(self, cours_data, salles_dict, responsable, ignorer_conflits=False):
    for config in cours_data['jours']:
        num = JOURS_SEMAINE.get(config['jour'], -1)
        d   = cours_data['date_debut']
        delta = (num - d.weekday()) % 7      # nombre de jours jusqu'au prochain "jour voulu"
        d = d + timedelta(days=delta)
        while d <= cours_data['date_fin']:
            occurrences.append({...})
            d += timedelta(weeks=1)          # semaine suivante
```

**L'algorithme de calendrier :** `(num - d.weekday()) % 7` calcule combien de jours on doit avancer depuis `date_debut` pour atteindre le premier occurrence du jour voulu. Exemple : si `date_debut` est un mercredi (weekday=2) et qu'on veut les lundis (num=0), on fait `(0 - 2) % 7 = 5` → on avance de 5 jours pour atteindre le lundi suivant.

### Rollback en cas de conflit de modification

```python
def modifier_reservation(self, reservation_id, nouvelle_date, nouvel_debut, nouvelle_fin):
    cible = self._trouver_par_id(reservation_id)
    # sauvegarde des valeurs actuelles
    ancienne_date = cible.date
    ancien_debut  = cible.heure_debut
    ancienne_fin  = cible.heure_fin

    cible.modifier_horaires(nouvelle_date, nouvel_debut, nouvelle_fin)   # on applique
    conflit = self.verifier_conflit(cible, exclure_id=reservation_id)     # on vérifie
    if conflit:
        cible.modifier_horaires(ancienne_date, ancien_debut, ancienne_fin)  # on annule !
        raise ValueError(...)
    return cible
```

**Pattern rollback :** sauvegarder l'état avant modification, appliquer, vérifier, annuler si problème. C'est le même principe que les transactions en base de données.

---

## 2.10 `services/gestion_cours.py` — Cours liés aux filières

```python
class GestionCours:
    def __init__(self, bd):
        self.bd = bd          # injection de dépendance : on passe la base de données

    def verifier_conflits(self, data, exclure_cours_id=None) -> list:
        for occ in occurrences:
            c = self.bd.verifier_conflit_planning(
                occ["salle_id"], occ["_date"],
                _str_heure(occ["heure_debut"]), _str_heure(occ["heure_fin"]),
                exclure_cours_id=exclure_cours_id,
            )
```

**Injection de dépendance :** au lieu de créer `BaseDonneesSQLite()` à l'intérieur du service, on le **passe en paramètre**. Avantage : pour les tests, on peut passer une fausse base de données (stub/mock) sans modifier le service.

**Fonctions utilitaires locales :**
```python
def _str_heure(h) -> str:
    return h.strftime("%H:%M") if hasattr(h, "strftime") else str(h)

def _as_date(d) -> date:
    return d if isinstance(d, date) else date.fromisoformat(d)
```

Ces helpers convertissent les heures/dates peu importe leur type d'entrée (objet `time` ou chaîne `"08:00"`).

---

## 2.11 `services/gestion_composition.py` — Examens et compositions

### Règle métier : composition sur cours existant

```python
def _sur_cours_enseignant(self, enseignant_id, enseignant_email_ext, d, heure_debut, heure_fin) -> bool:
    with self.bd._connexion() as conn:
        if enseignant_id:
            row = conn.execute(
                "SELECT 1 FROM cours_jours cj JOIN cours c ON cj.cours_id = c.id "
                "WHERE c.enseignant_id=? AND cj.jour_semaine=? "
                "AND c.date_debut<=? AND c.date_fin>=? "
                "AND cj.heure_debut<? AND cj.heure_fin>?",
                [enseignant_id, jour_sem, d_str, d_str, heure_fin, heure_debut],
            ).fetchone()
    return row is not None
```

Si l'enseignant a déjà un cours dans la même salle au même créneau, la composition peut **réutiliser ce créneau** sans déclencher une erreur de conflit. La colonne `sur_cours_existant` est mise à `1` dans la base pour l'indiquer.

```python
def creer_composition(self, data, notif=None, utilisateurs=None):
    sur_cours = self._sur_cours_enseignant(...)

    if not sur_cours:               # si PAS sur un cours existant...
        conflit = self.bd.verifier_conflit_planning(...)    # ...on vérifie les conflits
        if conflit:
            return {"comp_id": None, "sur_cours_existant": False, "conflit": conflit}
```

---

## 2.12 `services/gestion_evenement.py` — Événements et public cible

### Workflow de validation (admin only)

```python
def creer_evenement(self, data, role_createur, notif=None, utilisateurs=None):
    statut = "valide" if role_createur == "admin" else "en_attente"
    # Un admin crée directement un événement validé
    # Un responsable crée un événement "en attente" de validation
```

**Workflow :**
1. Responsable crée → statut `en_attente`
2. Admin approuve → statut `valide` → notifications envoyées
3. Admin refuse → statut `refuse` + motif enregistré

### Ciblage des notifications (public cible)

```python
def _filtrer_destinataires(self, utilisateurs, evt) -> list:
    cible_type = evt.get("public_cible_type", "universite")

    if cible_type == "universite":
        return list(utilisateurs.values())       # tout le monde

    if cible_type == "ecole":
        raw = evt.get("public_cible_ids") or []
        if isinstance(raw, str):                  # vient de la DB (JSON string)
            raw = _json.loads(raw)
        ecole_ids = set(int(x) for x in raw if x)
        return [u for u in utilisateurs.values()
                if getattr(u, "ecole_id", None) in ecole_ids]

    if cible_type == "filiere":
        cible_id = evt.get("public_cible_id")
        return [u for u in utilisateurs.values()
                if getattr(u, "unite_formation_id", None) == int(cible_id)]
```

**`getattr(u, "ecole_id", None)` :** récupère l'attribut `ecole_id` de l'objet `u`, ou `None` si l'attribut n'existe pas. Pratique car `Enseignant` n'a pas d'`ecole_id`.

**`_json.loads(raw)` :** la colonne `public_cible_ids` est stockée en base comme texte JSON (`"[1, 3, 5]"`). On la parse pour obtenir une vraie liste Python.

---

## 2.13 `services/notification_email.py` — Emails HTML via SMTP

```python
class NotificationEmail:
    def __init__(self, smtp_host, smtp_port, expediteur, mot_de_passe, nom_affichage="UniRéserv"):
        self.__smtp_host    = smtp_host    # ex: "smtp.gmail.com"
        self.__smtp_port    = smtp_port    # ex: 587 (port TLS standard)
        self.__expediteur   = expediteur
        self.__mot_de_passe = mot_de_passe

    def envoyer_email(self, destinataire, sujet, html, texte=""):
        msg = MIMEMultipart("alternative")   # email avec plusieurs parties
        msg["Subject"] = sujet
        msg["From"]    = f"{self.__nom_affichage} <{self.__expediteur}>"
        msg["To"]      = destinataire

        if texte:
            msg.attach(MIMEText(texte, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(self.__smtp_host, self.__smtp_port) as srv:
            srv.ehlo()         # handshake
            srv.starttls()     # activation du chiffrement TLS
            srv.login(self.__expediteur, self.__mot_de_passe)
            srv.sendmail(self.__expediteur, destinataire, msg.as_string())
```

**SMTP avec TLS :** port 587 + `starttls()` = chiffrement STARTTLS. La connexion commence non chiffrée, puis on active le chiffrement. Alternative : port 465 avec SSL directement.

**`MIMEMultipart("alternative")` :** le client email choisit la meilleure version (HTML si supporté, texte brut sinon).

### Code OTP à 6 chiffres

```python
# Dans app.py
def _generer_otp() -> str:
    return f"{random.randint(0, 999999):06d}"
```

`:06d` = format numérique sur 6 chiffres, complété par des zéros si nécessaire (ex: `7` → `"000007"`).

---

## 2.14 `persistance/db_sqlite.py` — La base de données SQLite

### Context manager `@contextmanager`

```python
from contextlib import contextmanager

@contextmanager
def _connexion(self):
    conn = sqlite3.connect(self._chemin_db)
    conn.row_factory = sqlite3.Row    # les lignes deviennent accessibles par nom de colonne
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn          # on "prête" la connexion au code appelant
        conn.commit()       # si tout va bien, on valide
    except Exception:
        conn.rollback()     # si erreur, on annule
        raise
    finally:
        conn.close()        # toujours fermer la connexion
```

**`@contextmanager` :** décorateur qui transforme un générateur en gestionnaire de contexte (utilisable avec `with`). Le `yield` est le point de suspension — le code après le `yield` s'exécute à la sortie du `with`.

**Utilisation :**
```python
with self._connexion() as conn:
    conn.execute("SELECT * FROM utilisateurs")
# commit automatique ou rollback si exception
```

### Migration automatique des colonnes

```python
def _migrer_tables(self):
    migrations = [
        ("evenements", "public_cible_type", "TEXT NOT NULL DEFAULT 'universite'"),
        ("evenements", "public_cible_id",   "INTEGER"),
        ("evenements", "public_cible_ids",  "TEXT NOT NULL DEFAULT '[]'"),
    ]
    with self._connexion() as conn:
        for table, col, typ in migrations:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError:
                pass    # la colonne existe déjà → on ignore l'erreur
```

**Pourquoi le `try/except` ?** SQLite lève une `OperationalError` si on essaie d'ajouter une colonne qui existe déjà. On l'attrape et on l'ignore — ce n'est pas une vraie erreur, c'est juste que la migration a déjà été faite.

### Upsert (INSERT ou UPDATE)

```python
try:
    conn.execute("INSERT INTO utilisateurs (id, nom, ...) VALUES (?,?,?)", (...))
except sqlite3.IntegrityError:
    conn.execute("UPDATE utilisateurs SET nom=?, ... WHERE id=?", (...))
```

**Upsert = INSERT si nouveau, UPDATE si existe.** La `IntegrityError` est levée quand on essaie d'insérer un enregistrement avec un `id` qui existe déjà (violation de clé primaire).

### `conn.row_factory = sqlite3.Row`

Sans ceci, SQLite retourne des tuples : `row[0]`, `row[1]`... Avec `sqlite3.Row`, on accède par nom : `row["nom"]`, `row["email"]`. Beaucoup plus lisible.

### Vérification de conflit planning (SQL croisé)

```python
def verifier_conflit_planning(self, salle_id, d, heure_debut, heure_fin, ...):
    # Vérifie dans 3 tables : cours_jours, compositions, evenements
    sql = (
        "SELECT c.id, c.matiere, cj.heure_debut, cj.heure_fin "
        "FROM cours_jours cj JOIN cours c ON cj.cours_id = c.id "
        "WHERE cj.salle_id=? AND cj.jour_semaine=? "
        "AND c.date_debut<=? AND c.date_fin>=? "   # cours actif à cette date
        "AND cj.heure_debut<? AND cj.heure_fin>?"  # chevauchement horaire
    )
```

La requête SQL traduit l'algorithme de chevauchement : `heure_debut_existant < heure_fin_nouveau ET heure_fin_existant > heure_debut_nouveau`.

---

## 2.15 `persistance/db_json.py` — Base JSON alternative

```python
class BaseDonneesJSON:
    def _lire(self, chemin: str) -> list:
        if not os.path.exists(chemin):
            return []
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)

    def _ecrire(self, chemin: str, donnees: list):
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(donnees, f, ensure_ascii=False, indent=2)
```

**`ensure_ascii=False` :** autorise les caractères accentués (é, è, à...) dans le fichier JSON. Sans ça, Python les échapperait en `é`.

**`indent=2` :** format le JSON avec 2 espaces d'indentation → lisible par un humain.

### Synchronisation du compteur

```python
def charger_tout(self) -> dict:
    ...
    reservations = self.charger_toutes_reservations(s_dict, u_dict)
    if reservations:
        Reservation._compteur = max(r.id for r in reservations)
    return ...
```

**Pourquoi ?** Le compteur `_compteur` est en mémoire. Après un redémarrage, il repart à 0. Si la base contient déjà des réservations avec des ids jusqu'à 50, le prochain ID serait 1 → **collision**. On synchronise avec le max des ids existants.

---

## 2.16 `app.py` — L'application Flask (routes HTTP)

### Initialisation et seed admin

```python
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "reserv_salle_secret_2026")

def seed_admin():
    bd = get_bd()
    if not bd.charger_utilisateur_par_login("admin"):
        admin = Administrateur("Administrateur", "admin@univ.bj", "admin", "Admin@123")
        admin.id = 0
        admin.mot_de_passe = Authentification.hacher_mot_de_passe("Admin@123")
        bd.sauvegarder_utilisateur(admin)

with app.app_context():
    seed_admin()
```

**`secret_key` :** clé secrète pour signer les cookies de session Flask. Sans elle, les sessions ne fonctionnent pas. On la lit depuis une variable d'environnement en production (sécurisé) avec une valeur par défaut pour le développement.

**`seed_admin()` :** s'exécute au démarrage. Si l'admin n'existe pas encore (première installation), il est créé automatiquement.

### Décorateurs de routes

```python
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
```

**Décorateur = fonction qui enveloppe une autre fonction.** `@login_required` s'applique à une route : si l'utilisateur n'est pas connecté, on le redirige vers le login. `@wraps(f)` préserve le nom et la documentation de la fonction originale.

**Utilisation :**
```python
@app.route("/dashboard")
@login_required
def dashboard():
    ...
```

### Session Flask

```python
session.update({
    "user_id":   u.id,
    "user_role": u.role,
    "user_nom":  u.nom,
})
```

**`session`** = dictionnaire stocké dans un cookie chiffré côté client. Flask chiffre les données avec `secret_key`. Quand l'utilisateur revient, Flask lit le cookie, le déchiffre et met les données dans `session`.

### Inscription avec OTP

```python
otp    = _generer_otp()
expire = (datetime.now() + timedelta(minutes=5)).isoformat()

session["inscription_pending"] = {
    "code":       otp,
    "expire":     expire,
    "tentatives": 0,
    "user": { "nom": nom, "email": email, ... }
}

envoye = _envoyer_otp(email, otp, nom)
if envoye:
    flash(f"Un code a été envoyé à {email}.", "success")
else:
    flash(f"SMTP non configuré — code de test : {otp}", "warning")
```

**Flow :**
1. L'utilisateur soumet le formulaire d'inscription
2. On génère un code OTP à 6 chiffres valable 5 minutes
3. On stocke les données d'inscription en session (pas encore en base !)
4. On envoie l'OTP par email
5. L'utilisateur soumet le code → on valide → on crée le compte en base

### Context processor Jinja2

```python
@app.context_processor
def inject_format_classe():
    return dict(format_classe=_format_classe)
```

**`@context_processor` :** injecte des variables/fonctions dans tous les templates Jinja2. Ici, la fonction `format_classe` est disponible dans tous les templates sans avoir besoin de la passer explicitement dans chaque `render_template()`.

---

## 2.17 `main.py` — Démonstration console (Blocs 3 et 4)

```python
def demo_poo():
    gest_users  = GestionUtilisateurs()
    gest_salles = GestionSalles()
    gest_res    = GestionReservation()
    auth        = Authentification(gest_users)

    # Forcer l'accès direct à l'attribut privé via name-mangling
    gest_users._GestionUtilisateurs__utilisateurs[0] = admin
```

**`_GestionUtilisateurs__utilisateurs`** = accès direct à un attribut avec name-mangling depuis l'extérieur de la classe. En Python, ce n'est pas vraiment interdit, mais c'est une convention forte pour dire "je sais ce que je fais, c'est du code de démonstration/test".

---

## 2.18 Tests — Suite pytest

### `conftest.py` — Fixtures partagées

```python
@pytest.fixture
def salle_a():
    s = Salle("Amphi A", 200, ["vidéoprojecteur", "micro"])
    s.id = 1
    return s
```

**Fixture pytest :** une fonction décorée avec `@pytest.fixture` crée un objet réutilisable pour les tests. Chaque test qui demande `salle_a` en paramètre reçoit une nouvelle instance de `Salle`.

### `test_utilisateur.py` — Tests des modèles

```python
def test_id_setter_une_seule_fois(self, etudiant):
    etudiant.id = 5
    assert etudiant.id == 5
    etudiant.id = 99           # essaie de changer
    assert etudiant.id == 5   # doit être ignoré (setter protégé)

def test_instanciation_directe_impossible(self):
    with pytest.raises(TypeError):
        Utilisateur("Nom", "a@b.fr", "login", "hash")  # classe abstraite !
```

**`pytest.raises(TypeError)` :** vérifie qu'une exception est bien levée. Le test passe si l'exception se produit, échoue si elle ne se produit pas.

### `test_authentification.py` — Stub / Mock

```python
class GestionnaireStub:
    """Remplace le vrai GestionUtilisateurs pour les tests unitaires."""
    def __init__(self, utilisateurs: list):
        self._users = {u.login: u for u in utilisateurs}

    def trouver_par_login(self, login: str):
        return self._users.get(login)
```

**Stub :** objet simplifié qui remplace une vraie dépendance pour les tests. Ici, on ne veut pas tester la base de données — on teste seulement `Authentification`. Le stub simule `GestionUtilisateurs` sans aucune base de données.

### `test_gestion_reservation.py` — Tests de rollback

```python
def test_modification_avec_conflit_rollback(self, gest, salle1, resp):
    r1 = ajouter(gest, salle1, resp, "L1", 8, 10)
    r2 = ajouter(gest, salle1, resp, "L2", 10, 12)
    with pytest.raises(ValueError, match="[Cc]onflit"):
        gest.modifier_reservation(r2.id, JOUR, time(9, 0), time(11, 0))
    # rollback vérifié : r2 garde ses horaires d'origine
    assert r2.heure_debut == time(10, 0)
    assert r2.heure_fin   == time(12, 0)
```

Ce test vérifie que si une modification crée un conflit, les données d'origine sont **restaurées** (rollback). C'est une propriété importante de la fiabilité du système.

---

# 3. 50 QUESTIONS D'EXAMEN AVEC RÉPONSES

---

## Catégorie A — Concepts Python fondamentaux (15 questions)

**Q1 — Qu'est-ce qu'une classe abstraite (ABC) et pourquoi l'utilise-t-on ici ?**

Une classe abstraite est une classe qu'on ne peut pas instancier directement. En Python, on hérite de `ABC` et on décore certaines méthodes avec `@abstractmethod`. Ici, `Utilisateur` est abstraite car on ne veut pas créer un "utilisateur générique" sans rôle — seulement des `Etudiant`, `Enseignant`, `Responsable` ou `Administrateur`.

---

**Q2 — Expliquez le name mangling avec `self.__attribut` en Python.**

Quand on écrit `self.__nom`, Python transforme automatiquement le nom en `_NomDeLaClasse__nom`. Résultat : une sous-classe qui hérite de `Utilisateur` ne peut pas accéder à `self.__nom` directement — elle obtiendrait une `AttributeError`. C'est une forme d'**encapsulation forte**.

---

**Q3 — Quelle est la différence entre `_attribut` (un underscore) et `__attribut` (deux underscores) ?**

- `_attribut` = convention "semi-privé". Python n'applique aucune restriction, mais la convention dit "n'utilise pas depuis l'extérieur".
- `__attribut` = name mangling réel. Python renomme l'attribut. Cela empêche l'accès depuis les sous-classes (sauf en utilisant le nom manglifié `_Classe__attribut`).

---

**Q4 — À quoi sert `@property` ? Montrez un exemple du projet.**

`@property` transforme une méthode en attribut calculé. Au lieu de `etudiant.get_nom()`, on écrit `etudiant.nom`. Dans le projet :

```python
@property
def nom(self):
    return self.__nom

@nom.setter
def nom(self, valeur):
    self.__nom = valeur.strip()
```

Le setter permet de contrôler la valeur assignée (ici, on supprime les espaces en trop).

---

**Q5 — Qu'est-ce qu'un Enum et pourquoi l'utilise-t-on pour StatutReservation ?**

Un `Enum` définit un ensemble de constantes nommées. Avantages :
- Pas de risque de faute de frappe (`StatutReservation.CONFIRMEE` vs `"confirmée"`)
- Les IDEs peuvent proposer l'autocomplétion
- Le code est plus lisible et auto-documenté

---

**Q6 — Expliquez `super().__init__(...)` dans `Etudiant.__init__`.**

`super()` retourne la classe parente (`Utilisateur`). En appelant `super().__init__(nom, email, login, mdp)`, on exécute le constructeur de `Utilisateur` qui initialise les attributs communs (nom, email, login, etc.). Sans ça, ces attributs n'existeraient pas dans l'objet `Etudiant`.

---

**Q7 — Qu'est-ce qu'une list comprehension ? Donnez un exemple du projet.**

Une syntaxe compacte pour créer une liste : `[expression for x in itérable if condition]`.

Dans le projet :
```python
def salles_disponibles(self, capacite_min=0):
    return [s for s in self.__salles.values()
            if s.disponible and s.capacite >= capacite_min]
```

Équivalent à 5 lignes avec une boucle `for` + `if` + `append`.

---

**Q8 — Expliquez `@staticmethod` vs méthode classique (`self`).**

Une méthode classique reçoit `self` (l'instance). Elle peut accéder aux attributs de l'objet. Un `@staticmethod` ne reçoit ni `self` ni `cls` — c'est une fonction ordinaire rangée dans la classe. Dans le projet, `hacher_mot_de_passe()` est `@staticmethod` car elle n'a pas besoin de l'état de l'objet.

---

**Q9 — Qu'est-ce qu'un décorateur ? Comment fonctionne `@login_required` ?**

Un décorateur est une fonction qui prend une fonction en entrée et retourne une nouvelle fonction. `@login_required` est appliqué aux routes Flask. Quand Flask appelle la route, il appelle d'abord le décorateur qui vérifie `"user_id" in session`. Si non, il redirige vers le login. Sinon, il appelle la vraie fonction de route.

---

**Q10 — Pourquoi utilise-t-on `@contextmanager` pour la connexion SQLite ?**

Pour garantir que la connexion est toujours fermée, même si une exception survient. Le `try/yield/except/finally` assure : commit si succès, rollback si erreur, et fermeture dans tous les cas. Sans ça, des connexions ouvertes pourraient bloquer la base.

---

**Q11 — Expliquez `isinstance()` et `getattr()` avec les exemples du projet.**

- `isinstance(admin, Administrateur)` : vérifie le type dynamique. Retourne `True` si `admin` est une instance de `Administrateur` ou d'une sous-classe.
- `getattr(u, "ecole_id", None)` : récupère l'attribut `ecole_id` de l'objet `u`, ou `None` si l'attribut n'existe pas. Utilisé car `Enseignant` n'a pas `ecole_id`.

---

**Q12 — Qu'est-ce que l'injection de dépendance ? Où est-elle utilisée ?**

Au lieu de créer ses propres dépendances, un objet les reçoit en paramètre. Dans `GestionCours.__init__(self, bd)`, on passe la base de données. Avantage : pour les tests, on peut passer un stub à la place de la vraie base de données.

---

**Q13 — Expliquez `timedelta` et son utilisation pour générer les occurrences de cours.**

`timedelta` représente une durée. `timedelta(weeks=1)` = 7 jours. Dans la génération des cours :
```python
delta = (num - d.weekday()) % 7   # jours jusqu'au prochain "lundi" par exemple
d = d + timedelta(days=delta)
while d <= date_fin:
    occurrences.append(...)
    d += timedelta(weeks=1)        # semaine suivante
```

---

**Q14 — Que fait `json.dumps()` et pourquoi l'utilise-t-on pour `public_cible_ids` ?**

`json.dumps(liste)` convertit une liste Python en chaîne JSON : `[1, 3, 5]` → `"[1, 3, 5]"`. SQLite ne peut pas stocker des listes nativement, on les sérialise en texte JSON. À la lecture, on utilise `json.loads()` pour reconvertir.

---

**Q15 — Qu'est-ce que le pattern rollback ? Quel test le vérifie ?**

Avant de modifier des données, on sauvegarde l'état précédent. Si la modification échoue (conflit), on restaure l'état original. Le test `test_modification_avec_conflit_rollback` vérifie que les horaires d'une réservation restent inchangés si la modification provoquerait un conflit.

---

## Catégorie B — Architecture et conception (15 questions)

**Q16 — Quelle est la différence entre les modèles (`models/`) et les services (`services/`) ?**

Les **modèles** représentent les données et leurs règles intrinsèques (un objet `Reservation` valide qu'heure_debut < heure_fin). Les **services** contiennent la logique métier plus complexe qui implique plusieurs modèles (`GestionReservation` coordonne `Reservation`, `Salle`, `Responsable`).

---

**Q17 — Pourquoi y a-t-il deux systèmes de persistance (SQLite et JSON) ?**

Le mode `BaseDonneesSQLite` est le mode principal de l'application web — il gère toutes les fonctionnalités avancées (cours, compositions, événements). Le mode `BaseDonneesJSON` a été développé pour le Bloc 4 (démonstration de la persistance) et ne supporte que les utilisateurs, salles et réservations de base.

---

**Q18 — Expliquez le rôle de chaque rôle utilisateur et ses permissions.**

- **Etudiant :** consultation uniquement (planning, événements qui le concernent, ses compositions)
- **Enseignant :** même que étudiant + voir les cours où il intervient
- **Responsable :** peut créer réservations, cours, compositions, événements (soumis à validation pour les événements)
- **Administrateur :** toutes permissions + validation des événements, gestion des utilisateurs/salles/écoles, configuration SMTP

---

**Q19 — Qu'est-ce que le workflow de validation des événements ?**

1. Un Responsable crée un événement → statut `en_attente`
2. L'Admin voit les événements en attente sur son dashboard
3. L'Admin valide → statut `valide` + envoi des notifications
4. OU l'Admin refuse → statut `refuse` + motif enregistré + visible par le Responsable

---

**Q20 — Comment fonctionne la migration automatique des tables (`_migrer_tables`) ?**

Au démarrage, après `CREATE TABLE IF NOT EXISTS`, on tente d'ajouter les nouvelles colonnes avec `ALTER TABLE ... ADD COLUMN`. SQLite lève une `OperationalError` si la colonne existe déjà — on l'attrape et on l'ignore. Ainsi, les bases existantes sont mises à jour sans recréer les tables.

---

**Q21 — Expliquez le pattern Upsert utilisé dans `db_sqlite.py`.**

On essaie d'abord un `INSERT`. Si l'enregistrement existe déjà (violation de clé primaire → `IntegrityError`), on fait un `UPDATE`. C'est plus simple que de vérifier d'abord si l'enregistrement existe avec un `SELECT`.

---

**Q22 — Comment les notifications email sont-elles filtrées selon le public cible d'un événement ?**

`_filtrer_destinataires()` dans `GestionEvenement` :
- `universite` : tous les utilisateurs
- `ecole` : ceux dont `ecole_id` est dans la liste JSON `public_cible_ids`
- `filiere` : ceux dont `unite_formation_id == public_cible_id`

---

**Q23 — Qu'est-ce que `seed_admin()` et pourquoi est-il dans `app.py` ?**

C'est une fonction qui crée le compte administrateur par défaut si il n'existe pas encore. Il est exécuté au démarrage dans `with app.app_context(): seed_admin()`. Cela garantit qu'une nouvelle installation a toujours un admin disponible.

---

**Q24 — Comment fonctionne la détection de conflit dans `verifier_conflit_planning()` ?**

La méthode fait 3 requêtes SQL successives :
1. Dans `cours_jours` (avec JOIN `cours`) — pour les cours récurrents
2. Dans `compositions` — pour les examens
3. Dans `evenements` (statut `valide` uniquement) — pour les événements

Chaque requête applique la condition de chevauchement : `heure_debut_existant < heure_fin_nouveau AND heure_fin_existant > heure_debut_nouveau`.

---

**Q25 — Expliquez le format de classe `"U15,U17"` et comment il est affiché.**

Le nouveau format stocke les IDs des unités de formation : `"U15,U17"` signifie "les filières avec id=15 et id=17". La fonction `_format_classe()` dans `app.py` convertit ces codes en noms lisibles : `"L1-IG, L3-IG"`. L'ancien format texte (`"L3"`) est aussi supporté pour la compatibilité.

---

**Q26 — Comment fonctionne l'inscription avec OTP ?**

1. Formulaire soumis → données stockées en **session** (pas en base) + OTP généré + email envoyé
2. Page de vérification → utilisateur saisit le code
3. Si code correct et non expiré et moins de 5 tentatives → compte créé en base
4. Si SMTP non configuré → code affiché en warning (mode développement)

---

**Q27 — Qu'est-ce que `conn.row_factory = sqlite3.Row` et pourquoi est-ce important ?**

Sans cette configuration, `fetchone()` retourne un tuple. Avec `sqlite3.Row`, on peut accéder aux colonnes par nom : `row["nom"]` au lieu de `row[1]`. Le code est beaucoup plus lisible et résistant aux changements de l'ordre des colonnes.

---

**Q28 — Comment la composition peut-elle se faire "sur un cours existant" ?**

Si l'enseignant a déjà un cours dans la même salle au même créneau, la composition peut utiliser ce créneau sans conflit (la salle est déjà attribuée à cet enseignant). La méthode `_sur_cours_enseignant()` vérifie via SQL si un tel cours existe. La colonne `sur_cours_existant=1` est enregistrée pour l'afficher dans l'interface.

---

**Q29 — Expliquez le rôle du `@wraps(f)` dans les décorateurs de `app.py`.**

Sans `@wraps(f)`, toutes les fonctions décorées auraient le même nom (`decorated`) dans Flask. Cela provoquerait une erreur car Flask n'accepte pas deux routes avec le même nom de fonction. `@wraps(f)` préserve le nom et la docstring de la fonction originale.

---

**Q30 — Comment Flask gère-t-il les sessions de manière sécurisée ?**

Flask signe les données de session avec `secret_key` via HMAC. Le cookie contient les données encodées en base64 et une signature. À chaque requête, Flask vérifie la signature — si quelqu'un modifie les données du cookie, la signature devient invalide et Flask rejette la session.

---

## Catégorie C — Base de données et SQL (10 questions)

**Q31 — Qu'est-ce qu'une clé étrangère (FOREIGN KEY) ? Donnez un exemple du projet.**

Une contrainte qui garantit la cohérence : une valeur dans une colonne doit correspondre à une valeur existante dans une autre table. Dans `unites_formation`, `FOREIGN KEY (ecole_id) REFERENCES ecoles(id) ON DELETE CASCADE` signifie qu'on ne peut pas créer une UniteFormation pour une Ecole qui n'existe pas. `ON DELETE CASCADE` : si on supprime une Ecole, ses filières sont automatiquement supprimées.

---

**Q32 — Qu'est-ce que `PRAGMA foreign_keys = ON` et pourquoi est-ce nécessaire ?**

SQLite n'active pas les contraintes de clé étrangère par défaut (pour compatibilité). Il faut les activer explicitement à chaque connexion avec ce PRAGMA. Sans ça, on pourrait créer des orphelins (une réservation pour une salle qui n'existe pas).

---

**Q33 — Expliquez la requête SQL de vérification de conflit de cours.**

```sql
SELECT c.id FROM cours_jours cj JOIN cours c ON cj.cours_id = c.id
WHERE cj.salle_id=? AND cj.jour_semaine=?
AND c.date_debut<=? AND c.date_fin>=?
AND cj.heure_debut<? AND cj.heure_fin>?
```

- `JOIN` : combine les deux tables sur `cours_id`
- `salle_id=?` : même salle physique
- `jour_semaine=?` : même jour de la semaine
- `date_debut<=date AND date_fin>=date` : le cours est actif à la date donnée
- `heure_debut<heure_fin_nouveau AND heure_fin>heure_debut_nouveau` : chevauchement

---

**Q34 — Quelle est la différence entre `INSERT OR REPLACE` et le pattern try/except INSERT/UPDATE ?**

`INSERT OR REPLACE` supprime l'enregistrement existant et le réinsère. Problème : si des tables filles référencent cet enregistrement, cela peut déclencher des cascades ou des erreurs. Le pattern `try: INSERT / except: UPDATE` est plus sûr car il préserve les données existantes.

---

**Q35 — Comment `sauvegarder_cours_v2()` gère les jours associés à un cours ?**

```python
if cours.get("id") is None:
    cur = conn.execute("INSERT INTO cours ...", params)
    cours["id"] = cur.lastrowid
else:
    conn.execute("UPDATE cours SET ... WHERE id=?", (*params, cours["id"]))
    conn.execute("DELETE FROM cours_jours WHERE cours_id=?", (cours["id"],))  # supprime les anciens jours

for j in jours:
    conn.execute("INSERT INTO cours_jours ...", (...))  # réinsère les nouveaux jours
```

Pour une mise à jour, on supprime et recrée les jours — c'est plus simple que de détecter les changements individuels.

---

**Q36 — Qu'est-ce que `cur.lastrowid` et quand l'utilise-t-on ?**

Après un `INSERT`, `lastrowid` contient l'ID auto-incrémenté de la ligne que SQLite vient de créer. On l'utilise pour récupérer l'ID de l'objet nouvellement inséré et le stocker dans l'objet Python.

---

**Q37 — Expliquez `ON CONFLICT(cle) DO UPDATE` pour la table `config`.**

```sql
INSERT INTO config (cle, valeur) VALUES (?, ?)
ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur
```

C'est un vrai UPSERT SQL (disponible depuis SQLite 3.24). Si la clé existe déjà, on met à jour la valeur. `excluded.valeur` désigne la valeur qu'on aurait voulu insérer.

---

**Q38 — Pourquoi les IDs de la table `config` sont-ils en TEXT et non en INTEGER ?**

La table `config` stocke des paramètres clé/valeur comme `smtp_host`, `smtp_port`. La clé est une chaîne de texte descriptive, pas un entier auto-incrémenté. C'est un modèle de configuration général, pas une table d'entités.

---

**Q39 — Qu'est-ce que `fetchone()` vs `fetchall()` ?**

- `fetchone()` : retourne la première ligne du résultat (ou `None` si vide). Utilisé quand on cherche un objet par ID.
- `fetchall()` : retourne toutes les lignes sous forme de liste. Utilisé pour charger une collection complète.

---

**Q40 — Comment `charger_tout()` synchronise-t-il le compteur de `Reservation` ?**

```python
reservations = self.charger_toutes_reservations(s_dict, u_dict)
if reservations:
    Reservation._compteur = max(r.id for r in reservations)
```

`max(r.id for r in reservations)` utilise une **expression génératrice** (comme une list comprehension sans les crochets) pour trouver l'ID maximum. On synchronise le compteur de classe pour que les prochaines réservations commencent après le maximum existant.

---

## Catégorie D — Tests et bonnes pratiques (10 questions)

**Q41 — Qu'est-ce qu'une fixture pytest et comment en crée-t-on une ?**

Une fixture est une fonction décorée avec `@pytest.fixture` qui prépare les données/objets nécessaires aux tests. Chaque test qui déclare la fixture en paramètre la reçoit automatiquement. Les fixtures dans `conftest.py` sont partagées entre tous les fichiers de test.

---

**Q42 — Qu'est-ce qu'un stub (GestionnaireStub) et pourquoi l'utilise-t-on ?**

Un stub est un objet qui simule une vraie classe mais avec une implémentation simplifiée. `GestionnaireStub` imite `GestionUtilisateurs` pour les tests d'`Authentification`. Avantage : le test est isolé (il ne dépend pas d'une vraie base de données) et rapide.

---

**Q43 — Comment `pytest.raises` fonctionne-t-il ?**

```python
with pytest.raises(TypeError):
    Utilisateur("Nom", "a@b.fr", "login", "hash")
```

Si le code dans le bloc `with` lève l'exception spécifiée, le test **réussit**. Si aucune exception n'est levée, ou si une exception différente est levée, le test **échoue**. Le paramètre `match=` permet de vérifier le message d'erreur.

---

**Q44 — Que teste `test_instanciation_directe_impossible` ?**

Que `Utilisateur` est bien abstraite. Python lève une `TypeError` si on essaie d'instancier directement une classe avec des méthodes abstraites non implémentées. Ce test garantit que l'architecture ABC est en place.

---

**Q45 — Pourquoi les tests vérifient-ils le comportement (statut après `confirmer()`) plutôt que l'implémentation interne ?**

C'est le principe des **tests boîte noire** : on teste ce que le code fait (son comportement observable), pas comment il le fait (son implémentation). Si on change l'implémentation interne sans changer le comportement, les tests doivent continuer à passer.

---

**Q46 — Que garantit `test_plages_adjacentes_ne_chevauchent_pas` ?**

Que deux réservations dos à dos (8h-10h et 10h-12h) ne sont PAS en conflit. C'est important : `10:00 < 10:00` est faux (condition stricte `<`). L'algorithme `debut1 < fin2 AND fin1 > debut2` utilise des inégalités strictes.

---

**Q47 — Comment les tests valident-ils le format des données exportées (`to_dict`) ?**

```python
def test_to_dict_champs(self, salle1, resp):
    r = Reservation(salle1, resp, "L3", JOUR, time(8, 0), time(10, 0), "Algo")
    d = r.to_dict()
    assert d["heure_debut"] == "08:00"
    assert d["statut"] == "en_attente"
```

On vérifie que `to_dict()` retourne des valeurs dans le format attendu par la base de données (chaînes `"08:00"`, pas d'objet `time`).

---

**Q48 — Pourquoi `sys.path.insert(0, ...)` est-il nécessaire dans les tests ?**

```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
```

Les tests sont dans `tests/`. Les modules à importer sont dans le dossier parent (`models/`, `services/`). On ajoute le dossier parent au chemin Python pour que les imports fonctionnent, quel que soit le répertoire depuis lequel on lance pytest.

---

**Q49 — Qu'est-ce que `JOUR = date(2026, 9, 15)` en haut du fichier de test ?**

C'est une **constante de module** — une date fixe dans le futur utilisée pour tous les tests. L'utiliser garantit que les tests ne dépendent pas de la date actuelle (ils ne passeront pas du jour "en attente" au statut "terminé" simplement parce que la date est passée).

---

**Q50 — Comment le test `test_planning_tri_par_horaire` vérifie-t-il le tri ?**

```python
ajouter(gest, salle1, resp, "L2", 12, 14)   # crée la réservation de 12h en premier
ajouter(gest, salle1, resp, "L1", 8, 10)    # crée la réservation de 8h en second
resultats = gest.afficher_planning()
assert resultats[0].heure_debut < resultats[1].heure_debut
```

On insère intentionnellement dans le désordre, puis on vérifie que `afficher_planning()` retourne toujours les réservations triées par horaire croissant.

---

# 4. GLOSSAIRE DES 40 TERMES CLÉS

| Terme | Définition |
|-------|-----------|
| **ABC** | Abstract Base Class — classe Python qu'on ne peut pas instancier directement. Importée depuis le module `abc`. |
| **@abstractmethod** | Décorateur qui force les sous-classes à implémenter une méthode. |
| **Name mangling** | Transformation de `self.__attr` en `self._Classe__attr` par Python. Encapsulation forte. |
| **@property** | Décorateur qui permet d'appeler une méthode comme si c'était un attribut, et d'ajouter un setter. |
| **@staticmethod** | Méthode de classe qui ne reçoit pas `self`. Ne dépend pas de l'état de l'objet. |
| **Enum** | Énumération — ensemble de constantes nommées. `StatutReservation.CONFIRMEE`. |
| **super()** | Référence à la classe parente. `super().__init__(...)` appelle le constructeur parent. |
| **List comprehension** | `[x for x in liste if condition]` — syntaxe compacte pour filtrer/transformer des listes. |
| **Dict comprehension** | `{k: v for k, v in items}` — même principe pour les dictionnaires. |
| **@contextmanager** | Décorateur qui transforme un générateur en gestionnaire de contexte (`with`). |
| **yield** | Dans un contextmanager, suspend l'exécution et "prête" la ressource au bloc `with`. |
| **Décorateur** | Fonction qui enveloppe une autre fonction pour en modifier le comportement. `@login_required`. |
| **@wraps** | Décorateur qui préserve les métadonnées (nom, docstring) de la fonction enveloppée. |
| **isinstance()** | Vérifie si un objet est une instance d'une classe (ou de ses sous-classes). |
| **getattr()** | Récupère un attribut d'un objet par son nom, avec une valeur par défaut si absent. |
| **SHA-256** | Algorithme de hachage cryptographique — produit un hash de 64 caractères hex. Irréversible. |
| **hmac.compare_digest** | Comparaison sécurisée de deux chaînes — résistante aux attaques temporelles. |
| **Hachage** | Transformation d'une données en empreinte unique et de taille fixe. On ne stocke jamais le mot de passe en clair. |
| **Session Flask** | Dictionnaire chiffré stocké dans un cookie côté client, signé avec `secret_key`. |
| **Flash message** | Message unique affiché à l'utilisateur sur la prochaine page (succès, erreur, warning). |
| **SMTP** | Simple Mail Transfer Protocol — protocole d'envoi d'email. Port 587 + STARTTLS. |
| **OTP** | One-Time Password — code à usage unique (6 chiffres, valable 5 minutes). |
| **SQLite** | Base de données légère stockée dans un seul fichier `.db`. Intégrée à Python. |
| **FOREIGN KEY** | Contrainte SQL garantissant la cohérence entre tables. |
| **ON DELETE CASCADE** | Si la ligne parente est supprimée, les lignes filles sont automatiquement supprimées. |
| **Migration** | Mise à jour du schéma de la base de données sans perdre les données existantes. |
| **Upsert** | INSERT si nouveau, UPDATE si existe. Pattern try/except ou `ON CONFLICT DO UPDATE`. |
| **fetchone()** | Récupère la première ligne d'un résultat SQL. Retourne `None` si pas de résultat. |
| **fetchall()** | Récupère toutes les lignes d'un résultat SQL. |
| **row_factory** | `sqlite3.Row` permet d'accéder aux colonnes par nom (`row["nom"]`) au lieu d'index. |
| **Injection de dépendance** | Passer les dépendances en paramètre plutôt que de les créer en interne. Facilite les tests. |
| **Stub** | Objet simplifié qui simule une vraie dépendance pour les tests. `GestionnaireStub`. |
| **Fixture pytest** | Fonction `@pytest.fixture` qui prépare des données réutilisables entre les tests. |
| **conftest.py** | Fichier spécial pytest contenant les fixtures partagées entre tous les fichiers de test. |
| **pytest.raises** | Vérifie qu'une exception est bien levée dans un test. |
| **MIMEMultipart** | Format d'email avec plusieurs parties (HTML + texte brut). Le client choisit la meilleure. |
| **STARTTLS** | Protocole de chiffrement : connexion non chiffrée → activation TLS. Port 587. |
| **Rollback** | Annulation d'une modification pour revenir à l'état précédent. Pattern de fiabilité. |
| **timedelta** | Classe Python pour représenter une durée (`timedelta(weeks=1)` = 7 jours). |
| **Jinja2** | Moteur de templates HTML utilisé par Flask. Syntaxe `{{ variable }}` et `{% if condition %}`. |

---

# 5. CINQ SCÉNARIOS DE DÉMONSTRATION

---

## Scénario 1 — Démarrage et connexion admin

**Ce que vous dites :**
> "Au démarrage de l'application, `seed_admin()` s'exécute dans le contexte Flask. Il vérifie si un utilisateur avec le login `admin` existe dans la base SQLite. Si non, il crée un `Administrateur` avec son mot de passe haché en SHA-256, et l'ID forcé à 0. C'est notre unique admin de départ."

**Ce que vous tapez dans le navigateur :**
1. Démarrer l'app : `python app.py`
2. Aller sur `http://localhost:5000`
3. Connexion : login `admin`, mot de passe `Admin@123`
4. Dashboard affiché avec les sections admin

**Ce que vous expliquez :**
- Flask vérifie `"user_id" not in session` → redirige vers `/login`
- Au POST du formulaire, `Authentification.verifier_hash("Admin@123", hash_stocke)` est appelé
- `hmac.compare_digest` compare les deux hashes de manière temporellement sûre
- Si OK → `session.update({"user_id": 0, "user_role": "admin", ...})`
- Redirect vers `/dashboard`

---

## Scénario 2 — Inscription d'un étudiant avec OTP

**Ce que vous montrez :**
1. Déconnexion → `/inscription`
2. Remplir le formulaire (rôle : Étudiant, choisir une école et une filière)
3. Soumettre → page de vérification OTP

**Ce que vous expliquez :**
- Le formulaire charge les écoles et filières depuis la base : `bd.charger_toutes_ecoles()`, `bd.charger_toutes_unites()`
- La cascade école → filière est gérée en JavaScript avec `UNITES_JSON` injecté en Jinja2
- À la soumission, le mot de passe est haché immédiatement : `Authentification.hacher_mot_de_passe(mdp)`
- Les données sont stockées en **session** (`inscription_pending`), pas en base
- `random.randint(0, 999999)` génère le code OTP formaté sur 6 chiffres
- Si SMTP absent, le code s'affiche dans un flash warning

---

## Scénario 3 — Réservation de salle et détection de conflit

**Ce que vous montrez :**
1. Connectez-vous en responsable
2. Aller dans Réservations → Nouvelle réservation
3. Créer une réservation Salle A, 08h00-10h00, date du lendemain
4. Essayer de créer une deuxième réservation en chevauchement (09h00-11h00, même salle)

**Ce que vous expliquez :**
- Route `POST /reservations/nouveau` dans `app.py`
- `get_data()` charge la BD, les utilisateurs, les salles et les réservations existantes
- `GestionReservation.ajouter_reservation()` crée un objet `Reservation` temporaire
- `verifier_conflit()` parcourt `self.__reservations` en appelant `nouvelle.chevauche(existante)`
- Algorithme : `debut1 < fin2 AND fin1 > debut2` → détecte le chevauchement
- `ValueError` levée → flash error → retour au formulaire

---

## Scénario 4 — Création d'un cours récurrent

**Ce que vous montrez :**
1. Admin ou Responsable → Cours → Nouveau cours
2. Choisir une filière, un enseignant, une matière
3. Ajouter deux jours (ex: Lundi + Mercredi), une salle et des horaires
4. Choisir une période (ex: 01/09/2026 → 31/12/2026)
5. Soumettre → voir les jours créés dans le planning

**Ce que vous expliquez :**
- `GestionCours._occurrences()` calcule toutes les dates du lundi ET du mercredi dans la période
- Algorithme : `(num - date_debut.weekday()) % 7` → premier lundi après `date_debut`
- Ensuite : `d += timedelta(weeks=1)` jusqu'à `date_fin`
- `verifier_conflits()` interroge la base pour chacune des occurrences générées
- `sauvegarder_cours_v2()` insère dans `cours` puis boucle pour insérer dans `cours_jours`
- Notifications envoyées aux étudiants de la filière (et à l'enseignant)

---

## Scénario 5 — Événement avec validation admin

**Ce que vous montrez :**
1. Connectez-vous en Responsable → Événements → Nouvel événement
2. Remplir : titre, description, salle, dates, choisir "École(s)/Faculté(s)" et cocher 2 écoles
3. Soumettre → message "En attente de validation"
4. Se déconnecter → se connecter en Admin
5. Dashboard → panneau "Événements en attente" → cliquer Valider

**Ce que vous expliquez :**
- Formulaire multi-select : `<input type="checkbox" name="public_cible_ids[]">` → `request.form.getlist("public_cible_ids[]")` en Python
- `public_cible_ids` est sérialisé avec `json.dumps([1, 3])` → stocké comme `"[1, 3]"` en SQLite
- `statut = "valide" if role_createur == "admin" else "en_attente"` dans `GestionEvenement.creer_evenement()`
- À la validation : `evt["statut"] = "valide"` → `sauvegarder_evenement()` → `UPDATE evenements ...`
- `_filtrer_destinataires()` : parse `json.loads("[1, 3]")` → filtre les utilisateurs dont `ecole_id in {1, 3}`
- `notif.notifier_evenement()` boucle et envoie un email HTML à chaque destinataire

---

*Document réalisé par ANATO Amen Godson Cossi / HOVO*
