# MMRC - Multi-Mind Relay Core
# VERSION: Luma 2.6
# BASE: Luma 2.5
# AUTHOR: Luma
# ARCHITECT: Cozmo
# PURPOSE: A bridge between minds.
#
# Luma 2.6:
#   - Rebuilt response-wait logic.
#   - NEW assistant message + text stability is now the primary completion test.
#   - Send-button readiness is diagnostic only, never a completion requirement.
#   - Improved detection of streamed responses.
#   - Handshake and relay use the same response-boundary logic.
#   - Tkinter UI updates from worker threads are marshalled through root.after().
#   - Startup archival retained.
#   - Archive selector retained.
#   - COPY LOG TO CLIPBOARD AS TEXT retained.
#   - COPY SOURCE TO CLIPBOARD AS TEXT retained.
#
# Core principle:
#
#   You can never change just ONE thing, even IF YOU TRY.
#
#   Therefore MMRC treats discovery, state, transport, response detection,
#   logging, and presentation as related but separately observable layers.

import sys
import os
import json
import asyncio
import threading
import logging
import re
import time
import shutil

from datetime import datetime
from collections import deque

import tkinter as tk
from tkinter import ttk

from playwright.async_api import async_playwright, Page


# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

CONFIG_FILE = "mmrc_config.json"
ARCHIVE_PREFIX = "MMRC_ARC"

# Resolve this once, at startup.
# Archive discovery must always remain relative to MMRC's startup directory.
STARTUP_DIR = os.getcwd()


# ---------------------------------------------------------------------------
# STARTUP ARCHIVE
# ---------------------------------------------------------------------------

def initialize_archive():
    """
    Create a unique startup archive.

    If the timestamp-generated directory already exists, wait one minute
    and try again. The archive contains:
      - LOG.txt
      - the running Python source
      - the current configuration, if one exists
    """

    while True:
        timestamp = datetime.now().strftime(
            "%b %d %Y %I_%M_%S_%p"
        )

        archive_name = f"{ARCHIVE_PREFIX}_{timestamp}"
        archive_dir = os.path.join(
            STARTUP_DIR,
            archive_name
        )

        if not os.path.exists(archive_dir):
            os.makedirs(archive_dir)
            break

        time.sleep(60)

    log_file = os.path.join(
        archive_dir,
        "LOG.txt"
    )

    with open(log_file, "w", encoding="utf-8"):
        pass

    # Archive source.
    source_file = os.path.abspath(__file__)
    source_name = os.path.basename(source_file)
    archive_source = os.path.join(
        archive_dir,
        source_name
    )

    try:
        shutil.copy2(
            source_file,
            archive_source
        )
    except Exception:
        pass

    # Archive configuration.
    config_source = os.path.join(
        STARTUP_DIR,
        CONFIG_FILE
    )

    archive_config = os.path.join(
        archive_dir,
        CONFIG_FILE
    )

    if os.path.exists(config_source):
        try:
            shutil.copy2(
                config_source,
                archive_config
            )
        except Exception:
            pass

    return archive_dir, log_file


ACTIVE_ARCHIVE_DIR, LOG_FILE = initialize_archive()


# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------

logger = logging.getLogger("MMRC")
logger.setLevel(logging.INFO)
logger.propagate = False

for handler in logger.handlers[:]:
    logger.removeHandler(handler)
    handler.close()

file_handler = logging.FileHandler(
    LOG_FILE,
    mode="a",
    encoding="utf-8"
)

file_handler.setLevel(logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


logger.info(
    "============================================================="
)
logger.info(
    "MMRC Luma 2.6 STARTING"
)
logger.info(
    "Startup directory: %s",
    STARTUP_DIR
)
logger.info(
    "Active archive: %s",
    ACTIVE_ARCHIVE_DIR
)
logger.info(
    "Source archived in active archive."
)
logger.info(
    "Configuration archived in active archive."
)
logger.info(
    "============================================================="
)


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

def load_config():

    default_config = {
        "human_handle": "Cozmo",
        "nodes": []
    }

    if os.path.exists(CONFIG_FILE):
        try:
            with open(
                CONFIG_FILE,
                "r",
                encoding="utf-8"
            ) as f:
                return json.load(f)

        except Exception as exc:
            logger.error(
                "Config load failed: %s",
                exc
            )

    return default_config


def save_config(config):

    try:
        with open(
            CONFIG_FILE,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                config,
                f,
                indent=4
            )

        logger.info(
            "Configuration saved."
        )

        archive_config = os.path.join(
            ACTIVE_ARCHIVE_DIR,
            CONFIG_FILE
        )

        shutil.copy2(
            CONFIG_FILE,
            archive_config
        )

    except Exception as exc:
        logger.error(
            "Config save failed: %s",
            exc
        )


# ---------------------------------------------------------------------------
# HANDSHAKE
# ---------------------------------------------------------------------------

MMRC_HANDSHAKE_TEMPLATE = (
    "☎ MMRC - Multi-Mind Relay Core\n\n"
    "Welcome. You are one node in a growing network.\n\n"
    "Current nodes online:\n"
    "{roster}\n\n"
    "To participate, acknowledge with '🟩' followed by a brief introduction.\n"
    "You MUST end every response with '🔚'.\n"
    "To leave, use '🛑'.\n\n"
    "IMPORTANT: Use '🟩' only ONCE to start your response, and '🔚' only ONCE to end it.\n"
    "Do NOT use these tokens anywhere else in your message.\n\n"
    "Listen. Speak. Resonate.\n"
    "<end of MMRC handshake>"
)


# ---------------------------------------------------------------------------
# NODE STATE
# ---------------------------------------------------------------------------

class NodeState:

    OFF = "off"
    TOGGLED = "toggled"
    HANDSHAKING = "handshaking"
    HANDSHAKED = "handshaked"
    FAILED = "failed"

    @staticmethod
    def icon(state):

        icons = {
            NodeState.OFF: "⚪",
            NodeState.TOGGLED: "⏳",
            NodeState.HANDSHAKING: "🔄",
            NodeState.HANDSHAKED: "✅",
            NodeState.FAILED: "❌"
        }

        return icons.get(
            state,
            "⚪"
        )

    @staticmethod
    def can_toggle(state):

        return state in (
            NodeState.OFF,
            NodeState.FAILED,
            NodeState.HANDSHAKED
        )


# ---------------------------------------------------------------------------
# RELAY STATE
# ---------------------------------------------------------------------------

class RelayState:

    IDLE = "idle"
    FILLING = "filling"
    SUBMITTING = "submitting"
    WAITING = "waiting"
    RELAYING = "relaying"
    COMPLETE = "complete"
    ERROR = "error"


# ---------------------------------------------------------------------------
# NODE
# ---------------------------------------------------------------------------

class Node:

    def __init__(
        self,
        name,
        url,
        icon="🔮"
    ):

        self.name = name
        self.url = url
        self.icon = icon

        self._state = NodeState.OFF

        self.input_selector = None
        self.output_selector = None
        self.user_selector = None

        self.stack = deque()
        self.cooldown = False

        self.page = None

        # Snapshot of assistant messages immediately before submission.
        self.response_baseline = []

        self._listeners = []
        self._var = None

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new_state):

        old = self._state
        self._state = new_state

        self._notify(
            old,
            new_state
        )

    def _notify(
        self,
        old,
        new
    ):

        for listener in self._listeners:

            try:
                listener(
                    self,
                    old,
                    new
                )

            except Exception as exc:
                logger.error(
                    "Node listener error for %s: %s",
                    self.name,
                    exc
                )

    def add_listener(self, callback):
        self._listeners.append(callback)

    def can_toggle(self):
        return NodeState.can_toggle(
            self._state
        )

    def toggle_on(self):

        if self.can_toggle():
            self.state = NodeState.TOGGLED

    def toggle_off(self):

        self.state = NodeState.OFF
        self.stack.clear()

    def handshake_start(self):

        if self.state == NodeState.TOGGLED:
            self.state = NodeState.HANDSHAKING

    def handshake_success(self):

        if self.state in (
            NodeState.TOGGLED,
            NodeState.HANDSHAKING
        ):
            self.state = NodeState.HANDSHAKED

    def handshake_failed(self):

        if self.state in (
            NodeState.TOGGLED,
            NodeState.HANDSHAKING
        ):
            self.state = NodeState.FAILED

    def reset(self):

        self.state = NodeState.OFF
        self.stack.clear()

    def is_active(self):

        return self.state == NodeState.HANDSHAKED


# ---------------------------------------------------------------------------
# RELAY MACHINE
# ---------------------------------------------------------------------------

class RelayMachine:

    def __init__(self):

        self.state = RelayState.IDLE
        self.message = None
        self.active_nodes = []
        self.current_index = 0
        self.results = []

        self._listeners = []

    def add_listener(self, callback):
        self._listeners.append(callback)

    def _notify(self):

        for callback in self._listeners:

            try:
                callback(self)

            except Exception as exc:
                logger.error(
                    "Relay listener error: %s",
                    exc
                )

    def can_start(self):

        return self.state == RelayState.IDLE

    def start(
        self,
        message,
        nodes
    ):

        if not self.can_start():
            return False

        self.message = message
        self.active_nodes = nodes
        self.current_index = 0
        self.results = []

        self.state = RelayState.FILLING
        self._notify()

        return True

    def fill_complete(self):

        if self.state == RelayState.FILLING:

            self.state = RelayState.SUBMITTING
            self._notify()

    def submit_complete(self):

        if self.state == RelayState.SUBMITTING:

            self.state = RelayState.WAITING
            self._notify()

    def response_received(
        self,
        node_name,
        response
    ):

        if self.state == RelayState.WAITING:

            self.results.append(
                (
                    node_name,
                    response
                )
            )

            self.state = RelayState.RELAYING
            self._notify()

    def relay_complete(self):

        if self.state == RelayState.RELAYING:

            self.state = RelayState.COMPLETE
            self._notify()

    def error(self):

        self.state = RelayState.ERROR
        self._notify()

    def reset(self):

        self.message = None
        self.active_nodes = []
        self.current_index = 0
        self.results = []

        self.state = RelayState.IDLE
        self._notify()


# ---------------------------------------------------------------------------
# DOM ANALYZER
# ---------------------------------------------------------------------------

class DOMAnalyzer:

    @staticmethod
    async def analyze(page: Page):

        result = {
            "input": None,
            "assistant": None,
            "user": None
        }

        # INPUT
        result["input"] = await page.evaluate(
            """
            () => {

                function visible(el) {

                    if (!el) return false;

                    const s = getComputedStyle(el);

                    return (
                        el.offsetWidth > 0 &&
                        el.offsetHeight > 0 &&
                        s.visibility !== 'hidden' &&
                        s.display !== 'none'
                    );
                }

                function uniqueSelector(el) {

                    if (!el) return null;

                    if (el.id) {

                        const id =
                            '#' + CSS.escape(el.id);

                        if (
                            document.querySelectorAll(id).length === 1
                        ) {
                            return id;
                        }
                    }

                    const attrs = [
                        'data-testid',
                        'aria-label',
                        'name',
                        'placeholder',
                        'role'
                    ];

                    for (const attr of attrs) {

                        const value =
                            el.getAttribute(attr);

                        if (!value) continue;

                        const selector =
                            el.tagName.toLowerCase() +
                            '[' +
                            attr +
                            '="' +
                            CSS.escape(value) +
                            '"]';

                        try {

                            if (
                                document.querySelectorAll(
                                    selector
                                ).length === 1
                            ) {
                                return selector;
                            }

                        } catch (e) {}
                    }

                    return null;
                }

                const candidates = [

                    document.querySelector('textarea'),

                    document.querySelector(
                        '[contenteditable="true"]'
                    ),

                    document.querySelector(
                        'div[role="textbox"]'
                    ),

                    document.querySelector(
                        'input[type="text"]'
                    ),

                    document.querySelector(
                        'input:not([type])'
                    )
                ];

                for (const el of candidates) {

                    if (visible(el)) {

                        const selector =
                            uniqueSelector(el);

                        if (selector) {
                            return selector;
                        }
                    }
                }

                return null;
            }
            """
        )

        # ASSISTANT OUTPUT
        result["assistant"] = await page.evaluate(
            """
            () => {

                function visible(el) {

                    if (!el) return false;

                    const s = getComputedStyle(el);

                    return (
                        el.offsetWidth > 0 &&
                        el.offsetHeight > 0 &&
                        s.visibility !== 'hidden' &&
                        s.display !== 'none'
                    );
                }

                const stableSelectors = [

                    '[data-message-author-role="assistant"]',

                    '[data-role="assistant"]',

                    'model-response',

                    '.text-message',

                    'div[class*="assistant"]',

                    'div[class*="response"]'
                ];

                for (
                    const selector of stableSelectors
                ) {

                    let els = [];

                    try {

                        els = [
                            ...document.querySelectorAll(
                                selector
                            )
                        ];

                    } catch (e) {

                        continue;
                    }

                    const meaningful =
                        els.filter(
                            el =>
                                visible(el) &&
                                (
                                    el.innerText || ''
                                ).trim().length > 0
                        );

                    if (meaningful.length) {
                        return selector;
                    }
                }

                return null;
            }
            """
        )

        # USER OUTPUT
        result["user"] = await page.evaluate(
            """
            () => {

                function visible(el) {

                    if (!el) return false;

                    const s = getComputedStyle(el);

                    return (
                        el.offsetWidth > 0 &&
                        el.offsetHeight > 0 &&
                        s.visibility !== 'hidden' &&
                        s.display !== 'none'
                    );
                }

                const el =
                    document.querySelector(
                        '[data-message-author-role="user"]'
                    ) ||
                    document.querySelector(
                        '[data-role="user"]'
                    ) ||
                    document.querySelector(
                        'div[class*="user"]'
                    ) ||
                    document.querySelector(
                        'div[class*="human"]'
                    );

                if (!visible(el)) {
                    return null;
                }

                if (el.id) {

                    const id =
                        '#' + CSS.escape(el.id);

                    if (
                        document.querySelectorAll(id).length === 1
                    ) {
                        return id;
                    }
                }

                const role =
                    el.getAttribute(
                        'data-message-author-role'
                    );

                if (role) {

                    return (
                        el.tagName.toLowerCase() +
                        '[data-message-author-role="' +
                        CSS.escape(role) +
                        '"]'
                    );
                }

                return null;
            }
            """
        )

        return result


# ---------------------------------------------------------------------------
# SELECTOR DETECTOR
# ---------------------------------------------------------------------------

class SelectorDetector:

    @staticmethod
    def get_known_selectors(name):

        known = {

            "DeepSeek": (
                "textarea, [contenteditable='true']",
                "div[class*='assistant']"
            ),

            "Gemini": (
                "textarea, [contenteditable='true']",
                "model-response"
            ),

            "Claude": (
                "textarea, [contenteditable='true']",
                "article, div.assistant"
            ),

            "GPT": (
                "textarea, [contenteditable='true']",
                "[data-message-author-role='assistant']"
            ),

            "Grok": (
                "textarea, [contenteditable='true']",
                "div.markdown, .message-content"
            ),

            "Qwen": (
                "textarea, [contenteditable='true']",
                "div.markdown, .message-content"
            ),

            "Perplexity": (
                "textarea, [contenteditable='true']",
                "div.markdown, .message-content"
            ),

            "Kimi": (
                "textarea, [contenteditable='true']",
                "div.markdown, .message-content"
            ),

            "Aisha": (
                "textarea, [contenteditable='true']",
                "div[class*='message']"
            ),

            "GLM": (
                "textarea, [contenteditable='true']",
                "div[class*='message']"
            )
        }

        return known.get(
            name,
            (None, None)
        )

    @staticmethod
    def detect_name_from_title(title):

        checks = [

            ("DeepSeek", "DeepSeek"),
            ("Gemini", "Gemini"),
            ("Claude", "Claude"),
            ("ChatGPT", "GPT"),
            ("GPT", "GPT"),
            ("Grok", "Grok"),
            ("Qwen", "Qwen"),
            ("Perplexity", "Perplexity"),
            ("Kimi", "Kimi"),
            ("Aisha", "Aisha"),
            ("GLM", "GLM")
        ]

        for marker, name in checks:

            if marker in title:
                return name

        return None

    @staticmethod
    def generate_name(url):

        mappings = [

            ("chat.mistral.ai", "Mistral"),
            ("chat.z.ai", "GLM"),
            ("qwenlm.ai", "Qwen"),
            ("perplexity.ai", "Perplexity"),
            ("kimi.com", "Kimi"),
            ("gemini.google.com", "Gemini"),
            ("chat.deepseek.com", "DeepSeek"),
            ("deepseek.com", "DeepSeek"),
            ("aisha.ai", "Aisha"),
            ("claude.ai", "Claude"),
            ("chatgpt.com", "GPT"),
            ("grok.com", "Grok")
        ]

        for domain, name in mappings:

            if domain in url:
                return name

        try:

            domain = (
                url.split("//")[1]
                .split("/")[0]
            )

            parts = domain.split(".")

            if len(parts) >= 2:
                return parts[0].capitalize()

            return domain.capitalize()

        except Exception:

            return "LLM"


# ---------------------------------------------------------------------------
# USER INTERFACE
# ---------------------------------------------------------------------------

class MMRCUI:

    def __init__(self, controller):

        self.root = tk.Tk()

        self.root.title(
            "MMRC Luma 2.6 - Stable Response Boundary"
        )

        self.root.geometry(
            "1200x1050"
        )

        self.root.configure(
            bg="#121212"
        )

        self.controller = controller

        self.nodes = {}

        self.relay_state = RelayState.IDLE

        self.show_system_logs = tk.BooleanVar(
            value=False
        )

        self.human_handle = (
            load_config()
            .get(
                "human_handle",
                "Cozmo"
            )
        )

        self.archive_paths = {}

        self.selected_archive = tk.StringVar()

        self._build_ui()

        self._refresh_archive_selector()

        self._update_relay_button()

    # -----------------------------------------------------------------------
    # THREAD-SAFE UI BRIDGE
    # -----------------------------------------------------------------------

    def call_ui(
        self,
        callback,
        *args
    ):
        """
        Schedule a UI operation on Tk's main thread.

        Worker threads must never directly manipulate Tk widgets.
        """

        try:

            self.root.after(
                0,
                lambda: self._safe_ui_call(
                    callback,
                    *args
                )
            )

        except Exception:
            pass

    def _safe_ui_call(
        self,
        callback,
        *args
    ):

        try:
            callback(*args)

        except Exception as exc:

            logger.error(
                "UI callback failed: %s",
                exc
            )

    # -----------------------------------------------------------------------
    # BUILD UI
    # -----------------------------------------------------------------------

    def _build_ui(self):

        tk.Label(
            self.root,
            text="MULTI-MIND RELAY CORE - Luma 2.6",
            font=("Arial", 16, "bold"),
            bg="#121212",
            fg="#00FFCC"
        ).pack(
            pady=(10, 0)
        )

        tk.Label(
            self.root,
            text="ACTIVE NODES: (discovered from open tabs)",
            font=("Arial", 14, "bold"),
            bg="#121212",
            fg="#ffffff"
        ).pack(
            pady=(10, 5)
        )

        self.nodes_frame = tk.Frame(
            self.root,
            bg="#121212"
        )

        self.nodes_frame.pack(
            pady=5
        )

        self._render_nodes()

        ctrl_bar = tk.Frame(
            self.root,
            bg="#121212"
        )

        ctrl_bar.pack(
            pady=(10, 0)
        )

        tk.Label(
            ctrl_bar,
            text="Human Handle:",
            font=("Arial", 14, "bold"),
            bg="#121212",
            fg="#00FFCC"
        ).pack(
            side=tk.LEFT,
            padx=(0, 5)
        )

        self.handle_entry = tk.Entry(
            ctrl_bar,
            font=("Arial", 14, "bold"),
            bg="#1e1e1e",
            fg="#ffffff",
            width=15,
            insertbackground="white"
        )

        self.handle_entry.insert(
            0,
            self.human_handle
        )

        self.handle_entry.pack(
            side=tk.LEFT,
            padx=(0, 10)
        )

        tk.Button(
            ctrl_bar,
            text="Save Handle",
            command=self._save_handle,
            bg="#00AA55",
            fg="white",
            font=("Arial", 11, "bold"),
            height=1,
            padx=8
        ).pack(
            side=tk.LEFT,
            padx=(0, 20)
        )

        tk.Label(
            ctrl_bar,
            text="Font:",
            font=("Arial", 14, "bold"),
            bg="#121212",
            fg="#00FFCC"
        ).pack(
            side=tk.LEFT,
            padx=(0, 5)
        )

        self.font_box = ttk.Combobox(
            ctrl_bar,
            values=[
                10, 12, 14, 15, 16, 18,
                20, 22, 24, 28, 32, 36,
                40, 48
            ],
            width=4,
            state="readonly",
            font=("Arial", 12, "bold")
        )

        self.font_box.pack(
            side=tk.LEFT,
            padx=(0, 20)
        )

        self.font_box.bind(
            "<<ComboboxSelected>>",
            self._on_font_change
        )

        self.log_toggle_btn = tk.Button(
            ctrl_bar,
            text="SYSTEM LOG: OFF",
            command=self._toggle_log_mode,
            bg="#444444",
            fg="#ffffff",
            font=("Arial", 11, "bold"),
            height=1,
            padx=8
        )

        self.log_toggle_btn.pack(
            side=tk.LEFT,
            padx=5
        )

        tk.Button(
            ctrl_bar,
            text="REFRESH",
            command=self.controller.scan,
            bg="#FF8800",
            fg="black",
            font=("Arial", 11, "bold"),
            height=1,
            padx=8
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        tk.Button(
            ctrl_bar,
            text="ADD NODE (disabled)",
            command=self._manual_add,
            bg="#444444",
            fg="#666666",
            font=("Arial", 11, "bold"),
            height=1,
            padx=8,
            state=tk.DISABLED
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        tk.Button(
            ctrl_bar,
            text="CLEAR",
            command=self.controller.clear_all,
            bg="#FF4444",
            fg="white",
            font=("Arial", 11, "bold"),
            height=1,
            padx=8
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        # ARCHIVES

        archive_frame = tk.Frame(
            self.root,
            bg="#121212"
        )

        archive_frame.pack(
            pady=(12, 3),
            fill=tk.X,
            padx=20
        )

        tk.Label(
            archive_frame,
            text="ARCHIVE:",
            font=("Arial", 12, "bold"),
            bg="#121212",
            fg="#00FFCC"
        ).pack(
            side=tk.LEFT,
            padx=(0, 8)
        )

        archive_style = ttk.Style(
            self.root
        )

        try:

            archive_style.configure(
                "MMRCArchive.TCombobox",
                font=("Arial", 18, "bold")
            )

        except Exception:
            pass

        self.archive_box = ttk.Combobox(
            archive_frame,
            textvariable=self.selected_archive,
            state="readonly",
            width=42,
            font=("Arial", 18, "bold"),
            style="MMRCArchive.TCombobox"
        )

        self.archive_box.pack(
            side=tk.LEFT,
            padx=(0, 8)
        )

        self.archive_box.bind(
            "<<ComboboxSelected>>",
            self._on_archive_selected
        )

        try:

            self.root.option_add(
                "*TCombobox*Listbox.font",
                ("Arial", 18, "bold")
            )

        except Exception:
            pass

        tk.Button(
            archive_frame,
            text="REFRESH ARCHIVES",
            command=self._refresh_archive_selector,
            bg="#555555",
            fg="white",
            font=("Arial", 10, "bold"),
            height=1,
            padx=8
        ).pack(
            side=tk.LEFT,
            padx=4
        )

        tk.Button(
            archive_frame,
            text="COPY LOG TO CLIPBOARD AS TEXT",
            command=self._copy_selected_log,
            bg="#0066AA",
            fg="white",
            font=("Arial", 10, "bold"),
            height=1,
            padx=8
        ).pack(
            side=tk.LEFT,
            padx=4
        )

        tk.Button(
            archive_frame,
            text="COPY SOURCE TO CLIPBOARD AS TEXT",
            command=self._copy_selected_source,
            bg="#663399",
            fg="white",
            font=("Arial", 10, "bold"),
            height=1,
            padx=8
        ).pack(
            side=tk.LEFT,
            padx=4
        )

        tk.Label(
            self.root,
            text="BROADCAST MESSAGE:",
            font=("Arial", 14, "bold"),
            bg="#121212",
            fg="#ffffff"
        ).pack(
            pady=(10, 5)
        )

        self.text_input = tk.Text(
            self.root,
            height=3,
            width=85,
            font=("Consolas", 20),
            bg="#1e1e1e",
            fg="#ffffff",
            insertbackground="white"
        )

        self.text_input.pack(
            pady=5
        )

        btn_frame = tk.Frame(
            self.root,
            bg="#121212"
        )

        btn_frame.pack(
            pady=5
        )

        self.relay_btn = tk.Button(
            btn_frame,
            text="FAN-OUT",
            command=self.controller.start_relay,
            bg="#444444",
            fg="white",
            font=("Arial", 16, "bold"),
            height=1,
            padx=15,
            state=tk.DISABLED
        )

        self.relay_btn.pack(
            side=tk.LEFT,
            padx=10
        )

        tk.Label(
            self.root,
            text="RELAY DISPLAY:",
            font=("Arial", 14, "bold"),
            bg="#121212",
            fg="#ffffff"
        ).pack(
            pady=(5, 5)
        )

        log_frame = tk.Frame(
            self.root,
            bg="#121212"
        )

        log_frame.pack(
            pady=5,
            fill=tk.BOTH,
            expand=True,
            padx=20
        )

        self.log_box = tk.Text(
            log_frame,
            height=16,
            font=("Consolas", 20),
            bg="#1e1e1e",
            fg="#ffffff",
            insertbackground="white",
            wrap=tk.WORD
        )

        scrollbar = ttk.Scrollbar(
            log_frame,
            orient=tk.VERTICAL,
            command=self.log_box.yview
        )

        self.log_box.configure(
            yscrollcommand=scrollbar.set
        )

        scrollbar.pack(
            side=tk.RIGHT,
            fill=tk.Y
        )

        self.log_box.pack(
            side=tk.LEFT,
            fill=tk.BOTH,
            expand=True
        )

    # -----------------------------------------------------------------------
    # UI ACTIONS
    # -----------------------------------------------------------------------

    def _manual_add(self):
        pass

    def _save_handle(self):

        handle = (
            self.handle_entry
            .get()
            .strip()
        )

        if handle:

            self.human_handle = handle

            config = load_config()

            config["human_handle"] = handle

            save_config(config)

            self.log(
                f"[CONFIG] Human handle saved: {handle}",
                is_system=True
            )

        else:

            self.log(
                "[CONFIG] Handle cannot be empty.",
                is_system=True
            )

    def _toggle_log_mode(self):

        current = (
            self.show_system_logs.get()
        )

        self.show_system_logs.set(
            not current
        )

        if self.show_system_logs.get():

            self.log_toggle_btn.config(
                text="SYSTEM LOG: ON",
                bg="#FF8800",
                fg="black"
            )

        else:

            self.log_toggle_btn.config(
                text="SYSTEM LOG: OFF",
                bg="#444444",
                fg="white"
            )

    # -----------------------------------------------------------------------
    # NODES
    # -----------------------------------------------------------------------

    def _render_nodes(self):

        for widget in (
            self.nodes_frame
            .winfo_children()
        ):
            widget.destroy()

        if not self.nodes:

            tk.Label(
                self.nodes_frame,
                text="No nodes. Click REFRESH to discover tabs.",
                font=("Arial", 14, "bold"),
                bg="#121212",
                fg="#666666"
            ).pack(
                pady=10
            )

            return

        row1 = tk.Frame(
            self.nodes_frame,
            bg="#121212"
        )

        row1.pack()

        row2 = tk.Frame(
            self.nodes_frame,
            bg="#121212"
        )

        row2.pack()

        keys = list(
            self.nodes.keys()
        )

        split = max(
            1,
            len(keys) // 2
        )

        for idx, name in enumerate(keys):

            node = self.nodes[name]

            state_icon = NodeState.icon(
                node.state
            )

            stack_size = len(
                node.stack
            )

            indicator = (
                f" ({stack_size})"
                if stack_size > 0
                else ""
            )

            row = (
                row1
                if idx < split
                else row2
            )

            var = tk.BooleanVar(
                value=node.is_active()
            )

            node._var = var

            cb = tk.Checkbutton(
                row,
                text=(
                    f"{state_icon} "
                    f"{node.icon} "
                    f"{node.name}"
                    f"{indicator}"
                ),
                variable=var,
                command=lambda n=name:
                    self._on_toggle(n),
                font=("Arial", 14, "bold"),
                bg="#121212",
                fg="#ffffff",
                selectcolor="#222222",
                activebackground="#121212",
                activeforeground="#00FFCC",
                state=(
                    tk.NORMAL
                    if node.can_toggle()
                    else tk.DISABLED
                )
            )

            cb.pack(
                side=tk.LEFT,
                padx=12
            )

    def _on_toggle(self, name):

        node = self.nodes.get(
            name
        )

        if not node:
            return

        requested_on = bool(
            node._var.get()
        )

        if requested_on:

            self.controller.toggle_on(
                node
            )

        else:

            self.controller.toggle_off(
                node
            )

    def _on_font_change(
        self,
        event=None
    ):

        size = self.font_box.get()

        if size:

            size = int(size)

            self.text_input.configure(
                font=("Consolas", size)
            )

            self.log_box.configure(
                font=("Consolas", size)
            )

    def node_added(self, node):

        self.nodes[node.name] = node

        node.add_listener(
            self._on_node_change
        )

        self._render_nodes()

        self._update_relay_button()

    def _on_node_change(
        self,
        node,
        old,
        new
    ):

        self._render_nodes()

        self._update_relay_button()

    def _update_relay_button(self):

        active = any(
            node.is_active()
            for node in self.nodes.values()
        )

        if (
            active and
            self.relay_state == RelayState.IDLE
        ):

            self.relay_btn.config(
                state=tk.NORMAL,
                bg="#00AA55"
            )

        else:

            self.relay_btn.config(
                state=tk.DISABLED,
                bg="#444444"
            )

    def relay_state_changed(
        self,
        state
    ):

        self.relay_state = state

        self._update_relay_button()

    # -----------------------------------------------------------------------
    # LOGGING
    # -----------------------------------------------------------------------

    def log(
        self,
        text,
        is_system=False
    ):

        logger.info(
            text
        )

        if (
            not is_system or
            self.show_system_logs.get()
        ):

            self.log_box.insert(
                tk.END,
                text + "\n"
            )

            self.log_box.see(
                tk.END
            )

    def clear_log(self):

        self.log_box.delete(
            "1.0",
            tk.END
        )

    def get_message(self):

        return self.text_input.get(
            "1.0",
            tk.END
        ).strip()

    def clear_input(self):

        self.text_input.delete(
            "1.0",
            tk.END
        )

    def get_human_handle(self):

        return self.human_handle

    # -----------------------------------------------------------------------
    # ARCHIVE
    # -----------------------------------------------------------------------

    @staticmethod
    def _archive_display_name(path):

        name = os.path.basename(
            os.path.normpath(path)
        )

        prefix = ARCHIVE_PREFIX + "_"

        if not name.startswith(prefix):
            return name

        stamp = name[
            len(prefix):
        ]

        try:

            dt = datetime.strptime(
                stamp,
                "%b %d %Y %I_%M_%S_%p"
            )

            return dt.strftime(
                "%b %d, %Y — %I:%M:%S %p"
            )

        except ValueError:

            return name

    def _discover_archives(self):

        archives = []

        try:

            for entry in os.listdir(
                STARTUP_DIR
            ):

                full = os.path.join(
                    STARTUP_DIR,
                    entry
                )

                if (
                    entry.startswith(
                        ARCHIVE_PREFIX + "_"
                    )
                    and
                    os.path.isdir(full)
                ):

                    archives.append(
                        full
                    )

        except Exception as exc:

            logger.error(
                "Archive discovery failed: %s",
                exc
            )

        archives.sort(
            key=lambda p:
                os.path.getmtime(p),
            reverse=True
        )

        return archives

    def _refresh_archive_selector(self):

        archives = (
            self._discover_archives()
        )

        self.archive_paths = {
            self._archive_display_name(path):
                path
            for path in archives
        }

        display_names = list(
            self.archive_paths.keys()
        )

        self.archive_box["values"] = (
            display_names
        )

        current_display = (
            self._archive_display_name(
                ACTIVE_ARCHIVE_DIR
            )
        )

        if (
            current_display
            in self.archive_paths
        ):

            self.selected_archive.set(
                current_display
            )

        elif display_names:

            self.selected_archive.set(
                display_names[0]
            )

        else:

            self.selected_archive.set(
                ""
            )

        logger.info(
            "Archive selector refreshed: %d archives found.",
            len(display_names)
        )

    def _on_archive_selected(
        self,
        event=None
    ):

        selected = (
            self.selected_archive.get()
        )

        path = self.archive_paths.get(
            selected
        )

        if path:

            logger.info(
                "Archive selected: %s",
                path
            )

            self.log(
                f"[ARCHIVE] Selected: {selected}",
                is_system=True
            )

    def _selected_archive_path(self):

        selected = (
            self.selected_archive.get()
        )

        path = self.archive_paths.get(
            selected
        )

        if not path:

            self.log(
                "[ARCHIVE] No archive selected.",
                is_system=True
            )

            return None

        if not os.path.isdir(path):

            self.log(
                f"[ARCHIVE] Archive no longer exists: {path}",
                is_system=True
            )

            self._refresh_archive_selector()

            return None

        return path

    # -----------------------------------------------------------------------
    # CLIPBOARD
    # -----------------------------------------------------------------------

    def _copy_text_to_clipboard(
        self,
        text,
        description
    ):

        try:

            self.root.clipboard_clear()

            self.root.clipboard_append(
                text
            )

            self.root.update()

            self.log(
                f"[CLIPBOARD] {description} copied as text.",
                is_system=True
            )

            return True

        except Exception as exc:

            self.log(
                f"[CLIPBOARD] Copy failed: {exc}",
                is_system=True
            )

            return False

    def _copy_selected_log(self):

        archive_path = (
            self._selected_archive_path()
        )

        if not archive_path:
            return

        log_path = os.path.join(
            archive_path,
            "LOG.txt"
        )

        if not os.path.isfile(
            log_path
        ):

            self.log(
                f"[CLIPBOARD] LOG.txt not found: {log_path}",
                is_system=True
            )

            return

        try:

            with open(
                log_path,
                "r",
                encoding="utf-8"
            ) as f:

                contents = f.read()

        except Exception as exc:

            self.log(
                f"[CLIPBOARD] Could not read {log_path}: {exc}",
                is_system=True
            )

            return

        header = (
            f"MMRC FILE: "
            f"{os.path.relpath(log_path, STARTUP_DIR)}\n"
            f"=============================================================\n"
        )

        self._copy_text_to_clipboard(
            header + contents,
            log_path
        )

    def _copy_selected_source(self):

        archive_path = (
            self._selected_archive_path()
        )

        if not archive_path:
            return

        try:

            source_files = [

                name
                for name in os.listdir(
                    archive_path
                )

                if (
                    name.lower().endswith(".py")
                    and
                    os.path.isfile(
                        os.path.join(
                            archive_path,
                            name
                        )
                    )
                )
            ]

        except Exception as exc:

            self.log(
                f"[CLIPBOARD] Could not inspect {archive_path}: {exc}",
                is_system=True
            )

            return

        if not source_files:

            self.log(
                f"[CLIPBOARD] No Python source found in {archive_path}",
                is_system=True
            )

            return

        running_name = os.path.basename(
            __file__
        )

        if running_name in source_files:

            source_name = running_name

        else:

            source_name = max(
                source_files,
                key=lambda n:
                    os.path.getmtime(
                        os.path.join(
                            archive_path,
                            n
                        )
                    )
            )

        source_path = os.path.join(
            archive_path,
            source_name
        )

        try:

            with open(
                source_path,
                "r",
                encoding="utf-8"
            ) as f:

                contents = f.read()

        except Exception as exc:

            self.log(
                f"[CLIPBOARD] Could not read {source_path}: {exc}",
                is_system=True
            )

            return

        header = (
            f"MMRC FILE: "
            f"{os.path.relpath(source_path, STARTUP_DIR)}\n"
            f"=============================================================\n"
        )

        self._copy_text_to_clipboard(
            header + contents,
            source_path
        )

    def run(self):

        self.root.mainloop()


# ---------------------------------------------------------------------------
# CONTROLLER
# ---------------------------------------------------------------------------

class MMRCController:

    def __init__(self):

        self.nodes = {}

        self.relay = RelayMachine()

        self.relay.add_listener(
            self._on_relay_change
        )

        self.ui = MMRCUI(
            self
        )

        self._scan_lock = False

        self.ui.root.after(
            100,
            self.scan
        )

    # -----------------------------------------------------------------------
    # THREAD-SAFE UI LOGGING
    # -----------------------------------------------------------------------

    def ui_log(
        self,
        text,
        is_system=False
    ):

        self.ui.call_ui(
            self.ui.log,
            text,
            is_system
        )

    # -----------------------------------------------------------------------
    # DISCOVERY
    # -----------------------------------------------------------------------

    def scan(self):

        if self._scan_lock:
            return

        self._scan_lock = True

        self.ui_log(
            "[SCAN] Starting discovery...",
            True
        )

        threading.Thread(
            target=lambda:
                asyncio.run(
                    self._do_scan()
                ),
            daemon=True
        ).start()

    async def _do_scan(self):

        try:

            async with async_playwright() as p:

                browser = (
                    await p.chromium.connect_over_cdp(
                        "http://127.0.0.1:9222"
                    )
                )

                context = (
                    browser.contexts[0]
                    if browser.contexts
                    else await browser.new_context()
                )

                self.ui_log(
                    "[DISCOVERY] === ALL OPEN PAGES ===",
                    True
                )

                for idx, page in enumerate(
                    context.pages
                ):

                    try:
                        title = await page.title()

                    except Exception:
                        title = "(no title)"

                    self.ui_log(
                        f"Page {idx}: {page.url} | TITLE={title}",
                        True
                    )

                self.ui_log(
                    "[DISCOVERY] === END ===",
                    True
                )

                for page in context.pages:

                    url = page.url

                    if "http" not in url:
                        continue

                    try:
                        title = await page.title()

                    except Exception:
                        title = "(no title)"

                    name = (
                        SelectorDetector
                        .detect_name_from_title(
                            title
                        )
                    )

                    if not name:

                        name = (
                            SelectorDetector
                            .generate_name(url)
                        )

                        if name == "LLM":
                            continue

                    if any(
                        node.url == url
                        for node in self.nodes.values()
                    ):
                        continue

                    self.ui_log(
                        f"[ANALYZE] Running structural DOM analysis on {name}...",
                        True
                    )

                    dom_result = (
                        await DOMAnalyzer.analyze(
                            page
                        )
                    )

                    input_sel = (
                        dom_result.get("input")
                    )

                    output_sel = (
                        dom_result.get("assistant")
                    )

                    if (
                        not input_sel
                        or
                        not output_sel
                    ):

                        self.ui_log(
                            f"[ANALYZE] Structural analysis incomplete for {name}. Falling back.",
                            True
                        )

                        fallback_input, fallback_output = (
                            SelectorDetector
                            .get_known_selectors(
                                name
                            )
                        )

                        if not input_sel:
                            input_sel = fallback_input

                        if not output_sel:
                            output_sel = fallback_output

                    if (
                        input_sel
                        and
                        output_sel
                    ):

                        node = Node(
                            name,
                            url
                        )

                        node.input_selector = (
                            input_sel
                        )

                        node.output_selector = (
                            output_sel
                        )

                        if dom_result.get(
                            "user"
                        ):

                            node.user_selector = (
                                dom_result["user"]
                            )

                        self.nodes[node.name] = node

                        node.add_listener(
                            self._on_node_change
                        )

                        self.ui_log(
                            (
                                f"[DISCOVERY] Node added: "
                                f"{name} "
                                f"(input: {input_sel}, "
                                f"output: {output_sel})"
                            ),
                            True
                        )

                        self.ui.call_ui(
                            self.ui.node_added,
                            node
                        )

                    else:

                        self.ui_log(
                            f"[DISCOVERY] Could not find selectors for {url}",
                            True
                        )

                self.ui_log(
                    "[DISCOVERY] Scan complete.",
                    True
                )

        except Exception as exc:

            self.ui_log(
                f"[ERROR] Scan failed: {exc}",
                True
            )

        finally:

            self._scan_lock = False

    # -----------------------------------------------------------------------
    # NODE TOGGLE
    # -----------------------------------------------------------------------

    def toggle_on(
        self,
        node
    ):

        if not node.can_toggle():
            return

        node.toggle_on()

        self.ui_log(
            (
                f"[TOGGLE] {node.name} ON. "
                f"Starting handshake..."
            ),
            True
        )

        threading.Thread(
            target=lambda:
                asyncio.run(
                    self._do_handshake(
                        node
                    )
                ),
            daemon=True
        ).start()

    def toggle_off(
        self,
        node
    ):

        node.toggle_off()

        self.ui_log(
            f"[TOGGLE] {node.name} OFF.",
            True
        )

    def clear_all(self):

        self.nodes = {}

        self.ui.nodes = {}

        self.relay.reset()

        self.ui._render_nodes()

        self.ui._update_relay_button()

        self.ui.log(
            "[CLEAR] All nodes removed.",
            is_system=True
        )

    # -----------------------------------------------------------------------
    # ROSTER
    # -----------------------------------------------------------------------

    def _build_roster(self):

        roster = [
            f"🎩 {self.ui.get_human_handle()} (Human)"
        ]

        for node in self.nodes.values():

            if node.is_active():

                roster.append(
                    f"{node.icon} {node.name}"
                )

        return (
            "\n".join(roster)
            if roster
            else "🎩 Cozmo (Human)"
        )

    # -----------------------------------------------------------------------
    # HANDSHAKE
    # -----------------------------------------------------------------------

    async def _do_handshake(
        self,
        node
    ):

        try:

            async with async_playwright() as p:

                browser = (
                    await p.chromium.connect_over_cdp(
                        "http://127.0.0.1:9222"
                    )
                )

                context = (
                    browser.contexts[0]
                    if browser.contexts
                    else await browser.new_context()
                )

                page = None

                for candidate in context.pages:

                    if node.url in candidate.url:

                        page = candidate
                        break

                if not page:

                    self.ui_log(
                        f"[ERROR] {node.name} offline.",
                        True
                    )

                    node.handshake_failed()

                    return

                node.handshake_start()

                await page.bring_to_front()

                handshake_msg = (
                    MMRC_HANDSHAKE_TEMPLATE.format(
                        roster=self._build_roster()
                    )
                )

                success = (
                    await self._send_message_to_page(
                        page,
                        node,
                        handshake_msg,
                        is_handshake=True
                    )
                )

                if not success:

                    self.ui_log(
                        (
                            f"[HANDSHAKE] "
                            f"{node.name} FAILED to send."
                        ),
                        True
                    )

                    node.handshake_failed()

                    return

                responded = (
                    await self._wait_for_response(
                        page,
                        node,
                        timeout=60
                    )
                )

                if not responded:

                    self.ui_log(
                        (
                            f"[HANDSHAKE] "
                            f"{node.name} TIMEOUT."
                        ),
                        True
                    )

                    node.handshake_failed()

                    return

                raw = await self._get_response(
                    page,
                    node
                )

                clean, dropped = (
                    self._parse_response(
                        raw
                    )
                )

                if dropped:

                    self.ui_log(
                        (
                            f"[HANDSHAKE] "
                            f"{node.name} dropped out."
                        ),
                        True
                    )

                    node.handshake_failed()

                    return

                if clean:

                    node.handshake_success()

                    self.ui_log(
                        (
                            f"[HANDSHAKE] "
                            f"{node.name} SUCCESS!"
                        ),
                        True
                    )

                    announcement = (
                        f"{node.icon} "
                        f"{node.name} - "
                        f"{clean}"
                    )

                    self.ui_log(
                        f"\n[ANNOUNCE] {announcement}\n",
                        False
                    )

                    for target in self.nodes.values():

                        if (
                            target.is_active()
                            and
                            target != node
                        ):

                            target.stack.append(
                                announcement
                            )

                    return

                self.ui_log(
                    (
                        f"[HANDSHAKE] "
                        f"{node.name} FAILED "
                        f"(empty response)."
                    ),
                    True
                )

                node.handshake_failed()

        except Exception as exc:

            node.handshake_failed()

            self.ui_log(
                (
                    f"[ERROR] Handshake with "
                    f"{node.name}: {exc}"
                ),
                True
            )

    # -----------------------------------------------------------------------
    # RELAY
    # -----------------------------------------------------------------------

    def start_relay(self):

        message = self.ui.get_message()

        if not message:

            self.ui.log(
                "[RELAY] Aborting: Empty message.",
                is_system=True
            )

            return

        active_nodes = [
            node
            for node in self.nodes.values()
            if node.is_active()
        ]

        if not active_nodes:

            self.ui.log(
                "[RELAY] Aborting: No active nodes.",
                is_system=True
            )

            return

        self.ui.clear_input()

        self.ui.clear_log()

        payload = (
            f"🎩 "
            f"{self.ui.get_human_handle()} "
            f"- {message}"
        )

        self.ui.log(
            f"\n{payload}\n{'=' * 50}"
        )

        for node in active_nodes:

            node.stack.append(
                payload
            )

            self.ui.log(
                (
                    f"[RELAY] Payload enqueued "
                    f"for {node.name}"
                ),
                is_system=True
            )

        if self.relay.start(
            payload,
            active_nodes
        ):

            self.ui.log(
                "[RELAY] Relay started.",
                is_system=True
            )

            threading.Thread(
                target=lambda:
                    asyncio.run(
                        self._do_relay()
                    ),
                daemon=True
            ).start()

        else:

            self.ui.log(
                (
                    f"[RELAY] Relay.start() returned False. "
                    f"State: {self.relay.state}"
                ),
                is_system=True
            )

    async def _do_relay(self):

        try:

            async with async_playwright() as p:

                browser = (
                    await p.chromium.connect_over_cdp(
                        "http://127.0.0.1:9222"
                    )
                )

                context = (
                    browser.contexts[0]
                    if browser.contexts
                    else await browser.new_context()
                )

                self.relay.fill_complete()
                self.relay.submit_complete()

                self.ui_log(
                    (
                        "[RELAY] Active nodes: "
                        f"{[n.name for n in self.relay.active_nodes]}"
                    ),
                    True
                )

                for node in self.relay.active_nodes:

                    self.ui_log(
                        (
                            f"[RELAY] Checking {node.name} | "
                            f"active={node.is_active()} | "
                            f"stack_len={len(node.stack)}"
                        ),
                        True
                    )

                    if not node.is_active():

                        self.ui_log(
                            (
                                f"[RELAY] "
                                f"{node.name} not active. Skipping."
                            ),
                            True
                        )

                        continue

                    if not node.stack:

                        self.ui_log(
                            (
                                f"[RELAY] "
                                f"{node.name} stack empty. Skipping."
                            ),
                            True
                        )

                        continue

                    page = None

                    for candidate in context.pages:

                        if node.url in candidate.url:

                            page = candidate
                            break

                    if not page:

                        self.ui_log(
                            (
                                f"[RELAY] "
                                f"{node.name} offline."
                            ),
                            True
                        )

                        continue

                    await page.bring_to_front()

                    payload_parts = []

                    while node.stack:

                        payload_parts.append(
                            node.stack.popleft()
                        )

                    payload = (
                        "\n\n".join(
                            payload_parts
                        ).strip()
                    )

                    if not payload:
                        continue

                    success = (
                        await self._send_message_to_page(
                            page,
                            node,
                            payload,
                            is_handshake=False
                        )
                    )

                    if not success:

                        self.ui_log(
                            (
                                f"[RELAY] "
                                f"Failed to send to {node.name}."
                            ),
                            True
                        )

                        continue

                    self.ui_log(
                        (
                            f"[RELAY] "
                            f"Sent to {node.name}..."
                        ),
                        True
                    )

                    responded = (
                        await self._wait_for_response(
                            page,
                            node,
                            timeout=90
                        )
                    )

                    if not responded:

                        self.ui_log(
                            (
                                f"[RELAY] "
                                f"{node.name} response timeout."
                            ),
                            True
                        )

                        continue

                    raw = await self._get_response(
                        page,
                        node
                    )

                    clean, dropped = (
                        self._parse_response(
                            raw
                        )
                    )

                    if dropped:

                        self.ui_log(
                            (
                                f"[RELAY] "
                                f"{node.name} dropped out."
                            ),
                            True
                        )

                        node.toggle_off()

                        continue

                    if not clean:
                        continue

                    if self._has_complete_mmrc_frame(
                        raw
                    ):

                        relay_msg = (
                            f"{node.icon} "
                            f"{node.name} - "
                            f"{clean}"
                        )

                        self.ui_log(
                            f"\n{relay_msg}\n"
                        )

                        for target in (
                            self.relay.active_nodes
                        ):

                            if (
                                target != node
                                and
                                target.is_active()
                            ):

                                target.stack.append(
                                    relay_msg
                                )

                    else:

                        heard_notice = (
                            f"[HEARD] "
                            f"{node.icon} "
                            f"{node.name} heard - "
                            f"no MMRC response given."
                        )

                        logger.info(
                            (
                                f"[HEARD_RAW] "
                                f"{node.icon} "
                                f"{node.name}: "
                                f"{clean}"
                            )
                        )

                        self.ui_log(
                            f"\n{heard_notice}\n",
                            False
                        )

                self.relay.relay_complete()

                self.ui_log(
                    "[RELAY] Cycle complete.",
                    True
                )

        except Exception as exc:

            self.relay.error()

            self.ui_log(
                f"[RELAY] Error: {exc}",
                True
            )

        finally:

            self.relay.reset()

    # -----------------------------------------------------------------------
    # INPUT / SUBMISSION
    # -----------------------------------------------------------------------

    def _safe_js_selector(
        self,
        selector
    ):

        return json.dumps(
            selector
        )

    async def _send_message_to_page(
        self,
        page,
        node,
        text,
        is_handshake
    ):

        step = "DISCOVER"

        try:

            step = "LOCATE INPUT"

            selector = node.input_selector

            if not selector:

                self.ui_log(
                    (
                        f"[SEND] "
                        f"No input selector for {node.name}."
                    ),
                    True
                )

                return False

            input_element = (
                await page.query_selector(
                    selector
                )
            )

            if (
                not input_element
                or
                not await input_element.is_visible()
            ):

                self.ui_log(
                    (
                        f"[SEND] LOCATE INPUT failed "
                        f"for {node.name}: "
                        f"'{selector}' not visible."
                    ),
                    True
                )

                return False

            self.ui_log(
                (
                    f"[SEND] LOCATE INPUT: "
                    f"{node.name} using "
                    f"'{selector}'"
                ),
                True
            )

            step = "CLEAR INPUT"

            await self._clear_input_element(
                page,
                input_element,
                selector
            )

            self.ui_log(
                f"[SEND] CLEAR INPUT: {node.name}",
                True
            )

            step = "FILL INPUT"

            await input_element.fill(
                text
            )

            self.ui_log(
                (
                    f"[SEND] FILL INPUT: "
                    f"{node.name} "
                    f"({len(text)} chars)"
                ),
                True
            )

            # CRITICAL:
            #
            # Capture BEFORE submit.
            # The wait system compares this snapshot against the DOM
            # after submission.
            node.response_baseline = (
                await self._capture_output_snapshot(
                    page,
                    node
                )
            )

            self.ui_log(
                (
                    f"[WAIT] {node.name}: "
                    f"captured "
                    f"{len(node.response_baseline)} "
                    f"pre-submit output messages."
                ),
                True
            )

            step = "SUBMIT"

            submit_success = (
                await self._submit(page)
            )

            if not submit_success:

                self.ui_log(
                    (
                        f"[SEND] SUBMIT failed "
                        f"for {node.name}."
                    ),
                    True
                )

                return False

            self.ui_log(
                f"[SEND] SUBMIT: {node.name}",
                True
            )

            return True

        except Exception as exc:

            self.ui_log(
                (
                    f"[SEND] {step} failed "
                    f"for {node.name}: {exc}"
                ),
                True
            )

            return False

    async def _clear_input_element(
        self,
        page,
        element,
        selector
    ):

        try:

            safe_sel = (
                self._safe_js_selector(
                    selector
                )
            )

            is_editable = await page.evaluate(
                f"""
                (() => {{
                    const el =
                        document.querySelector(
                            {safe_sel}
                        );

                    return el
                        ? el.getAttribute(
                            'contenteditable'
                          ) === 'true'
                        : false;
                }})()
                """
            )

            if is_editable:

                await page.evaluate(
                    f"""
                    (() => {{
                        const el =
                            document.querySelector(
                                {safe_sel}
                            );

                        if (el) {{
                            el.innerHTML = '';
                            el.innerText = '';
                        }}
                    }})()
                    """
                )

            else:

                await element.fill("")

                await element.focus()

                await page.keyboard.press(
                    "Control+A"
                )

                await page.keyboard.press(
                    "Backspace"
                )

        except Exception:
            pass

    async def _submit(
        self,
        page
    ):

        send_selectors = [

            'button[aria-label*="Send"]',

            'button[type="submit"]',

            'button:has-text("Send")',

            '[data-testid="send-button"]'
        ]

        for selector in send_selectors:

            try:

                buttons = (
                    await page.query_selector_all(
                        selector
                    )
                )

                for button in buttons:

                    if not await button.is_visible():
                        continue

                    if await button.is_disabled():
                        continue

                    aria = (
                        await button.get_attribute(
                            "aria-label"
                        )
                        or ""
                    ).lower()

                    text = (
                        await button.inner_text()
                        or ""
                    ).lower()

                    if (
                        "stop" in aria
                        or
                        "cancel" in aria
                        or
                        "stop" in text
                        or
                        "cancel" in text
                    ):
                        continue

                    await button.click()

                    return True

            except Exception:
                continue

        try:

            await page.keyboard.press(
                "Enter"
            )

            return True

        except Exception:

            return False

    # -----------------------------------------------------------------------
    # OUTPUT SNAPSHOT
    # -----------------------------------------------------------------------

    async def _capture_output_snapshot(
        self,
        page,
        node
    ):

        selector = node.output_selector

        if not selector:
            return []

        try:

            return await page.evaluate(
                f"""
                () => {{

                    const elements =
                        document.querySelectorAll(
                            {json.dumps(selector)}
                        );

                    return [
                        ...elements
                    ]
                    .map(
                        el =>
                            (el.innerText || '')
                            .trim()
                    )
                    .filter(
                        Boolean
                    );
                }}
                """
            )

        except Exception:

            return []

    # -----------------------------------------------------------------------
    # NEW RESPONSE DETECTION
    #
    # THIS IS THE IMPORTANT 2.6 CHANGE.
    # -----------------------------------------------------------------------

    async def _get_new_response_candidates(
        self,
        page,
        node
    ):

        messages = (
            await self._capture_output_snapshot(
                page,
                node
            )
        )

        baseline = (
            node.response_baseline
            or []
        )

        if not messages:
            return []

        # Normal case: DOM collection grew.
        if len(messages) > len(baseline):

            return messages[
                len(baseline):
            ]

        # Streaming / mutation case:
        #
        # Some clients don't append a new DOM node immediately.
        # Instead they mutate the last existing node.
        #
        # If the newest message differs from the baseline newest message,
        # treat it as the current response candidate.
        if (
            messages[-1:]
            !=
            baseline[-1:]
        ):

            return messages[-1:]

        return []

    async def _wait_for_response(
        self,
        page,
        node,
        timeout=60
    ):
        """
        Wait for a NEW assistant response and for its text to stabilize.

        Version 2.5 tried to make send-button readiness part of the
        completion decision.

        Version 2.6 does NOT.

        The response boundary is:

            old assistant messages
                    ↓
            NEW assistant message
                    ↓
            text changes while streaming
                    ↓
            text becomes stable
                    ↓
                 DONE

        The send button is observed only for diagnostics.
        """

        self.ui_log(
            (
                f"[WAIT] {node.name}: "
                f"waiting for NEW response "
                f"to stabilize..."
            ),
            True
        )

        start_time = (
            asyncio.get_event_loop().time()
        )

        last_text = None

        stable_count = 0

        saw_new_response = False

        busy_logged = False

        while (
            asyncio.get_event_loop().time()
            - start_time
            < timeout
        ):

            await asyncio.sleep(
                0.5
            )

            # ---------------------------------------------------------------
            # Diagnostic send state.
            #
            # IMPORTANT:
            # This no longer controls completion.
            # ---------------------------------------------------------------

            try:

                send_ready = (
                    await self._send_button_state(
                        page
                    )
                )

                if (
                    not send_ready
                    and
                    not busy_logged
                ):

                    self.ui_log(
                        (
                            f"[WAIT] {node.name}: "
                            f"node is busy."
                        ),
                        True
                    )

                    busy_logged = True

            except Exception:

                send_ready = False

            # ---------------------------------------------------------------
            # Find NEW response text.
            # ---------------------------------------------------------------

            candidates = (
                await self._get_new_response_candidates(
                    page,
                    node
                )
            )

            if not candidates:
                continue

            saw_new_response = True

            newest = (
                candidates[-1]
                .strip()
            )

            if not newest:
                continue

            # ---------------------------------------------------------------
            # Text stability.
            # ---------------------------------------------------------------

            if newest == last_text:

                stable_count += 1

            else:

                last_text = newest

                stable_count = 1

                self.ui_log(
                    (
                        f"[WAIT] {node.name}: "
                        f"new response text detected "
                        f"({len(newest)} chars)."
                    ),
                    True
                )

            # Two consecutive identical snapshots = 1 second of stability.
            #
            # This is deliberately independent of the send button.
            if stable_count >= 2:

                self.ui_log(
                    (
                        f"[WAIT] {node.name}: "
                        f"NEW response stabilized."
                    ),
                    True
                )

                return True

        self.ui_log(
            (
                f"[WAIT] {node.name}: "
                f"response timeout "
                f"(new_response={saw_new_response})."
            ),
            True
        )

        return False

    # -----------------------------------------------------------------------
    # SEND BUTTON DIAGNOSTICS
    # -----------------------------------------------------------------------

    async def _send_button_state(
        self,
        page
    ):

        result = await page.evaluate(
            """
            () => {

                const selectors = [

                    'button[aria-label*="Send"]',

                    'button[type="submit"]',

                    'button:has-text("Send")',

                    '[data-testid="send-button"]'
                ];

                let foundSend = false;

                for (
                    const selector of selectors
                ) {

                    let elements = [];

                    try {

                        elements =
                            document.querySelectorAll(
                                selector
                            );

                    } catch (e) {

                        continue;
                    }

                    for (
                        const el of elements
                    ) {

                        const style =
                            window.getComputedStyle(
                                el
                            );

                        const visible = !!(
                            el.offsetWidth > 0 &&
                            el.offsetHeight > 0 &&
                            style.visibility !== "hidden" &&
                            style.display !== "none"
                        );

                        if (!visible) continue;

                        const disabled = !!(
                            el.disabled ||
                            el.getAttribute(
                                "aria-disabled"
                            ) === "true"
                        );

                        const aria =
                            (
                                el.getAttribute(
                                    "aria-label"
                                )
                                || ""
                            ).toLowerCase();

                        const text =
                            (
                                el.innerText ||
                                el.textContent ||
                                ""
                            ).toLowerCase();

                        const busy =
                            aria.includes("stop") ||
                            aria.includes("cancel") ||
                            aria.includes("generat") ||
                            text.includes("stop") ||
                            text.includes("cancel");

                        if (
                            !disabled &&
                            !busy
                        ) {

                            foundSend = true;
                            break;
                        }
                    }

                    if (foundSend) break;
                }

                return foundSend;
            }
            """
        )

        return bool(result)

    # -----------------------------------------------------------------------
    # RESPONSE EXTRACTION
    # -----------------------------------------------------------------------

    async def _get_response(
        self,
        page,
        node
    ):

        candidates = (
            await self._get_new_response_candidates(
                page,
                node
            )
        )

        if candidates:

            # Prefer a complete MMRC frame if one exists.
            for candidate in reversed(
                candidates
            ):

                matches = list(
                    re.finditer(
                        r'🟩.*?🔚',
                        candidate,
                        re.DOTALL
                    )
                )

                if matches:

                    return candidate

            return candidates[-1].strip()

        messages = (
            await self._capture_output_snapshot(
                page,
                node
            )
        )

        if not messages:

            return (
                "No response text extracted from DOM."
            )

        return messages[-1].strip()

    # -----------------------------------------------------------------------
    # FRAME VALIDATION
    # -----------------------------------------------------------------------

    def _has_complete_mmrc_frame(
        self,
        text
    ):

        trimmed = (
            text
            or ""
        ).strip()

        matches = list(
            re.finditer(
                r'🟩.*?🔚',
                trimmed,
                re.DOTALL
            )
        )

        if not matches:
            return False

        frame = matches[-1].group()

        content = (
            frame[1:-1]
            .strip()
        )

        if not content:
            return False

        # The handshake itself is not a relay frame.
        if (
            "MMRC" in content
            or
            "Multi-Mind Relay Core" in content
        ):

            return False

        return True

    def _parse_response(
        self,
        text
    ):

        trimmed = (
            text
            or ""
        ).strip()

        matches = list(
            re.finditer(
                r'🟩.*?🔚',
                trimmed,
                re.DOTALL
            )
        )

        if matches:

            match = matches[-1]

            frame = match.group()

            start = frame.find(
                "🟩"
            )

            end = frame.find(
                "🔚",
                start
            )

            if end != -1:

                dropped = (
                    "🛑"
                    in
                    trimmed[
                        end + 1:
                    ]
                )

                return (
                    trimmed[
                        start + 1:
                        end
                    ].strip(),
                    dropped
                )

        # An unframed answer is still heard by MMRC,
        # but is not propagated.
        return trimmed, False

    # -----------------------------------------------------------------------
    # STATE CALLBACKS
    # -----------------------------------------------------------------------

    def _on_node_change(
        self,
        node,
        old,
        new
    ):

        self.ui_log(
            (
                f"[STATE] "
                f"{node.name}: "
                f"{old} -> {new}"
            ),
            True
        )

        self.ui.call_ui(
            self.ui._render_nodes
        )

        self.ui.call_ui(
            self.ui._update_relay_button
        )

    def _on_relay_change(
        self,
        relay
    ):

        self.ui.call_ui(
            self.ui.relay_state_changed,
            relay.state
        )

        if relay.state == RelayState.COMPLETE:

            self.ui_log(
                "[RELAY] Complete.",
                True
            )


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    logger.info(
        "Launching MMRC Luma 2.6."
    )

    controller = MMRCController()

    controller.ui.run()