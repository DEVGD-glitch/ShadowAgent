"""GenericAgent v0.6.0 — Browser Intelligence : DOM intelligence + sessions persistantes.

Inspire de Browser-Use (browser-use/browser-use).
Convertit le DOM en elements interactifs indexes pour une representation
token-efficient, et maintient des sessions navigateur persistantes.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger("ga.agentmain.browser_intel")


# ══════════════════════════════════════════════════════════════════════════════
#  DOMElement — Element interactif indexe
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class DOMElement:
    """Element interactif du DOM avec index pour reference par le LLM.

    Au lieu d'envoyer le HTML brut au LLM, on extrait les elements
    interactifs et on les indexe : "click [1]", "type [2]", etc.

    Attributes:
        index: Index unique pour reference par le LLM
        tag: Balise HTML (a, button, input, select, textarea, etc.)
        text: Texte visible de l'element
        attributes: Attributs HTML pertinents (href, placeholder, etc.)
        is_interactive: Si l'element est cliquable/saisissable
        bounding_box: Position et taille (x, y, width, height)
    """
    index: int
    tag: str
    text: str = ""
    attributes: Dict[str, str] = field(default_factory=dict)
    is_interactive: bool = True
    bounding_box: Tuple[int, int, int, int] = (0, 0, 0, 0)

    def format_for_llm(self) -> str:
        """Formate l'element pour le contexte LLM.

        Returns:
            Representation concise (ex: "[1] <button> 'Submit' [clickable]")
        """
        attrs = ""
        if self.attributes.get("href"):
            attrs += f" href={self.attributes['href'][:60]}"
        if self.attributes.get("placeholder"):
            attrs += f" placeholder='{self.attributes['placeholder'][:40]}'"
        if self.attributes.get("type"):
            attrs += f" type={self.attributes['type']}"
        if self.attributes.get("value"):
            attrs += f" value='{self.attributes['value'][:40]}'"

        action = "clickable" if self.tag in ("a", "button", "input[type=submit]", "input[type=button]") else \
                 "typeable" if self.tag in ("input", "textarea") else \
                 "selectable" if self.tag == "select" else "interactive"

        return f"[{self.index}] <{self.tag}>{attrs} '{self.text[:60]}' [{action}]"


# ══════════════════════════════════════════════════════════════════════════════
#  DOMExtractor — Extraction d'elements interactifs
# ══════════════════════════════════════════════════════════════════════════════

class DOMExtractor:
    """Extracteur d'elements interactifs du DOM.

    Convertit le HTML brut en une liste d'elements indexes, optimisee
    pour la consommation par un LLM (token-efficient).
    """

    INTERACTIVE_TAGS = {"a", "button", "input", "select", "textarea",
                        "summary", "details", "option", "label"}

    def extract_interactive_elements(self, html: str) -> List[DOMElement]:
        """Extrait les elements interactifs d'un document HTML.

        Parse le HTML et identifie tous les elements cliquables,
        saisissables, et selectionnables, en les indexant.

        Args:
            html: Contenu HTML a analyser

        Returns:
            Liste d'elements interactifs indexes
        """
        elements: List[DOMElement] = []
        index = 0

        # Pattern simple pour extraire les balises interactives
        tag_pattern = re.compile(
            r"<(a|button|input|select|textarea|summary|details|option|label)"
            r"\s([^>]*)>"
            r"([^<]*)",
            re.IGNORECASE,
        )

        for match in tag_pattern.finditer(html):
            tag = match.group(1).lower()
            attrs_str = match.group(2)
            text_content = match.group(3).strip()

            # Verifier si l'element est visible (pas hidden, pas display:none)
            if "hidden" in attrs_str.lower() or 'display:none' in attrs_str.lower():
                continue

            # Verifier si l'input est de type hidden
            input_type_match = re.search(r'type=["\']?(\w+)["\']?', attrs_str, re.IGNORECASE)
            if tag == "input" and input_type_match and input_type_match.group(1).lower() == "hidden":
                continue

            # Extraire les attributs pertinents
            attributes: Dict[str, str] = {}
            for attr_name in ("href", "placeholder", "type", "value", "name", "id",
                              "class", "aria-label", "title", "role", "action", "method"):
                attr_match = re.search(
                    rf'{attr_name}=["\']?([^"\'>\s]+)["\']?',
                    attrs_str, re.IGNORECASE,
                )
                if attr_match:
                    attributes[attr_name] = attr_match.group(1)

            # Texte visible
            if not text_content and attributes.get("value"):
                text_content = attributes["value"]
            if not text_content and attributes.get("placeholder"):
                text_content = attributes["placeholder"]
            if not text_content and attributes.get("aria-label"):
                text_content = attributes["aria-label"]

            index += 1
            elements.append(DOMElement(
                index=index,
                tag=tag,
                text=text_content[:200],
                attributes=attributes,
                is_interactive=True,
            ))

        logger.debug("DOMExtractor : %d elements interactifs extraits", len(elements))
        return elements

    def format_for_llm(self, elements: List[DOMElement]) -> str:
        """Formate les elements pour injection dans le contexte LLM.

        Genere une representation token-efficient ou chaque element
        est reference par son index : "click [1]", "type [2]", etc.

        Args:
            elements: Liste d'elements interactifs

        Returns:
            Texte formate pour le LLM
        """
        if not elements:
            return "Aucun element interactif detecte sur cette page."

        lines = ["Elements interactifs de la page (utilisez l'index pour interagir) :"]
        for elem in elements:
            lines.append(elem.format_for_llm())

        return "\n".join(lines)

    def find_element_by_index(self, elements: List[DOMElement], index: int) -> Optional[DOMElement]:
        """Trouve un element par son index.

        Args:
            elements: Liste d'elements
            index: Index de l'element a trouver

        Returns:
            L'element correspondant, ou None
        """
        for elem in elements:
            if elem.index == index:
                return elem
        return None

    def filter_by_tag(self, elements: List[DOMElement], tag: str) -> List[DOMElement]:
        """Filtre les elements par balise HTML.

        Args:
            elements: Liste d'elements
            tag: Balise HTML a filtrer

        Returns:
            Liste filtrée
        """
        return [e for e in elements if e.tag.lower() == tag.lower()]

    def find_by_text(self, elements: List[DOMElement], text: str,
                     case_sensitive: bool = False) -> List[DOMElement]:
        """Trouve les elements contenant un texte.

        Args:
            elements: Liste d'elements
            text: Texte a rechercher
            case_sensitive: Recherche sensible a la casse

        Returns:
            Elements correspondants
        """
        if case_sensitive:
            return [e for e in elements if text in e.text]
        return [e for e in elements if text.lower() in e.text.lower()]


# ══════════════════════════════════════════════════════════════════════════════
#  BrowserSession — Session navigateur persistante
# ══════════════════════════════════════════════════════════════════════════════

class BrowserSession:
    """Session navigateur persistante avec etat maintenu.

    Maintient les cookies, le login state, et le contexte entre
    les actions. Permet a l'agent de naviguer de maniere persistante.

    Attributes:
        session_id: Identifiant de session
    """

    def __init__(self, session_id: str = "") -> None:
        self.session_id = session_id or f"browser_{id(self)}"
        self._current_url: str = ""
        self._page_html: str = ""
        self._elements: List[DOMElement] = []
        self._extractor = DOMExtractor()
        self._history: List[str] = []
        self._cookies: Dict[str, str] = {}
        self._is_authenticated: bool = False
        logger.info("BrowserSession cree : %s", self.session_id)

    @property
    def current_url(self) -> str:
        """URL actuelle de la page."""
        return self._current_url

    @property
    def is_authenticated(self) -> bool:
        """Si l'utilisateur est connecte."""
        return self._is_authenticated

    def navigate(self, url: str) -> Dict[str, Any]:
        """Navigue vers une URL.

        Args:
            url: URL de destination

        Returns:
            Resultat de la navigation
        """
        self._history.append(self._current_url)
        self._current_url = url
        logger.info("Navigation vers : %s", url)
        # Dans une implementation reelle, on utiliserait Playwright/CDP
        return {"status": "success", "url": url}

    def get_page_state(self) -> Dict[str, Any]:
        """Retourne l'etat actuel de la page.

        Returns:
            Etat complet (URL, DOM elements, titre)
        """
        elements = self._extractor.format_for_llm(self._elements) if self._elements else "Aucun element"
        return {
            "url": self._current_url,
            "elements_summary": elements,
            "element_count": len(self._elements),
            "is_authenticated": self._is_authenticated,
        }

    def update_page_content(self, html: str) -> None:
        """Met a jour le contenu HTML de la page.

        Args:
            html: Nouveau contenu HTML
        """
        self._page_html = html
        self._elements = self._extractor.extract_interactive_elements(html)

    def click(self, element_index: int) -> Dict[str, Any]:
        """Clique sur un element par son index.

        Args:
            element_index: Index de l'element a cliquer

        Returns:
            Resultat du clic
        """
        elem = self._extractor.find_element_by_index(self._elements, element_index)
        if not elem:
            return {"status": "error", "message": f"Element {element_index} non trouve"}

        logger.info("Click sur element [%d] : <%s> '%s'",
                     element_index, elem.tag, elem.text[:50])

        # Si c'est un lien, naviguer
        if elem.tag == "a" and elem.attributes.get("href"):
            return self.navigate(elem.attributes["href"])

        return {"status": "success", "element": elem.format_for_llm()}

    def type_text(self, element_index: int, text: str) -> Dict[str, Any]:
        """Saisit du texte dans un element par son index.

        Args:
            element_index: Index de l'element
            text: Texte a saisir

        Returns:
            Resultat de la saisie
        """
        elem = self._extractor.find_element_by_index(self._elements, element_index)
        if not elem:
            return {"status": "error", "message": f"Element {element_index} non trouve"}

        if elem.tag not in ("input", "textarea"):
            return {"status": "error", "message": f"Element {element_index} n'est pas saisissable ({elem.tag})"}

        logger.info("Type '%s' dans element [%d]", text[:50], element_index)
        return {"status": "success", "element": elem.format_for_llm(), "text": text}

    def scroll(self, direction: str = "down", amount: int = 300) -> Dict[str, Any]:
        """Fait defiler la page.

        Args:
            direction: Direction du scroll ("up" ou "down")
            amount: Nombre de pixels

        Returns:
            Resultat du scroll
        """
        logger.info("Scroll %s de %dpx", direction, amount)
        return {"status": "success", "direction": direction, "amount": amount}

    def screenshot(self) -> bytes:
        """Prend une capture d'ecran de la page.

        Returns:
            Donnees de l'image (PNG)
        """
        logger.info("Screenshot pris")
        return b""  # Placeholder

    def go_back(self) -> Dict[str, Any]:
        """Revient a la page precedente."""
        if self._history:
            self._current_url = self._history.pop()
            return {"status": "success", "url": self._current_url}
        return {"status": "error", "message": "Pas d'historique"}


# ══════════════════════════════════════════════════════════════════════════════
#  BrowserAgent — Agent de navigation autonome
# ══════════════════════════════════════════════════════════════════════════════

class BrowserAgent:
    """Agent de navigation web autonome utilisant DOM intelligence.

    Combine un BrowserSession avec un callback LLM pour naviguer
    de maniere autonome sur le web en utilisant la representation
    token-efficient des elements DOM.

    Utilisation ::
        agent = BrowserAgent(session, llm_callback=my_llm)
        result = agent.execute_task("Cherche les prix des vols Paris-Tokyo")
    """

    def __init__(self, browser_session: BrowserSession,
                 llm_callback: Optional[Callable] = None,
                 max_steps: int = 20) -> None:
        """Initialise l'agent navigateur.

        Args:
            browser_session: Session navigateur persistante
            llm_callback: Fonction (prompt) -> str pour les decisions LLM
            max_steps: Nombre maximum d'etapes par tache
        """
        self.session = browser_session
        self.llm_callback = llm_callback
        self.max_steps = max_steps
        self._step_count = 0
        self._extractor = DOMExtractor()
        logger.info("BrowserAgent initialise (max_steps=%d)", max_steps)

    def observe(self) -> str:
        """Observe l'etat actuel de la page pour le LLM.

        Returns:
            Representation token-efficient de la page
        """
        state = self.session.get_page_state()
        return state.get("elements_summary", "Page vide")

    def act(self, action_description: str) -> Dict[str, Any]:
        """Execute une action basee sur la description du LLM.

        Parse la description de l'action et l'execute sur la session.

        Args:
            action_description: Description de l'action (ex: "click [3]", "type 'hello' in [5]")

        Returns:
            Resultat de l'action
        """
        self._step_count += 1
        action_lower = action_description.lower().strip()

        # Parser les actions courantes
        click_match = re.search(r"click\s*\[(\d+)\]", action_lower)
        if click_match:
            return self.session.click(int(click_match.group(1)))

        type_match = re.search(r"type\s*['\"](.+?)['\"]\s*(?:in|into|dans)\s*\[(\d+)\]", action_lower)
        if type_match:
            return self.session.type_text(int(type_match.group(2)), type_match.group(1))

        navigate_match = re.search(r"(?:navigate|go|aller)\s+(?:to|a|vers)\s+(.+)", action_lower)
        if navigate_match:
            url = navigate_match.group(1).strip()
            if not url.startswith("http"):
                url = f"https://{url}"
            return self.session.navigate(url)

        if "scroll" in action_lower:
            direction = "down" if "down" in action_lower or "bas" in action_lower else "up"
            return self.session.scroll(direction)

        if "back" in action_lower or "retour" in action_lower:
            return self.session.go_back()

        return {"status": "error", "message": f"Action non reconnue : {action_description}"}

    def execute_task(self, task_description: str) -> Dict[str, Any]:
        """Execute une tache web de maniere autonome.

        Args:
            task_description: Description de la tache a accomplir

        Returns:
            Resultat de l'execution avec trace
        """
        logger.info("BrowserAgent : execution tache '%s'", task_description[:100])
        self._step_count = 0
        trace: List[Dict[str, Any]] = []

        while self._step_count < self.max_steps:
            # Observer
            observation = self.observe()

            # Decider (via LLM ou simulation)
            if self.llm_callback:
                prompt = (
                    f"Tache : {task_description}\n\n"
                    f"Etat de la page :\n{observation}\n\n"
                    f"Quelle action executer ? (click [N], type 'text' in [N], navigate to URL, scroll, back)\n"
                    f"Reponds uniquement avec l'action, pas d'explication."
                )
                action = self.llm_callback(prompt)
            else:
                action = "done"

            # Verifier si la tache est terminee
            if action.lower().strip() in ("done", "termine", "fini", "complete"):
                break

            # Agir
            result = self.act(action)
            trace.append({
                "step": self._step_count,
                "observation": observation[:500],
                "action": action,
                "result": str(result)[:300],
            })

        return {
            "status": "completed" if self._step_count < self.max_steps else "max_steps_reached",
            "steps": self._step_count,
            "trace": trace,
        }
