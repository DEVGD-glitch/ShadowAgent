"""Fournisseur Google AI Studio pour GenericAgent.

Ce module implemente un fournisseur LLM pour Google AI Studio (API
generativelanguage), avec support du streaming SSE, de l'appel de
fonctions (FunctionDeclaration), et de la conversion de schema d'outils
du format GenericAgent/OpenAI vers le format Google.

Modeles supportes
-----------------
- ``gemma-4-31b-it`` (par defaut)
- Tout modele expose par l'API generativelanguage v1beta.

Usage::

    from llmcore.google_provider import GoogleAISession, GoogleAIConfig

    config = GoogleAIConfig(api_key="AIza...", model="gemma-4-31b-it")
    session = GoogleAISession(config)
    for chunk in session.stream("Explique-moi la relativite"):
        print(chunk, end="")
    session.abort()
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Generator, Optional

import requests

from logging_config import get_logger

logger = get_logger("llmcore.google_provider")

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_GOOGLE_AI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"

#: Delai d'attente entre les tentatives de reconnexion SSE (secondes).
_SSE_RETRY_DELAY: float = 0.5

#: Delai maximal d'attente pour une requete HTTP (secondes).
_HTTP_TIMEOUT: int = 120


# ---------------------------------------------------------------------------
# GoogleAIConfig
# ---------------------------------------------------------------------------

@dataclass
class GoogleAIConfig:
    """Configuration pour une session Google AI Studio.

    Attributes
    ----------
    api_key : str
        Cle API Google AI Studio.
    model : str
        Nom du modele a utiliser.
    temperature : float
        Temperature de generation (0.0 - 2.0).
    max_tokens : int
        Nombre maximal de tokens en sortie.
    top_p : float
        Parametre nucleus sampling.
    """

    api_key: str
    model: str = "gemma-4-31b-it"
    temperature: float = 0.7
    max_tokens: int = 8192
    top_p: float = 0.95


# ---------------------------------------------------------------------------
# Conversion de schema d'outils
# ---------------------------------------------------------------------------

def _convert_json_schema_to_google(schema: dict[str, Any]) -> dict[str, Any]:
    """Convertir un schema JSON (OpenAI-style) en schema Google.

    Google utilise un format de schema legerement different d'OpenAI.
    Cette fonction adapte les types et la structure recursivement.

    Parameters
    ----------
    schema : dict
        Schema JSON au format OpenAI.

    Returns
    -------
    dict
        Schema au format Google FunctionDeclaration.
    """
    if not schema:
        return {}

    result: dict[str, Any] = {"type": schema.get("type", "object").upper()}

    # Description
    if "description" in schema:
        result["description"] = schema["description"]

    # Proprietes
    if "properties" in schema:
        result["properties"] = {}
        for prop_name, prop_schema in schema["properties"].items():
            result["properties"][prop_name] = _convert_json_schema_to_google(prop_schema)

    # Champs obligatoires
    if "required" in schema:
        result["required"] = schema["required"]

    # Items (pour les tableaux)
    if "items" in schema:
        result["items"] = _convert_json_schema_to_google(schema["items"])

    # Enum
    if "enum" in schema:
        result["enum"] = schema["enum"]

    return result


def tools_to_google_format(tools_schema: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convertir un schema d'outils OpenAI en declarations de fonctions Google.

    Chaque outil au format OpenAI ``{"type": "function", "function": {...}}``
    est converti en ``FunctionDeclaration`` Google.

    Parameters
    ----------
    tools_schema : list[dict]
        Schema d'outils au format OpenAI.

    Returns
    -------
    list[dict]
        Liste de declarations de fonctions au format Google.
    """
    google_tools: list[dict[str, Any]] = []

    for tool in tools_schema:
        if tool.get("type") != "function":
            continue
        func = tool.get("function", {})
        name = func.get("name", "")
        description = func.get("description", "")
        parameters = func.get("parameters", {})

        func_decl: dict[str, Any] = {
            "name": name,
            "description": description,
        }

        if parameters:
            func_decl["parameters"] = _convert_json_schema_to_google(parameters)

        google_tools.append({"function_declarations": [func_decl]})

    # Regrouper toutes les declarations dans un seul tool
    if google_tools:
        all_decls: list[dict[str, Any]] = []
        for gt in google_tools:
            all_decls.extend(gt.get("function_declarations", []))
        return [{"function_declarations": all_decls}]

    return []


# ---------------------------------------------------------------------------
# Analyse de reponse
# ---------------------------------------------------------------------------

def parse_google_response(response_json: dict[str, Any]) -> dict[str, Any]:
    """Analyser une reponse JSON de l'API Google AI.

    Extrait le texte, les appels de fonction et les metadonnees d'utilisation
    depuis la reponse brute.

    Parameters
    ----------
    response_json : dict
        Reponse JSON de l'API Google AI.

    Returns
    -------
    dict
        Dictionnaire avec les cles ``text``, ``function_calls``, ``usage``,
        ``finish_reason``.
    """
    candidates = response_json.get("candidates", [])
    if not candidates:
        return {
            "text": "",
            "function_calls": [],
            "usage": {},
            "finish_reason": "NONE",
        }

    candidate = candidates[0]
    content = candidate.get("content", {})
    parts = content.get("parts", [])

    text_parts: list[str] = []
    function_calls: list[dict[str, Any]] = []

    for part in parts:
        if "text" in part:
            text_parts.append(part["text"])
        elif "function_call" in part:
            fc = part["function_call"]
            function_calls.append({
                "name": fc.get("name", ""),
                "args": fc.get("args", {}),
            })

    usage_meta = response_json.get("usageMetadata", {})
    finish_reason = candidate.get("finishReason", "NONE")

    return {
        "text": "".join(text_parts),
        "function_calls": function_calls,
        "usage": {
            "prompt_tokens": usage_meta.get("promptTokenCount", 0),
            "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
            "total_tokens": usage_meta.get("totalTokenCount", 0),
        },
        "finish_reason": finish_reason,
    }


def google_function_call_to_tool_call(function_call: dict[str, Any]) -> dict[str, Any]:
    """Convertir un appel de fonction Google en format GenericAgent.

    Parameters
    ----------
    function_call : dict
        Appel de fonction au format Google (``{"name": ..., "args": ...}``).

    Returns
    -------
    dict
        Appel d'outil au format GenericAgent (``{"name": ..., "arguments": ...}``).
    """
    return {
        "name": function_call.get("name", ""),
        "arguments": function_call.get("args", {}),
    }


# ---------------------------------------------------------------------------
# Analyse SSE (Server-Sent Events)
# ---------------------------------------------------------------------------

def _parse_sse_line(line: str) -> Optional[dict[str, Any]]:
    """Analyser une ligne SSE et extraire le JSON de donnee.

    Parameters
    ----------
    line : str
        Ligne brute du flux SSE.

    Returns
    -------
    dict | None
        Donnees JSON parsees, ou ``None`` si la ligne n'est pas une donnee.
    """
    line = line.strip()
    if not line or not line.startswith("data: "):
        return None
    payload = line[6:].strip()
    if payload == "[DONE]":
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        logger.debug("Echec du parse SSE : %s", payload[:120])
        return None


# ---------------------------------------------------------------------------
# GoogleAISession
# ---------------------------------------------------------------------------

class GoogleAISession:
    """Session LLM pour Google AI Studio avec support streaming et function calling.

    Cette classe communique avec l'API REST generativelanguage de Google AI
    Studio.  Elle supporte le streaming SSE, la conversion de schema d'outils,
    et l'execution d'appels de fonctions.

    Attributes
    ----------
    config : GoogleAIConfig
        Configuration de la session.
    """

    def __init__(self, config: GoogleAIConfig) -> None:
        self.config: GoogleAIConfig = config
        self._abort_flag: threading.Event = threading.Event()
        self._session: requests.Session = requests.Session()
        self._conversation_history: list[dict[str, Any]] = []
        self._lock: threading.Lock = threading.Lock()
        logger.debug(
            "GoogleAISession initialisee (modele=%s)", config.model,
        )

    # ------------------------------------------------------------------
    # Proprietes publiques
    # ------------------------------------------------------------------

    @property
    def model_name(self) -> str:
        """Nom du modele utilise.

        Returns
        -------
        str
            Nom du modele (par ex. ``"gemma-4-31b-it"``).
        """
        return self.config.model

    @property
    def api_mode(self) -> str:
        """Mode d'API utilise.

        Returns
        -------
        str
            Toujours ``"google_ai"`` pour ce fournisseur.
        """
        return "google_ai"

    # ------------------------------------------------------------------
    # Construction des requetes
    # ------------------------------------------------------------------

    def _build_url(self, endpoint: str) -> str:
        """Construire l'URL complete pour un point de terminaison.

        Parameters
        ----------
        endpoint : str
            Point de terminaison (par ex. ``"generateContent"``).

        Returns
        -------
        str
            URL complete avec la cle API.
        """
        return (
            f"{_GOOGLE_AI_BASE_URL}/models/{self.config.model}"
            f":{endpoint}?key={self.config.api_key}"
        )

    def _build_payload(
        self,
        contents: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Construire le payload JSON pour l'API Google AI.

        Parameters
        ----------
        contents : list[dict]
            Historique de conversation au format Google.
        tools : list[dict] | None
            Outils au format Google FunctionDeclaration.
        stream : bool
            Si ``True``, active le streaming.

        Returns
        -------
        dict
            Payload JSON complet.
        """
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens,
                "topP": self.config.top_p,
            },
        }

        if tools:
            payload["tools"] = tools

        return payload

    @staticmethod
    def _messages_to_google_contents(
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convertir des messages au format GenericAgent en contenu Google.

        Parameters
        ----------
        messages : list[dict]
            Messages au format GenericAgent.

        Returns
        -------
        list[dict]
            Contenu au format Google AI.
        """
        contents: list[dict[str, Any]] = []
        system_instruction: Optional[str] = None

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Extraire le message systeme
            if role == "system":
                system_instruction = content if isinstance(content, str) else str(content)
                continue

            # Mapper les roles
            google_role = "user" if role in ("user", "tool") else "model"

            # Gerer le contenu texte ou structure
            parts: list[dict[str, Any]] = []
            if isinstance(content, str):
                parts.append({"text": content})
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            parts.append({"text": block.get("text", "")})
                        elif block.get("type") == "tool_result":
                            parts.append({
                                "function_response": {
                                    "name": block.get("name", ""),
                                    "response": block.get("content", {}),
                                },
                            })
                    else:
                        parts.append({"text": str(block)})

            # Ajouter les resultats d'appels de fonction
            tool_results = msg.get("tool_results", [])
            for tr in tool_results:
                parts.append({
                    "function_response": {
                        "name": tr.get("name", ""),
                        "response": {"result": tr.get("content", "")},
                    },
                })

            if parts:
                contents.append({"role": google_role, "parts": parts})

        return contents, system_instruction  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    def stream(
        self,
        prompt: str,
        tools: Optional[list[dict[str, Any]]] = None,
        system: Optional[str] = None,
    ) -> Generator[str, None, dict[str, Any]]:
        """Envoyer un prompt et diffuser la reponse en streaming (SSE).

        Parameters
        ----------
        prompt : str
            Texte du prompt.
        tools : list[dict] | None
            Schema d'outils au format OpenAI (sera converti).
        system : str | None
            Instruction systeme optionnelle.

        Yields
        ------
        str
        Fragments de texte de la reponse.

        Returns
        -------
        dict
        Metadonnees de la reponse (utilisation, appels de fonction, etc.).
        """
        self._abort_flag.clear()

        # Preparer les messages
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # Ajouter l'historique
        with self._lock:
            all_messages = self._conversation_history + messages

        contents, system_instruction = self._messages_to_google_contents(all_messages)

        # Convertir les outils
        google_tools: Optional[list[dict[str, Any]]] = None
        if tools:
            google_tools = tools_to_google_format(tools)

        # Construire le payload
        payload = self._build_payload(contents, tools=google_tools, stream=True)
        if system_instruction:
            payload["system_instruction"] = {"parts": [{"text": system_instruction}]}

        url = self._build_url("streamGenerateContent?alt=sse")

        # Envoyer la requete
        try:
            response = self._session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                stream=True,
                timeout=_HTTP_TIMEOUT,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError as exc:
            logger.error("Erreur de connexion Google AI : %s", exc)
            yield f"!!!Error: Connexion echouee - {exc}"
            return {}
        except requests.exceptions.HTTPError as exc:
            status = getattr(exc.response, "status_code", 0)
            body = ""
            try:
                body = exc.response.text[:500] if exc.response else ""  # type: ignore[union-attr]
            except Exception:
                pass
            logger.error("HTTP %d Google AI : %s", status, body)
            if status == 429:
                yield "!!!Error: Limite de debit atteinte (429)"
            elif status == 401 or status == 403:
                yield "!!!Error: Authentification echouee - cle API invalide"
            else:
                yield f"!!!Error: HTTP {status} - {body}"
            return {}

        # Analyser le flux SSE
        full_text: list[str] = []
        all_function_calls: list[dict[str, Any]] = []
        usage: dict[str, Any] = {}

        try:
            for line in response.iter_lines(decode_unicode=True):
                if self._abort_flag.is_set():
                    logger.info("Streaming Google AI interrompu par l'utilisateur")
                    break

                if not line:
                    continue

                data = _parse_sse_line(line)
                if data is None:
                    continue

                parsed = parse_google_response(data)
                chunk_text = parsed.get("text", "")
                if chunk_text:
                    full_text.append(chunk_text)
                    yield chunk_text

                fc_list = parsed.get("function_calls", [])
                if fc_list:
                    all_function_calls.extend(fc_list)

                chunk_usage = parsed.get("usage", {})
                if chunk_usage:
                    usage = chunk_usage

        except requests.exceptions.ChunkedEncodingError as exc:
            logger.error("Flux SSE interrompu : %s", exc)
            yield "!!!Error: Flux interrompu anormalement"
        except Exception as exc:
            logger.error("Erreur pendant le streaming : %s", exc)
            yield f"!!!Error: {exc}"

        # Mettre a jour l'historique
        combined_text = "".join(full_text)
        with self._lock:
            self._conversation_history.append({"role": "user", "content": prompt})
            if combined_text:
                self._conversation_history.append({"role": "assistant", "content": combined_text})

        result: dict[str, Any] = {
            "text": combined_text,
            "function_calls": all_function_calls,
            "usage": usage,
        }
        return result

    # ------------------------------------------------------------------
    # Requete non-streaming
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        tools: Optional[list[dict[str, Any]]] = None,
        system: Optional[str] = None,
    ) -> dict[str, Any]:
        """Envoyer un prompt et retourner la reponse complete (sans streaming).

        Parameters
        ----------
        prompt : str
            Texte du prompt.
        tools : list[dict] | None
            Schema d'outils au format OpenAI.
        system : str | None
            Instruction systeme optionnelle.

        Returns
        -------
        dict
        Reponse parsee avec ``text``, ``function_calls``, ``usage``.
        """
        self._abort_flag.clear()

        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        with self._lock:
            all_messages = self._conversation_history + messages

        contents, system_instruction = self._messages_to_google_contents(all_messages)

        google_tools: Optional[list[dict[str, Any]]] = None
        if tools:
            google_tools = tools_to_google_format(tools)

        payload = self._build_payload(contents, tools=google_tools, stream=False)
        if system_instruction:
            payload["system_instruction"] = {"parts": [{"text": system_instruction}]}

        url = self._build_url("generateContent")

        try:
            resp = self._session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=_HTTP_TIMEOUT,
            )
            resp.raise_for_status()
        except requests.exceptions.ConnectionError as exc:
            logger.error("Erreur de connexion Google AI : %s", exc)
            return {"text": f"!!!Error: Connexion echouee - {exc}", "function_calls": [], "usage": {}}
        except requests.exceptions.HTTPError as exc:
            status = getattr(exc.response, "status_code", 0)
            logger.error("HTTP %d Google AI", status)
            return {"text": f"!!!Error: HTTP {status}", "function_calls": [], "usage": {}}

        result = parse_google_response(resp.json())

        # Mettre a jour l'historique
        with self._lock:
            self._conversation_history.append({"role": "user", "content": prompt})
            if result.get("text"):
                self._conversation_history.append({"role": "assistant", "content": result["text"]})

        return result

    # ------------------------------------------------------------------
    # Appel de fonction avec execution
    # ------------------------------------------------------------------

    def stream_with_tools(
        self,
        prompt: str,
        tools_schema: list[dict[str, Any]],
        tool_executor: Optional[Any] = None,
        system: Optional[str] = None,
        max_rounds: int = 5,
    ) -> Generator[str, None, dict[str, Any]]:
        """Streamer avec support d'appel de fonctions en boucle.

        Lorsque le modele demande un appel de fonction, la fonction est
        executee (via *tool_executor*) et le resultat est renvoye au modele
        pour continuer la generation.

        Parameters
        ----------
        prompt : str
            Prompt initial.
        tools_schema : list[dict]
            Schema d'outils au format OpenAI.
        tool_executor : Any | None
            Objet callable prenant ``(name, arguments)`` et retournant un resultat.
        system : str | None
            Instruction systeme.
        max_rounds : int
            Nombre maximal de tours d'appel de fonction.

        Yields
        ------
        str
        Fragments de texte.

        Returns
        -------
        dict
        Metadonnees de la reponse finale.
        """
        current_prompt: str = prompt
        all_text: list[str] = []
        final_result: dict[str, Any] = {}

        for round_idx in range(max_rounds):
            result = yield from self.stream(
                current_prompt, tools=tools_schema, system=system,
            )
            func_calls = result.get("function_calls", [])
            if not func_calls or tool_executor is None:
                final_result = result
                break

            # Executer les appels de fonction
            tool_results: list[dict[str, Any]] = []
            for fc in func_calls:
                tool_name = fc.get("name", "")
                tool_args = fc.get("args", {})
                try:
                    if callable(tool_executor):
                        exec_result = tool_executor(tool_name, tool_args)
                    else:
                        exec_result = f"Erreur : aucun executeur pour {tool_name}"
                    tool_results.append({
                        "name": tool_name,
                        "content": str(exec_result),
                    })
                except Exception as exc:
                    logger.error("Erreur execution outil %s : %s", tool_name, exc)
                    tool_results.append({
                        "name": tool_name,
                        "content": f"Erreur : {exc}",
                    })

            # Construire le prompt suivant avec les resultats
            result_parts: list[str] = []
            for tr in tool_results:
                result_parts.append(f"Resultat de {tr['name']} : {tr['content']}")
            current_prompt = "\n".join(result_parts)
            system = None  # Ne pas repeter le systeme

        return final_result

    # ------------------------------------------------------------------
    # Interruption
    # ------------------------------------------------------------------

    def abort(self) -> None:
        """Interrompre le streaming en cours.

        Positionne un drapeau d'annulation qui sera verifie a chaque
        iteration du flux SSE.
        """
        self._abort_flag.set()
        logger.info("Streaming Google AI : demande d'annulation")

    # ------------------------------------------------------------------
    # Nettoyage
    # ------------------------------------------------------------------

    def reset_conversation(self) -> None:
        """Reinitialiser l'historique de conversation."""
        with self._lock:
            self._conversation_history.clear()
        logger.debug("Historique de conversation reinitialise")

    def close(self) -> None:
        """Fermer la session HTTP."""
        self._session.close()
        logger.debug("Session Google AI fermee")


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

__all__ = [
    "GoogleAIConfig",
    "GoogleAISession",
    "tools_to_google_format",
    "parse_google_response",
    "google_function_call_to_tool_call",
]
