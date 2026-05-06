"""
Gestionnaire de sessions — logique métier pure, sans dépendance Qt.

Ce module extrait la gestion des sessions de ``ChatPanel`` (qtapp.py)
afin de la rendre testable indépendamment de l'interface graphique.

Responsabilités :
- État de la session courante (messages, dictionnaire de session, historique, fichiers en attente)
- Opérations de session : nouvelle, sauvegarde, sauvegarde automatique, effacement, restauration, suppression
- Estimation de l'utilisation de tokens
- État et bascule du mode autonome
- Suivi de l'heure de la dernière réponse

Extrait de qtapp.py pour la refonte modulaire (Phase 3).
"""
from __future__ import annotations

import time
import logging
from datetime import datetime
from typing import Optional

from frontends.qt.utils import (
    _make_session_id,
    _load_history,
    _save_history,
    _estimate_token_usage,
    _format_token_label,
    _auto_title_session,
    _merge_session_into_history,
)

logger = logging.getLogger(__name__)


class SessionManager:
    """Gestionnaire de sessions de conversation — logique métier pure.

    Cette classe encapsule tout l'état et les opérations liés à la gestion
    des sessions de chat. Elle ne dépend d'aucun composant Qt et peut être
    testée unitairement de manière isolée.

    Attributs
    ---------
    messages : list[dict]
        Liste des messages de la conversation courante.
        Chaque message est un dict avec les clés ``role`` et ``content``.
    session : dict
        Dictionnaire de la session courante (id, title, messages, updatedAt).
    history : list[dict]
        Historique des sessions sauvegardées.
    pending_files : list[dict]
        Fichiers en attente d'envoi. Chaque dict contient
        ``name``, ``type`` et ``raw``.
    autonomous_enabled : bool
        Indique si le mode autonome est activé.
    last_reply_time : float
        Horodatage (``time.time()``) de la dernière réponse de l'assistant.
    streaming_text : str
        Texte en cours de streaming (pour l'estimation des tokens de sortie).
    is_streaming : bool
        Indique si un streaming est en cours.
    """

    def __init__(self) -> None:
        """Initialise le gestionnaire de sessions avec un état vide."""
        self._messages: list[dict] = []
        self._session: dict = {
            "id": _make_session_id(),
            "title": "Nouvelle conversation",
            "messages": [],
        }
        self._history: list[dict] = _load_history()
        self._pending_files: list[dict] = []  # {'name', 'type', 'raw'}

        # Mode autonome
        self.autonomous_enabled: bool = False
        self.last_reply_time: float = time.time()

        # État du streaming (utilisé pour l'estimation des tokens)
        self.streaming_text: str = ""
        self.is_streaming: bool = False

    # ── Propriétés en lecture seule ─────────────────────────────────────────

    @property
    def messages(self) -> list[dict]:
        """Liste des messages de la conversation courante."""
        return self._messages

    @property
    def session(self) -> dict:
        """Dictionnaire de la session courante."""
        return self._session

    @property
    def history(self) -> list[dict]:
        """Historique des sessions sauvegardées."""
        return self._history

    @property
    def pending_files(self) -> list[dict]:
        """Fichiers en attente d'envoi."""
        return self._pending_files

    # ── Opérations de session ───────────────────────────────────────────────

    def auto_save(self) -> None:
        """Sauvegarde automatique de la session courante.

        Génère un titre automatique si celui-ci est encore « Nouvelle conversation »,
        puis appelle :meth:`save_session`. Ne fait rien si la conversation est vide.

        Notes
        -----
        Cette méthode est appelée automatiquement lors de la création d'une
        nouvelle session pour sauvegarder la session précédente.
        """
        if not self._messages:
            logger.debug("auto_save : conversation vide, rien à sauvegarder")
            return
        self._session["title"] = _auto_title_session(self._session, self._messages)
        logger.info(
            "auto_save : sauvegarde de la session « %s » (id=%s)",
            self._session["title"],
            self._session["id"],
        )
        self.save_session()

    def save_session(self) -> None:
        """Sauvegarde la session courante dans l'historique.

        Copie les messages courants dans le dictionnaire de session,
        met à jour l'horodatage ``updatedAt``, recharge l'historique
        depuis le disque (pour fusionner avec d'éventuelles modifications
        externes), y fusionne la session, puis sauvegarde l'historique.

        Ne fait rien si la conversation est vide.
        """
        if not self._messages:
            logger.debug("save_session : conversation vide, rien à sauvegarder")
            return
        self._session["messages"] = self._messages.copy()
        self._session["updatedAt"] = datetime.now().isoformat()
        self._history = _load_history()
        self._history = _merge_session_into_history(self._history, self._session)
        _save_history(self._history)
        logger.info(
            "save_session : session « %s » sauvegardée (%d messages)",
            self._session.get("title", "Sans titre"),
            len(self._messages),
        )

    def clear_session(self) -> None:
        """Efface la conversation courante et réinitialise la session.

        Vide la liste des messages, crée un nouvel identifiant de session,
        réinitialise le titre à « Nouvelle conversation » et efface les
        messages stockés dans le dictionnaire de session. Les fichiers
        en attente sont également effacés.

        Notes
        -----
        Cette méthode ne sauvegarde PAS la session avant de l'effacer.
        Appelez :meth:`save_session` ou :meth:`auto_save` au préalable
        si vous souhaitez conserver la conversation.
        """
        self._messages.clear()
        self._session = {
            "id": _make_session_id(),
            "title": "Nouvelle conversation",
            "messages": [],
        }
        self._pending_files.clear()
        self.streaming_text = ""
        self.is_streaming = False
        logger.info("clear_session : conversation effacée, nouvelle session créée")

    def new_session(self) -> None:
        """Crée une nouvelle session après avoir sauvegardé la précédente.

        Si la conversation courante contient des messages, elle est
        sauvegardée automatiquement (via :meth:`auto_save`) avant d'être
        effacée. Sinon, la session est simplement réinitialisée.

        Cette opération correspond au bouton « Nouvelle conversation »
        de l'interface.
        """
        if self._messages:
            self.auto_save()
        self.clear_session()

    # ── Restauration et suppression ─────────────────────────────────────────

    def restore_session(self, session_dict: dict) -> Optional[list[dict]]:
        """Restaure une session à partir de son dictionnaire.

        Remplace la session courante par celle fournie, reconstruit
        la liste des messages à partir des données du dictionnaire
        et recharge l'historique depuis le disque.

        Paramètres
        ----------
        session_dict : dict
            Dictionnaire de session contenant au moins les clés ``id``,
            ``title`` et ``messages``.

        Retourne
        --------
        list[dict] | None
            La liste des messages restaurés, ou ``None`` si le
            dictionnaire est invalide.

        Notes
        -----
        L'appelant est responsable de la mise à jour de l'interface
        graphique (reconstruction des widgets de message, mise à jour
        du label de tokens, etc.) après cette opération.
        """
        if not session_dict:
            logger.warning("restore_session : dictionnaire de session vide")
            return None

        self._session = session_dict.copy()
        self._messages = session_dict.get("messages", []).copy()
        self._pending_files.clear()
        self.streaming_text = ""
        self.is_streaming = False
        self._history = _load_history()
        logger.info(
            "restore_session : session « %s » restaurée (%d messages)",
            self._session.get("title", "Sans titre"),
            len(self._messages),
        )
        return self._messages

    def delete_session(self, session_id: str) -> bool:
        """Supprime une session de l'historique par son identifiant.

        Recherche la session dans l'historique, la supprime si elle
        existe, puis sauvegarde l'historique mis à jour.

        Paramètres
        ----------
        session_id : str
            Identifiant de la session à supprimer.

        Retourne
        --------
        bool
            ``True`` si la session a été trouvée et supprimée,
            ``False`` sinon.
        """
        initial_len = len(self._history)
        self._history = [
            h for h in self._history if h.get("id") != session_id
        ]
        if len(self._history) < initial_len:
            _save_history(self._history)
            logger.info(
                "delete_session : session id=%s supprimée de l'historique",
                session_id,
            )
            return True
        logger.warning(
            "delete_session : session id=%s introuvable dans l'historique",
            session_id,
        )
        return False

    # ── Utilisation de tokens ───────────────────────────────────────────────

    def update_token_usage(self) -> dict[str, int]:
        """Estime l'utilisation de tokens pour la conversation courante.

        Prend en compte les messages existants ainsi que le texte en cours
        de streaming (le cas échéant). Le calcul est une estimation basée
        sur le ratio caractères/tokens.

        Retourne
        --------
        dict[str, int]
            Dictionnaire avec les clés ``in_tokens`` et ``out_tokens``
            représentant l'estimation des tokens d'entrée et de sortie.

        Exemple
        -------
        >>> mgr = SessionManager()
        >>> mgr._messages = [{"role": "user", "content": "Bonjour"}]
        >>> mgr.update_token_usage()
        {'in_tokens': 3, 'out_tokens': 0}
        """
        usage = _estimate_token_usage(
            self._messages,
            self.streaming_text,
            self.is_streaming,
        )
        logger.debug(
            "update_token_usage : in=%d, out=%d",
            usage["in_tokens"],
            usage["out_tokens"],
        )
        return usage

    def get_token_label(self) -> str:
        """Génère le label d'affichage de l'utilisation de tokens.

        Retourne
        --------
        str
            Chaîne formatée pour la barre de statut, ou chaîne vide
            si aucun token n'a été consommé.
        """
        usage = self.update_token_usage()
        return _format_token_label(usage["in_tokens"], usage["out_tokens"])

    # ── Mode autonome ───────────────────────────────────────────────────────

    def toggle_autonomous(self) -> bool:
        """Bascule l'état du mode autonome.

        Active ou désactive le mode autonome et met à jour l'horodatage
        de la dernière réponse.

        Retourne
        --------
        bool
            Le nouvel état du mode autonome (``True`` = activé).
        """
        self.autonomous_enabled = not self.autonomous_enabled
        self.last_reply_time = time.time()
        state_str = "activé" if self.autonomous_enabled else "désactivé"
        logger.info("toggle_autonomous : mode autonome %s", state_str)
        return self.autonomous_enabled

    def is_idle_timeout(self, timeout_seconds: float = 1800.0) -> bool:
        """Vérifie si le délai d'inactivité est dépassé.

        Paramètres
        ----------
        timeout_seconds : float
            Délai d'inactivité en secondes (défaut : 1800 = 30 minutes).

        Retourne
        --------
        bool
            ``True`` si le délai est dépassé et que le mode autonome
            est activé, ``False`` sinon.
        """
        if not self.autonomous_enabled:
            return False
        elapsed = time.time() - self.last_reply_time
        return elapsed >= timeout_seconds

    # ── Dernier message utilisateur ─────────────────────────────────────────

    def get_last_user_message(self) -> Optional[str]:
        """Récupère le contenu du dernier message utilisateur.

        Parcourt la liste des messages en ordre inverse et retourne
        le contenu du premier message dont le rôle est ``user``.

        Retourne
        --------
        str | None
            Le contenu du dernier message utilisateur, ou ``None``
            s'il n'y a pas de message utilisateur.
        """
        for msg in reversed(self._messages):
            if msg.get("role") == "user":
                return msg.get("content")
        return None

    # ── Messages pour le contexte LLM ────────────────────────────────────────

    def get_messages_for_llm(self) -> list[dict]:
        """Retourne les messages à inclure dans le contexte envoyé au LLM.

        Exclut les messages marqués comme interrompus
        (``is_interrupted=True``), car ils ne constituent pas une
        réponse complète de l'assistant et pourraient induire le
        modèle en erreur.

        Retourne
        --------
        list[dict]
            Liste de dictionnaires ``{'role': str, 'content': str}``
            sans les messages interrompus.
        """
        return [
            {"role": m["role"], "content": m["content"]}
            for m in self._messages
            if not m.get("is_interrupted", False)
        ]

    # ── Ajout de messages ───────────────────────────────────────────────────

    def add_message(self, role: str, content: str,
                    is_interrupted: bool = False) -> None:
        """Ajoute un message à la conversation courante.

        Met également à jour le titre de la session si celui-ci est
        encore « Nouvelle conversation » et que le message est un
        message utilisateur.

        Paramètres
        ----------
        role : str
            Rôle du message (``user``, ``assistant``, ``system``).
        content : str
            Contenu textuel du message.
        is_interrupted : bool
            Si ``True``, le message a été interrompu manuellement
            (arrêt du stream). Ces messages sont exclus du contexte
            envoyé au LLM via :meth:`get_messages_for_llm`.
        """
        msg = {"role": role, "content": content}
        if is_interrupted:
            msg["is_interrupted"] = True
        self._messages.append(msg)
        # Mise à jour automatique du titre au premier message utilisateur
        if (
            role == "user"
            and self._session.get("title") == "Nouvelle conversation"
            and content
        ):
            self._session["title"] = content[:20] + ("..." if len(content) > 20 else "")
        # Mise à jour du temps de dernière réponse
        if role == "assistant" and not is_interrupted:
            self.last_reply_time = time.time()

    # ── Gestion des fichiers en attente ─────────────────────────────────────

    def add_pending_file(self, name: str, file_type: str, raw: bytes) -> None:
        """Ajoute un fichier en attente d'envoi.

        Paramètres
        ----------
        name : str
            Nom du fichier.
        file_type : str
            Type MIME du fichier (ex: ``image/png``, ``text/plain``).
        raw : bytes
            Contenu brut du fichier.
        """
        # Éviter les doublons par nom de fichier
        if any(f["name"] == name for f in self._pending_files):
            logger.debug("add_pending_file : fichier %s déjà en attente, ignoré", name)
            return
        self._pending_files.append({"name": name, "type": file_type, "raw": raw})
        logger.debug("add_pending_file : fichier %s ajouté (%d octets)", name, len(raw))

    def clear_pending_files(self) -> None:
        """Efface la liste des fichiers en attente d'envoi."""
        self._pending_files.clear()
        logger.debug("clear_pending_files : fichiers en attente effacés")

    # ── Rechargement de l'historique ────────────────────────────────────────

    def reload_history(self) -> list[dict]:
        """Recharge l'historique des sessions depuis le disque.

        Retourne
        --------
        list[dict]
            La liste mise à jour des sessions sauvegardées.
        """
        self._history = _load_history()
        return self._history
