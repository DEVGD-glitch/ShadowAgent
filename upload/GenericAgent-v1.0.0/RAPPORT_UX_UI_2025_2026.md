# Rapport Complet : Patterns UI/UX pour Applications Desktop d'Agents IA — 2025-2026

## Recommandations spécifiques pour l'amélioration de GenericAgent Qt Desktop App

**Date** : Mars 2026  
**Périmètre** : Analyse comparative des meilleures applications desktop IA, patrons de conception UI/UX, et recommandations concrètes pour GenericAgent (PySide6/Qt6)

---

## Table des Matières

1. [Analyse des Meilleures Applications Desktop IA](#1-analyse-des-meilleures-applications-desktop-ia)
2. [Patrons UI pour le Chat](#2-patrons-ui-pour-le-chat)
3. [Patrons UI Spécifiques aux Agents](#3-patrons-ui-spécifiques-aux-agents)
4. [Sidebar et Navigation](#4-sidebar-et-navigation)
5. [Fonctionnalités Avancées](#5-fonctionnalités-avancées)
6. [Recommandations Qt/PySide6](#6-recommandations-qtpyside6)
7. [Recommandations Priorisées pour GenericAgent](#7-recommandations-priorisées-pour-genericagent)
8. [Feuille de Route d'Implémentation](#8-feuille-de-route-dimplémentation)

---

## 1. Analyse des Meilleures Applications Desktop IA

### 1.1 ChatGPT Desktop (OpenAI)

**Ce qui rend l'UI exceptionnelle :**

- **Mode Canvas / Split-Pane** (février 2025+) : Vue à deux panneaux — conversation à gauche, éditeur de code/document à droite. L'utilisateur peut éditer inline le contenu généré pendant que la conversation continue.
- **Vue écran partagé** (février 2026) : « Write and edit text in-line. Preview diagrams and mini apps directly in chat. Review code in split-screen views. » (Notes de version ChatGPT)
- **Sidebar de conversations** avec recherche, groupes, et archivage automatique
- **Upload multimodal natif** : images, fichiers, avec aperçu inline
- **GPTs personnalisés** accessibles depuis la sidebar
- **Streaming fluide** avec rendu markdown progressif et indicateurs de token

**Leçons pour GenericAgent :**
- Le split-pane Canvas est le nouveau standard — les utilisateurs s'attendent à pouvoir éditer le résultat tout en continuant la conversation
- L'aperçu inline (diagrammes, mini-apps) dans le chat est un différentiateur majeur
- La vue écran partagé pour le code (chat + éditeur côte à côte) est devenue indispensable

### 1.2 Claude Desktop / Claude Code (Anthropic)

**Ce qui rend l'UI exceptionnelle :**

- **Redesign d'avril 2026** — transformation majeure : de « simple assistant conversationnel » vers « tableau de bord d'orchestration multi-agents »
- **Sidebar multi-sessions « Mission Control »** : gérer plusieurs sessions actives en parallèle, filtrer par statut/projet/environnement, grouper par projet
  - Filtrage par statut (actif, en attente, terminé)
  - `Cmd+N` / `Ctrl+N` pour nouvelle session, `Ctrl+Tab` pour naviguer
  - Auto-archivage quand une PR est mergée
- **Drag-and-drop de layout** : réorganisation libre de l'espace de travail
- **Isolation Git Worktree** : chaque session obtient sa copie isolée du projet
- **Trois modes de vue** : Verbose, Normal, Summary
- **Terminal intégré + éditeur de fichiers** : plus besoin de fenêtres externes
- **Side Chat** : conversation secondaire sans quitter le contexte principal
- **Routines Cloud** : automatisation basée sur le cloud
- **Extended Thinking** (depuis Claude 3.7 Sonnet) : visualisation du raisonnement de l'agent avec section dépliante/repliable

**Leçons pour GenericAgent :**
- La sidebar multi-session est le cœur du workflow moderne — l'utilisateur orchestre, l'agent exécute
- L'isolation des sessions (worktree) est critique pour le multi-tâche
- Les trois modes de vue (Verbose/Normal/Summary) répondent à des besoins différents
- Le terminal intégré élimine les changements de contexte

### 1.3 Cursor IDE

**Ce qui rend l'UI exceptionnelle :**

- **Architecture IDE-native** : pas un chat superposé, mais une intégration profonde dans l'éditeur
- **Chat Panel latéral** (droite/gauche configurable) : conversation IA toujours visible pendant le codage
- **Inline Edit** : modifications proposées directement dans l'éditeur avec diff visuel (surlignage vert/rouge)
- **Composer** : mode agent qui peut modifier plusieurs fichiers simultanément
- **Cmd+K** : édition inline rapide — sélection de code + instruction naturelle
- **File Tree** avec indicateurs de modification IA
- **Preview de diff** avant acceptation
- **@-mentions** pour référencer des fichiers, du code, de la documentation
- **Contexte automatique** : le chat IA connaît le fichier ouvert, les erreurs, le repo

**Leçons pour GenericAgent :**
- L'édition inline avec diff visuel est le gold standard pour les modifications de code
- Les @-mentions pour le contexte sont un UX puissant et intuitif
- L'intégration fichier-chat (pas de séparation) est cruciale

### 1.4 Windsurf Editor (Codeium)

**Ce qui rend l'UI exceptionnelle :**

- **Cascade Panel** : panneau IA à droite de l'IDE, avec conversation + actions visibles
- **AI Flow** : l'IA agit comme un pair programmer qui comprend le contexte complet du projet
- **Memories** : l'agent mémorise les préférences et le contexte du projet entre les sessions
- **Supercomplete** : complétion intelligente multi-lignes
- **Actions en temps réel** : l'utilisateur voit les modifications de fichiers pendant que l'agent travaille

**Leçons pour GenericAgent :**
- Le système de « Memories » est essentiel pour la continuité entre sessions
- La visibilité en temps réel des actions de l'agent renforce la confiance

### 1.5 Devin / Replit Agent / Bolt.new / v0.dev

| Application | Pattern UI Clé | Innovation |
|---|---|---|
| **Devin** | Timeline d'actions étape par étape | Visualisation complète du raisonnement et des outils utilisés |
| **Replit Agent** | Chat + Éditeur + Preview intégré | Cycle développe-réviser-déployer dans une seule fenêtre |
| **Bolt.new** | Chat → Code → Aperçu en temps réel | Déploiement instantané visible |
| **v0.dev** | Chat → Génération visuelle → Édition | Prévisualisation live du composant UI généré |

**Leçon transversale** : Toutes ces applications combinent **Chat + Éditeur/Preview** dans un layout unifié. Le chat seul est insuffisant — l'utilisateur doit voir le résultat.

---

## 2. Patrons UI pour le Chat

### 2.1 Rendu Markdown en Streaming

**État de l'art (2025-2026) :**

- **Rendu progressif token par token** : le markdown est parsé et rendu au fur et à mesure de la réception (comme ChatGPT/Claude)
- **Bloc de code fermé pendant le streaming** : les blocs de code sont affichés dans une « boîte » avec titre de langage, et ne sont rendus qu'une fois complets
- **Animation de curseur clignotant** : un curseur animé ▌ à la fin du texte en streaming

**Implémentation Qt actuelle dans GenericAgent :**
- `QTextBrowser` avec CSS markdown (`_MD_CSS` dans `theme.py`)
- `StreamHandler` avec polling à 40ms (`POLL_INTERVAL_MS`)
- `_MsgRow.set_text()` met à jour le HTML à chaque chunk

**Problèmes identifiés :**
- Le `QTextBrowser` a des performances médiocres pour le rendu markdown riche (pas de coloration syntaxique, pas de LaTeX, pas de diagrammes Mermaid)
- Pas de curseur de streaming animé
- Les blocs de code manquent de bouton « Copier » dédié et de coloration syntaxique

**Recommandation :**
```
Priorité HAUTE — Remplacer QTextBrowser par QWebEngineView pour le rendu markdown
```
Voir section 6.1 pour les détails d'implémentation.

### 2.2 Coloration Syntaxique du Code avec Bouton Copier

**Standard de l'industrie :**
- Chaque bloc de code a : nom du langage (label en haut à gauche), bouton « Copier » (en haut à droite), coloration syntaxique (highlight.js, Prism.js)
- Numéros de ligne optionnels
- Bouton « Insérer dans l'éditeur » si un éditeur est intégré

**Implémentation recommandée avec QWebEngineView :**
- Utiliser highlight.js via CDN ou local dans le HTML rendu
- Template de bloc de code avec en-tête :
  ```html
  <div class="code-block">
    <div class="code-header">
      <span class="lang">python</span>
      <button onclick="copyCode(this)">Copier</button>
    </div>
    <pre><code class="language-python">...</code></pre>
  </div>
  ```
- Communication JS→Python via `QWebChannel` pour le bouton « Copier »

### 2.3 Upload et Aperçu de Fichiers Inline

**État de l'art :**
- **Glisser-déposer** de fichiers directement dans la zone de saisie
- **Aperçu inline** : images affichées comme thumbnails, fichiers texte avec extrait
- **Indicateur de progression** d'upload
- **Suppression individuelle** des pièces jointes (bouton ×)

**État actuel GenericAgent :**
- `_attach_files()` via `QFileDialog`
- Chips de noms de fichiers (sans aperçu)
- Pas de drag-and-drop

**Recommandations :**
1. Ajouter le **drag-and-drop** sur la `ChatPage` avec `setAcceptDrops(True)` et `dropEvent()`
2. Afficher des **miniatures** pour les images (QPixmap scaled)
3. Ajouter un bouton **× de suppression** sur chaque chip
4. Prévisualiser les fichiers texte (premières lignes)

### 2.4 Branchement/Fork de Messages

**Pattern émergent (2025-2026) :**
- ChatGPT : « Edit message » — l'utilisateur peut modifier un message envoyé et relancer la conversation depuis ce point
- Plusieurs applications permettent de créer des « branches » visuelles d'une conversation
- Représentation en arbre avec indication de la branche active

**Recommandation pour GenericAgent :**
- **Priorité MOYENNE** — Implémenter d'abord l'édition de message utilisateur
- Ajouter un bouton « ✏️ Modifier » au hover sur les messages utilisateur
- Conserver l'historique des branches en mémoire (dict avec structure arborescente)
- Indicateur visuel « Branche 1/3 » pour naviguer entre les variantes

### 2.5 Indicateurs d'Utilisation de Tokens

**État de l'art :**
- Affichage discret dans la barre de statut : « ~2.4K tokens in / 1.1K out »
- Barre de progression vers la limite de contexte
- Indicateur de coût estimé (pour les APIs payantes)
- Avertissement quand on approche la limite

**État actuel GenericAgent :**
- `_token_lbl` dans la barre inférieure de `ChatPage`
- `_format_token_label()` dans `utils.py`
- `_estimate_token_usage()` — estimation basique par ratio caractères/tokens

**Recommandations :**
1. Ajouter une **barre de progression visuelle** vers la limite de contexte
2. Afficher le **coût estimé** si le pricing du modèle est connu
3. **Avertissement** quand >80% du contexte est utilisé
4. Utiliser les compteurs réels de tokens de l'API quand disponibles (usage.prompt_tokens, usage.completion_tokens)

### 2.6 Affichage du Raisonnement (Thinking/Reasoning)

**État de l'art :**
- **Claude Extended Thinking** : section repliable « Pensée étendue » avec animation de progression, contenu progressivement révélé
- **OpenAI o1/o3** : chaîne de raisonnement affichée dans une section séparée et réductible
- **DeepSeek R1** : affichage du raisonnement en mode « pensée » avec style distinct (gris/italique)

**Pattern UI recommandé :**
```python
class ThinkingSection(QWidget):
    """Section réductible affichant le raisonnement de l'agent."""
    - Flèche dépliante ▶/▼
    - Label "Raisonnement (12s)"
    - Contenu dans un QTextBrowser avec style distinct (fond plus sombre, texte gris clair)
    - Animation de dépliage avec QPropertyAnimation
```

**Recommandation pour GenericAgent :**
- **Priorité HAUTE** — C'est un différenciateur majeur en 2026
- Détecter automatiquement les sections `<thinkering>...</thinkering>` ou `<thinking>...</thinking>` dans la réponse
- Rendre ces sections dans un widget `_ThinkingSection` réductible
- Afficher la durée du raisonnement

---

## 3. Patrons UI Spécifiques aux Agents

### 3.1 Visualisation des Appels d'Outils (Tool Calls)

**Le problème** : Quand un agent utilise des outils (recherche web, exécution de code, lecture de fichier), l'utilisateur doit voir ce qui se passe en temps réel.

**État de l'art :**
- **Devin** : timeline visuelle avec icônes d'outils (🔍 Recherche, 📝 Édition, ▶️ Exécution)
- **Claude Code** : chaque tool call est un bloc réductible avec statut (⏳ en cours, ✅ succès, ❌ erreur)
- **Cursor Composer** : les modifications de fichiers sont listées avec diff mini-preview
- **Replit Agent** : onglets d'outils actifs avec animation de progression

**Pattern UI recommandé pour GenericAgent :**

```
┌──────────────────────────────────────────────┐
│ 🤖 Assistant                                  │
│ Je vais rechercher cette information...       │
│                                               │
│ ┌─ 🔍 Recherche Web ──────── ⏳ En cours ──┐ │
│ │  Requête : "Python async patterns"        │ │
│ │  ████████████░░░░░ Chargement...          │ │
│ └────────────────────────────────────────────┘ │
│                                               │
│ ┌─ 📁 Lecture fichier ───── ✅ Terminé ────┐ │
│ │  main.py (45 lignes)                      │ │
│ │  ▼ Voir le contenu                        │ │
│ └────────────────────────────────────────────┘ │
│                                               │
│ D'après ma recherche...                       │
└──────────────────────────────────────────────┘
```

**Implémentation Qt :**

```python
class ToolCallWidget(QWidget):
    """Widget affichant un appel d'outil avec statut et résultat."""
    
    STATES = {
        "pending":  {"icon": "⏳", "color": "#fbbf24", "label": "En cours"},
        "success":  {"icon": "✅", "color": "#22c55e", "label": "Terminé"},
        "error":    {"icon": "❌", "color": "#ef4444", "label": "Erreur"},
        "waiting":  {"icon": "⏸️", "color": "#a1a1aa", "label": "En attente"},
    }
    
    # Layout :
    # [Icone] [Nom outil + résumé] [Statut badge]
    # [Détail réductible avec résultat]
```

**Recommandation :**
- **Priorité HAUTE** — C'est la fonctionnalité la plus distinctive d'une app agent vs. un simple chatbot
- Intercepter les événements de tool_call dans l'agent_loop
- Créer des widgets `ToolCallWidget` insérés dans le flux de conversation
- Supporter les types d'outils : recherche web, lecture/écriture fichier, exécution commande, appel API

### 3.2 Timeline d'Actions

**Pattern** : Vue chronologique des actions de l'agent, similaire au « Activity Log » de Devin.

```
12:34:01  📝 Reçu instruction utilisateur
12:34:02  🔍 Recherche web : "Python async patterns"
12:34:05  📁 Lecture : src/main.py
12:34:06  ✏️ Modification : src/main.py (ligne 45-67)
12:34:08  ▶️ Exécution : python main.py
12:34:10  ✅ Résultat : sortie console (2 lignes)
12:34:11  📝 Réponse générée
```

**Implémentation recommandée :**
- Widget `ActionTimeline` dans un panneau latéral ou onglet dédié
- Chaque entrée est cliquable → scroll vers le message correspondant dans le chat
- Filtres par type d'action
- Export possible en JSON pour debugging

### 3.3 Dialogues d'Approbation/Rejet

**Problème critique** : Les agents autonomes peuvent exécuter des actions dangereuses (suppression de fichiers, envoi d'emails, déploiement). L'utilisateur doit pouvoir approuver ou rejeter ces actions.

**Patterns observés :**
- **Claude Code** : dialogue modal « Autoriser cette commande ? » avec boutons Autoriser / Refuser / Toujours autoriser
- **Cursor** : les modifications de code sont en mode « suggestion » par défaut — l'utilisateur doit cliquer « Accept » ou « Reject »
- **OpenAI Operator** : capture d'écran de l'action proposée avant exécution

**Pattern UI recommandé :**

```python
class ApprovalDialog(QDialog):
    """Dialogue d'approbation pour les actions dangereuses de l'agent."""
    
    NIVEAUX = {
        "low":      {"color": "#22c55e", "auto_approve": True},   # lecture de fichier
        "medium":   {"color": "#fbbf24", "auto_approve": False},  # écriture de fichier
        "high":     {"color": "#ef4444", "auto_approve": False},  # exécution de commande
        "critical": {"color": "#dc2626", "auto_approve": False},  # suppression, déploiement
    }
    
    # Layout :
    # [⚠️ Icône d'avertissement]
    # [Description de l'action proposée]
    # [Détail de la commande/fichier]
    # [✅ Autoriser] [❌ Refuser] [🔄 Toujours autoriser ce type]
```

**Recommandation :**
- **Priorité HAUTE** — Sécurité utilisateur fondamentale
- Catégoriser chaque outil par niveau de risque
- En mode autonome (`autonomous_enabled`), auto-approuver les actions « low » uniquement
- Journaliser toutes les approbations/refus

### 3.4 Indicateurs de Statut de l'Agent

**Patterns observés :**
- **ChatGPT** : animation de三点 (typing indicator) pendant la génération
- **Claude** : « Thinking... » avec animation de pulsation
- **Cursor** : barre de progression circulaire sur l'icône de l'agent
- **Windsurf** : Cascade affiche « Reading your code... » / « Writing changes... » / « Running tests... »

**États recommandés pour GenericAgent :**

| État | Icône | Animation | Description |
|---|---|---|---|
| Idle | 🟢 | Aucune | Agent en attente d'instruction |
| Thinking | 🟡 | Pulsation | Agent en train de réfléchir |
| Acting | 🔵 | Rotation | Agent exécute un outil |
| Waiting Input | 🟠 | Clignotement | Agent attend une approbation |
| Error | 🔴 | Fixe | Une erreur s'est produite |
| Streaming | 🟣 | Progression | Réponse en cours de streaming |

**Implémentation :**
```python
class AgentStatusBar(QWidget):
    """Barre de statut de l'agent avec indicateur animé."""
    
    def set_state(self, state: str):
        """Change l'état visuel de l'indicateur."""
        # Utiliser QPropertyAnimation pour les transitions fluides
        # Couleurs et icônes selon le tableau ci-dessus
```

Le `FloatingButton` existant implémente déjà des états visuels (idle bleu, running vert) — étendre ce pattern au chat panel.

### 3.5 Vue Multi-Agent

**Pattern émergent (2026) :**
- Plusieurs agents travaillent en parallèle sur des tâches différentes
- Chaque agent a son propre thread de conversation
- Vue d'ensemble avec statut de chaque agent

**Recommandation :**
- **Priorité BASSE** — Anticiper l'architecture mais ne pas implémenter immédiatement
- Concevoir le `SessionManager` pour supporter N sessions parallèles
- La sidebar multi-session de Claude Code est le modèle à suivre

---

## 4. Sidebar et Navigation

### 4.1 Historique de Sessions avec Recherche

**État de l'art :**
- **ChatGPT** : sidebar gauche avec historique groupé par date (Aujourd'hui, 7 derniers jours, 30 derniers jours), recherche en haut, groupes personnalisables
- **Claude** : sidebar similaire avec onglets (Conversations / Projects)
- **Cursor** : pas de sidebar d'historique (focus sur l'éditeur), mais panneau de chat avec onglets

**État actuel GenericAgent :**
- `HistoryPage` avec liste de sessions
- Recherche par mot-clé dans le titre
- Pas de groupement par date
- Pas de recherche dans le contenu des messages

**Recommandations :**
1. **Groupement par date** (Aujourd'hui, Hier, Cette semaine, Plus ancien)
2. **Recherche full-text** dans le contenu des messages (pas seulement les titres)
3. **Aperçu au survol** (tooltip avec les premiers mots de la conversation)
4. **Actions rapides** : renommer, supprimer, épingler en haut
5. **Compteur de messages** et indicateur de tokens par session

### 4.2 Navigateur de Fichiers Intégré

**Pattern** : Panneau latéral avec arborescence de fichiers du projet/workspace, similaire à VS Code.

**Recommandation :**
- Utiliser `QTreeView` avec `QFileSystemModel`
- Indicateurs visuels pour les fichiers modifiés par l'agent
- Clic sur un fichier → ouverture dans l'onglet éditeur
- Menu contextuel : Ouvrir, Ouvrir avec l'agent, Copier le chemin

### 4.3 Panneau de Paramètres/Configuration

**État actuel GenericAgent :**
- `SettingsPage` existant

**Recommandations d'amélioration :**
1. **Catégories organisées** : Général, Modèle IA, Outils, Apparence, Avancé
2. **Sélection de modèle** avec description et pricing
3. **Gestion des clés API** par fournisseur (OpenAI, Anthropic, Google, etc.)
4. **Configuration des outils** : activer/désactiver chaque outil, configurer les niveaux d'approbation
5. **Thème** : sélecteur dark/light/custom avec aperçu live

### 4.4 Panneau de Gestion des Outils

**Nouveau patron (2025-2026) :**

Les applications agent modernes ont un panneau dédié à la gestion des outils disponibles pour l'agent :

- **Liste des outils** avec toggle on/off
- **Configuration par outil** : paramètres, niveaux d'approbation
- **Statistiques d'utilisation** : combien de fois chaque outil a été appelé
- **MCP Servers** : gestion des serveurs Model Context Protocol (standard Anthropic)

**Recommandation :**
- **Priorité MOYENNE** — Ajouter un onglet « Outils » dans la sidebar
- Modèle de données : liste de `ToolConfig` avec nom, description, activé, niveau_approbation, stats

---

## 5. Fonctionnalités Avancées

### 5.1 Vue Split (Chat + Éditeur + Preview)

**Le layout révolutionnaire de 2025-2026 :**

```
┌─────────────────────────────────────────────────────────┐
│ ┌──────────┐ ┌────────────────┐ ┌────────────────────┐ │
│ │          │ │                │ │                    │ │
│ │  Chat    │ │  Éditeur de    │ │  Preview /         │ │
│ │  Panel   │ │  Code          │ │  Navigateur        │ │
│ │          │ │                │ │                    │ │
│ │          │ │                │ │                    │ │
│ └──────────┘ └────────────────┘ └────────────────────┘ │
│ ┌──────────────────────────────────────────────────────┐ │
│ │  Terminal Intégré                                     │ │
│ └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Implémentation Qt :**
- `QSplitter` principal (horizontal) pour les 3 colonnes
- `QSplitter` vertical pour ajouter le terminal en bas
- Les proportions sont sauvegardées/restaurées via QSettings
- Chaque panneau peut être masqué/réaffiché

**Recommandation :**
- **Priorité HAUTE** — C'est le pattern #1 de 2025-2026
- Commencer par 2 panneaux (Chat + Éditeur), ajouter le preview ensuite
- Utiliser `QWebEngineView` pour l'éditeur de code (Monaco Editor ou CodeMirror en HTML)
- Utiliser `QWebEngineView` pour le preview navigateur

### 5.2 Opérations Drag-and-Drop

**Patterns :**
- **Fichiers** : glisser un fichier depuis l'explorateur vers la zone de chat
- **Code** : glisser un bloc de code vers l'éditeur
- **Layout** : réorganiser les panneaux par drag-and-drop (comme Claude Code)

**Implémentation Qt :**
```python
class ChatPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            # Ajouter le fichier aux pièces jointes
```

### 5.3 Raccourcis Clavier et Mode Vim

**Raccourcis essentiels :**

| Raccourci | Action | Source |
|---|---|---|
| `Ctrl+Enter` | Envoyer le message | Standard |
| `Shift+Enter` | Nouvelle ligne | Standard |
| `Ctrl+K` | Command palette | VS Code/Cursor |
| `Ctrl+N` | Nouvelle session | Claude Code |
| `Ctrl+Tab` | Session suivante | Claude Code |
| `Ctrl+Shift+Tab` | Session précédente | Claude Code |
| `Ctrl+/` | Toggle commentaire | IDE standard |
| `Ctrl+Shift+P` | Paramètres | VS Code |
| `Ctrl+F` | Recherche dans le chat | Standard |
| `Escape` | Arrêter le streaming | ChatGPT/Claude |

**Mode Vim :**
- **Priorité BASSE** — Implémentable via un éditeur web (CodeMirror supporte Vim mode)
- Ajouter une option dans les paramètres

### 5.4 Système de Thèmes (Dark/Light/Custom)

**État actuel GenericAgent :**
- Thème dark uniquement avec constantes dans `theme.py`
- Palette codée en dur

**Recommandations :**
1. **Système de thème dynamique** :
   ```python
   THEMES = {
       "dark": {
           "bg": QColor(14, 14, 18),
           "panel": QColor(20, 20, 24, 248),
           "text": "#e4e4e7",
           "accent": "#7c3aed",
           # ...
       },
       "light": {
           "bg": QColor(255, 255, 255),
           "panel": QColor(245, 245, 247),
           "text": "#18181b",
           "accent": "#6d28d9",
           # ...
       },
       "catppuccin": { ... },
       "nord": { ... },
   }
   ```
2. **Détection automatique** du thème système (Windows : registre, macOS : NSAppleScript, Linux : gsettings)
3. **Switch rapide** : `Ctrl+K` → « Toggle Theme » dans la command palette
4. **Thème custom** : fichier JSON éditable par l'utilisateur

### 5.5 Système de Notification pour les Tâches Longues

**Problème** : Les tâches d'agent peuvent prendre plusieurs minutes. L'utilisateur peut changer de fenêtre.

**Solutions :**
1. **Notification système** via `QSystemTrayIcon.showMessage()`
2. **Badge sur l'icône** dans la barre des tâches (Windows : overlay icon)
3. **Son de notification** configurable
4. **Indicateur de progression** dans la barre de titre : « [GenericAgent] Réflexion... (45s) »

**Implémentation Qt :**
```python
class NotificationManager:
    def __init__(self, tray_icon: QSystemTrayIcon):
        self._tray = tray_icon
    
    def notify_task_complete(self, title: str, message: str):
        self._tray.showMessage(
            title, message,
            QSystemTrayIcon.Information, 5000
        )
    
    def notify_approval_needed(self, action: str):
        self._tray.showMessage(
            "Approbation requise", action,
            QSystemTrayIcon.Warning, 0  # persistant
        )
```

### 5.6 Command Palette (Actions Rapides)

**Le pattern de VS Code adopté par tous les outils IA en 2025-2026 :**

- `Ctrl+K` (ou `Cmd+K`) ouvre un overlay modal avec champ de recherche
- Liste fuzzy-searchable de toutes les commandes disponibles
- Catégories : Actions, Navigation, Paramètres, Outils
- Raccourcis affichés à côté de chaque commande

**Implémentation Qt :**
```python
class CommandPalette(QDialog):
    """Palette de commandes inspirée de VS Code."""
    
    def __init__(self, parent):
        super().__init__(parent, Qt.Popup)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Popup)
        # Layout :
        # [Champ de recherche QLineEdit]
        # [Liste filtrée QListView]
        # Modèle : liste de {name, shortcut, category, callback}
```

**Commandes recommandées :**
- Nouvelle conversation
- Changer de modèle IA
- Toggle thème dark/light
- Toggle mode autonome
- Rechercher dans l'historique
- Exporter la conversation
- Effacer la conversation
- Ouvrir les paramètres
- Toggle terminal

---

## 6. Recommandations Qt/PySide6

### 6.1 QWebEngineView pour le Rendu Markdown Riche

**Pourquoi remplacer QTextBrowser :**

| Critère | QTextBrowser | QWebEngineView |
|---|---|---|
| Coloration syntaxique | ❌ Non | ✅ highlight.js / Prism.js |
| Diagrammes Mermaid | ❌ Non | ✅ mermaid.js |
| LaTeX / Math | ❌ Non | ✅ KaTeX / MathJax |
| CSS riche | ⚠️ Limité | ✅ Complet |
| Performance streaming | ✅ Bonne | ⚠️ Overhead initial |
| Communication Python↔JS | ❌ N/A | ✅ QWebChannel |
| Copy/presse-papier | ✅ Natif | ⚠️ Nécessite QWebChannel |

**Architecture recommandée :**

```python
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel

class MarkdownView(QWebEngineView):
    """Widget de rendu markdown basé sur Chromium."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Canal de communication Python ↔ JavaScript
        self._channel = QWebChannel()
        self._bridge = JSBridge()
        self._channel.registerObject("pybridge", self._bridge)
        self.page().setWebChannel(self._channel)
        
        # Charger le template HTML avec markdown-it + highlight.js
        self.setHtml(self._build_html_template())
    
    def set_markdown(self, text: str):
        """Met à jour le contenu markdown via JavaScript."""
        js = f"renderMarkdown({json.dumps(text)})"
        self.page().runJavaScript(js)
    
    def append_streaming_chunk(self, text: str):
        """Ajoute un chunk de streaming."""
        js = f"appendChunk({json.dumps(text)})"
        self.page().runJavaScript(js)


class JSBridge(QObject):
    """Pont Python ↔ JavaScript pour les actions côté navigateur."""
    
    copyToClipboard = Signal(str)
    
    @Slot(str)
    def copyCode(self, code: str):
        self.copyToClipboard.emit(code)
```

**Template HTML recommandé :**
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <script src="qrc:/js/markdown-it.min.js"></script>
    <script src="qrc:/js/highlight.min.js"></script>
    <script src="qrc:/js/mermaid.min.js"></script>
    <script src="qrc:/js/katex.min.js"></script>
    <script src="qrc:/js/qwebchannel.js"></script>
    <style>
        /* Thème CSS dynamique injecté depuis Python */
        {{THEME_CSS}}
    </style>
</head>
<body>
    <div id="content"></div>
    <script>
        const md = markdownit({
            highlight: (str, lang) => {
                if (lang && hljs.getLanguage(lang)) {
                    return hljs.highlight(str, {language: lang}).value;
                }
                return hljs.highlightAuto(str).value;
            }
        });
        
        function renderMarkdown(text) {
            document.getElementById('content').innerHTML = md.render(text);
        }
        
        function appendChunk(text) {
            // Rendu progressif pour le streaming
        }
        
        function copyCode(btn) {
            const code = btn.closest('.code-block').querySelector('code').textContent;
            new QWebChannel(qt.webChannelTransport, (channel) => {
                channel.objects.pybridge.copyCode(code);
            });
        }
    </script>
</body>
</html>
```

### 6.2 Widgets Personnalisés pour le Statut de l'Agent

**Widget d'indicateur de statut animé :**

```python
from PySide6.QtCore import QPropertyAnimation, QEasingCurve

class StatusIndicator(QWidget):
    """Indicateur de statut animé (pulsation, rotation, etc.)."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pulse_anim = QPropertyAnimation(self, b"opacity")
        self._pulse_anim.setDuration(1200)
        self._pulse_anim.setStartValue(0.3)
        self._pulse_anim.setEndValue(1.0)
        self._pulse_anim.setEasingCurve(QEasingCurve.InOutSine)
        self._pulse_anim.setLoopCount(-1)  # infini
    
    def set_state(self, state: str):
        """Change l'état et démarre/arrête l'animation."""
        if state in ("thinking", "acting", "waiting"):
            self._pulse_anim.start()
        else:
            self._pulse_anim.stop()
        self.update()
```

### 6.3 Animations avec QPropertyAnimation

**Animations recommandées :**

1. **Apparition des messages** : fade-in + slide-up (200ms, ease-out)
2. **Dépliage des sections** : animation de hauteur (300ms, ease-in-out)
3. **Badge de streaming** : pulsation d'opacité (1200ms, infinite)
4. **Transition de thème** : fondu crossfade (400ms)
5. **Apparition de la palette de commandes** : scale + fade (150ms, ease-out)
6. **Indicateur de statut** : pulsation ou rotation selon l'état

```python
def animate_widget_appear(widget: QWidget, duration=200):
    """Anime l'apparition d'un widget."""
    anim = QPropertyAnimation(widget, b"windowOpacity")
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.start(QPropertyAnimation.DeleteWhenStopped)
```

### 6.4 Intégration System Tray

**Fonctionnalités recommandées :**

```python
class SystemTrayIcon(QSystemTrayIcon):
    """Icône de barre système avec menu contextuel."""
    
    def __init__(self, app, chat_panel):
        super().__init__(QIcon(":/icon.png"), app)
        self._panel = chat_panel
        
        menu = QMenu()
        menu.addAction("Ouvrir", self._show_panel)
        menu.addAction("Nouvelle conversation", self._new_conversation)
        menu.addSeparator()
        menu.addAction("Mode autonome", self._toggle_autonomous)
        menu.addSeparator()
        menu.addAction("Quitter", app.quit)
        
        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)
        
        # Notification pour les tâches longues
        # self.showMessage(title, message, icon, duration)
```

### 6.5 Intégration OS Native

**Windows :**
- `QWinTaskbarButton` / `QWinTaskbarProgress` : progression dans la barre des tâches
- Jump list pour les conversations récentes
- Toast notifications via WinRT

**macOS :**
- `NSUserNotification` pour les notifications système
- Touch Bar integration (si applicable)
- Menu bar icon

**Linux :**
- `QDBusInterface` pour les notifications freedesktop
- AppIndicator pour la barre système

---

## 7. Recommandations Priorisées pour GenericAgent

### Analyse de l'Existant

L'application GenericAgent dispose déjà de :
- ✅ **FloatingButton** animé avec glow et états visuels (idle/running)
- ✅ **ChatPage** avec streaming, pièces jointes, recherche dans la conversation
- ✅ **StreamHandler** découplé avec callbacks
- ✅ **SessionManager** avec historique, tokens, mode autonome
- ✅ **_MsgRow** avec avatar, markdown, boutons copier/régénérer
- ✅ **Thème dark** avec CSS markdown
- ✅ **HistoryPage**, **SettingsPage**, **SopPage**

### Lacunes Identifiées vs. État de l'Art

1. ❌ Pas de visualisation des tool calls
2. ❌ Pas de vue split (éditeur/preview)
3. ❌ Pas de rendu markdown riche (pas de coloration syntaxique, Mermaid, LaTeX)
4. ❌ Pas de dialogue d'approbation pour les actions dangereuses
5. ❌ Pas d'affichage du raisonnement (thinking)
6. ❌ Pas de command palette
7. ❌ Pas de drag-and-drop de fichiers
8. ❌ Pas de notifications système
9. ❌ Pas de thème clair / custom
10. ❌ Pas de sidebar multi-session
11. ❌ Pas de terminal intégré
12. ❌ Pas de timeline d'actions
13. ❌ Pas de branchement de conversation
14. ⚠️ Token estimation basique (ratio chars/tokens)

### Priorisation (Impact × Effort)

| # | Fonctionnalité | Impact | Effort | Priorité |
|---|---|---|---|---|
| 1 | **Visualisation des Tool Calls** | ⭐⭐⭐⭐⭐ | 🔧🔧🔧 | **P0 — Critique** |
| 2 | **Dialogue d'Approbation** | ⭐⭐⭐⭐⭐ | 🔧🔧 | **P0 — Critique** |
| 3 | **Rendu Markdown Riche (QWebEngineView)** | ⭐⭐⭐⭐⭐ | 🔧🔧🔧🔧 | **P0 — Critique** |
| 4 | **Affichage du Raisonnement (Thinking)** | ⭐⭐⭐⭐ | 🔧🔧 | **P1 — Important** |
| 5 | **Indicateurs de Statut Agent** | ⭐⭐⭐⭐ | 🔧🔧 | **P1 — Important** |
| 6 | **Vue Split (Chat + Éditeur)** | ⭐⭐⭐⭐⭐ | 🔧🔧🔧🔧🔧 | **P1 — Important** |
| 7 | **Command Palette** | ⭐⭐⭐⭐ | 🔧🔧 | **P1 — Important** |
| 8 | **Drag-and-Drop Fichiers** | ⭐⭐⭐ | 🔧 | **P2 — Souhaité** |
| 9 | **Notifications Système** | ⭐⭐⭐ | 🔧 | **P2 — Souhaité** |
| 10 | **Thème Light / Custom** | ⭐⭐⭐ | 🔧🔧 | **P2 — Souhaité** |
| 11 | **Sidebar Multi-Session** | ⭐⭐⭐⭐ | 🔧🔧🔧🔧 | **P2 — Souhaité** |
| 12 | **Terminal Intégré** | ⭐⭐⭐⭐ | 🔧🔧🔧🔧 | **P2 — Souhaité** |
| 13 | **Timeline d'Actions** | ⭐⭐⭐ | 🔧🔧🔧 | **P3 — Futur** |
| 14 | **Branchement de Conversation** | ⭐⭐⭐ | 🔧🔧🔧🔧 | **P3 — Futur** |
| 15 | **Mode Vim** | ⭐⭐ | 🔧🔧🔧 | **P3 — Futur** |

---

## 8. Feuille de Route d'Implémentation

### Phase 1 — Fondations Agent UI (2-3 semaines)

**Objectif** : Transformer GenericAgent d'un chatbot en une véritable interface d'agent.

1. **ToolCallWidget** — Widget réductible pour afficher les appels d'outils
   - États : pending, success, error
   - Icônes par type d'outil
   - Inséré dans le flux de conversation
   - Fichier : `frontends/qt/widgets.py` (ajout)

2. **ApprovalDialog** — Dialogue modal pour les actions dangereuses
   - Niveaux de risque : low, medium, high, critical
   - Options : Autoriser, Refuser, Toujours autoriser
   - Fichier : `frontends/qt/widgets.py` (ajout)

3. **ThinkingSection** — Section rétractable pour le raisonnement
   - Détection automatique des balises `<thinking>` 
   - Animation de dépliage
   - Affichage de la durée
   - Fichier : `frontends/qt/widgets.py` (ajout)

4. **AgentStatusBar** — Indicateur d'état de l'agent
   - 6 états visuels (idle, thinking, acting, waiting, error, streaming)
   - Animations QPropertyAnimation
   - Fichier : `frontends/qt/widgets.py` (ajout)

5. **Mise à jour de agent_loop.py** — Émettre des événements de tool_call
   - Nouveaux types dans la display_queue : `{"tool_call": {...}}`, `{"tool_result": {...}}`
   - Événements `{"thinking_start": ...}`, `{"thinking_end": ...}`

### Phase 2 — Rendu Riche et Productivité (2-3 semaines)

1. **MarkdownView** — Remplacement de QTextBrowser par QWebEngineView
   - markdown-it + highlight.js + mermaid.js
   - QWebChannel pour copier le code
   - Streaming progressif via JavaScript
   - Fichier : `frontends/qt/markdown_view.py` (nouveau)

2. **CommandPalette** — Recherche rapide de commandes
   - `Ctrl+K` pour ouvrir
   - Fuzzy search
   - Catégories de commandes
   - Fichier : `frontends/qt/command_palette.py` (nouveau)

3. **Drag-and-Drop** — Support du glisser-déposer de fichiers
   - Sur ChatPage et la zone de saisie
   - Aperçu miniature des images
   - Fichier : modification de `chat_page.py`

4. **Notifications Système** — QSystemTrayIcon avec messages
   - Notification de fin de tâche
   - Notification d'approbation requise
   - Badge de progression dans la barre des tâches
   - Fichier : `frontends/qt/tray_icon.py` (nouveau)

### Phase 3 — Layout Avancé et Thèmes (3-4 semaines)

1. **Thème Dynamique** — Système de thèmes switchable
   - Dark (existant), Light, Catppuccin, Nord
   - Détection auto du thème OS
   - Sauvegarde de la préférence
   - Fichier : refonte de `theme.py`

2. **Vue Split** — Layout à panneaux divisés
   - QSplitter horizontal : Chat | Éditeur | Preview
   - Éditeur : QWebEngineView avec CodeMirror
   - Preview : QWebEngineView pour rendu HTML
   - Sauvegarde des proportions
   - Fichiers : `frontends/qt/split_view.py` (nouveau), `frontends/qt/editor_panel.py` (nouveau)

3. **Sidebar Multi-Session** — Gestion de sessions parallèles
   - Modèle inspiré de Claude Code
   - Filtrage par statut et projet
   - Raccourcis Ctrl+Tab / Ctrl+N
   - Fichier : refonte de `history_page.py`

### Phase 4 — Fonctionnalités Avancées (4+ semaines)

1. **Terminal Intégré** — QTermWidget ou QWebEngineView avec xterm.js
2. **Timeline d'Actions** — Panneau chronologique des opérations
3. **Branchement de Conversation** — Édition et forking des messages
4. **Navigateur de Fichiers** — QTreeView avec QFileSystemModel
5. **Panneau de Gestion des Outils** — Configuration et stats

---

## Annexe A : Comparatif des Layouts des Principales Applications

| Application | Layout | Split View | Terminal | File Tree | Multi-Session |
|---|---|---|---|---|---|
| ChatGPT Desktop | Sidebar + Chat + Canvas | ✅ (Canvas) | ❌ | ❌ | ❌ (tabs) |
| Claude Code | Sidebar + Chat + Editor + Terminal | ✅ (3 panneaux) | ✅ | ✅ | ✅ (sidebar) |
| Cursor | Sidebar + Editor + Chat | ✅ (3 panneaux) | ✅ | ✅ | ✅ (tabs) |
| Windsurf | Sidebar + Editor + Cascade | ✅ (3 panneaux) | ✅ | ✅ | ❌ |
| Devin | Chat + Timeline + Terminal + Preview | ✅ (4 zones) | ✅ | ✅ | ✅ |
| Replit Agent | Chat + Editor + Preview + Terminal | ✅ (4 panneaux) | ✅ | ✅ | ✅ (tabs) |
| **GenericAgent (cible)** | **Sidebar + Chat + Editor + Preview** | **✅ (3 panneaux)** | **✅** | **✅** | **✅ (sidebar)** |

## Annexe B : Ressources Qt/PySide6 Utiles

| Ressource | Usage |
|---|---|
| `QWebEngineView` | Rendu markdown riche, éditeur de code, preview navigateur |
| `QWebChannel` | Communication Python ↔ JavaScript |
| `QSplitter` | Layout redimensionnable multi-panneaux |
| `QPropertyAnimation` | Animations fluides (fade, slide, pulse) |
| `QSystemTrayIcon` | Icône de barre système + notifications |
| `QTreeView + QFileSystemModel` | Navigateur de fichiers |
| `QShortcut` | Raccourcis clavier globaux |
| `QDialog` | Dialogues modaux (approbation, command palette) |
| `QStackedWidget` | Navigation entre pages (chat, settings, outils) |
| `QProgressBar` | Indicateurs de progression |
| `QGraphicsOpacityEffect` | Effets de transparence pour les animations |
| `QSettings` | Persistance des préférences utilisateur |
| `QScreen.availableGeometry` | Positionnement intelligent des fenêtres |

## Annexe C : Bibliothèques JavaScript Recommandées (pour QWebEngineView)

| Bibliothèque | Usage | Taille |
|---|---|---|
| markdown-it | Parseur Markdown extensible | ~50KB |
| highlight.js | Coloration syntaxique (190+ langages) | ~70KB |
| mermaid.js | Diagrammes (flowchart, sequence, class) | ~400KB |
| KaTeX | Rendu LaTeX mathématique | ~150KB |
| CodeMirror 6 | Éditeur de code inline | ~200KB |
| xterm.js | Terminal émulé dans le navigateur | ~150KB |
| markmap | Mind maps depuis markdown | ~100KB |

---

*Ce rapport est basé sur l'analyse de 23 recherches web, 5 lectures d'articles détaillés, et l'audit complet du code source GenericAgent (frontends/qt/). Les recommandations tiennent compte de l'architecture existante et proposent une feuille de route progressive et réaliste.*
