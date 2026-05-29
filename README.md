# UniRéserv — Système de Gestion de Salles Universitaires

> Projet académique Python (TP Projet 7) — ANATO Amen Godson Cossi & HOVO  
> Application web complète de gestion des salles, cours, compositions et événements pour un établissement universitaire.  
> [Cahier des charges initial (Notion)](https://www.notion.so/Cahier-des-Charges-Version-Initiale-35254b4737808030b138f4b1083ce6ba)  
> [Cahier des charges final (Notion)](https://www.notion.so/Cahier-des-Charges-Mis-Jour-34854b47378080c4915ac273609da4d2)

---

## Table des matières

1. [Présentation du projet](#1-présentation-du-projet)
2. [Architecture du projet](#2-architecture-du-projet)
3. [Installation et lancement](#3-installation-et-lancement)
4. [Fonctionnalités par rôle](#4-fonctionnalités-par-rôle)
5. [Nouvelles fonctionnalités](#5-nouvelles-fonctionnalités)
6. [Tableau des routes Flask](#6-tableau-des-routes-flask)
7. [Lancer les tests](#7-lancer-les-tests)
8. [Technologies utilisées](#8-technologies-utilisées)
9. [Captures d'écran](#9-captures-décran)

---

## 1. Présentation du projet

**UniRéserv** est une application web de gestion des espaces universitaires développée en Python avec le framework Flask. Elle couvre l'intégralité du cycle de vie des activités académiques : réservations ponctuelles, cours récurrents, compositions (examens), et événements institutionnels.

### Points clés

- Architecture orientée objet stricte (classes abstraites, encapsulation, héritage, polymorphisme)
- Double backend de persistance : **SQLite** (production) et **JSON** (tests/fallback)
- Authentification sécurisée avec **OTP par email** (inscription et réinitialisation mot de passe)
- Détection automatique des **conflits horaires** sur toutes les activités (cours, compositions, événements, réservations)
- **Recherche d'enseignant avec autocomplétion AJAX** et gestion des enseignants **vacataires**
- **Notifications email HTML** automatiques aux personnes concernées pour chaque activité
- Workflow de **validation admin** pour les événements créés par les responsables
- **Hub de navigation unifié** (`/reservations/hub`) regroupant les 4 types d'activités en une page centrale
- Planning hebdomadaire unifié avec **filtrage par type** (réservations, cours, compositions, événements)
- Cours planifiables du **lundi au samedi**
- Déploiement prêt pour **Render.com** via Gunicorn
- Suite de **101 tests pytest** couvrant les 5 blocs du cahier des charges

---

## 2. Architecture du projet

```
TP_Python_Projet_7_ANATO&HOVO/
│
├── requirements.txt                        # Dépendances Python (flask, gunicorn)
├── wsgi.py                                 # Point d'entrée Gunicorn (Render.com)
├── render.yaml                             # Config déploiement Render.com
├── .gitignore
│
└── gestion de salle/
    │
    ├── app.py                              # Application Flask — 80+ routes, helpers, décorateurs
    ├── main.py                             # Lancement local (python main.py)
    │
    ├── models/                             # Bloc 1 — Modèles POO
    │   ├── __init__.py
    │   ├── utilisateur.py                  # Utilisateur (ABC), Etudiant, Enseignant,
    │   │                                   #   Responsable, Administrateur
    │   ├── salle.py                        # Salle (nom, capacité, équipements)
    │   ├── reservation.py                  # Reservation + StatutReservation (enum)
    │   └── etablissement.py                # Ecole, UniteFormation (filières L1→M2)
    │
    ├── exceptions/                         # Bloc 2 — Exceptions métier
    │   ├── __init__.py
    │   └── exceptions.py                   # ConflitHoraireError, PermissionError…
    │
    ├── services/                           # Bloc 3 — Couche métier / services
    │   ├── __init__.py
    │   ├── authentification.py             # Login, logout, hachage SHA-256, rôles
    │   ├── gestion_reservation.py          # Réservations ponctuelles + détection conflit
    │   ├── gestion_cours.py                # Cours récurrents (occurrences hebdomadaires)
    │   ├── gestion_composition.py          # Examens ponctuels, détection sur cours existant
    │   ├── gestion_evenement.py            # Événements institutionnels, workflow validation
    │   ├── gestion_salles.py               # CRUD salles
    │   ├── gestion_utilisateurs.py         # CRUD utilisateurs, recherche par login
    │   └── notification_email.py           # Emails HTML (OTP, réservation, cours,
    │                                       #   composition, événement, test SMTP)
    │
    ├── persistance/                        # Bloc 4 — Persistance des données
    │   ├── __init__.py
    │   ├── db_sqlite.py                    # Backend SQLite — 10 tables, migrations auto
    │   └── db_json.py                      # Backend JSON (fallback/tests)
    │
    ├── templates/                          # Interface web Jinja2 + Tailwind CSS (32 fichiers)
    │   │
    │   ├── — Authentification —
    │   ├── base.html                       # Layout commun (nav unifiée, flash messages)
    │   ├── login.html                      # Connexion (lien "Mot de passe oublié ?")
    │   ├── inscription.html                # Inscription étudiant/enseignant + sélection filière
    │   ├── otp_verification.html           # Saisie code OTP inscription (6 chiffres, 5 min)
    │   ├── mot_de_passe_oublie.html        # Saisie email pour réinitialisation mot de passe
    │   ├── mot_de_passe_reset.html         # OTP reset + formulaire nouveau mot de passe
    │   │
    │   ├── — Tableau de bord & Profil —
    │   ├── dashboard.html                  # Stats, hub réservations, compos à venir (étudiant),
    │   │                                   #   événements en attente (admin), refus (responsable)
    │   ├── profil.html                     # Profil utilisateur + gestion multi-matières
    │   ├── parametres.html                 # Config SMTP, email admin, test d'envoi (admin)
    │   │
    │   ├── — Salles —
    │   ├── salles.html                     # Liste des salles avec disponibilité
    │   ├── salle_form.html                 # Ajout / modification salle
    │   ├── salle_detail.html               # Détail salle + planning hebdomadaire
    │   │
    │   ├── — Hub de navigation —
    │   ├── reservations_hub.html           # Page centrale : 4 cartes (Cours, Composition,
    │   │                                   #   Événement, Réservation ponctuelle) avec compteurs
    │   │                                   #   et droits d'accès par carte
    │   │
    │   ├── — Réservations ponctuelles —
    │   ├── reservations.html               # Liste des réservations avec filtres
    │   ├── reservation_form.html           # Création (école → filière → enseignant → matière)
    │   ├── reservation_modifier.html       # Modification réservation
    │   │
    │   ├── — Cours récurrents (lundi → samedi) —
    │   ├── cours_v2.html                   # Liste des cours (actifs / terminés, planning hebdo)
    │   ├── cours_v2_form.html              # Création / modification cours (AJAX, jours lun-sam,
    │   │                                   #   vérification conflits, enseignant vacataire)
    │   ├── cours.html                      # Liste cours v1 (legacy — redirige vers /cours/v2)
    │   ├── cours_form.html                 # Formulaire cours v1 (legacy)
    │   │
    │   ├── — Compositions (Examens) —
    │   ├── compositions.html               # Liste des épreuves (badge "Sur cours existant")
    │   ├── composition_form.html           # Création composition (AJAX enseignant,
    │   │                                   #   filière cascade, vacataire)
    │   │
    │   ├── — Événements institutionnels —
    │   ├── evenements.html                 # Liste avec badges statut, Valider/Refuser (admin)
    │   ├── evenement_form.html             # Création / modification événement
    │   │                                   #   (public cible : université / école(s) / filière)
    │   │
    │   ├── — Planning —
    │   ├── planning.html                   # Planning visuel hebdomadaire filtrable par type
    │   │                                   #   (réservations, cours, compositions, événements)
    │   │
    │   ├── — Utilisateurs & Écoles —
    │   ├── utilisateurs.html               # Gestion utilisateurs, filtres école/rôle (admin)
    │   ├── utilisateur_form.html           # Ajout utilisateur (admin)
    │   ├── utilisateur_modifier.html       # Modification utilisateur (admin)
    │   ├── ecoles.html                     # Gestion écoles / facultés / filières (admin)
    │   ├── ecole_form.html                 # Ajout / modification école
    │   ├── unite_form.html                 # Ajout filière (L1→M2)
    │   │
    │   └── 404.html                        # Pages d'erreur 404 / 500
    │
    ├── data/                               # Données JSON (backend alternatif + SQLite)
    │   ├── utilisateurs.json
    │   ├── salles.json
    │   ├── reservations.json
    │   └── reservation_salles.db           # Base de données SQLite (production)
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
┌──────────────────────────────────────────────────────────────┐
│                    Interface Web (Flask)                      │
│              app.py  +  templates/ (Jinja2)                   │
│   Réservations · Cours · Compositions · Événements · Admin    │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                     Couche Services                           │
│  GestionReservation · GestionCours · GestionComposition       │
│  GestionEvenement · GestionSalles · GestionUtilisateurs       │
│  Authentification · NotificationEmail                         │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                     Couche Modèles                            │
│  Utilisateur (ABC) · Salle · Reservation · Ecole              │
│  UniteFormation · StatutReservation (Enum)                    │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                   Couche Persistance                          │
│         BaseDonneesSQLite  /  BaseDonneesJSON                 │
│                                                               │
│  Tables SQLite : ecoles · unites_formation · utilisateurs     │
│   salles · reservations · cours · cours_jours                 │
│   compositions · evenements · config                          │
└──────────────────────────────────────────────────────────────┘
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

| Login | Mot de passe | Email |
|-------|-------------|-------|
| `admin` | `Admin@123` | `godsoninvest@gmail.com` |

> Après la première connexion, rendez-vous dans **Paramètres** pour mettre à jour l'email admin et configurer le serveur SMTP.

### Page Paramètres (admin uniquement)

La page **Paramètres** regroupe deux sections :

**1. Email du compte administrateur**  
Permet de modifier l'adresse email de l'administrateur. Un mot de passe est requis pour confirmer.

**2. Configuration SMTP** (pour les notifications et les OTP)

| Champ | Valeur Gmail recommandée |
|-------|--------------------------|
| Hôte SMTP | `smtp.gmail.com` |
| Port | `587` |
| Email expéditeur | votre adresse Gmail |
| Nom d'affichage | `UniRéserv — Université` |
| Mot de passe | Clé d'application Google (16 caractères) |

> Pour générer une clé d'application Google : **Compte Google → Sécurité → Vérification en 2 étapes → Mots de passe des applications**.

Un **bouton de test** permet d'envoyer un email de vérification pour valider la configuration.

### Déploiement sur Render.com

```bash
# Le fichier render.yaml est déjà configuré.
# Connecter le dépôt GitHub à Render.com.
# Render détecte automatiquement render.yaml et lance :
#   pip install -r requirements.txt
#   gunicorn wsgi:app
```

---

## 4. Fonctionnalités par rôle

### Administrateur

- Tableau de bord avec statistiques globales et **événements en attente de validation**
- Gestion complète des **salles** (ajout, modification, suppression, équipements)
- Gestion complète des **utilisateurs** :
  - Filtres par rôle, école, recherche textuelle
  - Ajout, modification de rôle, suppression
  - Attribution / révocation du rôle **Responsable de promotion**
- Gestion des **écoles / facultés** et de leurs **filières/niveaux** (L1→M2)
- **Validation ou refus** des événements soumis par les responsables (avec motif)
- Création directe d'événements (statut **validé** immédiatement)
- Création de réservations, cours, compositions avec sélection école/filière/enseignant
- Export **CSV** de toutes les réservations
- Page **Paramètres** (SMTP, email admin, test d'envoi)

### Responsable de promotion

- Tableau de bord avec ses réservations et **événements refusés** (avec motif)
- Création de réservations (sa classe est pré-sélectionnée)
- Création d'**événements** soumis à validation admin
- Modification et annulation de ses propres réservations
- Vue planning de sa salle et de sa classe

### Enseignant

- Tableau de bord personnel avec les prochains cours/compositions
- **Plusieurs matières enseignées** : ajout/suppression depuis le profil
- Création de compositions (examens) pour ses filières
- **Notification email** à chaque réservation le désignant comme enseignant
- Vue du planning global

### Étudiant

- Inscription avec **vérification OTP par email** (code à 6 chiffres, valable 5 minutes)
- Tableau de bord avec **compositions à venir** pour sa filière
- Consultation du planning et des salles disponibles
- Modification de son profil

### Tous les rôles

- Authentification sécurisée (SHA-256 + `hmac.compare_digest`)
- **Réinitialisation de mot de passe** par email OTP (10 minutes, 5 tentatives max)
- **Notifications email HTML** automatiques pour chaque activité concernant leur filière ou école
- Consultation des salles et de leurs équipements
- Vue du planning filtrable par date et par type d'activité

---

## 5. Nouvelles fonctionnalités

### Module Cours (planning hebdomadaire récurrent)

Les cours permettent de planifier des séances récurrentes sur une période (date début → date fin), avec un ou plusieurs jours de la semaine, chacun dans une salle et un créneau horaire définis.

- **Création** via formulaire avec sélection cascade école → filière, recherche AJAX d'enseignant, support vacataire
- **Jours disponibles : lundi, mardi, mercredi, jeudi, vendredi, samedi**
- **Vérification AJAX des conflits** avant soumission (bouton "Vérifier les conflits")
- **Détection de conflits** automatique sur toutes les activités existantes (cours, compositions, événements, réservations)
- **Annulation** du cours (status archivé)
- Affichage en **planning visuel** avec couleur bleue distincte

**Tables concernées :** `cours`, `cours_jours`

```
cours
  id, filiere_id, enseignant_id, enseignant_nom_ext, enseignant_email_ext,
  matiere, date_debut, date_fin, created_by, created_at

cours_jours
  id, cours_id, jour_semaine, salle_id, heure_debut, heure_fin
```

### Module Composition (examens ponctuels)

Les compositions sont des épreuves ponctuelles (une seule date). Le système détecte automatiquement si l'enseignant a un cours sur ce créneau et marque alors la composition **"Sur cours existant"** (la composition se tient dans la salle de cours habituelle).

- **Création** avec filière, enseignant (AJAX + vacataire), matière, salle, date, horaires
- **Badge "Sur cours existant"** si l'enseignant a déjà un cours ce créneau
- **Notification email** à l'enseignant et aux étudiants de la filière
- Affichage en **planning visuel** avec couleur orange distincte

**Table concernée :** `compositions`

```
compositions
  id, filiere_id, enseignant_id, enseignant_nom_ext, enseignant_email_ext,
  matiere, salle_id, date, heure_debut, heure_fin, sur_cours_existant,
  created_by, created_at
```

### Module Événement institutionnel (avec workflow de validation)

Les événements couvrent une plage de dates (ex : Journée portes ouvertes, Conférence). Ils disposent d'un **workflow de validation** selon le rôle du créateur :

| Rôle créateur | Statut initial | Validation requise |
|---|---|---|
| Admin | `valide` | Non (immédiat) |
| Responsable | `en_attente` | Oui (admin) |

- **Public cible configurable** : université entière, une ou plusieurs école(s)/faculté(s), une filière précise
- **Notification email ciblée** selon le public sélectionné (filtre par `ecole_id` / `unite_formation_id`)
- **Panneau de validation inline** dans la liste (admin) : bouton Valider + champ motif de refus
- Affichage en **planning visuel** avec couleur verte distincte

**Table concernée :** `evenements`

```
evenements
  id, titre, description, salle_id, date_debut, date_fin, heure_debut, heure_fin,
  statut (en_attente|valide|refuse), motif_refus,
  public_cible_type (universite|ecole|filiere), public_cible_id, public_cible_ids,
  created_by, validated_by, created_at
```

### Hub de navigation unifié (`/reservations/hub`)

La navigation a été restructurée : un seul lien **Réservations** dans le menu latéral mène à une page centrale qui regroupe les 4 types d'activités sous forme de cartes cliquables.

| Carte | Icône | Accès | Compteur affiché |
|-------|-------|-------|-----------------|
| Cours | academic-cap | Admin + Responsable | Cours actifs |
| Composition | document-text | Admin + Responsable + Enseignant | Compositions à venir |
| Événement | calendar | Admin + Responsable | Événements validés |
| Réservation ponctuelle | building-office | Admin + Responsable | Réservations confirmées |

Chaque carte affiche le compteur d'entrées actives, les boutons **Voir tout** et **Nouveau**, et un message **Accès restreint** si l'utilisateur n'a pas les droits. Les étudiants accèdent directement à la liste des réservations, sans passer par le hub.

### Recherche enseignant avec autocomplétion AJAX

Tous les formulaires de cours, composition et réservation disposent d'un **champ de recherche AJAX** pour les enseignants :

- Frappe d'au moins 2 caractères → requête `GET /api/enseignants/recherche?q=…`
- Dropdown avec nom + email, délai anti-rebond 300 ms
- Badge de confirmation à la sélection, bouton ✕ pour effacer
- **Détection vacataire** : si l'utilisateur tape un `@` sans correspondance, les champs nom et email d'un enseignant externe s'affichent automatiquement

### Planning hebdomadaire unifié

Le planning global regroupe désormais toutes les activités sur une même vue :

- **Onglets de filtre** : Tout | Réservations | Cours | Compositions | Événements
- **Code couleur** par type : indigo (réservations), bleu (cours), orange (compositions), vert (événements)
- Navigation semaine précédente / suivante avec conservation du filtre actif
- Badge de type visible sur chaque bloc en vue "Tout"

### Notifications email enrichies

Le service `NotificationEmail` envoie désormais des emails HTML pour :

| Déclencheur | Destinataires |
|---|---|
| Réservation confirmée / annulée | Enseignant + classe(s) concernée(s) |
| Cours créé / annulé | Enseignant + étudiants de la filière |
| Composition créée / annulée | Enseignant + étudiants de la filière |
| Événement validé | Tous les utilisateurs du public cible sélectionné |
| OTP inscription | Étudiant / Enseignant qui s'inscrit |
| OTP reset mot de passe | Utilisateur qui demande la réinitialisation |

---

## 6. Tableau des routes Flask

### Authentification & Inscription

| Méthode | Route | Description | Accès |
|---------|-------|-------------|-------|
| GET, POST | `/login` | Formulaire de connexion | Public |
| GET, POST | `/inscription` | Formulaire d'inscription | Public |
| GET, POST | `/inscription/verifier` | Vérification OTP inscription | Public |
| POST | `/logout` | Déconnexion | Connecté |
| GET, POST | `/mot-de-passe-oublie` | Demande réinitialisation mot de passe | Public |
| GET, POST | `/mot-de-passe-oublie/verifier` | Vérification OTP + nouveau mot de passe | Public |

### Tableau de bord & Profil

| Méthode | Route | Description | Accès |
|---------|-------|-------------|-------|
| GET | `/dashboard` | Tableau de bord principal | Connecté |
| GET, POST | `/profil` | Affichage / modification du profil | Connecté |
| POST | `/profil/matieres/ajouter` | Ajout d'une matière (enseignant) | Enseignant |
| POST | `/profil/matieres/supprimer` | Suppression d'une matière | Enseignant |

### Salles

| Méthode | Route | Description | Accès |
|---------|-------|-------------|-------|
| GET | `/salles` | Liste des salles | Connecté |
| GET | `/salles/<id>/detail` | Détail + planning d'une salle | Connecté |
| GET, POST | `/salles/ajouter` | Ajout d'une salle | Admin |
| GET, POST | `/salles/<id>/modifier` | Modification d'une salle | Admin |
| POST | `/salles/<id>/supprimer` | Suppression d'une salle | Admin |

### Hub de navigation

| Méthode | Route | Description | Accès |
|---------|-------|-------------|-------|
| GET | `/reservations/hub` | Page centrale — 4 cartes avec compteurs | Responsable / Admin / Enseignant |

### Réservations ponctuelles

| Méthode | Route | Description | Accès |
|---------|-------|-------------|-------|
| GET | `/reservations` | Liste des réservations | Responsable / Admin |
| GET, POST | `/reservations/ajouter` | Nouvelle réservation | Responsable / Admin |
| GET, POST | `/reservations/<id>/modifier` | Modification | Responsable / Admin |
| POST | `/reservations/<id>/annuler` | Annulation | Responsable / Admin |
| POST | `/reservations/<id>/supprimer` | Suppression | Admin |
| GET | `/reservations/export` | Export CSV | Admin |

### Cours récurrents

| Méthode | Route | Description | Accès |
|---------|-------|-------------|-------|
| GET | `/cours/v2` | Liste des cours | Responsable / Admin |
| GET, POST | `/cours/v2/nouveau` | Nouveau cours | Responsable / Admin |
| GET, POST | `/cours/v2/<id>/modifier` | Modification | Responsable / Admin |
| POST | `/cours/v2/<id>/annuler` | Annulation | Responsable / Admin |
| POST | `/cours/v2/verifier-conflits` | Vérification AJAX des conflits | Responsable / Admin |

### Compositions (examens)

| Méthode | Route | Description | Accès |
|---------|-------|-------------|-------|
| GET | `/compositions` | Liste des compositions | Responsable / Admin / Enseignant |
| GET, POST | `/compositions/nouvelle` | Nouvelle composition | Responsable / Admin |
| POST | `/compositions/<id>/annuler` | Annulation | Responsable / Admin |

### Événements institutionnels

| Méthode | Route | Description | Accès |
|---------|-------|-------------|-------|
| GET | `/evenements` | Liste des événements | Responsable / Admin |
| GET, POST | `/evenements/nouveau` | Nouvel événement | Responsable / Admin |
| GET, POST | `/evenements/<id>/modifier` | Modification | Responsable / Admin |
| POST | `/evenements/<id>/valider` | Valider un événement | Admin |
| POST | `/evenements/<id>/refuser` | Refuser avec motif | Admin |

### Planning & API

| Méthode | Route | Description | Accès |
|---------|-------|-------------|-------|
| GET | `/planning` | Planning hebdomadaire unifié | Connecté |
| GET | `/api/enseignants/recherche` | Recherche AJAX `?q=…` | Connecté |

### Utilisateurs (Admin)

| Méthode | Route | Description | Accès |
|---------|-------|-------------|-------|
| GET | `/utilisateurs` | Liste des utilisateurs | Admin |
| GET, POST | `/utilisateurs/inscrire` | Ajouter un utilisateur | Admin |
| GET, POST | `/utilisateurs/<id>/modifier` | Modifier un utilisateur | Admin |
| POST | `/utilisateurs/<id>/supprimer` | Supprimer un utilisateur | Admin |
| POST | `/utilisateurs/<id>/promouvoir` | Attribuer le rôle responsable | Admin |
| POST | `/utilisateurs/<id>/revoquer` | Révoquer le rôle responsable | Admin |

### Écoles & Filières (Admin)

| Méthode | Route | Description | Accès |
|---------|-------|-------------|-------|
| GET | `/ecoles` | Liste des écoles / facultés | Admin |
| GET, POST | `/ecoles/ajouter` | Ajouter une école | Admin |
| GET, POST | `/ecoles/<id>/modifier` | Modifier une école | Admin |
| POST | `/ecoles/<id>/supprimer` | Supprimer une école | Admin |
| GET, POST | `/ecoles/<id>/unites/ajouter` | Ajouter une filière | Admin |
| GET, POST | `/ecoles/<id>/filieres/modifier` | Modifier une filière | Admin |
| POST | `/ecoles/<id>/filieres/supprimer` | Supprimer une filière | Admin |

### Paramètres (Admin)

| Méthode | Route | Description | Accès |
|---------|-------|-------------|-------|
| GET, POST | `/parametres` | Config SMTP + email admin | Admin |
| POST | `/parametres/email` | Mettre à jour l'email admin | Admin |
| POST | `/parametres/tester` | Envoyer un email de test | Admin |

---

## 7. Lancer les tests

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

| Fichier de test | Nb tests | Ce qui est couvert |
|---|---|---|
| `test_utilisateur.py` | 41 | Classes Utilisateur, Etudiant, Enseignant, Responsable, Administrateur — propriétés, setters, `to_dict()`, attribution/révocation de rôle |
| `test_authentification.py` | 27 | Hachage SHA-256, `verifier_hash()`, login/logout, `verifier_role()`, `exiger_role()`, état de connexion |
| `test_gestion_reservation.py` | 33 | Création, chevauchement, conflits, modification avec rollback, suppression, filtres planning |
| `test_persistance.py` | — | Backends SQLite et JSON — CRUD complet salles, utilisateurs, réservations |

---

## 8. Technologies utilisées

| Technologie | Usage | Version |
|---|---|---|
| **Python** | Langage principal | 3.10+ |
| **Flask** | Framework web | 3.1.1+ |
| **Jinja2** | Moteur de templates HTML | inclus avec Flask |
| **SQLite** | Base de données relationnelle (10 tables) | stdlib Python |
| **smtplib** | Envoi d'emails SMTP (OTP, notifications) | stdlib Python |
| **hashlib + hmac** | Hachage SHA-256 sécurisé | stdlib Python |
| **json** | Backend alternatif + sérialisation `public_cible_ids` | stdlib Python |
| **pytest** | Suite de tests unitaires | 9.0+ |
| **Gunicorn** | Serveur WSGI pour la production | 21.2.0+ |
| **Tailwind CSS** | Framework CSS utilitaire | CDN v3 |
| **Fetch API** | Requêtes AJAX (recherche enseignant, conflits) | Navigateur natif |
| **Render.com** | Hébergement cloud | — |

### Patrons de conception appliqués

- **Héritage et classes abstraites** — `Utilisateur` (ABC) → `Etudiant`, `Enseignant`, `Responsable`, `Administrateur`
- **Encapsulation** — attributs privés avec name mangling (`__attribut`) et propriétés Python
- **Enum** — `StatutReservation` (EN_ATTENTE, CONFIRMEE, ANNULEE, TERMINEE)
- **Strategy / Dépendance inversée** — double backend de persistance (SQLite / JSON) avec même interface
- **Service Layer** — logique métier isolée dans `services/` (GestionCours, GestionComposition, GestionEvenement…)
- **Context Processor Flask** — `format_classe()` injecté globalement dans tous les templates
- **Migration automatique** — `_migrer_tables()` dans `db_sqlite.py` pour les colonnes ajoutées en cours de développement

---

## 9. Captures d'écran

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
│  Statistiques globales, événements en   │
│  attente, dernières réservations        │
└─────────────────────────────────────────┘
```
![Dashboard](screenshots/dashboard_admin.png)

### Formulaire de cours récurrent
```
┌─────────────────────────────────────────┐
│  [ capture : cours_v2_form.png ]        │
│  Sélection école/filière, recherche     │
│  AJAX enseignant, planning hebdomadaire │
│  avec vérification des conflits         │
└─────────────────────────────────────────┘
```
![Cours](screenshots/cours_v2_form.png)

### Formulaire d'événement (public cible)
```
┌─────────────────────────────────────────┐
│  [ capture : evenement_form.png ]       │
│  Sélection université entière /         │
│  école(s) / filière avec cases à cocher │
└─────────────────────────────────────────┘
```
![Événement](screenshots/evenement_form.png)

### Planning hebdomadaire unifié
```
┌─────────────────────────────────────────┐
│  [ capture : planning.png ]             │
│  Vue filtrée par type avec codes        │
│  couleurs (bleu/orange/vert/indigo)     │
└─────────────────────────────────────────┘
```
![Planning](screenshots/planning.png)

### Gestion des événements (admin)
```
┌─────────────────────────────────────────┐
│  [ capture : evenements.png ]           │
│  Liste avec badges statut, panneau      │
│  Valider / Refuser inline               │
└─────────────────────────────────────────┘
```
![Événements](screenshots/evenements.png)

### Email de notification HTML
```
┌─────────────────────────────────────────┐
│  [ capture : email_notification.png ]   │
│  Email HTML avec header dégradé         │
│  marine, badge statut, tableau récap    │
└─────────────────────────────────────────┘
```
![Email](screenshots/email_notification.png)

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
