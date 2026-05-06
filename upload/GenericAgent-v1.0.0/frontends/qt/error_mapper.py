"""
Exception → User-friendly UI message mapping for GenericAgent.

Maps Python exception types to human-readable messages with suggested
actions, supporting i18n via t() for all user-facing strings.

Usage::

    from frontends.qt.error_mapper import map_exception_to_user_message

    try:
        ...
    except Exception as exc:
        info = map_exception_to_user_message(exc)
        # info = {"title": ..., "message": ..., "action": ..., "action_type": ...}
"""
from __future__ import annotations

import logging
from typing import Dict

logger = logging.getLogger(__name__)

try:
    from i18n import t
except ImportError:
    def t(key, *args, **kwargs):
        return key


# Lazy imports for exception classes to avoid circular imports
def _get_exception_classes():
    """Return a dict of exception class → name, lazily importing."""
    classes = {}
    try:
        from exceptions import (
            LLMRateLimitError, LLMAuthError, LLMConnectionError,
            APIKeyMissingError, MaxTurnsExceededError,
        )
        classes["LLMRateLimitError"] = LLMRateLimitError
        classes["LLMAuthError"] = LLMAuthError
        classes["LLMConnectionError"] = LLMConnectionError
        classes["APIKeyMissingError"] = APIKeyMissingError
        classes["MaxTurnsExceededError"] = MaxTurnsExceededError
    except ImportError:
        pass
    try:
        from circuit_breaker import CircuitBreaker
        # CircuitBreakerOpenError is actually LLMConnectionError raised by CB
        # We detect it by the message pattern
    except ImportError:
        pass
    return classes


def _is_circuit_breaker_error(exc: Exception) -> bool:
    """Check if an exception was raised by the circuit breaker."""
    msg = str(exc).lower()
    return "circuit breaker" in msg and ("open" in msg or "rejeté" in msg)


def _is_network_error(exc: Exception) -> bool:
    """Check if an exception is a network-level error."""
    if isinstance(exc, (ConnectionError, OSError, TimeoutError)):
        return True
    msg = str(exc).lower()
    network_keywords = ["connection", "timeout", "network", "dns", "socket",
                        "refused", "unreachable", "connexion", "délai"]
    return any(kw in msg for kw in network_keywords)


def map_exception_to_user_message(exc: Exception) -> Dict[str, str]:
    """Map a Python exception to a user-friendly UI message.

    Parameters
    ----------
    exc : Exception
        The exception to map.

    Returns
    -------
    dict
        A dictionary with keys:
        - ``title``: User-friendly title for the error.
        - ``message``: Explanation in plain language.
        - ``action``: Suggested action (button text).
        - ``action_type``: One of 'retry', 'settings', 'dismiss'.
    """
    classes = _get_exception_classes()

    # LLMRateLimitError
    LLMRateLimitError = classes.get("LLMRateLimitError")
    if LLMRateLimitError and isinstance(exc, LLMRateLimitError):
        return {
            "title": t("error_mapper.rate_limit_title", "Service temporairement saturé"),
            "message": t("error_mapper.rate_limit_msg",
                         "Le fournisseur LLM limite actuellement les requêtes. "
                         "Veuillez patienter quelques secondes et réessayer."),
            "action": t("error_mapper.retry", "Réessayer"),
            "action_type": "retry",
        }

    # LLMAuthError
    LLMAuthError = classes.get("LLMAuthError")
    if LLMAuthError and isinstance(exc, LLMAuthError):
        return {
            "title": t("error_mapper.auth_title", "Clé API invalide"),
            "message": t("error_mapper.auth_msg",
                         "La clé API fournie n'est pas valide ou a expiré. "
                         "Vérifiez vos paramètres de connexion."),
            "action": t("error_mapper.check_settings", "Vérifier les paramètres"),
            "action_type": "settings",
        }

    # APIKeyMissingError
    APIKeyMissingError = classes.get("APIKeyMissingError")
    if APIKeyMissingError and isinstance(exc, APIKeyMissingError):
        return {
            "title": t("error_mapper.no_key_title", "Aucune clé API configurée"),
            "message": t("error_mapper.no_key_msg",
                         "Vous devez configurer une clé API pour utiliser l'assistant. "
                         "Allez dans les paramètres pour ajouter votre clé."),
            "action": t("error_mapper.configure", "Configurer"),
            "action_type": "settings",
        }

    # MaxTurnsExceededError
    MaxTurnsExceededError = classes.get("MaxTurnsExceededError")
    if MaxTurnsExceededError and isinstance(exc, MaxTurnsExceededError):
        return {
            "title": t("error_mapper.max_turns_title", "Tâche trop complexe"),
            "message": t("error_mapper.max_turns_msg",
                         "L'agent a dépassé le nombre maximum d'étapes pour cette tâche. "
                         "Essayez de décomposer votre demande en étapes plus simples."),
            "action": t("error_mapper.break_down", "Décomposer en étapes"),
            "action_type": "dismiss",
        }

    # CircuitBreakerOpenError (detected by message pattern)
    if _is_circuit_breaker_error(exc):
        return {
            "title": t("error_mapper.circuit_breaker_title", "Provider indisponible"),
            "message": t("error_mapper.circuit_breaker_msg",
                         "Le fournisseur LLM est temporairement indisponible suite à "
                         "des erreurs répétées. Le système réessaiera automatiquement."),
            "action": t("error_mapper.retry", "Réessayer"),
            "action_type": "retry",
        }

    # Network errors
    if _is_network_error(exc):
        return {
            "title": t("error_mapper.network_title", "Problème de connexion"),
            "message": t("error_mapper.network_msg",
                         "Impossible de se connecter au serveur. "
                         "Vérifiez votre connexion internet et réessayez."),
            "action": t("error_mapper.retry", "Réessayer"),
            "action_type": "retry",
        }

    # Generic fallback
    return {
        "title": t("error_mapper.generic_title", "Une erreur est survenue"),
        "message": t("error_mapper.generic_msg",
                     f"Une erreur inattendue s'est produite : {str(exc)[:100]}"),
        "action": t("error_mapper.ok", "OK"),
        "action_type": "dismiss",
    }
