# 🚀 Getting Started / 新手上手指南 / Guide de démarrage

> **GenericAgent v1.0.0**
>
> No programming experience required. Works on Mac / Windows / Linux.
> 无需编程经验，Mac / Windows 都适用。
> Aucune expérience de programmation requise. Fonctionne sur Mac / Windows / Linux.
>
> If you already have Python, skip to [Step 2](#2-configure-api-key--配置-api-key--configurer-la-clé-api).
> 如果你已经有 Python 环境，直接跳到[第 2 步](#2-configure-api-key--配置-api-key--configurer-la-clé-api)。
> Si Python est déjà installé, passez à [l'étape 2](#2-configure-api-key--配置-api-key--configurer-la-clé-api).

---

## 1. Install Python / 安装 Python / Installer Python

### Mac

Open **Terminal** (search "Terminal" in Launchpad), paste this command and press Enter:

打开「终端」（启动台搜索 "终端" 或 "Terminal"），粘贴这行命令然后回车：

Ouvrez le **Terminal** (recherchez "Terminal" dans Launchpad), collez cette commande et appuyez sur Entrée :

```bash
brew install python
```

If you see `brew: command not found`, install Homebrew first:

如果提示 `brew: command not found`，说明还没装 Homebrew，先粘贴这行：

Si vous voyez `brew: command not found`, installez d'abord Homebrew :

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Then run `brew install python` again.

装完后再执行 `brew install python`。

Ensuite, relancez `brew install python`.

### Windows

1. Open [python.org/downloads](https://www.python.org/downloads/), click the yellow button to download
2. Run the installer — **make sure to check "Add Python to PATH" at the bottom**
3. Click "Install Now"

1. 打开 [python.org/downloads](https://www.python.org/downloads/)，点黄色大按钮下载
2. 运行安装包，**底部的 "Add Python to PATH" 一定要勾上**
3. 点 "Install Now"

1. Ouvrez [python.org/downloads](https://www.python.org/downloads/), cliquez sur le bouton jaune pour télécharger
2. Lancez l'installateur — **cochez "Add Python to PATH" en bas**
3. Cliquez sur "Install Now"

### Verify / 验证 / Vérifier

```bash
python3 --version
```

You should see `Python 3.x.x`. On Windows, try `python --version` as well.

看到 `Python 3.x.x` 就 OK。Windows 上也可以试 `python --version`。

Vous devriez voir `Python 3.x.x`. Sur Windows, essayez aussi `python --version`.

> ⚠️ **Version note / 版本提示 / Remarque de version** : Python **3.11 or 3.12** is recommended. Do **not** use 3.14 (incompatible with pywebview and other dependencies).
>
> 推荐 **Python 3.11 或 3.12**。不要使用 3.14（与 pywebview 等依赖不兼容）。
>
> Python **3.11 ou 3.12** est recommandé. N'utilisez **pas** 3.14 (incompatible avec pywebview et autres dépendances).

---

## 2. Configure API Key / 配置 API Key / Configurer la clé API

### Download the Project / 下载项目 / Télécharger le projet

1. Open the [GitHub repository](https://github.com/lsdefine/GenericAgent)
2. Click the green **Code** button → **Download ZIP**
3. Extract to a location of your choice

1. 打开 [GitHub 仓库页面](https://github.com/lsdefine/GenericAgent)
2. 点绿色 **Code** 按钮 → **Download ZIP**
3. 解压到你喜欢的位置

1. Ouvrez le [dépôt GitHub](https://github.com/lsdefine/GenericAgent)
2. Cliquez sur le bouton vert **Code** → **Download ZIP**
3. Extrayez à l'emplacement de votre choix

### ⚠️ About `mykey.py` (DEPRECATED) / 关于 `mykey.py`（已弃用）/ À propos de `mykey.py` (OBSOLÈTE)

> **v1.0.0 Change / v1.0.0 变更 / Changement v1.0.0** :
>
> `mykey.py` is **deprecated** as of v1.0.0. API keys should now be stored in the **OS keyring** via `credential_store.py` (uses the `keyring` library). Plaintext credentials in `mykey.py` are no longer recommended.
>
> `mykey.py` 从 v1.0.0 起**已弃用**。API 密钥现在应通过 `credential_store.py` 存储在**操作系统密钥链**中（使用 `keyring` 库）。不再推荐在 `mykey.py` 中明文存储凭据。
>
> `mykey.py` est **obsolète** depuis v1.0.0. Les clés API doivent désormais être stockées dans le **trousseau du système** via `credential_store.py` (utilise la bibliothèque `keyring`). Les identifiants en clair dans `mykey.py` ne sont plus recommandés.

#### Migration from mykey.py / 从 mykey.py 迁移 / Migration depuis mykey.py

If you have an existing `mykey.py`, migrate your credentials to the OS keyring:

如果你有现有的 `mykey.py`，将凭据迁移到操作系统密钥链：

Si vous avez un fichier `mykey.py` existant, migrez vos identifiants vers le trousseau du système :

```bash
python -m agentmain.credential_store --migrate
```

This reads your `mykey.py` and stores all API keys securely in the OS keyring. After migration, you can delete `mykey.py`.

这会读取你的 `mykey.py` 并将所有 API 密钥安全地存储在操作系统密钥链中。迁移完成后可以删除 `mykey.py`。

Cela lit votre `mykey.py` et stocke toutes les clés API en toute sécurité dans le trousseau du système. Après la migration, vous pouvez supprimer `mykey.py`.

### Configuration Examples / 配置示例 / Exemples de configuration

When using the **GUI onboarding wizard** (see Step 3), you can enter your API key directly in the wizard. If you prefer manual setup or are using CLI mode, you can use `credential_store.py`:

使用 **GUI 引导向导**（见第 3 步）时，可以直接在向导中输入 API 密钥。如果喜欢手动配置或使用 CLI 模式，可以使用 `credential_store.py`：

Lors de l'utilisation de l'**assistant de configuration GUI** (voir étape 3), vous pouvez entrer votre clé API directement dans l'assistant. Si vous préférez la configuration manuelle ou le mode CLI, utilisez `credential_store.py` :

```bash
python -m agentmain.credential_store --set oai_config.apikey "sk-your-key"
python -m agentmain.credential_store --set oai_config.apibase "http://your-api-address:port"
python -m agentmain.credential_store --set oai_config.model "model-name"
```

**Most common usage / 最常见的用法 / Usage le plus courant :**

```python
# Variable name contains 'oai' → OpenAI compatible format (/chat/completions)
# 变量名含 'oai' → 走 OpenAI 兼容格式 (/chat/completions)
# Nom de variable contenant 'oai' → format compatible OpenAI (/chat/completions)
oai_config = {
    'apikey': 'sk-your-key',
    'apibase': 'http://your-api-address:port',
    'model': 'model-name',
}
```

```python
# Variable name contains 'claude' (no 'native') → Claude compatible format (/messages)
# 变量名含 'claude'（不含 'native'）→ 走 Claude 兼容格式 (/messages)
# Nom de variable contenant 'claude' (sans 'native') → format compatible Claude (/messages)
claude_config = {
    'apikey': 'sk-your-key',
    'apibase': 'http://your-api-address:port',
    'model': 'claude-sonnet-4-20250514',
}
```

```python
# MiniMax uses OpenAI compatible format — variable name with 'oai' works
# MiniMax 使用 OpenAI 兼容格式，变量名含 'oai' 即可
# MiniMax utilise le format compatible OpenAI — nom de variable avec 'oai'
oai_minimax_config = {
    'apikey': 'eyJh...',
    'apibase': 'https://api.minimax.io/v1',
    'model': 'MiniMax-M2.7',
}
```

**Standard tool-calling format (recommended for weaker models) / 标准工具调用格式（适合较弱模型）/ Format d'appel d'outil standard (recommandé pour les modèles faibles) :**

```python
# Variable name contains both 'native' and 'claude' → Claude standard tool-calling format
# 变量名同时含 'native' 和 'claude' → Claude 标准工具调用格式
# Nom de variable contenant 'native' et 'claude' → format d'appel d'outil standard Claude
native_claude_config = {
    'apikey': 'sk-ant-your-key',
    'apibase': 'https://api.anthropic.com',
    'model': 'claude-sonnet-4-20250514',
}
```

> 💡 Also supports `native_oai_config` (OpenAI standard tool-calling), `sider_cookie` (Sider), etc. See comments in `mykey_template.py` for details.
>
> 还支持 `native_oai_config`（OpenAI 标准工具调用）、`sider_cookie`（Sider）等，详见 `mykey_template.py` 中的注释。
>
> Prend également en charge `native_oai_config` (appel d'outil standard OpenAI), `sider_cookie` (Sider), etc. Voir les commentaires dans `mykey_template.py`.

### Key Rules / 关键规则 / Règles clés

**Variable naming determines the API format (not the model name) / 变量命名决定接口格式（不是模型名决定的）/ Le nommage des variables détermine le format d'API (pas le nom du modèle) :**

| Variable contains | Session triggered | Use case |
|---|---|---|
| `oai` | OpenAI compatible | Most API services, official OpenAI |
| `claude` (no `native`) | Claude compatible | Claude API services |
| `native` + `claude` | Claude standard tool-calling | Recommended for weaker models |
| `native` + `oai` | OpenAI standard tool-calling | Recommended for weaker models |

**`apibase` rules (endpoint path is auto-appended) / `apibase` 填写规则（会自动拼接端点路径）/ Règles `apibase` (le chemin de l'endpoint est ajouté automatiquement) :**

| What you enter | System behavior |
|---|---|
| `http://host:2001` | Auto-appends `/v1/chat/completions` |
| `http://host:2001/v1` | Auto-appends `/chat/completions` |
| `http://host:2001/v1/chat/completions` | Uses as-is, no appending |

---

## 3. First Launch / 初次启动 / Premier lancement

Open a terminal, navigate to the project folder, and run:

终端里进入项目文件夹，运行：

Ouvrez un terminal, accédez au dossier du projet et exécutez :

```bash
cd /path/to/extracted/folder
python3 agentmain.py
```

### 🆕 GUI Onboarding Wizard / GUI 引导向导 / Assistant de configuration GUI

**v1.0.0 new feature / v1.0.0 新功能 / Nouvelle fonctionnalité v1.0.0** :

On first launch, if Qt is available, a **GUI onboarding wizard** will appear automatically (instead of the old terminal menu). The wizard guides you through 5 steps:

首次启动时，如果 Qt 可用，会自动出现 **GUI 引导向导**（而非旧版终端菜单）。向导引导你完成 5 个步骤：

Au premier lancement, si Qt est disponible, un **assistant de configuration GUI** apparaît automatiquement (au lieu de l'ancien menu du terminal). L'assistant vous guide en 5 étapes :

1. **Welcome** — Language selection (zh / en / fr)
2. **API Key Setup** — Enter your API key (stored in OS keyring, not plaintext)
3. **Model Selection** — Choose your preferred model
4. **Workspace Configuration** — Set your working directory
5. **Ready** — Start using GenericAgent

> The wizard stores your API keys in the **OS keyring** via `keyring`, never in plaintext files.
>
> 向导通过 `keyring` 将 API 密钥存储在**操作系统密钥链**中，永远不会明文存储。
>
> L'assistant stocke vos clés API dans le **trousseau du système** via `keyring`, jamais en clair.

If Qt is not available, the CLI mode starts as before. You'll see an input prompt — just type your task.

如果 Qt 不可用，则和以前一样进入命令行模式。你会看到一个输入提示符，直接打字发送任务即可。

Si Qt n'est pas disponible, le mode CLI démarre comme avant. Vous verrez une invite de saisie — tapez simplement votre tâche.

Try your first task / 试试你的第一个任务 / Essayez votre première tâche :

```
Help me create a hello.txt on the desktop with the content Hello World
帮我在桌面创建一个 hello.txt，内容是 Hello World
Aide-moi à créer un hello.txt sur le bureau avec le contenu Hello World
```

> 💡 On Windows, if `python3` is not recognized, use `python agentmain.py`.
>
> Windows 上如果 `python3` 不识别，换成 `python agentmain.py`。
>
> Sur Windows, si `python3` n'est pas reconnu, utilisez `python agentmain.py`.

### `--overlay` Flag / `--overlay` 标志 / Indicateur `--overlay`

For **developer overlay mode** (floating transparent window), launch with:

用于**开发者覆盖模式**（浮动透明窗口），启动时使用：

Pour le **mode overlay développeur** (fenêtre transparente flottante), lancez avec :

```bash
python3 agentmain.py --overlay
```

> **v1.0.0 change / v1.0.0 变更 / Changement v1.0.0** : The Qt default is now **normal window mode** (not overlay). Use `--overlay` only if you want the old floating window behavior.
>
> Qt 默认现在是**普通窗口模式**（不再是覆盖模式）。只有在你需要旧的浮动窗口行为时才使用 `--overlay`。
>
> Le mode par défaut de Qt est désormais le **mode fenêtre normale** (plus l'overlay). Utilisez `--overlay` uniquement si vous souhaitez l'ancien comportement de fenêtre flottante.

---

## 4. Let the Agent Install Dependencies / 让 Agent 自己装依赖 / Laisser l'agent installer les dépendances

After the agent starts, just say one sentence and it will handle all dependencies:

Agent 启动后，只需要一句话，它就会自己搞定所有依赖：

Après le démarrage de l'agent, dites simplement une phrase et il gérera toutes les dépendances :

```
Please check your code and install all Python dependencies you need
请查看你的代码，安装所有用得上的 python 依赖
Vérifie ton code et installe toutes les dépendances Python nécessaires
```

The agent will read its own code, find required packages, and install them all.

Agent 会自己读代码、找出需要的包、全部装好。

L'agent lira son propre code, trouvera les paquets nécessaires et les installera.

> ⚠️ If network issues prevent the agent from calling the API, you may need to install one package manually:
> ```bash
> pip install requests
> ```
>
> 如果遇到网络问题导致 Agent 无法调用 API，可能需要先手动装一个包：
> ```bash
> pip install requests
> ```
>
> Si des problèmes réseau empêchent l'agent d'appeler l'API, vous devrez peut-être installer un paquet manuellement :
> ```bash
> pip install requests
> ```

### Upgrade to GUI Mode / 升级到图形界面 / Passer au mode GUI

After dependencies are installed, you can use GUI mode:

依赖装完后，就可以用 GUI 模式了：

Une fois les dépendances installées, vous pouvez utiliser le mode GUI :

```bash
python3 launch.pyw
```

This launches the desktop application. A normal window will appear (or overlay with `--overlay`).

启动后会出现桌面应用程序。默认是普通窗口模式（使用 `--overlay` 可切换为覆盖模式）。

Cela lance l'application de bureau. Une fenêtre normale apparaîtra (ou overlay avec `--overlay`).

### Optional: Let the Agent Help You / 可选：让 Agent 帮你做的事 / Facultatif : laissez l'agent vous aider

```
Please set up a git connection so I can update the code later
请帮我建立 git 连接，方便以后更新代码
Configure une connexion git pour pouvoir mettre à jour le code plus tard
```

The agent will configure it automatically. If you don't have Git, it will download a portable version.

Agent 会自动配好。如果你电脑上没有 Git，它也会帮你下载 portable 版。

L'agent le configurera automatiquement. Si vous n'avez pas Git, il téléchargera une version portable.

```
Please create a desktop shortcut for launch.pyw
请帮我在桌面创建一个 launch.pyw 的快捷方式
Crée un raccourci sur le bureau pour launch.pyw
```

---

## 5. Unlock Capabilities / 能力解锁 / Débloquer les capacités

Once the environment is running, you can progressively unlock more capabilities. Each one just requires **telling the agent one sentence**:

环境跑起来之后，你可以逐步解锁更多能力。每一项都只需要**对 Agent 说一句话**：

Une fois l'environnement en marche, vous pouvez débloquer progressivement d'autres capacités. Il suffit de **dire une phrase à l'agent** :

### Basic Capabilities / 基础能力 / Capacités de base

| Capability | Tell the Agent | Description |
|---|---|---|
| **PowerShell script execution** | `Help me unlock PowerShell ps1 execution for current user` | Windows blocks .ps1 scripts by default |
| **Global file search** | `Install and configure Everything CLI tool into PATH` | Millisecond full-disk file search |

### Browser Automation / 浏览器自动化 / Automatisation du navigateur

| Capability | Tell the Agent | Description |
|---|---|---|
| **Web tools** | `Execute web setup SOP, unlock web tools` | Injects browser extension for direct web control |

After unlocking, the agent can operate a **real browser with your login sessions intact**:

解锁后，Agent 可以在**保留你登录态**的真实浏览器中操作：

Après le déblocage, l'agent peut opérer dans un **navigateur réel avec vos sessions de connexion intactes** :

```
Open Amazon, search for iPhone 16, sort by price
打开淘宝，搜索 iPhone 16，按价格排序
Ouvre Amazon, cherche iPhone 16, trie par prix
```

### Advanced Capabilities / 进阶能力 / Capacités avancées

| Capability | Tell the Agent | Description |
|---|---|---|
| **OCR** | `Configure OCR with rapidocr and save to memory` | Lets the agent "see" screen text |
| **Screen Vision** | `Build a vision capability like your llmcore and save to memory` | Lets the agent "see" screen content |
| **Mobile Control** | `Configure ADB environment for Android device connection` | Control Android via USB/WiFi |

### Chat Platform Integration (Optional) / 聊天平台接入（可选）/ Intégration de plateformes de chat (facultatif)

After integration, you can send commands to your computer's agent from your phone anytime.

接入后可以随时随地通过手机给电脑上的 Agent 发指令。

Après l'intégration, vous pouvez envoyer des commandes à l'agent de votre ordinateur depuis votre téléphone à tout moment.

Tell the agent: `Look at your code, help me configure XX platform bot integration`

对 Agent 说：`看你的代码，帮我配置 XX 平台的机器人接入`

Dites à l'agent : `Regarde ton code, aide-moi à configurer l'intégration du bot de la plateforme XX`

Supported platforms / 支持的平台 / Plateformes prises en charge : **WeChat Bot** / QQ / Feishu / WeCom / DingTalk / Telegram

### Advanced Modes / 高级模式 / Modes avancés

All of these modes are **self-documenting** — no need to check the manual, just ask the agent:

以下模式全部**自文档化**——不用查手册，直接问 Agent 即可：

Tous ces modes sont **auto-documentés** — pas besoin de consulter le manuel, demandez simplement à l'agent :

| Mode | Tell the Agent |
|---|---|
| **Reflect** | `Look at your code, tell me how to enable reflect mode` |
| **Scheduled Tasks** | `Look at your code, tell me how to enable scheduled task mode` |
| **Plan** | `Look at your code, tell me how to enable plan mode` |
| **SubAgent** | `Look at your code, tell me how to enable subagent mode` |
| **Autonomous Exploration** | `Look at your code, tell me how to enable autonomous exploration mode` |

> 💡 This is GenericAgent's core design philosophy: **Code is documentation**. The agent can read its own source code, so you can ask it about any feature.
>
> 💡 这就是 GenericAgent 的核心设计理念：**代码即文档**。Agent 能读懂自己的源码，所以任何功能你都可以直接问它。
>
> 💡 C'est la philosophie de conception centrale de GenericAgent : **Le code est la documentation**. L'agent peut lire son propre code source, vous pouvez donc lui poser des questions sur n'importe quelle fonctionnalité.

---

## 🔒 Security Note (v1.0.0) / 安全提示 / Note de sécurité

**`code_run` path traversal protection / `code_run` 路径遍历防护 / Protection contre le parcours de chemin dans `code_run`** :

As of v1.0.0, the `code_run` tool enforces **path traversal protection** — it can only write files within the configured workspace directory. Attempts to write outside the workspace are blocked.

从 v1.0.0 起，`code_run` 工具强制执行**路径遍历防护**——只能在配置的工作区目录内写入文件。尝试写入工作区外的操作会被阻止。

Depuis v1.0.0, l'outil `code_run` applique la **protection contre le parcours de chemin** — il ne peut écrire des fichiers que dans le répertoire de travail configuré. Les tentatives d'écriture en dehors de l'espace de travail sont bloquées.

---

## 💡 The More You Use It, the Stronger It Gets / 使用越久越强 / Plus vous l'utilisez, plus il devient puissant

GenericAgent doesn't come with preset skills — it **evolves through use**. Each time it completes a new task, it automatically saves the execution path as a Skill, and reuses it for similar tasks next time.

GenericAgent 不预设技能，而是**靠使用进化**。每完成一个新任务，它会自动将执行路径固化为 Skill，下次遇到类似任务直接调用。

GenericAgent n'a pas de compétences prédéfinies — il **évolue par l'utilisation**. Chaque fois qu'il accomplit une nouvelle tâche, il sauvegarde automatiquement le chemin d'exécution comme compétence et le réutilise pour des tâches similaires.

You don't need to manage these Skills — the agent handles it automatically. The longer you use it, the more skills accumulate, forming a completely personalized skill tree.

你不需要管理这些 Skill，Agent 会自动处理。使用时间越长，积累的技能越多，最终形成一棵完全属于你的专属技能树。

Vous n'avez pas besoin de gérer ces compétences — l'agent s'en charge automatiquement. Plus vous l'utilisez longtemps, plus les compétences s'accumulent, formant un arbre de compétences entièrement personnalisé.

> 💡 If you feel the agent missed important information, just tell it: `Remember this` / `把这个记到你的记忆里` / `Mémorise ça`, and it will save it proactively.

**Reuse skills from other Claw users / 复用其他 Claw 用户的 Skill / Réutiliser les compétences d'autres utilisateurs Claw :**

- Ask the agent to search: `Help me find a skill for XXX` → then → `Add it to your memory`
- Specify a source: `Access XXX folder/URL, follow this skill to do XXX`

**Keep updated / 保持更新 / Rester à jour :**

Tell the agent: `Update your code with git, then check what's new in the commits`

对 Agent 说：`git 更新你的代码，然后看看 commit 有什么新功能`

Dites à l'agent : `Mets à jour ton code avec git, puis vérifie les nouveautés dans les commits`

> The agent will automatically pull the latest code and interpret the commit log, telling you about new capabilities.
>
> Agent 会自动 pull 最新代码并解读 commit log，告诉你新增了什么能力。
>
> L'agent tirera automatiquement le dernier code et interprétera le journal des commits, vous informant des nouvelles capacités.

> For more details, see [README.md](README.md) or the [detailed illustrated tutorial](https://my.feishu.cn/wiki/CGrDw0T76iNFuskmwxdcWrpinPb).
>
> 更多细节请参阅 [README.md](README.md) 或 [详细版图文教程](https://my.feishu.cn/wiki/CGrDw0T76iNFuskmwxdcWrpinPb)。
>
> Pour plus de détails, voir [README.md](README.md) ou le [tutoriel illustré détaillé](https://my.feishu.cn/wiki/CGrDw0T76iNFuskmwxdcWrpinPb).
