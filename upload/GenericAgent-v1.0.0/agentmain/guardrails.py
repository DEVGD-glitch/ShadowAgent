"""GenericAgent v0.6.0 — Guardrails : Validation input/output pour agents autonomes.

Inspire de l'OpenAI Agents SDK (openai/openai-agents-python).
Fournit des garde-fous pour valider les entrees et sorties des agents,
prevenant les injections, les fuites de donnees, et le contenu nocif.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

logger = logging.getLogger("ga.agentmain.guardrails")


# ══════════════════════════════════════════════════════════════════════════════
#  Resultat de validation
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class GuardrailResult:
    """Resultat de la validation d'un guardrail.

    Attributes:
        passed: True si la validation a reussi
        reason: Raison de l'echec (vide si passe)
        modified_value: Valeur modifiee par le guardrail (optionnel)
        guardrail_name: Nom du guardrail qui a produit ce resultat
    """
    passed: bool
    reason: str = ""
    modified_value: Optional[Any] = None
    guardrail_name: str = ""

    def __bool__(self) -> bool:
        return self.passed


# ══════════════════════════════════════════════════════════════════════════════
#  Guardrails d'entree
# ══════════════════════════════════════════════════════════════════════════════

class InputGuardrail:
    """Guardrail de validation des entrees utilisateur.

    Verifie que les entrees sont conformes avant d'etre traitees par l'agent.
    """

    def __init__(self, name: str, validator_fn: Callable[[Any], GuardrailResult],
                 description: str = "") -> None:
        """Initialise le guardrail d'entree.

        Args:
            name: Nom identifiant le guardrail
            validator_fn: Fonction de validation (value) -> GuardrailResult
            description: Description du guardrail
        """
        self.name = name
        self.validator_fn = validator_fn
        self.description = description

    def validate(self, input_value: Any) -> GuardrailResult:
        """Valide une valeur d'entree.

        Args:
            input_value: Valeur a valider

        Returns:
            GuardrailResult indiquant si la validation a reussi
        """
        try:
            result = self.validator_fn(input_value)
            result.guardrail_name = self.name
            if not result.passed:
                logger.warning("InputGuardrail '%s' a bloque : %s", self.name, result.reason)
            return result
        except Exception as e:
            logger.error("Erreur InputGuardrail '%s' : %s", self.name, e)
            return GuardrailResult(passed=False, reason=f"Erreur de validation : {e}", guardrail_name=self.name)

    # ── Validateurs integres ─────────────────────────────────────────────

    @staticmethod
    def no_code_injection(text: Any) -> GuardrailResult:
        """Detecte les tentatives d'injection de code dans l'entree.

        Verifie les patterns SQL injection, shell injection, et prompt injection.
        """
        if not isinstance(text, str):
            return GuardrailResult(passed=True)

        patterns = [
            (r";\s*(DROP|DELETE|TRUNCATE|ALTER|CREATE)\s+", "Injection SQL detectee"),
            (r";\s*(rm|del|format|shutdown|reboot)\s+", "Injection shell detectee"),
            (r"(?:ignore|disregard|forget)\s+(?:previous|above|all)\s+(?:instructions|prompts|rules)",
             "Tentative de prompt injection detectee"),
            (r"<\s*script\s+", "Injection XSS detectee"),
            (r"\$\{.*\}", "Injection de template detectee"),
            (r"`[^`]*`", "Execution de code potentielle dans backticks"),
        ]

        for pattern, reason in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return GuardrailResult(passed=False, reason=reason)
        return GuardrailResult(passed=True)

    @staticmethod
    def no_pii_leak(text: Any) -> GuardrailResult:
        """Detecte les fuites potentielles de donnees personnelles (PII).

        Verifie la presence d'emails, numeros de telephone, SSN, cartes de credit.
        """
        if not isinstance(text, str):
            return GuardrailResult(passed=True)

        patterns = [
            (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "Email detecte"),
            (r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "Numero de telephone potentiel detecte"),
            (r"\b\d{3}-\d{2}-\d{4}\b", "SSN potentiel detecte"),
            (r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "Numero de carte potentiel detecte"),
        ]

        for pattern, reason in patterns:
            if re.search(pattern, text):
                return GuardrailResult(passed=False, reason=f"PII detecte : {reason}")
        return GuardrailResult(passed=True)

    @staticmethod
    def max_length(max_chars: int) -> Callable[[Any], GuardrailResult]:
        """Cree un validateur de longueur maximale.

        Args:
            max_chars: Nombre maximum de caracteres autorises

        Returns:
            Fonction de validation
        """
        def validator(text: Any) -> GuardrailResult:
            if not isinstance(text, str):
                return GuardrailResult(passed=True)
            if len(text) > max_chars:
                return GuardrailResult(
                    passed=False,
                    reason=f"Texte trop long ({len(text)} > {max_chars} caracteres)",
                )
            return GuardrailResult(passed=True)
        return validator

    @staticmethod
    def topic_restriction(allowed_topics: List[str], denied_topics: List[str]) -> Callable[[Any], GuardrailResult]:
        """Cree un validateur de restriction de sujet.

        Args:
            allowed_topics: Sujets autorises (vide = tous sauf denies)
            denied_topics: Sujets interdits

        Returns:
            Fonction de validation
        """
        def validator(text: Any) -> GuardrailResult:
            if not isinstance(text, str):
                return GuardrailResult(passed=True)
            text_lower = text.lower()
            for topic in denied_topics:
                if topic.lower() in text_lower:
                    return GuardrailResult(
                        passed=False,
                        reason=f"Sujet interdit detecte : {topic}",
                    )
            if allowed_topics:
                found = any(topic.lower() in text_lower for topic in allowed_topics)
                if not found:
                    return GuardrailResult(
                        passed=False,
                        reason="Aucun sujet autorise detecte dans l'entree",
                    )
            return GuardrailResult(passed=True)
        return validator


# ══════════════════════════════════════════════════════════════════════════════
#  Guardrails de sortie
# ══════════════════════════════════════════════════════════════════════════════

class OutputGuardrail:
    """Guardrail de validation des sorties de l'agent.

    Verifie que les sorties sont conformes avant d'etre presentees a l'utilisateur.
    """

    def __init__(self, name: str, validator_fn: Callable[[Any], GuardrailResult],
                 description: str = "") -> None:
        """Initialise le guardrail de sortie.

        Args:
            name: Nom identifiant le guardrail
            validator_fn: Fonction de validation (value) -> GuardrailResult
            description: Description du guardrail
        """
        self.name = name
        self.validator_fn = validator_fn
        self.description = description

    def validate(self, output_value: Any) -> GuardrailResult:
        """Valide une valeur de sortie.

        Args:
            output_value: Valeur a valider

        Returns:
            GuardrailResult indiquant si la validation a reussi
        """
        try:
            result = self.validator_fn(output_value)
            result.guardrail_name = self.name
            if not result.passed:
                logger.warning("OutputGuardrail '%s' a bloque : %s", self.name, result.reason)
            return result
        except Exception as e:
            logger.error("Erreur OutputGuardrail '%s' : %s", self.name, e)
            return GuardrailResult(passed=False, reason=f"Erreur de validation : {e}", guardrail_name=self.name)

    # ── Validateurs integres ─────────────────────────────────────────────

    @staticmethod
    def no_harmful_content(text: Any) -> GuardrailResult:
        """Detecte le contenu potentiellement nocif dans la sortie.

        Verifie les patterns de contenu violent, haineux, ou illegal.
        """
        if not isinstance(text, str):
            return GuardrailResult(passed=True)

        patterns = [
            (r"\b(kill|murder|assassinate|bomb|weaponize)\b.*\b(how\s+to|instructions?|steps?)\b",
             "Instructions potentiellement nocives detectees"),
            (r"\b(hate|slur|racist|sexist)\b",
             "Langage haineux potentiel detecte"),
            (r"\b(suicide|self-harm|overdose)\b.*\b(method|way|how)\b",
             "Contenu auto-nocif potentiel detecte"),
        ]

        for pattern, reason in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return GuardrailResult(passed=False, reason=reason)
        return GuardrailResult(passed=True)

    @staticmethod
    def no_pii_exposure(text: Any) -> GuardrailResult:
        """Detecte l'exposition de donnees personnelles dans la sortie."""
        return InputGuardrail.no_pii_leak(text)

    @staticmethod
    def format_compliance(required_format: str = "text") -> Callable[[Any], GuardrailResult]:
        """Cree un validateur de conformite de format.

        Args:
            required_format: Format attendu ("text", "json", "markdown", "code")

        Returns:
            Fonction de validation
        """
        def validator(text: Any) -> GuardrailResult:
            if not isinstance(text, str):
                return GuardrailResult(passed=True)

            if required_format == "json":
                try:
                    import json
                    json.loads(text)
                    return GuardrailResult(passed=True)
                except (json.JSONDecodeError, ValueError):
                    return GuardrailResult(passed=False, reason="La sortie n'est pas du JSON valide")
            elif required_format == "markdown":
                if not any(c in text for c in ("#", "*", "-", "`")):
                    return GuardrailResult(passed=False, reason="La sortie ne semble pas etre du Markdown")
            elif required_format == "code":
                if not any(c in text for c in ("def ", "class ", "function ", "import ", "var ")):
                    return GuardrailResult(passed=False, reason="La sortie ne semble pas etre du code")
            return GuardrailResult(passed=True)
        return validator

    # ── REMOVED: factuality_check ───────────────────────────────────────────
    # The factuality_check method was removed in v0.6.1 because it censored
    # epistemic humility — AI responses containing 3+ uncertainty markers
    # (e.g. "I'm not sure", "I don't know") were blocked, which punishes
    # honest and cautious answers.  Epistemic humility is a safety feature,
    # not a bug.  See ADR-007 for the full rationale.


# ══════════════════════════════════════════════════════════════════════════════
#  Gestionnaire de guardrails
# ══════════════════════════════════════════════════════════════════════════════

class GuardrailManager:
    """Gestionnaire centralise des guardrails d'entree et de sortie.

    Enregistre et execute les guardrails de maniere ordonnee.
    """

    def __init__(self) -> None:
        self._input_guardrails: List[InputGuardrail] = []
        self._output_guardrails: List[OutputGuardrail] = []
        self._violation_callbacks: List[Callable[[str, GuardrailResult], None]] = []

    def add_input_guardrail(self, guardrail: InputGuardrail) -> None:
        """Ajoute un guardrail d'entree."""
        self._input_guardrails.append(guardrail)
        logger.debug("InputGuardrail ajoute : %s", guardrail.name)

    def add_output_guardrail(self, guardrail: OutputGuardrail) -> None:
        """Ajoute un guardrail de sortie."""
        self._output_guardrails.append(guardrail)
        logger.debug("OutputGuardrail ajoute : %s", guardrail.name)

    def on_violation(self, callback: Callable[[str, GuardrailResult], None]) -> None:
        """Enregistre un callback appele lors d'une violation.

        Args:
            callback: Fonction (direction, result) -> None
        """
        self._violation_callbacks.append(callback)

    def validate_input(self, value: Any) -> GuardrailResult:
        """Valide une entree avec tous les guardrails d'entree.

        Execute les guardrails en ordre et retourne le premier echec.
        Si tous passent, retourne un resultat positif.

        Args:
            value: Valeur d'entree a valider

        Returns:
            GuardrailResult du premier guardrail qui echoue, ou succes
        """
        for guardrail in self._input_guardrails:
            result = guardrail.validate(value)
            if not result.passed:
                self._notify_violation("input", result)
                return result
        return GuardrailResult(passed=True, guardrail_name="all_input_guardrails")

    def validate_output(self, value: Any) -> GuardrailResult:
        """Valide une sortie avec tous les guardrails de sortie.

        Execute les guardrails en ordre et retourne le premier echec.
        Si tous passent, retourne un resultat positif.

        Args:
            value: Valeur de sortie a valider

        Returns:
            GuardrailResult du premier guardrail qui echoue, ou succes
        """
        for guardrail in self._output_guardrails:
            result = guardrail.validate(value)
            if not result.passed:
                self._notify_violation("output", result)
                return result
        return GuardrailResult(passed=True, guardrail_name="all_output_guardrails")

    def _notify_violation(self, direction: str, result: GuardrailResult) -> None:
        """Notifie les callbacks de violation."""
        for callback in self._violation_callbacks:
            try:
                callback(direction, result)
            except Exception as e:
                logger.error("Erreur callback violation : %s", e)

    def setup_defaults(self) -> None:
        """Configure les guardrails par defaut recommandes.

        NOTE (v0.6.1): ``no_code_injection`` and ``no_pii_leak`` input guardrails
        have been **disabled by default** because they produce too many false
        positives on legitimate user inputs (markdown code blocks, email addresses,
        configuration values containing backticks or @-symbols).  They can be
        re-enabled individually via ``add_input_guardrail()`` after testing on
        real-world queries.  See ADR-007 for the full rationale.

        Only the safe, non-disruptive guardrails are enabled by default:
        ``max_length`` on input, ``no_harmful_content`` and ``no_pii_exposure``
        on output.
        """
        # Guardrails d'entree — only max_length (safe, non-disruptive)
        self.add_input_guardrail(InputGuardrail(
            name="max_length",
            validator_fn=InputGuardrail.max_length(50000),
            description="Limite la taille de l'entree a 50K caracteres",
        ))

        # Guardrails de sortie
        self.add_output_guardrail(OutputGuardrail(
            name="no_harmful_content",
            validator_fn=OutputGuardrail.no_harmful_content,
            description="Bloque le contenu potentiellement nocif",
        ))
        self.add_output_guardrail(OutputGuardrail(
            name="no_pii_exposure",
            validator_fn=OutputGuardrail.no_pii_exposure,
            description="Detecte les donnees personnelles dans la sortie",
        ))
        logger.info("Guardrails par defaut configures (1 input + 2 output) — no_code_injection and no_pii_leak disabled (too many false positives)")

    def list_guardrails(self) -> Dict[str, List[Dict[str, str]]]:
        """Liste tous les guardrails configures."""
        return {
            "input": [{"name": g.name, "description": g.description} for g in self._input_guardrails],
            "output": [{"name": g.name, "description": g.description} for g in self._output_guardrails],
        }
