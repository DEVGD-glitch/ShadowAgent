"""GenericAgent v0.6.0 — Closed Learning Loop : Cycle auto-evolutif Discover->Execute->Reflect->Codify->Improve.

Inspire de Hermes Agent (NousResearch/hermes-agent).
Fournit le mecanisme central d'auto-evolution : l'agent decouvre, execute,
reflechit, codifie en skills, et s'ameliorne continuellement.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Tuple

logger = logging.getLogger("ga.agentmain.closed_learning")


# ══════════════════════════════════════════════════════════════════════════════
#  SkillDocument — Format de skill standard (agentskills.io compatible)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SkillDocument:
    """Document de skill au format agentskills.io.

    Represente une competence cristallisee que l'agent peut reutiliser.

    Attributes:
        name: Nom unique du skill
        description: Description detaillee de la capacite
        domain: Domaine de competences (ex: "web_automation", "data_analysis")
        steps: Liste ordonnee des etapes d'execution
        prerequisites: Conditions prealables pour utiliser ce skill
        success_indicators: Criteres de reussite de l'execution
        version: Version du skill (semver)
        created_at: Date de creation (ISO 8601)
        updated_at: Date de derniere mise a jour (ISO 8601)
        usage_count: Nombre d'utilisations
        success_rate: Taux de reussite (0.0 a 1.0)
        tags: Mots-cles pour la recherche
    """
    name: str
    description: str
    domain: str = "general"
    steps: List[Dict[str, str]] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    success_indicators: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    usage_count: int = 0
    success_rate: float = 1.0
    tags: List[str] = field(default_factory=list)

    def record_usage(self, success: bool) -> None:
        """Enregistre une utilisation et met a jour le taux de reussite."""
        total = self.usage_count
        successes = int(total * self.success_rate)
        self.usage_count += 1
        if success:
            successes += 1
        self.success_rate = successes / self.usage_count if self.usage_count > 0 else 0.0
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_agentskills_io(self) -> Dict[str, Any]:
        """Exporte au format agentskills.io compatible.

        Returns:
            Dictionnaire au format standard agentskills.io
        """
        return {
            "schema_version": "1.0",
            "skill": {
                "name": self.name,
                "description": self.description,
                "domain": self.domain,
                "steps": self.steps,
                "prerequisites": self.prerequisites,
                "success_indicators": self.success_indicators,
                "metadata": {
                    "version": self.version,
                    "created_at": self.created_at,
                    "updated_at": self.updated_at,
                    "usage_count": self.usage_count,
                    "success_rate": round(self.success_rate, 3),
                    "tags": self.tags,
                },
            },
        }

    @classmethod
    def from_agentskills_io(cls, data: Dict[str, Any]) -> "SkillDocument":
        """Importe depuis le format agentskills.io.

        Args:
            data: Dictionnaire au format agentskills.io

        Returns:
            Instance de SkillDocument
        """
        skill_data = data.get("skill", data)
        meta = skill_data.get("metadata", {})
        return cls(
            name=skill_data.get("name", "unknown"),
            description=skill_data.get("description", ""),
            domain=skill_data.get("domain", "general"),
            steps=skill_data.get("steps", []),
            prerequisites=skill_data.get("prerequisites", []),
            success_indicators=skill_data.get("success_indicators", []),
            version=meta.get("version", "1.0.0"),
            created_at=meta.get("created_at", ""),
            updated_at=meta.get("updated_at", ""),
            usage_count=meta.get("usage_count", 0),
            success_rate=meta.get("success_rate", 1.0),
            tags=meta.get("tags", []),
        )

    def to_json(self) -> str:
        """Serialize en JSON."""
        return json.dumps(self.to_agentskills_io(), indent=2, ensure_ascii=False)


# ══════════════════════════════════════════════════════════════════════════════
#  SkillToolset — Progressive disclosure (Google ADK-inspired)
# ══════════════════════════════════════════════════════════════════════════════

class SkillToolset:
    """Ensemble de skills avec chargement progressif a la demande.

    Inspire du SkillToolset de Google ADK. Seuls les N skills les plus
    pertinents sont charges dans le contexte, reduisant la consommation
    de tokens.

    Attributes:
        max_skills_in_context: Nombre maximum de skills injectes dans le prompt
    """

    def __init__(self, max_skills_in_context: int = 3) -> None:
        self.max_skills_in_context = max_skills_in_context
        self._skills: Dict[str, SkillDocument] = {}
        self._domain_index: Dict[str, List[str]] = {}
        logger.info("SkillToolset initialise (max %d skills en contexte)", max_skills_in_context)

    def register_skill(self, skill_doc: SkillDocument) -> None:
        """Enregistre un skill dans le toolset.

        Args:
            skill_doc: Document du skill a enregistrer
        """
        self._skills[skill_doc.name] = skill_doc
        domain = skill_doc.domain
        if domain not in self._domain_index:
            self._domain_index[domain] = []
        if skill_doc.name not in self._domain_index[domain]:
            self._domain_index[domain].append(skill_doc.name)
        logger.debug("Skill enregistre : %s (domaine: %s)", skill_doc.name, domain)

    def get_relevant_skills(self, context: str, n: Optional[int] = None) -> List[SkillDocument]:
        """Recupere les N skills les plus pertinents pour un contexte donne.

        Utilise un scoring base sur la correspondance de mots-cles,
        le domaine, et le taux de reussite.

        Args:
            context: Contexte de la tache actuelle
            n: Nombre de skills a retourner (defaut: max_skills_in_context)

        Returns:
            Liste des skills les plus pertinents, tries par score
        """
        n = n or self.max_skills_in_context
        if not self._skills:
            return []

        context_lower = context.lower()
        context_words = set(context_lower.split())
        scored: List[Tuple[float, SkillDocument]] = []

        for skill in self._skills.values():
            score = 0.0
            # Correspondance du nom
            if skill.name.lower() in context_lower:
                score += 10.0
            # Correspondance des tags
            for tag in skill.tags:
                if tag.lower() in context_lower:
                    score += 5.0
            # Correspondance du domaine
            if skill.domain.lower() in context_lower:
                score += 3.0
            # Correspondance des mots-cles dans la description
            desc_words = set(skill.description.lower().split())
            overlap = context_words & desc_words
            score += len(overlap) * 0.5
            # Bonus de taux de reussite
            score *= (0.5 + 0.5 * skill.success_rate)
            # Malus d'usage (privilegier les skills recemment utiles)
            if skill.usage_count > 0:
                score *= min(1.0, skill.success_rate + 0.1)

            scored.append((score, skill))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:n]]

    def format_skills_prompt(self, skills: Optional[List[SkillDocument]] = None,
                             context: str = "") -> str:
        """Formate les skills pour injection dans le system prompt.

        Args:
            skills: Skills a formater (si None, recupere automatiquement)
            context: Contexte pour la selection automatique

        Returns:
            Texte formate pour le prompt systeme
        """
        if skills is None:
            skills = self.get_relevant_skills(context)

        if not skills:
            return ""

        parts = ["\n## Skills disponibles (charges progressivement) :\n"]
        for i, skill in enumerate(skills, 1):
            parts.append(f"### {i}. {skill.name} (v{skill.version})")
            parts.append(f"   Domaine: {skill.domain} | Reussite: {skill.success_rate:.0%} | Utilisations: {skill.usage_count}")
            parts.append(f"   {skill.description}")
            if skill.steps:
                parts.append(f"   Etapes: {len(skill.steps)} etapes definies")
            parts.append("")

        return "\n".join(parts)

    def list_skills(self) -> List[Dict[str, Any]]:
        """Liste tous les skills enregistres avec leurs metadonnees."""
        return [
            {
                "name": s.name,
                "domain": s.domain,
                "version": s.version,
                "usage_count": s.usage_count,
                "success_rate": s.success_rate,
            }
            for s in self._skills.values()
        ]


# ══════════════════════════════════════════════════════════════════════════════
#  SelfNudge — Persistance proactive avant perte de contexte
# ══════════════════════════════════════════════════════════════════════════════

class SelfNudge:
    """Persistance proactive des connaissances avant perte de contexte.

    Inspire du self-nudge de Hermes Agent. L'agent persiste proactivement
    ses connaissances avant que le contexte ne soit perdu, prevenant
    ainsi les pertes d'information aux frontieres de contexte.

    Attributes:
        nudge_interval_turns: Nombre de tours entre les nudges
        context_window_ratio: Ratio d'utilisation du contexte declenchant un nudge
    """

    def __init__(self, nudge_interval_turns: int = 10,
                 context_window_ratio: float = 0.8) -> None:
        self.nudge_interval_turns = nudge_interval_turns
        self.context_window_ratio = context_window_ratio
        self._last_nudge_turn = 0
        self._nudge_count = 0
        logger.info("SelfNudge initialise (interval=%d tours, ratio=%.0f%%)",
                     nudge_interval_turns, context_window_ratio * 100)

    def should_nudge(self, current_turn: int, context_usage: float = 0.0) -> bool:
        """Determine si un nudge de persistance est necessaire.

        Args:
            current_turn: Numero du tour actuel
            context_usage: Ratio d'utilisation du contexte (0.0 a 1.0)

        Returns:
            True si un nudge est necessaire
        """
        # Nudge periodique
        if current_turn - self._last_nudge_turn >= self.nudge_interval_turns:
            return True
        # Nudge d'urgence si contexte presque plein
        if context_usage >= self.context_window_ratio:
            return True
        return False

    def nudge(self, agent_state: Dict[str, Any]) -> Dict[str, Any]:
        """Persiste les informations cles de l'etat de l'agent.

        Extrait et sauvegarde les elements les plus importants de l'etat
        actuel avant qu'ils ne soient perdus.

        Args:
            agent_state: Etat actuel de l'agent (messages, key_info, etc.)

        Returns:
            Dictionnaire des informations persistees
        """
        self._nudge_count += 1
        persisted: Dict[str, Any] = {
            "nudge_id": self._nudge_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "turn": agent_state.get("current_turn", 0),
        }

        # Extraire les informations cles
        messages = agent_state.get("messages", [])
        if messages:
            # Sauvegarder les derniers echanges
            recent = messages[-6:] if len(messages) > 6 else messages
            persisted["recent_context"] = [
                {"role": m.get("role", ""), "content": str(m.get("content", ""))[:500]}
                for m in recent
            ]

        # Sauvegarder les key_info
        key_info = agent_state.get("key_info", {})
        if key_info:
            persisted["key_info"] = key_info

        # Sauvegarder le checkpoint de travail
        working_checkpoint = agent_state.get("working_checkpoint", "")
        if working_checkpoint:
            persisted["working_checkpoint"] = working_checkpoint[:2000]

        logger.info("SelfNudge #%d execute : %d cles persistees",
                     self._nudge_count, len(persisted))
        return persisted


# ══════════════════════════════════════════════════════════════════════════════
#  ClosedLearningLoop — Cycle complet d'auto-evolution
# ══════════════════════════════════════════════════════════════════════════════

class ClosedLearningLoop:
    """Cycle d'apprentissage ferme : Discover -> Execute -> Reflect -> Codify -> Improve.

    Le coeur du mecanisme d'auto-evolution. L'agent decouvre une nouvelle tache,
    l'execute, reflechit sur le resultat, codifie le chemin en skill, et
    ameliore les skills existants avec le feedback.

    Utilisation ::
        loop = ClosedLearningLoop(agent)
        result = loop.run_full_cycle("Analyser les ventes du trimestre")
    """

    def __init__(self, agent: Any = None,
                 min_tool_calls_for_skill: int = 5,
                 reflection_enabled: bool = True) -> None:
        """Initialise la boucle d'apprentissage ferme.

        Args:
            agent: Instance de l'agent GenericAgent
            min_tool_calls_for_skill: Nombre minimum d'appels d'outils pour cristalliser un skill
            reflection_enabled: Activer la phase de reflexion
        """
        self.agent = agent
        self.min_tool_calls_for_skill = min_tool_calls_for_skill
        self.reflection_enabled = reflection_enabled
        self._skill_toolset = SkillToolset()
        self._self_nudge = SelfNudge()
        self._execution_traces: List[Dict[str, Any]] = []
        logger.info("ClosedLearningLoop initialise (min_tools=%d, reflection=%s)",
                     min_tool_calls_for_skill, reflection_enabled)

    # ── Phase 1 : Decouverte ─────────────────────────────────────────────

    def discover(self, task: str) -> Dict[str, Any]:
        """Decouvre une nouvelle tache et collecte les observations.

        Explore l'environnement et les skills existants pour comprendre
        le contexte de la tache.

        Args:
            task: Description de la tache a decouvrir

        Returns:
            Observations collectees (contexte, skills pertinents, ressources)
        """
        logger.info("Phase Discover : %s", task[:100])

        observations: Dict[str, Any] = {
            "task": task,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "relevant_skills": [],
            "domain_hints": [],
        }

        # Rechercher les skills pertinents
        relevant = self._skill_toolset.get_relevant_skills(task)
        if relevant:
            observations["relevant_skills"] = [
                {"name": s.name, "domain": s.domain, "success_rate": s.success_rate}
                for s in relevant
            ]

        # Detecter le domaine
        domain_keywords = {
            "web_automation": ["navigateur", "browser", "web", "site", "page", "click"],
            "data_analysis": ["analyser", "data", "csv", "excel", "statistiques", "graphique"],
            "code_generation": ["code", "programme", "script", "fonction", "class"],
            "communication": ["email", "message", "envoyer", "notifier", "slack"],
            "file_management": ["fichier", "dossier", "lire", "ecrire", "organiser"],
        }
        task_lower = task.lower()
        for domain, keywords in domain_keywords.items():
            if any(kw in task_lower for kw in keywords):
                observations["domain_hints"].append(domain)

        return observations

    # ── Phase 2 : Execution ──────────────────────────────────────────────

    def execute(self, task: str, observations: Dict[str, Any]) -> Dict[str, Any]:
        """Execute la tache avec le contexte collecte.

        Args:
            task: Description de la tache
            observations: Observations de la phase Discover

        Returns:
            Trace d'execution (resultat, appels d'outils, duree)
        """
        logger.info("Phase Execute : %s", task[:100])
        start_time = time.monotonic()

        execution_trace: Dict[str, Any] = {
            "task": task,
            "observations": observations,
            "tool_calls": [],
            "result": None,
            "success": False,
            "duration_ms": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            if self.agent and hasattr(self.agent, "put_task"):
                # Execution reelle via l'agent
                queue = self.agent.put_task(task)
                results = []
                tool_call_count = 0
                while True:
                    try:
                        item = queue.get(timeout=300)
                        if item.get("type") == "done":
                            execution_trace["result"] = item.get("content", "")
                            execution_trace["success"] = True
                            break
                        elif item.get("type") == "tool_call":
                            tool_call_count += 1
                            execution_trace["tool_calls"].append({
                                "tool": item.get("tool", ""),
                                "args": str(item.get("args", ""))[:200],
                            })
                        results.append(item)
                    except Exception:
                        break
            else:
                # Mode simulation (pas d'agent reel)
                execution_trace["result"] = f"Execution simulee pour : {task}"
                execution_trace["success"] = True

        except Exception as e:
            execution_trace["result"] = f"Erreur : {e}"
            execution_trace["success"] = False
            logger.error("Erreur execution : %s", e)

        execution_trace["duration_ms"] = int((time.monotonic() - start_time) * 1000)
        self._execution_traces.append(execution_trace)
        return execution_trace

    # ── Phase 3 : Reflexion ──────────────────────────────────────────────

    def reflect(self, execution_trace: Dict[str, Any]) -> Dict[str, Any]:
        """Reflechit sur l'execution et identifie les ameliorations.

        Auto-critique le chemin d'execution pour determiner ce qui a bien
        fonctionne et ce qui pourrait etre ameliore.

        Args:
            execution_trace: Trace d'execution de la phase Execute

        Returns:
            Reflexion avec points positifs, ameliorations, et score
        """
        logger.info("Phase Reflect")

        reflection: Dict[str, Any] = {
            "positives": [],
            "improvements": [],
            "score": 0.0,
            "should_codify": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if not self.reflection_enabled:
            return reflection

        # Analyser la trace d'execution
        tool_calls = execution_trace.get("tool_calls", [])
        success = execution_trace.get("success", False)
        duration = execution_trace.get("duration_ms", 0)

        # Points positifs
        if success:
            reflection["positives"].append("Tache completee avec succes")
        if len(tool_calls) > 0:
            reflection["positives"].append(f"{len(tool_calls)} appels d'outils effectues")
        if duration < 30000:
            reflection["positives"].append("Execution rapide (< 30s)")

        # Ameliorations potentielles
        if not success:
            reflection["improvements"].append("Tache echouee - investiguer les causes")
        if len(tool_calls) > 20:
            reflection["improvements"].append("Trop d'appels d'outils - optimiser le chemin")
        if duration > 120000:
            reflection["improvements"].append("Execution lente - chercher des raccourcis")

        # Score de qualite
        score = 0.0
        if success:
            score += 0.5
        if len(tool_calls) > 0 and len(tool_calls) < 20:
            score += 0.3
        if duration < 60000:
            score += 0.2
        reflection["score"] = score

        # Decision de codification
        reflection["should_codify"] = (
            len(tool_calls) >= self.min_tool_calls_for_skill
            and success
            and score >= 0.5
        )

        return reflection

    # ── Phase 4 : Codification ───────────────────────────────────────────

    def codify(self, execution_trace: Dict[str, Any],
               reflection: Dict[str, Any]) -> Optional[SkillDocument]:
        """Cristallise le chemin d'execution en un skill document.

        Cree un SkillDocument formel a partir de la trace d'execution
        et de la reflexion, si les criteres de qualite sont remplis.

        Args:
            execution_trace: Trace d'execution
            reflection: Reflexion sur l'execution

        Returns:
            SkillDocument si codifie, None sinon
        """
        logger.info("Phase Codify")

        if not reflection.get("should_codify", False):
            logger.info("Codification annulee : criteres non remplis")
            return None

        task = execution_trace.get("task", "unknown_task")
        tool_calls = execution_trace.get("tool_calls", [])

        # Generer le domaine
        domain = "general"
        domain_hints = execution_trace.get("observations", {}).get("domain_hints", [])
        if domain_hints:
            domain = domain_hints[0]

        # Creer les etapes a partir des appels d'outils
        steps = []
        for i, tc in enumerate(tool_calls, 1):
            steps.append({
                "step": str(i),
                "tool": tc.get("tool", ""),
                "description": f"Appel de l'outil {tc.get('tool', '')}",
                "args_summary": tc.get("args", "")[:200],
            })

        # Creer le skill document
        skill = SkillDocument(
            name=f"skill_{domain}_{int(time.time())}",
            description=f"Skill cristallise pour : {task[:200]}",
            domain=domain,
            steps=steps,
            prerequisites=[],
            success_indicators=["Tache completee avec succes"],
            version="1.0.0",
            tags=[domain, "auto-generated", "closed-learning"],
        )

        # Enregistrer dans le toolset
        self._skill_toolset.register_skill(skill)
        logger.info("Skill codifie : %s (%d etapes, domaine: %s)",
                     skill.name, len(steps), domain)

        return skill

    # ── Phase 5 : Amelioration ───────────────────────────────────────────

    def improve(self, skill: SkillDocument, feedback: str) -> SkillDocument:
        """Ameliore un skill existant base sur le feedback.

        Met a jour les etapes, le taux de reussite, et la description
        du skill en fonction du retour d'experience.

        Args:
            skill: Skill a ameliorer
            feedback: Feedback textuel sur l'execution du skill

        Returns:
            Skill ameliore
        """
        logger.info("Phase Improve : %s", skill.name)

        # Incrementer la version
        parts = skill.version.split(".")
        if len(parts) >= 2:
            parts[1] = str(int(parts[1]) + 1)
            skill.version = ".".join(parts)

        # Mettre a jour la description avec le feedback
        skill.description = f"{skill.description}\n\nFeedback: {feedback[:500]}"

        # Mettre a jour les tags
        if "improved" not in skill.tags:
            skill.tags.append("improved")

        skill.updated_at = datetime.now(timezone.utc).isoformat()
        logger.info("Skill ameliore : %s v%s", skill.name, skill.version)
        return skill

    # ── Cycle complet ────────────────────────────────────────────────────

    def run_full_cycle(self, task: str) -> Dict[str, Any]:
        """Execute le cycle complet Discover->Execute->Reflect->Codify->Improve.

        Args:
            task: Description de la tache

        Returns:
            Resultat complet du cycle avec toutes les phases
        """
        logger.info("=== Cycle complet demarre : %s ===", task[:80])
        start_time = time.monotonic()

        # Phase 1 : Decouverte
        observations = self.discover(task)

        # Phase 2 : Execution
        execution_trace = self.execute(task, observations)

        # Phase 3 : Reflexion
        reflection = self.reflect(execution_trace)

        # Phase 4 : Codification
        skill = self.codify(execution_trace, reflection)

        # Phase 5 : Amelioration (si skill existant similaire)
        if skill:
            existing = self._skill_toolset.get_relevant_skills(task, n=1)
            if existing and existing[0].name != skill.name:
                self.improve(existing[0], f"Nouveau skill similaire cree : {skill.name}")

        result = {
            "task": task,
            "observations": observations,
            "execution_trace": {
                "success": execution_trace.get("success", False),
                "tool_calls": len(execution_trace.get("tool_calls", [])),
                "duration_ms": execution_trace.get("duration_ms", 0),
            },
            "reflection": {
                "score": reflection.get("score", 0),
                "should_codify": reflection.get("should_codify", False),
            },
            "skill_created": skill.to_agentskills_io() if skill else None,
            "total_duration_ms": int((time.monotonic() - start_time) * 1000),
        }

        logger.info("=== Cycle complet termine en %dms (skill: %s) ===",
                     result["total_duration_ms"],
                     skill.name if skill else "aucun")
        return result

    # ── Accesseurs ───────────────────────────────────────────────────────

    @property
    def skill_toolset(self) -> SkillToolset:
        """Retourne le toolset de skills."""
        return self._skill_toolset

    @property
    def self_nudge(self) -> SelfNudge:
        """Retourne le gestionnaire de nudge."""
        return self._self_nudge

    @property
    def execution_traces(self) -> List[Dict[str, Any]]:
        """Retourne l'historique des traces d'execution."""
        return self._execution_traces
