"""
Fonctions utilitaires pour l'interface Qt.
Convertisseur Markdown, icônes SVG, gestion des sessions, pièces jointes,
calcul de tokens, vérification de santé des backends et styles UI.
Extrait de qtapp.py pour la refonte modulaire (Phase 3).
"""
from __future__ import annotations

import os
import re
import json
import base64
from datetime import datetime

from frontends.qt.constants import HISTORY_FILE, TEXT_FILE_EXTS, MAX_INLINE_CHARS, _icon_cache

# Import conditionnel de PySide6 — les fonctions pure-logic restent utilisables sans PySide6
try:
    from PySide6.QtCore import Qt, QByteArray
    from PySide6.QtGui import QPainter, QIcon, QPixmap
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False

try:
    from frontends.qt.theme import C, SCROLLBAR_STYLE
except ImportError:
    C = {}
    SCROLLBAR_STYLE = ""


# ── Markdown → HTML ────────────────────────────────────────────────────────────

def _md_to_html(text: str) -> str:
    try:
        import markdown
        return markdown.markdown(
            text, extensions=["fenced_code", "tables", "nl2br", "sane_lists"]
        )
    except ImportError:
        pass
    html, in_code, in_ul = [], False, False
    for raw in text.split("\n"):
        if raw.strip().startswith("```"):
            if in_code:
                html.append("</code></pre>")
            else:
                html.append("<pre><code>")
            in_code = not in_code
            continue
        if in_code:
            html.append(raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            continue
        line = raw
        line = re.sub(r"`([^`]+)`", r"<code>\1</code>", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
        line = re.sub(r"\*(.+?)\*", r"<i>\1</i>", line)
        line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', line)
        if re.match(r"^#{1,6}\s", line):
            lvl = len(line.split()[0])
            line = f"<h{lvl}>{line[lvl:].strip()}</h{lvl}>"
        elif re.match(r"^-{3,}$|^_{3,}$|^\*{3,}$", line.strip()):
            line = "<hr>"
        elif re.match(r"^\s*[-*+]\s", line):
            content = re.sub(r"^\s*[-*+]\s", "", line)
            if not in_ul:
                html.append("<ul>")
                in_ul = True
            line = f"<li>{content}</li>"
        else:
            if in_ul:
                html.append("</ul>")
                in_ul = False
            line = f"<p>{line}</p>" if line.strip() else ""
        html.append(line)
    if in_code:
        html.append("</code></pre>")
    if in_ul:
        html.append("</ul>")
    return "\n".join(html)


# ── SVG icon with cache ────────────────────────────────────────────────────────

def _svg_icon(key: str, svg_template: str, color: str = "#a1a1aa",
              size: int = 16):
    """Crée une icône SVG avec cache. Retourne None si PySide6 n'est pas disponible."""
    if not HAS_PYSIDE6:
        return None
    cache_key = f"{key}_{color}_{size}"
    if cache_key not in _icon_cache:
        try:
            from PySide6.QtSvg import QSvgRenderer
        except ImportError:
            return None
        data = QByteArray(svg_template.format(c=color).encode("utf-8"))
        renderer = QSvgRenderer(data)
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        _icon_cache[cache_key] = QIcon(pixmap)
    return _icon_cache[cache_key]


# ── utilities ──────────────────────────────────────────────────────────────────

def _make_session_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _load_history() -> list:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_history(history: list):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def _build_prompt_with_uploads(prompt: str, files: list) -> tuple:
    """
    files: list of {'name': str, 'type': str, 'raw': bytes}
    returns (full_prompt, display_prompt, display_attachments)
    """
    if not files:
        return prompt, prompt, []

    os.makedirs("temp/uploaded", exist_ok=True)
    attachment_chunks = ["\n\n[Fichier joint — sauvegardé sur le disque, lisible via file_read]"]
    display_attachments = []
    img_count, file_names = 0, []

    for f in files:
        raw, name, mime = f["raw"], f["name"], f.get("type", "")
        size = len(raw)
        ext = os.path.splitext(name)[1].lower()
        safe = re.sub(r"[^A-Za-z0-9._\-]", "_", name)
        saved = os.path.join(
            "temp", "uploaded",
            f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{safe}",
        )
        try:
            with open(saved, "wb") as out:
                out.write(raw)
        except Exception:
            saved = "(échec de sauvegarde)"

        if mime.startswith("image/"):
            b64 = base64.b64encode(raw).decode()
            attachment_chunks.append(
                f"\n- [Image jointe] {name} ({size} bytes)\n  Chemin disque : {saved}"
                f"\n  data:{mime};base64,{b64}"
            )
            display_attachments.append({"type": "image", "name": name})
            img_count += 1
        elif ext in TEXT_FILE_EXTS:
            text = raw.decode("utf-8", errors="replace")
            attachment_chunks.append(
                f"\n--- Fichier texte : {name} ({size} bytes) ---\nChemin disque : {saved}\n{text[:MAX_INLINE_CHARS]}"
                + ("\n[Contenu tronqué, utilisez file_read pour lire la totalité]" if len(text) > MAX_INLINE_CHARS else "")
            )
            display_attachments.append({"type": "file", "name": name})
            file_names.append(name)
        else:
            attachment_chunks.append(
                f"\n- Fichier : {name} ({size} bytes)\n  Chemin disque : {saved}"
            )
            display_attachments.append({"type": "file", "name": name})
            file_names.append(name)

    parts = []
    if img_count:
        parts.append(f"{img_count} image(s)")
    if file_names:
        parts.append(f"{len(file_names)} fichier(s) ({', '.join(file_names)})")
    display_prompt = f"{prompt}\n\n📎 Pièces jointes : {', '.join(parts)}" if parts else prompt
    return prompt + "\n".join(attachment_chunks), display_prompt, display_attachments


# ── Token usage calculation ────────────────────────────────────────────────────

def _estimate_token_usage(messages: list[dict], streaming_text: str = "",
                          is_streaming: bool = False) -> dict:
    """
    Estime l'utilisation de tokens pour un ensemble de messages.

    Parameters
    ----------
    messages : list[dict]
        Liste de messages avec clés 'role' et 'content'.
    streaming_text : str
        Texte en cours de streaming (ajouté aux tokens de sortie).
    is_streaming : bool
        Indique si un streaming est en cours.

    Returns
    -------
    dict
        {'in_tokens': int, 'out_tokens': int} — Estimation par char/2.5.
    """
    in_chars = sum(len(m.get("content", "")) for m in messages if m.get("role") == "user")
    out_chars = sum(len(m.get("content", "")) for m in messages if m.get("role") == "assistant")
    if is_streaming and streaming_text:
        out_chars += len(streaming_text)
    return {
        "in_tokens": int(in_chars / 2.5),
        "out_tokens": int(out_chars / 2.5),
    }


def _format_token_label(in_tokens: int, out_tokens: int) -> str:
    """
    Formate le label d'utilisation de tokens pour la barre de statut.

    Returns
    -------
    str
        Chaîne formatée ou chaîne vide si les deux tokens sont à zéro.
    """
    if in_tokens == 0 and out_tokens == 0:
        return ""
    return f"|   Contexte session : entrée {in_tokens}  sortie {out_tokens} tokens"


# ── Backend health check ───────────────────────────────────────────────────────

def _check_backend_health(backend) -> bool:
    """
    Vérifie la santé d'un backend LLM en envoyant un message test.

    Parameters
    ----------
    backend : object
        Objet backend avec une méthode ask() et un attribut model.

    Returns
    -------
    bool
        True si le backend répond correctement, False sinon.
    """
    ok = False
    try:
        reply = backend.ask("Bonjour")
        # Compatibilité : NativeClaudeSession.ask est un générateur
        if hasattr(reply, '__iter__') and not isinstance(reply, str):
            reply = ''.join(str(b) for b in reply if isinstance(b, str))
        text = str(reply).strip() if reply else ""
        ok = len(text) > 0 and not text.startswith("Error") and not text.startswith("[")
        print(f"[HealthCheck] Backend {type(backend).__name__}/{backend.model}: {'OK' if ok else 'FAIL'} -> {text[:60]}")
    except Exception as e:
        print(f"[HealthCheck] Backend {type(backend).__name__}/{backend.model}: ERROR -> {e}")
        ok = False
    # Nettoyer le message de test de l'historique du backend
    if hasattr(backend, 'raw_msgs') and backend.raw_msgs:
        backend.raw_msgs = [m for m in backend.raw_msgs if m.get("prompt") != "Bonjour"]
    return ok


# ── Session management helpers ─────────────────────────────────────────────────

def _auto_title_session(session: dict, messages: list[dict]) -> str:
    """
    Génère un titre automatique pour une session à partir du premier message utilisateur.

    Parameters
    ----------
    session : dict
        Session avec clé 'title'.
    messages : list[dict]
        Messages de la session.

    Returns
    -------
    str
        Nouveau titre (tronqué à 30 chars) ou le titre existant.
    """
    if session.get("title") != "Nouvelle conversation":
        return session["title"]
    first_user = next(
        (m["content"] for m in messages if m.get("role") == "user"), ""
    )
    if first_user:
        return first_user[:30].replace("\n", " ")
    return session["title"]


def _merge_session_into_history(history: list[dict], session: dict) -> list[dict]:
    """
    Fusionne une session dans l'historique existant.
    Si une session avec le même ID existe, elle est mise à jour.
    Sinon, la session est ajoutée.

    Parameters
    ----------
    history : list[dict]
        Historique existant.
    session : dict
        Session à fusionner.

    Returns
    -------
    list[dict]
        Nouvel historique avec la session fusionnée.
    """
    for i, s in enumerate(history):
        if s.get("id") == session.get("id"):
            history[i] = session.copy()
            break
    else:
        history.append(session.copy())
    return history


# ── UI style helpers ───────────────────────────────────────────────────────────

def _small_btn_style(color: str) -> str:
    """
    Génère une feuille de style CSS pour un petit bouton coloré.

    Parameters
    ----------
    color : str
        Couleur de fond (hex ou nom CSS).

    Returns
    -------
    str
        Chaîne CSS pour QPushButton.
    """
    return (
        f"QPushButton {{ background: {color}; color: white; border: none;"
        f" border-radius: 7px; padding: 4px 12px; font-size: 12px; font-weight: 600; }}"
        f"QPushButton:hover {{ opacity: 0.85; }}"
    )


# Modèle de styles pour les lignes de modèle dans les paramètres
MODEL_ROW_STYLE = (
    "QPushButton { background: rgba(39,39,42,0.7); color: #e4e4e7;"
    " border: 1px solid #3f3f46; border-radius: 8px;"
    " padding: 6px 10px; font-size: 12px; font-weight: 700; text-align: left; }"
    " QPushButton:hover { background: rgba(63,63,70,0.8); }"
)
MODEL_ROW_ACTIVE = (
    "QPushButton { background: rgba(124,58,237,0.25); color: #c4b5fd;"
    " border: 1px solid rgba(124,58,237,0.5); border-radius: 8px;"
    " padding: 6px 10px; font-size: 12px; font-weight: 700; text-align: left; }"
    " QPushButton:hover { background: rgba(124,58,237,0.35); }"
)
