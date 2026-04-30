# UniRéserv — Système de Gestion de Réservation de Salles Universitaires

> Projet académique Python (TP Projet 7) — ANATO Amen Godson Cossi & HOVO  
> Application web complète de réservation de salles pour un établissement universitaire.

---

## Table des matières

1. [Présentation du projet](#1-présentation-du-projet)
2. [Architecture du projet](#2-architecture-du-projet)
3. [Installation et lancement](#3-installation-et-lancement)
4. [Fonctionnalités par rôle](#4-fonctionnalités-par-rôle)
5. [Lancer les tests](#5-lancer-les-tests)
6. [Technologies utilisées](#6-technologies-utilisées)
7. [Captures d'écran](#7-captures-décran)

---

## 1. Présentation du projet

**UniRéserv** est une application web de gestion de réservation de salles universitaires développée en Python avec le framework Flask. Elle permet à plusieurs types d'utilisateurs (administrateurs, responsables de promotion, enseignants, étudiants) de gérer les créneaux horaires des salles de cours.

### Points clés

- Architecture orientée objet stricte (classes abstraites, encapsulation, héritage, polymorphisme)
- Double backend de persistance : **SQLite** (production) et **JSON** (tests/fallback)
- Authentification sécurisée avec **OTP par email** lors de l'inscription
- Détection automatique des **conflits horaires**
- **Notifications email HTML** automatiques aux classes concernées lors d'une réservation
- Déploiement prêt pour **Render.com** via Gunicorn
- Suite de **101 tests pytest** couvrant les 5 blocs du cahier des charges

---

## 2. Architecture du projet

```
TP_Python_Projet_7_ANATO&HOVO/
│
├── requirements.txt                        # Dépendances Python
├── wsgi.py                                 # Point d'entrée Gunicorn (Render.com)
├── render.yaml                             # Config déploiement Render.com
│
└── gestion de salle/
    │
    ├── app.py                              # Application Flask — toutes les routes
    ├── main.py                             # Lancement local (python main.py)
    │
    ├── models/                             # Bloc 1 — Modèles POO
    │   ├── __init__.py
    │   ├── utilisateur.py                  # Utilisateur (ABC), Etudiant, Enseignant,
    │   │                                   #   Responsable, Administrateur
    │   ├── salle.py                        # Salle (nom, capacité, équipements)
    │   ├── reservation.py                  # Reservation + StatutReservation (enum)
    │   └── etablissement.py               # Ecole, UniteFormation (filières/niveaux)
    │
    ├── exceptions/                         # Bloc 2 — Exceptions métier
    │   ├── __init__.py
    │   └── exceptions.py                   # ConflitHoraireError, PermissionError…
    │
    ├── services/                           # Bloc 3 — Couche métier / services
    │   ├── __init__.py
    │   ├── authentification.py             # Login, logout, hachage SHA-256, rôles
    │   ├── gestion_reservation.py          # Ajout/modif/suppression + détection conflit
    │   ├── gestion_salles.py               # CRUD salles
    │   ├── gestion_utilisateurs.py         # CRUD utilisateurs, recherche par login
    │   └── notification_email.py           # Emails HTML (OTP, réservation, test SMTP)
    │
    ├── persistance/                        # Bloc 4 — Persistance des données
    │   ├── __init__.py
    │   ├── db_sqlite.py                    # Backend SQLite (production)
    │   └── db_json.py                      # Backend JSON (fallback/tests)
    │
    ├── templates/                          # Interface web Jinja2 + Tailwind CSS
    │   ├── base.html                       # Layout commun (nav, flash messages)
    │   ├── login.html                      # Connexion
    │   ├── inscription.html                # Inscription étudiant/enseignant + OTP
    │   ├── otp_verification.html           # Vérification code OTP
    │   ├── dashboard.html                  # Tableau de bord
    │   ├── salles.html                     # Liste des salles
    │   ├── salle_form.html                 # Ajout/modification salle
    │   ├── salle_detail.html               # Détail salle + planning
    │   ├── reservations.html               # Liste des réservations
    │   ├── reservation_form.html           # Nouvelle réservation (école → filières)
    │   ├── reservation_modifier.html       # Modification réservation
    │   ├── planning.html                   # Vue planning globale
    │   ├── utilisateurs.html               # Gestion utilisateurs (admin)
    │   ├── utilisateur_form.html           # Ajout utilisateur (admin)
    │   ├── utilisateur_modifier.html       # Modification utilisateur (admin)
    │   ├── ecoles.html                     # Gestion écoles/filières (admin)
    │   ├── ecole_form.html                 # Ajout école
    │   ├── unite_form.html                 # Ajout filière/niveau
    │   ├── parametres.html                 # Config SMTP + email admin
    │   ├── profil.html                     # Profil utilisateur connecté
    │   └── 404.html                        # Page d'erreur
    │
    ├── data/                               # Données JSON (backend alternatif)
    │   ├── utilisateurs.json
    │   ├── salles.json
    │   └── reservations.json
    │
    └── tests/                              # Bloc 5 — Suite de tests pytest
        ├── __init__.py
        ├── conftest.py                     # Fixtures partagées
        ├── test_utilisateur.py             # 41 tests — modèles utilisateur
        ├── test_authentification.py        # 27 tests — login, hachage, rôles
        ├── test_gestion_reservation.py     # 33 tests — réservations, conflits
        └── test_persistance.py             # Tests backends SQLite + JSON
```

### Diagramme des couches

```
┌─────────────────────────────────────────────┐
│              Interface Web (Flask)           │
│         app.py  +  templates/ (Jinja2)       │
└─────────────────────┬───────────────────────┘
                      │
┌─────────────────────▼───────────────────────┐
│              Couche Services                 │
│  Authentification · GestionReservation       │
│  GestionSalles · GestionUtilisateurs         │
│  NotificationEmail                           │
└─────────────────────┬───────────────────────┘
                      │
┌─────────────────────▼───────────────────────┐
│               Couche Modèles                 │
│  Utilisateur · Salle · Reservation           │
│  Ecole · UniteFormation                      │
└─────────────────────┬───────────────────────┘
                      │
┌─────────────────────▼───────────────────────┐
│             Couche Persistance               │
│       BaseDonneesSQLite  /  BaseDonneesJSON  │
└─────────────────────────────────────────────┘
```

---

## 3. Installation et lancement

### Prérequis

- Python 3.10 ou supérieur
- pip

### Installation locale

```bash
# 1. Cloner le dépôt
git clone https://github.com/<votre-compte>/TP_Python_Projet_7_ANATO-HOVO.git
cd TP_Python_Projet_7_ANATO-HOVO

# 2. Créer et activer un environnement virtuel
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

# 3. Installer les dépendances
pip install -r requirements.txt
```

### Lancement en développement

```bash
cd "gestion de salle"
python main.py
```

L'application est accessible à l'adresse : `http://127.0.0.1:5000`

### Compte administrateur par défaut

| Login | Mot de passe | email |
|-------|-------------|--------|
| `admin` | `Admin@123` | `godsoninvest@gmail.com`|

> Après la première connexion, rendez-vous dans **Paramètres** pour mettre à jour l'email admin et configurer le serveur SMTP.

### Page Paramètres (admin uniquement)

La page **Paramètres** regroupe deux sections :

**1. Email du compte administrateur**

Permet de modifier l'adresse email de l'administrateur. Un mot de passe est requis pour confirmer la modification.

**2. Configuration SMTP** (pour les notifications email et les OTP d'inscription)

| Champ | Valeur Gmail recommandée |
|-------|--------------------------|
| Hôte SMTP | `smtp.gmail.com` |
| Port | `587` |
| Email expéditeur | `godsoninvest@gmail.com` |
| Nom d'affichage | `UniRéserv — Université` |
| Mot de passe | Clé d'application Google (16 caractères) |

> Pour générer une clé d'application Google : **Compte Google → Sécurité → Vérification en 2 étapes → Mots de passe des applications**.

Un **bouton de test** permet d'envoyer un email de vérification à n'importe quelle adresse pour valider la configuration avant usage.

### Déploiement sur Render.com

```bash
# Le fichier render.yaml est déjà configuré.
# Il suffit de connecter le dépôt GitHub à Render.com.
# Render détecte automatiquement render.yaml et lance :
#   pip install -r requirements.txt
#   gunicorn wsgi:app
```

---

## 4. Fonctionnalités par rôle

### Administrateur

- Tableau de bord avec statistiques globales (salles, réservations, utilisateurs, écoles)
- Gestion complète des **salles** (ajout, modification, suppression, équipements)
- Gestion complète des **utilisateurs** (liste, ajout, modification de rôle, suppression)
- Attribution / révocation du rôle **Responsable de promotion** (via bouton dédié)
- Gestion des **écoles / facultés** et de leurs **filières/niveaux** (L1→M2)
- Page **Paramètres** (accessible uniquement à l'admin) avec :
  - Affichage et **modification de l'email** du compte admin (confirmation par mot de passe actuel)
  - Configuration complète du serveur **SMTP** (hôte, port, compte, nom d'affichage, mot de passe)
  - Indicateurs visuels de statut SMTP (configuré / non configuré)
  - **Email de test** pour valider la configuration SMTP avant usage
- Création de réservations avec **sélection de l'école et des filières/niveaux** à notifier
- Export **CSV** de toutes les réservations
- Accès à toutes les réservations et au planning global
- Suppression de n'importe quelle réservation

### Responsable de promotion

- Tableau de bord avec ses réservations en cours
- Création de réservations avec **sélection de l'école et des filières/niveaux** concernés
- Modification et annulation de ses propres réservations
- Vue planning de sa salle et de sa classe
- Sa classe est pré-sélectionnée lors de la création d'une réservation

### Enseignant

- Tableau de bord personnel
- Création, modification et annulation de réservations
- Sélection de l'école et des filières à notifier
- Vue du planning global

### Étudiant

- Inscription avec **vérification OTP par email** (code à 6 chiffres, valable 5 minutes)
- Tableau de bord — vue des réservations concernant sa filière
- Consultation du planning et des salles disponibles
- Modification de son profil

### Tous les rôles

- Authentification sécurisée (SHA-256 + comparaison timing-safe)
- Réception automatique de **notifications email HTML** lors d'une réservation ou annulation concernant leur filière
- Consultation des salles et de leurs équipements
- Vue du planning filtrable par date, salle ou classe

---

## 5. Lancer les tests

### Prérequis

```bash
pip install pytest
```

### Lancer toute la suite

```bash
cd "gestion de salle"
python -m pytest tests/ -v
```

### Lancer un fichier spécifique

```bash
# Modèles utilisateur
python -m pytest tests/test_utilisateur.py -v

# Service d'authentification
python -m pytest tests/test_authentification.py -v

# Gestion des réservations et détection de conflits
python -m pytest tests/test_gestion_reservation.py -v

# Persistance SQLite et JSON
python -m pytest tests/test_persistance.py -v
```

### Résultats attendus

```
============================= test session starts ==============================
collected 101 items

tests/test_utilisateur.py          41 passed
tests/test_authentification.py     27 passed
tests/test_gestion_reservation.py  33 passed
...
============================== 101 passed in 0.52s =============================
```

### Couverture des tests

| Fichier de test | Nombre de tests | Ce qui est couvert |
|---|---|---|
| `test_utilisateur.py` | 41 | Classes Utilisateur, Etudiant, Enseignant, Responsable, Administrateur — propriétés, setters, `to_dict()`, attribution/révocation de rôle |
| `test_authentification.py` | 27 | Hachage SHA-256, `verifier_hash()`, login/logout, `verifier_role()`, `exiger_role()`, état de connexion |
| `test_gestion_reservation.py` | 33 | Création, chevauchement, conflits, modification avec rollback, suppression, filtres du planning |
| `test_persistance.py` | — | Backends SQLite et JSON — CRUD complet salles, utilisateurs, réservations |

---

## 6. Technologies utilisées

| Technologie | Usage | Version |
|---|---|---|
| **Python** | Langage principal | 3.10+ |
| **Flask** | Framework web | 3.1.1+ |
| **Jinja2** | Moteur de templates HTML | (inclus avec Flask) |
| **SQLite** | Base de données relationnelle | (stdlib Python) |
| **smtplib** | Envoi d'emails SMTP | (stdlib Python) |
| **hashlib + hmac** | Hachage SHA-256 sécurisé | (stdlib Python) |
| **pytest** | Suite de tests unitaires | 9.0+ |
| **Gunicorn** | Serveur WSGI pour la production | 21.2.0+ |
| **Tailwind CSS** | Framework CSS utilitaire | CDN (v3) |
| **Render.com** | Hébergement cloud (déploiement) | — |

### Patrons de conception appliqués

- **Héritage et classes abstraites** — `Utilisateur` (ABC) → `Etudiant`, `Enseignant`, `Responsable`, `Administrateur`
- **Encapsulation** — attributs privés avec name mangling (`__attribut`) et propriétés
- **Enum** — `StatutReservation` (EN_ATTENTE, CONFIRMEE, ANNULEE, TERMINEE)
- **Strategy / Dépendance inversée** — double backend de persistance (SQLite / JSON) avec même interface
- **Context Processor Flask** — `format_classe()` injecté globalement dans tous les templates

---

## 7. Captures d'écran

> Les captures ci-dessous sont des emplacements réservés. Remplacez-les par vos propres captures après lancement de l'application.

### Page de connexion
```
┌─────────────────────────────────────────┐
│  [ capture : login.png ]                │
│  Formulaire de connexion avec logo      │
│  UniRéserv, champs login + mot de passe │
└─────────────────────────────────────────┘
```
![Login](screenshots/login.png)

### Tableau de bord administrateur
```
┌─────────────────────────────────────────┐
│  [ capture : dashboard_admin.png ]      │
│  Statistiques globales, dernières       │
│  réservations, accès rapide             │
└─────────────────────────────────────────┘
```
![Dashboard](screenshots/dashboard_admin.png)

### Formulaire de réservation
```
┌─────────────────────────────────────────┐
│  [ capture : reservation_form.png ]     │
│  Sélection salle, école, filières,      │
│  date et horaires                       │
└─────────────────────────────────────────┘
```
![Réservation](screenshots/reservation_form.png)

### Planning des salles
```
┌─────────────────────────────────────────┐
│  [ capture : planning.png ]             │
│  Vue planning filtrée par date,         │
│  salle ou classe                        │
└─────────────────────────────────────────┘
```
![Planning](screenshots/planning.png)

### Email de notification (HTML)
```
┌─────────────────────────────────────────┐
│  [ capture : email_reservation.png ]    │
│  Email HTML avec header dégradé         │
│  marine, badge vert, tableau récap      │
└─────────────────────────────────────────┘
```
![Email](screenshots/email_reservation.png)

### Paramètres SMTP
```
┌─────────────────────────────────────────┐
│  [ capture : parametres.png ]           │
│  Configuration SMTP, changement email   │
│  admin, test d'envoi                    │
└─────────────────────────────────────────┘
```
![Paramètres](screenshots/parametres.png)

---

## Auteurs

| Nom | Rôle |
|-----|------|
| **ANATO Amen Godson Cossi** | Développeur principal |
| **HOVO** | Co-développeur |

---

## Licence

Projet académique — usage éducatif uniquement.
