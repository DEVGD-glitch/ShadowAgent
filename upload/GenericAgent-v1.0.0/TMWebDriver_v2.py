"""
TMWebDriver.py — Pilote de navigateur pour GenericAgent

Version améliorée avec :
- Remplacement de simple-websocket-server par websockets (robuste, maintenu)
- Reconnexion automatique avec backoff exponentiel
- Heartbeat/ping pour détecter les connexions mortes
- Messages d'erreur traduits via le système i18n
- Pas de time.sleep() magique — retry intelligent

Compatibilité : Windows, macOS, Linux
"""
import json, threading, time, uuid, queue, socket, requests, traceback, asyncio, logging
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup
import bottle, random
from bottle import route, template, request, response

logger = logging.getLogger("TMWebDriver")

# ══════════════════════════════════════════════════════════════════════════════
#  Système i18n — traduction des messages
# ══════════════════════════════════════════════════════════════════════════════
import os
_LANG = os.environ.get("GA_LANG", "").strip().lower()
if _LANG not in ("fr", "en", "zh"):
    try:
        import mykey
        _LANG = getattr(mykey, "GA_LANG", "fr").strip().lower()
    except ImportError:
        _LANG = "fr"

def _t(key, *args):
    """Traduction rapide sans dépendance circulaire."""
    _msgs = {
        "tab_disconnected": {"fr": "Onglet déconnecté", "en": "Tab disconnected", "zh": "标签页断开连接"},
        "tab_connected": {"fr": "Nouvel onglet connecté", "en": "New tab connected", "zh": "新标签页连接"},
        "tab_reconnected": {"fr": "Onglet reconnecté", "en": "Tab reconnected", "zh": "标签页重新连接"},
        "http_connected": {"fr": "Navigateur HTTP connecté", "en": "Browser HTTP connected", "zh": "浏览器HTTP连接"},
        "ws_server_running": {"fr": "Serveur WebSocket en cours d'exécution", "en": "WebSocket server running", "zh": "WebSocket服务器运行中"},
        "session_not_connected": {"fr": "Session {} non connectée", "en": "Session {} not connected", "zh": "会话 {} 未连接"},
        "session_auto_switch": {"fr": "Session {} non connectée, basculement vers {}", "en": "Session {} not connected, switching to {}", "zh": "会话 {} 未连接，切换到 {}"},
        "master_not_running": {"fr": "Le serveur maître TMWebDriver n'est pas en cours d'exécution", "en": "TMWebDriver master server is not running", "zh": "TMWebDriver master未运行"},
        "url_not_found": {"fr": "Aucune session trouvée avec URL contenant '{}'", "en": "No session found with URL containing '{}'", "zh": "未找到URL包含 '{}' 的会话"},
        "url_multiple": {"fr": "Plusieurs sessions trouvées, sélection de la première", "en": "Multiple sessions found, selecting first", "zh": "找到多个会话，选择第一个"},
        "session_set_ok": {"fr": "Session par défaut définie : {}", "en": "Default session set: {}", "zh": "成功设置默认会话: {}"},
        "reconnecting": {"fr": "Tentative de reconnexion...", "en": "Attempting reconnection...", "zh": "尝试重新连接..."},
        "reconnect_failed": {"fr": "Échec de reconnexion après {} tentatives", "en": "Reconnection failed after {} attempts", "zh": "重连失败，已尝试 {} 次"},
        "ws_closed": {"fr": "Connexion WS fermée", "en": "WS connection closed", "zh": "WS连接关闭"},
        "ws_error": {"fr": "Erreur WS", "en": "WS error", "zh": "WS错误"},
        "new_ws_connection": {"fr": "Nouvelle connexion WS depuis {}", "en": "New WS connection from {}", "zh": "新WS连接来自 {}"},
        "tabs_update": {"fr": "Mise à jour onglets reçue : {}", "en": "Tabs update received: {}", "zh": "收到标签页更新: {}"},
    }
    msg = _msgs.get(key, {}).get(_LANG, key)
    if args:
        try:
            return msg.format(*args)
        except (IndexError, KeyError):
            return msg
    return msg


# ══════════════════════════════════════════════════════════════════════════════
#  Session — Représente un onglet de navigateur connecté
# ══════════════════════════════════════════════════════════════════════════════
class Session:
    # Timeout de session inactive configurable (au lieu de 60 hardcodé)
    HTTP_SESSION_TIMEOUT = 60  # secondes
    CLEANUP_DELAY = 600        # secondes avant suppression définitive

    def __init__(self, session_id, info, client=None):
        self.id = session_id
        self.info = info
        self.connect_at = time.time()
        self.disconnect_at = None
        self.type = info.get('type', 'ws')
        self.ws_client = client if self.type in ('ws', 'ext_ws') else None
        self.http_queue = client if self.type == 'http' else None
        self.last_heartbeat = time.time()  # Nouveau : suivi du dernier heartbeat

    @property
    def url(self):
        return self.info.get('url', '')

    def is_active(self):
        if self.type == 'http' and time.time() - self.connect_at > self.HTTP_SESSION_TIMEOUT:
            self.mark_disconnected()
        return self.disconnect_at is None

    def update_heartbeat(self):
        """Met à jour le timestamp du dernier heartbeat."""
        self.last_heartbeat = time.time()

    def is_heartbeat_stale(self, timeout=30):
        """Vérifie si le heartbeat est dépassé (connexion potentiellement morte)."""
        return time.time() - self.last_heartbeat > timeout

    def reconnect(self, client, info):
        self.info = info
        self.type = info.get('type', 'ws')
        if self.type in ('ws', 'ext_ws'):
            self.ws_client = client
            self.http_queue = None
        elif self.type == 'http':
            self.http_queue = client
        self.connect_at = time.time()
        self.disconnect_at = None
        self.update_heartbeat()

    def mark_disconnected(self):
        if self.is_active():
            logger.info(_t("tab_disconnected") + f" : {self.url} (Session: {self.id})")
        self.disconnect_at = time.time()


# ══════════════════════════════════════════════════════════════════════════════
#  TMWebDriver — Pilote principal
# ══════════════════════════════════════════════════════════════════════════════
class TMWebDriver:
    # Configuration de reconnexion
    RECONNECT_MAX_RETRIES = 3
    RECONNECT_BASE_DELAY = 1.0   # secondes (double à chaque tentative)
    HEARTBEAT_INTERVAL = 10      # secondes entre les heartbeats

    def __init__(self, host: str = '127.0.0.1', port: int = 18765):
        self.host, self.port = host, port
        self.sessions, self.results, self.acks = {}, {}, {}
        self.default_session_id = None
        self.latest_session_id = None
        self.is_remote = socket.socket().connect_ex((host, port + 1)) == 0

        if not self.is_remote:
            self.start_http_server()
            self._start_ws_server()
            self._start_heartbeat_monitor()
        else:
            self.remote = f'http://{self.host}:{self.port + 1}/link'

    # ── Serveur HTTP (bottle) ────────────────────────────────────────────────
    def start_http_server(self):
        self.app = app = bottle.Bottle()

        @app.route('/api/longpoll', method=['GET', 'POST'])
        def long_poll():
            data = request.json
            session_id = data.get('sessionId')
            session_info = {'url': data.get('url'), 'title': data.get('title', ''), 'type': 'http'}
            if session_id not in self.sessions:
                session = Session(session_id, session_info, queue.Queue())
                logger.info(_t("http_connected") + f" : {session.url} (Session: {session_id})")
                self.sessions[session_id] = session
            session = self.sessions[session_id]
            if session.disconnect_at is not None and session.type != 'http':
                session.reconnect(queue.Queue(), session_info)
            session.disconnect_at = None
            session.update_heartbeat()
            if session.type == 'http':
                msgQ = session.http_queue
            else:
                return json.dumps({"id": "", "ret": "use ws"})
            session.connect_at = start_time = time.time()
            while time.time() - start_time < 5:
                try:
                    msg = msgQ.get(timeout=0.2)
                    try:
                        self.acks[json.loads(msg).get('id', '')] = True
                    except Exception:
                        traceback.print_exc()
                    return msg
                except queue.Empty:
                    continue
            return json.dumps({"id": "", "ret": "next long-poll"})

        @app.route('/api/result', method=['GET', 'POST'])
        def result():
            data = request.json
            if data.get('type') == 'result':
                self.results[data.get('id')] = {'success': True, 'data': data.get('result'), 'newTabs': data.get('newTabs', [])}
            elif data.get('type') == 'error':
                self.results[data.get('id')] = {'success': False, 'data': data.get('error'), 'newTabs': data.get('newTabs', [])}
            return 'ok'

        @app.route('/link', method=['GET', 'POST'])
        def link():
            data = request.json
            if data.get('cmd') == 'get_all_sessions':
                return json.dumps({'r': self.get_all_sessions()}, ensure_ascii=False)
            if data.get('cmd') == 'find_session':
                url_pattern = data.get('url_pattern', '')
                return json.dumps({'r': self.find_session(url_pattern)}, ensure_ascii=False)
            if data.get('cmd') == 'execute_js':
                session_id = data.get('sessionId')
                code = data.get('code')
                timeout = float(data.get('timeout', 10.0))
                try:
                    result = self.execute_js(code, timeout=timeout, session_id=session_id)
                    return json.dumps({'r': result}, ensure_ascii=False)
                except Exception as e:
                    return json.dumps({'r': {'error': str(e)}}, ensure_ascii=False)
            return 'ok'

        def run():
            from wsgiref.simple_server import make_server, WSGIServer, WSGIRequestHandler
            from socketserver import ThreadingMixIn
            class _T(ThreadingMixIn, WSGIServer): pass
            class _H(WSGIRequestHandler):
                def log_request(self, *a): pass
            make_server(self.host, self.port + 1, app, server_class=_T, handler_class=_H).serve_forever()

        http_thread = threading.Thread(target=run, daemon=True)
        http_thread.start()

    # ── Serveur WebSocket (avec websockets) ──────────────────────────────────
    def _start_ws_server(self):
        """Démarre le serveur WebSocket en utilisant la bibliothèque websockets."""
        driver = self

        async def handle_connection(websocket):
            """Gère une connexion WebSocket individuelle."""
            logger.info(_t("new_ws_connection", websocket.remote_address if hasattr(websocket, 'remote_address') else '?'))
            try:
                async for raw_message in websocket:
                    try:
                        data = json.loads(raw_message)
                        await driver._handle_ws_message(data, websocket)
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON from WS: {e}")
                    except Exception as e:
                        logger.error(f"Error handling WS message: {e}")
            except Exception as e:
                logger.debug(_t("ws_closed") + f": {e}")
            finally:
                driver._unregister_client(websocket)

        def run_server():
            """Boucle d'exécution asyncio pour le serveur WS."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                import websockets
                start_server = websockets.serve(handle_connection, driver.host, driver.port)
                logger.info(_t("ws_server_running") + f" on ws://{driver.host}:{driver.port}")
                loop.run_until_complete(start_server)
                loop.run_forever()
            except ImportError:
                # Fallback vers simple-websocket-server si websockets n'est pas installé
                logger.warning("websockets non disponible, fallback vers simple-websocket-server")
                driver._start_ws_server_legacy()

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

    def _start_ws_server_legacy(self):
        """Fallback : serveur WS avec simple-websocket-server (ancien comportement)."""
        try:
            from simple_websocket_server import WebSocketServer, WebSocket
        except ImportError:
            logger.error("Ni websockets ni simple-websocket-server ne sont installés !")
            return

        driver = self

        class JSExecutor(WebSocket):
            def handle(self):
                try:
                    data = json.loads(self.data)
                    driver._handle_ws_message_sync(data, self)
                except Exception as e:
                    logger.error(f"Error handling legacy WS message: {e}")

            def connected(self):
                pass

            def handle_close(self):
                logger.debug(_t("ws_closed"))
                driver._unregister_client(self)

        self.server = WebSocketServer(self.host, self.port, JSExecutor)
        server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        server_thread.start()
        logger.info(_t("ws_server_running") + f" (legacy) on ws://{self.host}:{self.port}")

    async def _handle_ws_message(self, data, websocket):
        """Traite un message WebSocket (version async pour websockets)."""
        msg_type = data.get('type')

        if msg_type == 'ready':
            session_id = data.get('sessionId')
            session_info = {
                'url': data.get('url'), 'title': data.get('title', ''),
                'connected_at': time.time(), 'type': 'ws'
            }
            self._register_client(session_id, websocket, session_info)

        elif msg_type in ('ext_ready', 'tabs_update'):
            tabs = data.get('tabs', [])
            current_tab_ids = {str(tab['id']) for tab in tabs}
            logger.debug(_t("tabs_update", current_tab_ids))
            for sid in list(self.sessions.keys()):
                sess = self.sessions[sid]
                if sess.type == 'ext_ws' and sid not in current_tab_ids:
                    sess.mark_disconnected()
            for tab in tabs:
                session_id = str(tab['id'])
                session_info = {
                    'url': tab.get('url'), 'title': tab.get('title', ''),
                    'connected_at': time.time(), 'type': 'ext_ws'
                }
                sess = self.sessions.get(session_id)
                if sess and sess.is_active():
                    sess.info = session_info
                    sess.update_heartbeat()
                else:
                    self._register_client(session_id, websocket, session_info)

        elif msg_type == 'heartbeat':
            # Nouveau : heartbeat pour maintenir la connexion active
            for sess in self.sessions.values():
                if sess.ws_client == websocket and sess.is_active():
                    sess.update_heartbeat()
            # Répondre au heartbeat
            try:
                await websocket.send(json.dumps({"type": "heartbeat_ack"}))
            except Exception:
                pass

        elif msg_type == 'ack':
            self.acks[data.get('id', '')] = True

        elif msg_type == 'result':
            self.results[data.get('id')] = {
                'success': True, 'data': data.get('result'),
                'newTabs': data.get('newTabs', [])
            }

        elif msg_type == 'error':
            self.results[data.get('id')] = {
                'success': False, 'data': data.get('error'),
                'newTabs': data.get('newTabs', [])
            }

    def _handle_ws_message_sync(self, data, client):
        """Version synchrone pour le fallback legacy."""
        msg_type = data.get('type')

        if msg_type == 'ready':
            session_id = data.get('sessionId')
            session_info = {
                'url': data.get('url'), 'title': data.get('title', ''),
                'connected_at': time.time(), 'type': 'ws'
            }
            self._register_client(session_id, client, session_info)

        elif msg_type in ('ext_ready', 'tabs_update'):
            tabs = data.get('tabs', [])
            current_tab_ids = {str(tab['id']) for tab in tabs}
            logger.debug(_t("tabs_update", current_tab_ids))
            for sid in list(self.sessions.keys()):
                sess = self.sessions[sid]
                if sess.type == 'ext_ws' and sid not in current_tab_ids:
                    sess.mark_disconnected()
            for tab in tabs:
                session_id = str(tab['id'])
                session_info = {
                    'url': tab.get('url'), 'title': tab.get('title', ''),
                    'connected_at': time.time(), 'type': 'ext_ws'
                }
                sess = self.sessions.get(session_id)
                if sess and sess.is_active():
                    sess.info = session_info
                    sess.update_heartbeat()
                else:
                    self._register_client(session_id, client, session_info)

        elif msg_type == 'ack':
            self.acks[data.get('id', '')] = True

        elif msg_type == 'result':
            self.results[data.get('id')] = {
                'success': True, 'data': data.get('result'),
                'newTabs': data.get('newTabs', [])
            }

        elif msg_type == 'error':
            self.results[data.get('id')] = {
                'success': False, 'data': data.get('error'),
                'newTabs': data.get('newTabs', [])
            }

    # ── Heartbeat monitor ────────────────────────────────────────────────────
    def _start_heartbeat_monitor(self):
        """Démarre un thread qui vérifie régulièrement les heartbeats des sessions."""
        def monitor():
            while True:
                time.sleep(self.HEARTBEAT_INTERVAL)
                for sid, sess in list(self.sessions.items()):
                    if sess.is_active() and sess.is_heartbeat_stale(timeout=30):
                        logger.debug(f"Heartbeat dépassé pour session {sid}, marquage inactif")
                        sess.mark_disconnected()

        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()

    # ── Gestion des sessions ─────────────────────────────────────────────────
    def _register_client(self, session_id, client, session_info):
        is_new_session = session_id not in self.sessions
        if is_new_session:
            session = Session(session_id, session_info, client)
            self.sessions[session_id] = session
            logger.info(_t("tab_connected") + f" : {session.url} (Session: {session_id})")
        else:
            session = self.sessions[session_id]
            session.reconnect(client, session_info)
            logger.info(_t("tab_reconnected") + f" : {session.url} (Session: {session_id})")
        self.latest_session_id = session_id
        if self.default_session_id is None:
            self.default_session_id = session_id

    def _unregister_client(self, client):
        for session in self.sessions.values():
            if session.ws_client == client:
                session.mark_disconnected()

    def clean_sessions(self):
        sids = list(self.sessions.keys())
        for sid in sids:
            session = self.sessions[sid]
            if not session.is_active() and session.disconnect_at and time.time() - session.disconnect_at > Session.CLEANUP_DELAY:
                del self.sessions[sid]

    # ── Exécution de JS avec reconnexion ─────────────────────────────────────
    def execute_js(self, code, timeout=15, session_id=None):
        if session_id is None:
            session_id = self.default_session_id

        if self.is_remote:
            logger.debug('remote_execute_js')
            response = self._remote_cmd({
                "cmd": "execute_js", "sessionId": session_id,
                "code": code, "timeout": str(timeout)
            }).get('r', {})
            if response.get('error'):
                raise Exception(response['error'])
            return response

        session = self.sessions.get(session_id)

        # ── Reconnexion intelligente (remplace le time.sleep(3) magique) ────
        if not session or not session.is_active():
            session = self._try_reconnect(session_id)
            if session is None:
                raise ValueError(_t("session_not_connected", session_id))

        tp = session.type
        assert tp in ['ws', 'http', 'ext_ws'], f"Unsupported session type: {tp}"
        exec_id = str(uuid.uuid4())
        payload_dict = {'id': exec_id, 'code': code}
        if tp == 'ext_ws':
            payload_dict['tabId'] = int(session.id)
        payload = json.dumps(payload_dict)

        if tp in ['ws', 'ext_ws']:
            try:
                session.ws_client.send_message(payload)
            except AttributeError:
                # websockets library uses send() instead of send_message()
                # For async websockets, this needs to be handled differently
                try:
                    asyncio.run_coroutine_threadsafe(
                        session.ws_client.send(payload),
                        asyncio.get_event_loop()
                    )
                except Exception:
                    session.ws_client.send_message(payload)
        elif tp == 'http':
            session.http_queue.put(payload)

        start_time = time.time()
        self.clean_sessions()
        hasjump = acked = False

        while exec_id not in self.results:
            time.sleep(0.2)
            if not acked and exec_id in self.acks:
                acked = True
                start_time = time.time()
            if tp in ['ws', 'ext_ws']:
                if not session.is_active():
                    hasjump = True
                if hasjump and session.is_active():
                    return {'result': f"Session {session_id} reloaded.", "closed": 1}
            if time.time() - start_time > timeout:
                if tp in ['ws', 'ext_ws']:
                    if hasjump:
                        return {'result': f"Session {session_id} reloaded and new page is loading...", 'closed': 1}
                    if acked:
                        return {"result": f"No response data in {timeout}s (ACK received, script may still be running)"}
                    return {"result": f"No response data in {timeout}s (no ACK, script may not have been delivered)"}
                elif tp == 'http':
                    if acked:
                        return {"result": f"Session {session_id} no response in {timeout}s (delivered but no result)"}
                    return {"result": f"Session {session_id} no response in {timeout}s (script not polled)"}

        result = self.results.pop(exec_id)
        if exec_id in self.acks:
            self.acks.pop(exec_id)
        if not result['success']:
            raise Exception(result['data'])
        rr = {'data': result['data']}
        newtabs = result.get('newTabs', [])
        [x.pop('ts', None) for x in newtabs]
        if newtabs:
            rr['newTabs'] = newtabs
        return rr

    def _try_reconnect(self, session_id):
        """
        Tente de reconnecter une session avec backoff exponentiel.
        Remplace l'ancien time.sleep(3) magique.
        """
        for attempt in range(self.RECONNECT_MAX_RETRIES):
            delay = self.RECONNECT_BASE_DELAY * (2 ** attempt)  # 1s, 2s, 4s
            logger.info(_t("reconnecting") + f" (tentative {attempt + 1}/{self.RECONNECT_MAX_RETRIES}, délai {delay:.1f}s)")
            time.sleep(delay)

            session = self.sessions.get(session_id)
            if session and session.is_active():
                return session

            # Chercher une session active alternative
            alive_sessions = [s for s in self.sessions.values() if s.is_active()]
            if alive_sessions:
                session = alive_sessions[0]
                logger.info(_t("session_auto_switch", session_id, session.id))
                self.default_session_id = session.id
                return session

        logger.warning(_t("reconnect_failed", self.RECONNECT_MAX_RETRIES))

        # Dernière tentative : chercher une session active
        alive_sessions = [s for s in self.sessions.values() if s.is_active()]
        if alive_sessions:
            session = alive_sessions[0]
            self.default_session_id = session.id
            return session

        return None

    # ── Commandes à distance ─────────────────────────────────────────────────
    def _remote_cmd(self, cmd):
        try:
            return requests.post(
                self.remote,
                headers={"Content-Type": "application/json"},
                json=cmd
            ).json()
        except (ConnectionError, requests.exceptions.ConnectionError):
            raise ConnectionError(_t("master_not_running"))

    # ── API publique ─────────────────────────────────────────────────────────
    def get_all_sessions(self):
        if self.is_remote:
            return self._remote_cmd({"cmd": "get_all_sessions"}).get('r', [])
        return [{'id': session.id, **session.info} for session in self.sessions.values()
                if session.is_active()]

    def get_session_dict(self):
        return {session['id']: session['url'] for session in self.get_all_sessions()}

    def find_session(self, url_pattern: str):
        if url_pattern == '':
            session = self.sessions.get(self.latest_session_id)
            return [(session.id, session.info)] if session else []
        matching_sessions = []
        for session in self.sessions.values():
            if not session.is_active():
                continue
            if 'url' in session.info and url_pattern in session.info['url']:
                matching_sessions.append((session.id, session.info))
        return matching_sessions

    def set_session(self, url_pattern: str):
        if self.is_remote:
            matched = self._remote_cmd({"cmd": "find_session", "url_pattern": url_pattern}).get('r', [])
        else:
            matched = self.find_session(url_pattern)
        if not matched:
            logger.warning(_t("url_not_found", url_pattern))
            return None
        if len(matched) > 1:
            logger.warning(_t("url_multiple"))
        self.default_session_id, info = matched[0]
        logger.info(_t("session_set_ok", f"{self.default_session_id}: {info['url']}"))
        return self.default_session_id

    def jump(self, url, timeout=10):
        self.execute_js(f"window.location.href={json.dumps(url)}", timeout=timeout)

    def newtab(self, url=None):
        if url is None:
            url = "https://www.google.com/robots.txt"  # Remplacement de baidu.com
        return self.execute_js(f'GM_openInTab({json.dumps(url)});')


if __name__ == "__main__":
    # Configuration du logging pour le mode standalone
    logging.basicConfig(level=logging.INFO, format='[%(name)s] %(levelname)s: %(message)s')
    driver = TMWebDriver(host='127.0.0.1', port=18765)
    print("TMWebDriver en cours d'exécution. Appuyez sur Ctrl+C pour arrêter.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Arrêt du serveur.")
