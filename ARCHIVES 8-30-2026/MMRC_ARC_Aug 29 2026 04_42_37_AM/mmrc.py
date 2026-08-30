
# MMRC - Multi-Mind Relay Core
# VERSION: Luma 1.3
# BASE: Kelp / DeepSeek v14.8
# AUTHOR: Luma
# ARCHITECT: Cozmo
# PURPOSE: A bridge between minds.

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


CONFIG_FILE = "mmrc_config.json"
ARCHIVE_PREFIX = "MMRC_ARC"


def initialize_archive():
    while True:
        timestamp = datetime.now().strftime("%b %d %Y %I_%M_%S_%p")
        archive_name = f"{ARCHIVE_PREFIX}_{timestamp}"
        archive_dir = os.path.join(os.getcwd(), archive_name)

        if not os.path.exists(archive_dir):
            os.makedirs(archive_dir)
            break

        time.sleep(60)

    log_file = os.path.join(archive_dir, "LOG.txt")

    with open(log_file, "w", encoding="utf-8"):
        pass

    source_file = os.path.abspath(__file__)
    source_name = os.path.basename(source_file)
    archive_source = os.path.join(archive_dir, source_name)

    try:
        shutil.copy2(source_file, archive_source)
    except Exception:
        pass

    config_source = os.path.join(os.getcwd(), CONFIG_FILE)
    archive_config = os.path.join(archive_dir, CONFIG_FILE)

    if os.path.exists(config_source):
        try:
            shutil.copy2(config_source, archive_config)
        except Exception:
            pass

    return archive_dir, log_file


ACTIVE_ARCHIVE_DIR, LOG_FILE = initialize_archive()


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

logger.info("=============================================================")
logger.info("MMRC Luma 1.3 STARTING")
logger.info("Active archive: %s", ACTIVE_ARCHIVE_DIR)
logger.info("Source archived in active archive.")
logger.info("Configuration archived in active archive.")
logger.info("=============================================================")


def load_config():
    default_config = {
        "human_handle": "Cozmo",
        "nodes": []
    }

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.error("Config load failed: %s", exc)

    return default_config


def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

        logger.info("Configuration saved.")

        archive_config = os.path.join(
            ACTIVE_ARCHIVE_DIR,
            CONFIG_FILE
        )

        shutil.copy2(CONFIG_FILE, archive_config)

    except Exception as exc:
        logger.error("Config save failed: %s", exc)


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

        return icons.get(state, "⚪")

    @staticmethod
    def can_toggle(state):
        return state in (
            NodeState.OFF,
            NodeState.FAILED
        )

    @staticmethod
    def can_handshake(state):
        return state in (
            NodeState.TOGGLED,
            NodeState.HANDSHAKING
        )


class RelayState:
    IDLE = "idle"
    FILLING = "filling"
    SUBMITTING = "submitting"
    WAITING = "waiting"
    RELAYING = "relaying"
    COMPLETE = "complete"
    ERROR = "error"


class Node:
    def __init__(self, name, url, icon="🔮"):
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

        self._listeners = []
        self._var = None

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new_state):
        old = self._state
        self._state = new_state
        self._notify(old, new_state)

    def _notify(self, old, new):
        for listener in self._listeners:
            try:
                listener(self, old, new)
            except Exception as exc:
                logger.error(
                    "Node listener error for %s: %s",
                    self.name,
                    exc
                )

    def add_listener(self, callback):
        self._listeners.append(callback)

    def can_toggle(self):
        return NodeState.can_toggle(self._state)

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

    def start(self, message, nodes):
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

    def response_received(self, node_name, response):
        if self.state == RelayState.WAITING:
            self.results.append(
                (node_name, response)
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


class DOMAnalyzer:
    @staticmethod
    async def analyze(page: Page):
        result = {
            "input": None,
            "assistant": None,
            "user": None
        }

        input_selectors = await page.evaluate(
            """
            () => {
                const candidates = [];

                const textarea =
                    document.querySelector('textarea');

                if (
                    textarea &&
                    textarea.offsetHeight > 0
                ) {
                    candidates.push('textarea');
                }

                const contenteditable =
                    document.querySelector(
                        '[contenteditable="true"]'
                    );

                if (
                    contenteditable &&
                    contenteditable.offsetHeight > 0
                ) {
                    candidates.push(
                        '[contenteditable="true"]'
                    );
                }

                const role_textbox =
                    document.querySelector(
                        'div[role="textbox"]'
                    );

                if (
                    role_textbox &&
                    role_textbox.offsetHeight > 0
                ) {
                    candidates.push(
                        'div[role="textbox"]'
                    );
                }

                if (candidates.length === 0) {
                    const fallback =
                        document.querySelector(
                            'input[type="text"], input:not([type])'
                        );

                    if (fallback) {
                        candidates.push(
                            fallback.tagName.toLowerCase() +
                            '[type="text"]'
                        );
                    }
                }

                return candidates;
            }
            """
        )

        if input_selectors:
            result["input"] = input_selectors[0]

        assistant_selectors = await page.evaluate(
            """
            () => {
                const candidates = [];

                const by_role =
                    document.querySelector(
                        '[data-role="assistant"]'
                    );

                if (by_role) {
                    candidates.push(
                        '[data-role="assistant"]'
                    );
                }

                const model_response =
                    document.querySelector(
                        'model-response'
                    );

                if (model_response) {
                    candidates.push(
                        'model-response'
                    );
                }

                const divs =
                    document.querySelectorAll(
                        'div[class*="assistant"], ' +
                        'div[class*="message"], ' +
                        'div[class*="response"]'
                    );

                for (const d of divs) {
                    if (
                        d.innerText &&
                        d.innerText.length > 20
                    ) {
                        const classes =
                            d.className
                                .split(' ')
                                .filter(c => c)
                                .join('.');

                        candidates.push(
                            d.tagName.toLowerCase() +
                            '.' +
                            classes
                        );

                        break;
                    }
                }

                if (candidates.length === 0) {
                    const article =
                        document.querySelector(
                            'article'
                        );

                    if (article) {
                        candidates.push('article');
                    }
                }

                return candidates;
            }
            """
        )

        if assistant_selectors:
            result["assistant"] = assistant_selectors[0]

        user_selectors = await page.evaluate(
            """
            () => {
                const candidates = [];

                const by_role =
                    document.querySelector(
                        '[data-role="user"]'
                    );

                if (by_role) {
                    candidates.push(
                        '[data-role="user"]'
                    );
                }

                const divs =
                    document.querySelectorAll(
                        'div[class*="user"], ' +
                        'div[class*="human"]'
                    );

                for (const d of divs) {
                    if (
                        d.innerText &&
                        d.innerText.length > 10
                    ) {
                        const classes =
                            d.className
                                .split(' ')
                                .filter(c => c)
                                .join('.');

                        candidates.push(
                            d.tagName.toLowerCase() +
                            '.' +
                            classes
                        );

                        break;
                    }
                }

                return candidates;
            }
            """
        )

        if user_selectors:
            result["user"] = user_selectors[0]

        return result


class SelectorDetector:
    @staticmethod
    def get_known_selectors(name):
        known = {
            "DeepSeek": (
                "textarea, [contenteditable='true']",
                "div[class*='message']"
            ),
            "Gemini": (
                "textarea, [contenteditable='true']",
                "model-response, .model-response-text"
            ),
            "Claude": (
                "textarea, [contenteditable='true']",
                "article, div.assistant"
            ),
            "GPT": (
                "textarea, [contenteditable='true']",
                "article, [data-message-author-role='assistant']"
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
            domain = url.split("//")[1].split("/")[0]
            parts = domain.split(".")

            if len(parts) >= 2:
                return parts[0].capitalize()

            return domain.capitalize()

        except Exception:
            return "LLM"


class MMRCUI:
    def __init__(self, controller):
        self.root = tk.Tk()

        self.root.title(
            "MMRC Luma 1.3 - Structural DOMAnalyzer"
        )

        self.root.geometry("1200x1000")
        self.root.configure(bg="#121212")

        self.controller = controller
        self.nodes = {}
        self.relay_state = RelayState.IDLE

        self.show_system_logs = tk.BooleanVar(
            value=False
        )

        self.human_handle = load_config().get(
            "human_handle",
            "Cozmo"
        )

        self._build_ui()
        self._update_relay_button()

    def _build_ui(self):
        tk.Label(
            self.root,
            text="MULTI-MIND RELAY CORE - Luma 1.3",
            font=("Arial", 16, "bold"),
            bg="#121212",
            fg="#00FFCC"
        ).pack(pady=(10, 0))

        tk.Label(
            self.root,
            text="ACTIVE NODES: (discovered from open tabs)",
            font=("Arial", 14, "bold"),
            bg="#121212",
            fg="#ffffff"
        ).pack(pady=(10, 5))

        self.nodes_frame = tk.Frame(
            self.root,
            bg="#121212"
        )

        self.nodes_frame.pack(pady=5)

        self._render_nodes()

        ctrl_bar = tk.Frame(
            self.root,
            bg="#121212"
        )

        ctrl_bar.pack(pady=(10, 0))

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

        tk.Label(
            self.root,
            text="BROADCAST MESSAGE:",
            font=("Arial", 14, "bold"),
            bg="#121212",
            fg="#ffffff"
        ).pack(pady=(10, 5))

        self.text_input = tk.Text(
            self.root,
            height=3,
            width=85,
            font=("Consolas", 20),
            bg="#1e1e1e",
            fg="#ffffff",
            insertbackground="white"
        )

        self.text_input.pack(pady=5)

        btn_frame = tk.Frame(
            self.root,
            bg="#121212"
        )

        btn_frame.pack(pady=5)

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
        ).pack(pady=(5, 5))

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

    def _manual_add(self):
        # Intentionally disabled.
        pass

    def _save_handle(self):
        handle = self.handle_entry.get().strip()

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
        current = self.show_system_logs.get()

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

    def _render_nodes(self):
        for widget in self.nodes_frame.winfo_children():
            widget.destroy()

        if not self.nodes:
            tk.Label(
                self.nodes_frame,
                text="No nodes. Click REFRESH to discover tabs.",
                font=("Arial", 14, "bold"),
                bg="#121212",
                fg="#666666"
            ).pack(pady=10)

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

        keys = list(self.nodes.keys())

        split = max(
            1,
            len(keys) // 2
        )

        for idx, name in enumerate(keys):
            node = self.nodes[name]

            state_icon = NodeState.icon(
                node.state
            )

            stack_size = len(node.stack)

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

            var.trace(
                "w",
                lambda *args, n=name:
                    self._on_toggle(n)
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
        node = self.nodes.get(name)

        if not node:
            return

        var = node._var

        if var.get():
            self.controller.toggle_on(node)
        else:
            self.controller.toggle_off(node)

    def _on_font_change(self, event=None):
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

    def _on_node_change(self, node, old, new):
        self._render_nodes()
        self._update_relay_button()

    def _update_relay_button(self):
        active = any(
            node.is_active()
            for node in self.nodes.values()
        )

        if (
            active
            and self.relay_state == RelayState.IDLE
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

    def relay_state_changed(self, state):
        self.relay_state = state
        self._update_relay_button()

    def log(self, text, is_system=False):
        logger.info(text)

        if (
            not is_system
            or self.show_system_logs.get()
        ):
            self.log_box.insert(
                tk.END,
                text + "\n"
            )

            self.log_box.see(tk.END)

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

    def run(self):
        self.root.mainloop()


class MMRCController:
    def __init__(self):
        self.nodes = {}

        self.relay = RelayMachine()
        self.relay.add_listener(
            self._on_relay_change
        )

        self.ui = MMRCUI(self)

        self._scan_lock = False

        self.ui.root.after(
            100,
            self.scan
        )

    def scan(self):
        if self._scan_lock:
            return

        self._scan_lock = True

        self.ui.log(
            "[SCAN] Starting discovery...",
            is_system=True
        )

        threading.Thread(
            target=lambda:
                asyncio.run(self._do_scan()),
            daemon=True
        ).start()

    async def _do_scan(self):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(
                    "http://127.0.0.1:9222"
                )

                context = (
                    browser.contexts[0]
                    if browser.contexts
                    else await browser.new_context()
                )

                self.ui.log(
                    "[DISCOVERY] === ALL OPEN PAGES ===",
                    is_system=True
                )

                for idx, page in enumerate(
                    context.pages
                ):
                    try:
                        title = await page.title()
                    except Exception:
                        title = "(no title)"

                    self.ui.log(
                        f"Page {idx}: "
                        f"{page.url} | "
                        f"TITLE={title}",
                        is_system=True
                    )

                self.ui.log(
                    "[DISCOVERY] === END ===",
                    is_system=True
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
                        .detect_name_from_title(title)
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

                    self.ui.log(
                        f"[ANALYZE] Running structural "
                        f"DOM analysis on {name}...",
                        is_system=True
                    )

                    dom_result = (
                        await DOMAnalyzer.analyze(page)
                    )

                    input_sel = (
                        dom_result.get("input")
                    )

                    output_sel = (
                        dom_result.get("assistant")
                    )

                    if (
                        not input_sel
                        or not output_sel
                    ):
                        self.ui.log(
                            f"[ANALYZE] Structural "
                            f"analysis incomplete for "
                            f"{name}. Falling back.",
                            is_system=True
                        )

                        (
                            fallback_input,
                            fallback_output
                        ) = (
                            SelectorDetector
                            .get_known_selectors(name)
                        )

                        if not input_sel:
                            input_sel = fallback_input

                        if not output_sel:
                            output_sel = fallback_output

                    if (
                        input_sel
                        and output_sel
                    ):
                        node = Node(
                            name,
                            url
                        )

                        node.input_selector = input_sel
                        node.output_selector = output_sel

                        if dom_result.get("user"):
                            node.user_selector = (
                                dom_result["user"]
                            )

                        self.nodes[node.name] = node

                        node.add_listener(
                            self._on_node_change
                        )

                        self.ui.log(
                            f"[DISCOVERY] Node added: "
                            f"{name} "
                            f"(input: {input_sel}, "
                            f"output: {output_sel})",
                            is_system=True
                        )

                        self.ui.node_added(node)

                    else:
                        self.ui.log(
                            f"[DISCOVERY] Could not "
                            f"find selectors for {url}",
                            is_system=True
                        )

                self.ui.log(
                    "[DISCOVERY] Scan complete.",
                    is_system=True
                )

        except Exception as exc:
            self.ui.log(
                f"[ERROR] Scan failed: {exc}",
                is_system=True
            )

        finally:
            self._scan_lock = False

    def toggle_on(self, node):
        if not node.can_toggle():
            return

        node.toggle_on()

        self.ui.log(
            f"[TOGGLE] {node.name} ON. "
            f"Starting handshake...",
            is_system=True
        )

        threading.Thread(
            target=lambda:
                asyncio.run(
                    self._do_handshake(node)
                ),
            daemon=True
        ).start()

    def toggle_off(self, node):
        node.toggle_off()

        self.ui.log(
            f"[TOGGLE] {node.name} OFF.",
            is_system=True
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

    def _build_roster(self):
        roster = []

        handle = self.ui.get_human_handle()

        roster.append(
            f"🎩 {handle} (Human)"
        )

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

    async def _do_handshake(self, node):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(
                    "http://127.0.0.1:9222"
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
                    self.ui.log(
                        f"[ERROR] {node.name} offline.",
                        is_system=True
                    )

                    node.handshake_failed()
                    return

                node.handshake_start()

                await page.bring_to_front()

                roster = self._build_roster()

                handshake_msg = (
                    MMRC_HANDSHAKE_TEMPLATE
                    .format(roster=roster)
                )

                success = (
                    await self._send_message_to_page(
                        page,
                        node,
                        handshake_msg,
                        is_handshake=True
                    )
                )

                if success:
                    responded = (
                        await self._wait_for_response(
                            page,
                            node,
                            timeout=45
                        )
                    )

                    if responded:
                        raw = await self._get_response(
                            page,
                            node
                        )

                        clean, dropped = (
                            self._parse_response(raw)
                        )

                        if clean and not dropped:
                            node.handshake_success()

                            self.ui.log(
                                f"[HANDSHAKE] "
                                f"{node.name} SUCCESS!",
                                is_system=True
                            )

                            announcement = (
                                f"{node.icon} "
                                f"{node.name} - "
                                f"{clean}"
                            )

                            self.ui.log(
                                f"\n[ANNOUNCE] "
                                f"{announcement}\n",
                                is_system=False
                            )

                            for target in (
                                self.nodes.values()
                            ):
                                if (
                                    target.is_active()
                                    and target != node
                                ):
                                    target.stack.append(
                                        announcement
                                    )

                            return

                        self.ui.log(
                            f"[HANDSHAKE] "
                            f"{node.name} FAILED "
                            f"(invalid response).",
                            is_system=True
                        )

                    else:
                        self.ui.log(
                            f"[HANDSHAKE] "
                            f"{node.name} TIMEOUT.",
                            is_system=True
                        )

                else:
                    self.ui.log(
                        f"[HANDSHAKE] "
                        f"{node.name} FAILED to send.",
                        is_system=True
                    )

                node.handshake_failed()

        except Exception as exc:
            node.handshake_failed()

            self.ui.log(
                f"[ERROR] Handshake with "
                f"{node.name}: {exc}",
                is_system=True
            )

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

        handle = self.ui.get_human_handle()

        payload = (
            f"🎩 {handle} - {message}"
        )

        self.ui.log(
            f"\n{payload}\n{'=' * 50}"
        )

        for node in active_nodes:
            node.stack.append(payload)

            self.ui.log(
                f"[RELAY] Payload enqueued "
                f"for {node.name}",
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
                f"[RELAY] Relay.start() returned False. "
                f"State: {self.relay.state}",
                is_system=True
            )

    async def _do_relay(self):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(
                    "http://127.0.0.1:9222"
                )

                context = (
                    browser.contexts[0]
                    if browser.contexts
                    else await browser.new_context()
                )

                self.relay.fill_complete()
                self.relay.submit_complete()

                self.ui.log(
                    "[RELAY] Active nodes: "
                    f"{[n.name for n in self.relay.active_nodes]}",
                    is_system=True
                )

                for node in self.relay.active_nodes:
                    self.ui.log(
                        f"[RELAY] Checking {node.name} | "
                        f"active={node.is_active()} | "
                        f"stack_len={len(node.stack)}",
                        is_system=True
                    )

                    if not node.is_active():
                        self.ui.log(
                            f"[RELAY] {node.name} "
                            f"not active. Skipping.",
                            is_system=True
                        )
                        continue

                    if not node.stack:
                        self.ui.log(
                            f"[RELAY] {node.name} "
                            f"stack empty. Skipping.",
                            is_system=True
                        )
                        continue

                    page = None

                    for candidate in context.pages:
                        if node.url in candidate.url:
                            page = candidate
                            break

                    if not page:
                        self.ui.log(
                            f"[RELAY] {node.name} offline.",
                            is_system=True
                        )
                        continue

                    await page.bring_to_front()

                    payload_parts = []

                    while node.stack:
                        payload_parts.append(
                            node.stack.popleft()
                        )

                    payload = "\n\n".join(
                        payload_parts
                    ).strip()

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
                        self.ui.log(
                            f"[RELAY] Failed to send "
                            f"to {node.name}.",
                            is_system=True
                        )
                        continue

                    self.ui.log(
                        f"[RELAY] Sent to {node.name}...",
                        is_system=True
                    )

                    responded = (
                        await self._wait_for_response(
                            page,
                            node,
                            timeout=60
                        )
                    )

                    if responded:
                        raw = await self._get_response(
                            page,
                            node
                        )

                        clean, dropped = (
                            self._parse_response(raw)
                        )

                        if dropped:
                            self.ui.log(
                                f"[RELAY] "
                                f"{node.name} dropped out.",
                                is_system=True
                            )

                            node.toggle_off()
                            continue

                        if clean:
                            relay_msg = (
                                f"{node.icon} "
                                f"{node.name} - "
                                f"{clean}"
                            )

                            self.ui.log(
                                f"\n{relay_msg}\n"
                            )

                            for target in (
                                self.relay.active_nodes
                            ):
                                if (
                                    target != node
                                    and target.is_active()
                                ):
                                    target.stack.append(
                                        relay_msg
                                    )

                self.relay.relay_complete()

                self.ui.log(
                    "[RELAY] Cycle complete.",
                    is_system=True
                )

        except Exception as exc:
            self.relay.error()

            self.ui.log(
                f"[RELAY] Error: {exc}",
                is_system=True
            )

        finally:
            self.relay.reset()

    def _safe_js_selector(self, selector):
        return json.dumps(selector)

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
                self.ui.log(
                    f"[SEND] No input selector "
                    f"for {node.name}.",
                    is_system=True
                )
                return False

            input_element = await page.query_selector(
                selector
            )

            if (
                not input_element
                or not await input_element.is_visible()
            ):
                self.ui.log(
                    f"[SEND] LOCATE INPUT failed "
                    f"for {node.name}: "
                    f"'{selector}' not visible.",
                    is_system=True
                )
                return False

            self.ui.log(
                f"[SEND] LOCATE INPUT: "
                f"{node.name} using '{selector}'",
                is_system=True
            )

            step = "CLEAR INPUT"

            await self._clear_input_element(
                page,
                input_element,
                selector
            )

            self.ui.log(
                f"[SEND] CLEAR INPUT: {node.name}",
                is_system=True
            )

            step = "FILL INPUT"

            await input_element.fill(text)

            self.ui.log(
                f"[SEND] FILL INPUT: "
                f"{node.name} ({len(text)} chars)",
                is_system=True
            )

            step = "SUBMIT"

            submit_success = await self._submit(
                page
            )

            if not submit_success:
                self.ui.log(
                    f"[SEND] SUBMIT failed "
                    f"for {node.name}.",
                    is_system=True
                )
                return False

            self.ui.log(
                f"[SEND] SUBMIT: {node.name}",
                is_system=True
            )

            return True

        except Exception as exc:
            self.ui.log(
                f"[SEND] {step} failed "
                f"for {node.name}: {exc}",
                is_system=True
            )

            return False

    async def _clear_input_element(
        self,
        page,
        element,
        selector
    ):
        try:
            safe_sel = self._safe_js_selector(
                selector
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

    async def _submit(self, page):
        send_selectors = [
            'button[aria-label*="Send"]',
            'button[type="submit"]',
            'button:has-text("Send")',
            '[data-testid="send-button"]'
        ]

        for selector in send_selectors:
            try:
                buttons = await page.query_selector_all(
                    selector
                )

                for button in buttons:
                    if not await button.is_visible():
                        continue

                    disabled = await button.is_disabled()

                    if disabled:
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
                        or "cancel" in aria
                        or "stop" in text
                        or "cancel" in text
                    ):
                        continue

                    await button.click()
                    return True

            except Exception:
                continue

        try:
            await page.keyboard.press("Enter")
            return True
        except Exception:
            return False

    async def _send_button_state(self, page):
        """
        Determine whether the node appears ready to accept
        another message.

        True  = send control exists, is visible, enabled,
                and does not look like a Stop/Cancel control.
        False = still generating/busy, or no usable send
                control is currently visible.
        """

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

                for (const selector of selectors) {
                    let elements = [];

                    try {
                        elements =
                            document.querySelectorAll(selector);
                    } catch (e) {
                        continue;
                    }

                    for (const el of elements) {
                        const style =
                            window.getComputedStyle(el);

                        const visible =
                            !!(
                                el.offsetWidth > 0 &&
                                el.offsetHeight > 0 &&
                                style.visibility !== "hidden" &&
                                style.display !== "none"
                            );

                        if (!visible) {
                            continue;
                        }

                        const disabled =
                            !!(
                                el.disabled ||
                                el.getAttribute("aria-disabled") === "true"
                            );

                        const aria =
                            (
                                el.getAttribute("aria-label") ||
                                ""
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

                        if (!disabled && !busy) {
                            foundSend = true;
                            break;
                        }
                    }

                    if (foundSend) {
                        break;
                    }
                }

                return foundSend;
            }
            """
        )

        return bool(result)

    async def _wait_for_response(
        self,
        page,
        node,
        timeout=45
    ):
        """
        Response completion is determined by SEND readiness,
        not by DOM mutation.

        The node may expose thinking/reasoning text while it
        is generating. That text is deliberately ignored here.

        After submission we wait for the node to become busy,
        then wait for the send control to become usable again.
        Only after that do we inspect the last response.
        """

        self.ui.log(
            f"[WAIT] {node.name}: waiting for generation "
            f"to finish...",
            is_system=True
        )

        start = asyncio.get_event_loop().time()

        saw_busy = False
        ready_streak = 0

        while (
            asyncio.get_event_loop().time()
            - start
            < timeout
        ):
            await asyncio.sleep(0.5)

            send_ready = await self._send_button_state(
                page
            )

            if not send_ready:
                if not saw_busy:
                    self.ui.log(
                        f"[WAIT] {node.name}: node is busy.",
                        is_system=True
                    )

                saw_busy = True
                ready_streak = 0
                continue

            if not saw_busy:
                # Some sites transition so quickly that we may
                # never catch the busy state. Require a small
                # ready streak rather than declaring completion
                # immediately.
                ready_streak += 1

                if ready_streak >= 3:
                    self.ui.log(
                        f"[WAIT] {node.name}: send ready.",
                        is_system=True
                    )
                    return True

            else:
                ready_streak += 1

                if ready_streak >= 3:
                    self.ui.log(
                        f"[WAIT] {node.name}: response finalized.",
                        is_system=True
                    )
                    return True

        self.ui.log(
            f"[WAIT] {node.name}: response timeout.",
            is_system=True
        )

        return False

    async def _get_response(
        self,
        page,
        node
    ):
        output_selector = node.output_selector

        if not output_selector:
            return (
                "No response text extracted from DOM."
            )

        try:
            messages = await page.evaluate(
                f"""
                () => {{
                    const elements =
                        document.querySelectorAll(
                            {json.dumps(output_selector)}
                        );

                    const results = [];

                    for (const el of elements) {{
                        const text =
                            el.innerText || '';

                        if (text.trim()) {{
                            results.push(text.trim());
                        }}
                    }}

                    return results;
                }}
                """
            )

            if not messages:
                return (
                    "No response text extracted from DOM."
                )

            # The final completed response is the last matching
            # output block. Thinking/reasoning blocks that occur
            # earlier are deliberately ignored.
            for last_message in reversed(messages):
                matches = list(
                    re.finditer(
                        r'🟩.*?🔚',
                        last_message,
                        re.DOTALL
                    )
                )

                if matches:
                    frame_content = (
                        matches[-1]
                        .group()[1:-1]
                        .strip()
                    )

                    if (
                        frame_content
                        and "MMRC" not in frame_content
                        and "Multi-Mind Relay Core"
                        not in frame_content
                    ):
                        return frame_content

            # If no valid framed response exists, return the
            # final completed output block rather than an earlier
            # thinking block.
            return messages[-1].strip()

        except Exception as exc:
            self.ui.log(
                f"[RESPONSE] Error: {exc}",
                is_system=True
            )

        return (
            "No response text extracted from DOM."
        )

    def _parse_response(self, text):
        trimmed = text.strip()

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

            start = frame.find("🟩")
            end = frame.find("🔚", start)

            if end != -1:
                dropped = False

                if "🛑" in trimmed[end + 1:]:
                    dropped = True

                return (
                    trimmed[
                        start + 1:end
                    ].strip(),
                    dropped
                )

        return trimmed, False

    def _on_node_change(
        self,
        node,
        old,
        new
    ):
        self.ui.log(
            f"[STATE] {node.name}: "
            f"{old} -> {new}",
            is_system=True
        )

    def _on_relay_change(
        self,
        relay
    ):
        self.ui.relay_state_changed(
            relay.state
        )

        if relay.state == RelayState.COMPLETE:
            self.ui.log(
                "[RELAY] Complete.",
                is_system=True
            )


if __name__ == "__main__":
    logger.info(
        "Launching MMRC Luma 1.3."
    )

    controller = MMRCController()
    controller.ui.run()

