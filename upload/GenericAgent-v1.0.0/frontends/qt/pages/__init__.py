"""
Pages modulaires pour l'interface Qt GenericAgent.

Chaque page est un widget autonome qui peut être construit indépendamment
et inséré dans le QStackedWidget principal.

Pages disponibles :
- ChatPage      : Zone de messages + saisie, streaming, pièces jointes
- HistoryPage   : Liste de l'historique des sessions
- SOPPage       : Visionneuse de procédures (SOP)
- SettingsPage  : Panneau de contrôle, modèles, santé, mode autonome
"""
from __future__ import annotations

from frontends.qt.pages.chat_page import ChatPage
from frontends.qt.pages.history_page import HistoryPage
from frontends.qt.pages.sop_page import SOPPage
from frontends.qt.pages.settings_page import SettingsPage
from frontends.qt.pages.onboarding_page import OnboardingWizard, has_credentials

__all__ = ["ChatPage", "HistoryPage", "SOPPage", "SettingsPage", "OnboardingWizard", "has_credentials"]
