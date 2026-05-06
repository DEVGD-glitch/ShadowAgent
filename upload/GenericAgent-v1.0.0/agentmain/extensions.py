"""
GenericAgent v0.6.0 — Système d'extensions et gestion du contexte.

Ce module fournit un cadre de cycle de vie des extensions inspiré de pi-mono,
ainsi qu'un moteur de gestion fine de la fenêtre de contexte avec compactage.
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence

logger = logging.getLogger("ga.agentmain.extensions")


# ---------------------------------------------------------------------------
# ExtensionHook — Points d'accroche du cycle de vie
# ---------------------------------------------------------------------------

class ExtensionHook(Enum):
    """Énumération des points d'accroche disponibles pour les extensions."""

    ON_BEFORE_TOOL_CALL = "on_before_tool_call"
    ON_AFTER_TOOL_CALL = "on_after_tool_call"
    ON_AFTER_RESPONSE = "on_after_response"
    ON_COMPACTION = "on_compaction"
    ON_SESSION_START = "on_session_start"
    ON_SESSION_END = "on_session_end"
    ON_ERROR = "on_error"


# ---------------------------------------------------------------------------
# Extension — Représentation d'une extension enregistrée
# ---------------------------------------------------------------------------

@dataclass
class Extension:
    """Représente une extension du cycle de vie de l'agent.

    Attributs :
        name: Identifiant unique de l'extension.
        version: Version sémantique de l'extension (ex. « 1.0.0 »).
        description: Description humaine de l'extension.
        hooks: Dictionnaire associant un point d'accroche à une fonction callback.
        config: Paramètres de configuration propres à l'extension.
    """

    name: str
    version: str = "0.1.0"
    description: str = ""
    hooks: Dict[ExtensionHook, Callable] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Le nom de l'extension ne peut pas être vide.")

    def has_hook(self, hook_type: ExtensionHook) -> bool:
        """Retourne True si l'extension écoute le point d'accroche donné."""
        return hook_type in self.hooks


# ---------------------------------------------------------------------------
# ExtensionManager — Registre et orchestrateur des extensions
# ---------------------------------------------------------------------------

class ExtensionManager:
    """Gestionnaire central du cycle de vie des extensions.

    Permet d'enregistrer, de désenregistrer et de déclencher des extensions
    sur les différents points d'accroche du cycle de vie de l'agent.
    """

    def __init__(self) -> None:
        self._extensions: Dict[str, Extension] = {}
        logger.info("ExtensionManager initialisé.")

    # -- Enregistrement -----------------------------------------------------

    def register(self, extension: Extension) -> None:
        """Enregistre une extension dans le gestionnaire.

        Args:
            extension: L'extension à enregistrer.

        Raises:
            ValueError: Si une extension avec le même nom existe déjà.
        """
        if extension.name in self._extensions:
            raise ValueError(
                f"L'extension « {extension.name} » est déjà enregistrée."
            )
        self._extensions[extension.name] = extension
        logger.info(
            "Extension enregistrée : %s v%s — %s",
            extension.name,
            extension.version,
            extension.description,
        )

    def unregister(self, name: str) -> None:
        """Retire une extension du gestionnaire par son nom.

        Args:
            name: Nom de l'extension à retirer.

        Raises:
            KeyError: Si aucune extension portant ce nom n'existe.
        """
        if name not in self._extensions:
            raise KeyError(f"Aucune extension nommée « {name} » n'est enregistrée.")
        removed = self._extensions.pop(name)
        logger.info("Extension désenregistrée : %s", removed.name)

    # -- Déclenchement ------------------------------------------------------

    async def fire_hook(self, hook_type: ExtensionHook, **kwargs: Any) -> Dict[str, Any]:
        """Déclenche toutes les callbacks enregistrées pour un point d'accroche.

        Les callbacks peuvent être synchrones ou asynchrones. Elles reçoivent
        les arguments nommés transmis et peuvent retourner un dictionnaire de
        modifications qui sera fusionné dans le contexte partagé.

        Args:
            hook_type: Le point d'accroche à déclencher.
            **kwargs: Arguments transmis à chaque callback.

        Returns:
            Un dictionnaire agrégeant les résultats non-nuls de chaque callback.
        """
        combined: Dict[str, Any] = {}
        for ext in self._extensions.values():
            callback = ext.hooks.get(hook_type)
            if callback is None:
                continue
            try:
                logger.debug(
                    "Déclenchement %s pour l'extension %s",
                    hook_type.value,
                    ext.name,
                )
                result = callback(**kwargs)
                if asyncio.iscoroutine(result):
                    result = await result
                if isinstance(result, dict):
                    combined.update(result)
            except Exception as exc:
                logger.error(
                    "Erreur dans le hook %s de l'extension %s : %s",
                    hook_type.value,
                    ext.name,
                    exc,
                )
                # Propager l'erreur aux hooks ON_ERROR
                await self.fire_hook(
                    ExtensionHook.ON_ERROR,
                    extension_name=ext.name,
                    hook_type=hook_type,
                    error=exc,
                )
        return combined

    # -- Liste --------------------------------------------------------------

    def list_extensions(self) -> List[Extension]:
        """Retourne la liste des extensions enregistrées."""
        return list(self._extensions.values())

    def get_extension(self, name: str) -> Optional[Extension]:
        """Récupère une extension par son nom, ou None."""
        return self._extensions.get(name)

    def __len__(self) -> int:
        return len(self._extensions)

    def __contains__(self, name: str) -> bool:
        return name in self._extensions


# ---------------------------------------------------------------------------
# ContextEngine — Gestion fine de la fenêtre de contexte
# ---------------------------------------------------------------------------

class ContextEngine:
    """Moteur de gestion de la fenêtre de contexte avec compactage automatique.

    Surveille l'utilisation des tokens et déclenche un compactage lorsque
    le seuil configuré est atteint. Plusieurs stratégies de compactage sont
    disponibles pour préserver les informations pertinentes.

    Args:
        max_context_tokens: Nombre maximal de tokens autorisés dans le contexte.
        compaction_threshold: Ratio (0–1) à partir duquel le compactage est déclenché.
    """

    # Constantes d'estimation
    _AVG_CHARS_PER_TOKEN: float = 4.0
    _PATTERNS_WEIGHT: Dict[str, float] = {
        "code": 0.75,       # Le code est plus dense
        "json": 0.80,
        "prose": 1.0,       # Texte naturel
    }

    def __init__(
        self,
        max_context_tokens: int = 30_000,
        compaction_threshold: float = 0.85,
    ) -> None:
        if max_context_tokens <= 0:
            raise ValueError("max_context_tokens doit être strictement positif.")
        if not (0.0 < compaction_threshold <= 1.0):
            raise ValueError("compaction_threshold doit être dans ]0, 1].")
        self.max_context_tokens = max_context_tokens
        self.compaction_threshold = compaction_threshold
        logger.info(
            "ContextEngine initialisé : max=%d tokens, seuil=%.0f%%",
            max_context_tokens,
            compaction_threshold * 100,
        )

    # -- Estimation ---------------------------------------------------------

    def estimate_tokens(self, text: str) -> int:
        """Estime le nombre de tokens d'un texte.

        Utilise une heuristique basée sur le nombre de caractères et ajuste
        le ratio selon le type de contenu détecté (code, JSON, prose).

        Args:
            text: Le texte dont on veut estimer le nombre de tokens.

        Returns:
            Estimation du nombre de tokens.
        """
        if not text:
            return 0
        # Détection du type de contenu
        code_chars = len(re.findall(r"[{}\[\]()=<>;]", text))
        json_chars = len(re.findall(r'[:,"]', text))
        total_chars = len(text)
        if total_chars == 0:
            return 0
        code_ratio = code_chars / total_chars
        json_ratio = json_chars / total_chars
        if code_ratio > 0.05:
            weight = self._PATTERNS_WEIGHT["code"]
        elif json_ratio > 0.08:
            weight = self._PATTERNS_WEIGHT["json"]
        else:
            weight = self._PATTERNS_WEIGHT["prose"]
        estimated = math.ceil(total_chars / (self._AVG_CHARS_PER_TOKEN * weight))
        return estimated

    # -- Seuil de compactage ------------------------------------------------

    def should_compact(self, current_tokens: int) -> bool:
        """Détermine si un compactage est nécessaire.

        Args:
            current_tokens: Nombre de tokens actuellement utilisés.

        Returns:
            True si le nombre de tokens dépasse le seuil de compactage.
        """
        threshold_tokens = int(self.max_context_tokens * self.compaction_threshold)
        needed = current_tokens >= threshold_tokens
        if needed:
            logger.info(
                "Compactage nécessaire : %d tokens ≥ seuil %d",
                current_tokens,
                threshold_tokens,
            )
        return needed

    # -- Compactage ---------------------------------------------------------

    def compact(
        self,
        messages: Sequence[Dict[str, Any]],
        strategy: str = "keep_recent",
    ) -> List[Dict[str, Any]]:
        """Compacte l'historique des messages selon la stratégie choisie.

        Stratégies disponibles :
            - « keep_recent » : Conserve les N messages les plus récents,
              où N est calculé pour rester sous le seuil de tokens.
            - « summarize_old » : Remplace les anciens messages par un
              résumé synthétique tout en conservant les messages récents.
            - « extract_key_facts » : Extrait les faits clés des anciens
              messages et les regroupe dans un message système.

        Args:
            messages: Liste des messages du contexte.
            strategy: Nom de la stratégie de compactage.

        Returns:
            Liste compactée des messages.

        Raises:
            ValueError: Si la stratégie est inconnue.
        """
        if not messages:
            return []

        if strategy == "keep_recent":
            return self._compact_keep_recent(messages)
        elif strategy == "summarize_old":
            return self._compact_summarize_old(messages)
        elif strategy == "extract_key_facts":
            return self._compact_extract_key_facts(messages)
        else:
            raise ValueError(f"Stratégie de compactage inconnue : « {strategy} »")

    # -- Stratégies internes ------------------------------------------------

    def _compact_keep_recent(
        self, messages: Sequence[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Conserve les messages les plus récents jusqu'à la limite de tokens."""
        target_tokens = int(self.max_context_tokens * self.compaction_threshold * 0.7)
        result: List[Dict[str, Any]] = []
        running_tokens = 0
        # Parcourir en ordre inverse pour garder les plus récents
        for msg in reversed(messages):
            content = msg.get("content", "")
            msg_tokens = self.estimate_tokens(content)
            if running_tokens + msg_tokens > target_tokens:
                break
            result.insert(0, dict(msg))
            running_tokens += msg_tokens
        logger.info(
            "Compactage keep_recent : %d → %d messages (~%d tokens)",
            len(messages),
            len(result),
            running_tokens,
        )
        return result

    def _compact_summarize_old(
        self, messages: Sequence[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Résume les anciens messages et conserve les récents intacts."""
        target_tokens = int(self.max_context_tokens * self.compaction_threshold * 0.7)
        # Conserver au minimum les 20 % les plus récents
        min_recent = max(1, len(messages) // 5)
        recent = list(messages[-min_recent:])
        old = list(messages[:-min_recent])

        # Synthétiser les anciens en un résumé
        summary_parts: List[str] = []
        for msg in old:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if content:
                summary_parts.append(f"[{role}] {content[:200]}")
        summary_text = " ".join(summary_parts)
        # Tronquer si le résumé est trop long
        max_summary_tokens = target_tokens // 3
        while self.estimate_tokens(summary_text) > max_summary_tokens and len(summary_text) > 100:
            summary_text = summary_text[: len(summary_text) // 2]

        summary_msg: Dict[str, Any] = {
            "role": "system",
            "content": f"[Résumé du contexte antérieur] {summary_text}",
        }
        compacted = [summary_msg] + recent
        total = sum(self.estimate_tokens(m.get("content", "")) for m in compacted)
        logger.info(
            "Compactage summarize_old : %d → %d messages (~%d tokens)",
            len(messages),
            len(compacted),
            total,
        )
        return compacted

    def _compact_extract_key_facts(
        self, messages: Sequence[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extrait les faits clés des anciens messages."""
        target_tokens = int(self.max_context_tokens * self.compaction_threshold * 0.7)
        # Identifier les messages avec du contenu factuel
        facts: List[str] = []
        for msg in messages:
            content = msg.get("content", "")
            if not content:
                continue
            # Extraction heuristique des phrases déclaratives
            sentences = re.split(r"(?<=[.!?])\s+", content)
            for sentence in sentences:
                # Heuristique : phrase contenant des données ou des noms
                if re.search(r"\b\d+\b|\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)+\b", sentence):
                    facts.append(sentence.strip())
                    if len(facts) >= 30:
                        break
            if len(facts) >= 30:
                break

        # Construire le message de faits clés
        facts_text = "\n".join(f"- {f}" for f in facts[:30])
        facts_msg: Dict[str, Any] = {
            "role": "system",
            "content": f"[Faits clés extraits]\n{facts_text}",
        }

        # Conserver les messages récents sous la limite
        result: List[Dict[str, Any]] = [facts_msg]
        running = self.estimate_tokens(facts_msg.get("content", ""))
        for msg in reversed(messages):
            content = msg.get("content", "")
            msg_tokens = self.estimate_tokens(content)
            if running + msg_tokens > target_tokens:
                break
            result.insert(1, dict(msg))
            running += msg_tokens

        logger.info(
            "Compactage extract_key_facts : %d → %d messages, %d faits (~%d tokens)",
            len(messages),
            len(result),
            len(facts[:30]),
            running,
        )
        return result
