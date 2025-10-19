import sys
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QFileDialog,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QSpinBox,
    QDoubleSpinBox,
    QCompleter,
    QComboBox,
    QCheckBox,
    QVBoxLayout,
    QWidget,
)

from app.ollama_client import OllamaClient, load_config, save_config
import threading
import json
from PyQt6.QtGui import QKeySequence, QShortcut


class PullThread(QThread):
    progress = pyqtSignal(dict)
    finished_ok = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, client: OllamaClient, name: str) -> None:
        super().__init__()
        self._client = client
        self._name = name
        self._stop_event = threading.Event()

    def run(self) -> None:
        try:
            for event in self._client.pull_model(self._name, stream=True, stop_event=self._stop_event):
                self.progress.emit(event)
            self.finished_ok.emit()
        except Exception as e:
            self.failed.emit(str(e))

    def stop(self) -> None:
        self._stop_event.set()


class ChatThread(QThread):
    token = pyqtSignal(str)
    failed = pyqtSignal(str)
    finished_ok = pyqtSignal()

    def __init__(self, client: OllamaClient, model: str, messages: List[Dict[str, str]], options: Optional[Dict[str, Any]] = None) -> None:
        super().__init__()
        self._client = client
        self._model = model
        self._messages = messages
        self._options = options
        self._stop_event = threading.Event()

    def run(self) -> None:
        try:
            for event in self._client.chat_stream(self._model, self._messages, self._options, stop_event=self._stop_event):
                msg = event.get("message") or {}
                content = msg.get("content", "")
                if content:
                    self.token.emit(content)
            self.finished_ok.emit()
        except Exception as e:
            self.failed.emit(str(e))

    def stop(self) -> None:
        self._stop_event.set()


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget, client: OllamaClient) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self._client = client

        cfg = load_config()
        host = cfg.get("host", "127.0.0.1")
        port = str(cfg.get("port", 11434))

        self.host_edit = QLineEdit(host)
        self.port_edit = QLineEdit(port)
        self.port_edit.setInputMask("00000")

        form = QFormLayout()
        form.addRow("Host", self.host_edit)
        form.addRow("Port", self.port_edit)

        btns = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        btns.addWidget(save_btn)
        btns.addWidget(cancel_btn)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(btns)
        self.setLayout(layout)

        save_btn.clicked.connect(self.on_save)
        cancel_btn.clicked.connect(self.reject)

    def on_save(self) -> None:
        try:
            host = self.host_edit.text().strip() or "127.0.0.1"
            port = int(self.port_edit.text()) if self.port_edit.text() else 11434
            save_config({"host": host, "port": port})
            self._client.configure(host, port)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Ollama GUI")

        cfg = load_config()
        host = cfg.get("host", "127.0.0.1")
        port = int(cfg.get("port", 11434))
        self.client = OllamaClient(host, port)

        self.models_list = QListWidget()
        self.refresh_btn = QPushButton("Refresh Models")
        self.pull_input = QLineEdit()
        self.pull_input.setPlaceholderText("model (e.g., llama3.1:8b)")
        self.pull_btn = QPushButton("Pull")
        self.pull_stop_btn = QPushButton("Stop Pull")
        self.delete_btn = QPushButton("Delete Selected")
        self.pull_log = QTextEdit()
        self.pull_log.setReadOnly(True)

        left = QVBoxLayout()
        left.addWidget(QLabel("Installed Models"))
        left.addWidget(self.models_list)
        left.addWidget(self.refresh_btn)
        left.addWidget(QLabel("Pull model"))
        left.addWidget(self.pull_input)
        left.addWidget(self.pull_btn)
        left.addWidget(self.pull_stop_btn)
        left.addWidget(self.delete_btn)
        left.addWidget(QLabel("Operations Log"))
        left.addWidget(self.pull_log)
        left_widget = QWidget()
        left_widget.setLayout(left)

        # Chat pane
        self.chat_model = QLineEdit()
        self.chat_model.setPlaceholderText("model to use (e.g., llama3.1:8b)")
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_input = QTextEdit()
        self.send_btn = QPushButton("Send")
        self.stop_btn = QPushButton("Stop")

        # Chat parameters
        chat_params = cfg.get("chat_params", {})
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(float(chat_params.get("temperature", 0.7)))
        self.top_p_spin = QDoubleSpinBox()
        self.top_p_spin.setRange(0.0, 1.0)
        self.top_p_spin.setSingleStep(0.05)
        self.top_p_spin.setValue(float(chat_params.get("top_p", 0.9)))
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(16, 32768)
        self.max_tokens_spin.setValue(int(chat_params.get("num_predict", 512)))
        self.ctx_spin = QSpinBox()
        self.ctx_spin.setRange(256, 32768)
        self.ctx_spin.setValue(int(chat_params.get("num_ctx", 4096)))
        self.gpu_checkbox = QCheckBox("Use GPU")
        self.gpu_checkbox.setChecked(bool(chat_params.get("use_gpu", True)))
        self.system_prompt = QTextEdit()
        self.system_prompt.setPlaceholderText("System prompt (optional)")
        self.system_prompt.setPlainText(chat_params.get("system", ""))

        # Prompt templates controls
        self.template_combo = QComboBox()
        self.save_template_btn = QPushButton("Save Template")
        self.apply_template_btn = QPushButton("Apply Template")
        self.delete_template_btn = QPushButton("Delete Template")
        self._load_templates_into_combo()

        # Per-model preset controls
        self.save_preset_btn = QPushButton("Save Preset for Model")
        self.delete_preset_btn = QPushButton("Delete Preset")

        chat_layout = QVBoxLayout()
        chat_layout.addWidget(QLabel("Chat Model"))
        chat_layout.addWidget(self.chat_model)
        params_row = QHBoxLayout()
        params_row.addWidget(QLabel("Temp"))
        params_row.addWidget(self.temp_spin)
        params_row.addWidget(QLabel("Top-p"))
        params_row.addWidget(self.top_p_spin)
        params_row.addWidget(QLabel("Max tokens"))
        params_row.addWidget(self.max_tokens_spin)
        params_row.addWidget(QLabel("Ctx"))
        params_row.addWidget(self.ctx_spin)
        params_row.addWidget(self.gpu_checkbox)
        chat_layout.addLayout(params_row)
        chat_layout.addWidget(QLabel("System"))
        chat_layout.addWidget(self.system_prompt)
        tmpl_row = QHBoxLayout()
        tmpl_row.addWidget(QLabel("Templates"))
        tmpl_row.addWidget(self.template_combo)
        tmpl_row.addWidget(self.save_template_btn)
        tmpl_row.addWidget(self.apply_template_btn)
        tmpl_row.addWidget(self.delete_template_btn)
        chat_layout.addLayout(tmpl_row)
        preset_row = QHBoxLayout()
        preset_row.addWidget(self.save_preset_btn)
        preset_row.addWidget(self.delete_preset_btn)
        chat_layout.addLayout(preset_row)
        chat_layout.addWidget(QLabel("Conversation"))
        chat_layout.addWidget(self.chat_history)
        chat_layout.addWidget(QLabel("Your Message"))
        chat_layout.addWidget(self.chat_input)
        row = QHBoxLayout()
        row.addWidget(self.send_btn)
        row.addWidget(self.stop_btn)
        chat_layout.addLayout(row)
        chat_widget = QWidget()
        chat_widget.setLayout(chat_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(chat_widget)
        splitter.setStretchFactor(1, 2)

        container = QWidget()
        container_layout = QVBoxLayout()
        container_layout.addWidget(splitter)
        container.setLayout(container_layout)
        self.setCentralWidget(container)

        # Menubar
        menubar = self.menuBar() if isinstance(self.menuBar(), QMenuBar) else QMenuBar()
        settings_menu = menubar.addMenu("Settings")
        act = QAction("Configure host/port", self)
        act.triggered.connect(self.open_settings)
        settings_menu.addAction(act)
        file_menu = menubar.addMenu("File")
        save_act = QAction("Save Conversation", self)
        load_act = QAction("Load Conversation", self)
        clear_act = QAction("Clear Conversation", self)
        save_act.triggered.connect(self.save_conversation)
        load_act.triggered.connect(self.load_conversation)
        clear_act.triggered.connect(self.clear_conversation)
        file_menu.addAction(save_act)
        file_menu.addAction(load_act)
        file_menu.addAction(clear_act)
        self.setMenuBar(menubar)

        # State
        self.messages: List[Dict[str, str]] = []
        self.pull_thread: Optional[PullThread] = None
        self.chat_thread: Optional[ChatThread] = None
        self.current_assistant: str = ""
        self.status_label = QLabel("Disconnected")
        self.statusBar().addPermanentWidget(self.status_label)
        self.health_timer = QTimer(self)
        self.health_timer.timeout.connect(self.check_health)
        self.health_timer.start(3000)

        # Wiring
        self.refresh_btn.clicked.connect(self.refresh_models)
        self.pull_btn.clicked.connect(self.pull_model)
        self.pull_stop_btn.clicked.connect(self.stop_pull)
        self.delete_btn.clicked.connect(self.delete_selected)
        self.send_btn.clicked.connect(self.send_message)
        self.stop_btn.clicked.connect(self.stop_stream)
        self.save_template_btn.clicked.connect(self.save_template)
        self.apply_template_btn.clicked.connect(self.apply_template)
        self.delete_template_btn.clicked.connect(self.delete_template)
        self.save_preset_btn.clicked.connect(self.save_preset)
        self.delete_preset_btn.clicked.connect(self.delete_preset)
        self.chat_model.textChanged.connect(self._maybe_load_preset_for_model)

        # Initial
        self.refresh_models()
        # Load default model into inputs, set completers after refresh
        default_model = cfg.get("default_model", "")
        if default_model:
            self.chat_model.setText(default_model)

        # Shortcuts
        send_sc = QShortcut(QKeySequence("Ctrl+Return"), self)
        send_sc.activated.connect(self.send_message)
        send_sc2 = QShortcut(QKeySequence("Ctrl+Enter"), self)
        send_sc2.activated.connect(self.send_message)
        stop_sc = QShortcut(QKeySequence("Esc"), self)
        stop_sc.activated.connect(self.stop_stream)

    def open_settings(self) -> None:
        dlg = SettingsDialog(self, self.client)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh_models()

    def refresh_models(self) -> None:
        self.models_list.clear()
        try:
            models = self.client.list_models()
            names = []
            for m in models:
                item = QListWidgetItem(m.get("name", ""))
                self.models_list.addItem(item)
                name = m.get("name", "")
                if name:
                    names.append(name)
            # Completers for inputs
            completer = QCompleter(names)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.chat_model.setCompleter(completer)
            pull_completer = QCompleter(names)
            pull_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.pull_input.setCompleter(pull_completer)
            # Context menu
            self.models_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.models_list.customContextMenuRequested.connect(self.open_models_context_menu)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to fetch models: {e}")

    def append_log(self, text: str) -> None:
        self.pull_log.append(text)

    def pull_model(self) -> None:
        name = self.pull_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Input", "Enter a model name to pull.")
            return
        if self.pull_thread and self.pull_thread.isRunning():
            QMessageBox.information(self, "Busy", "A pull is already in progress.")
            return
        self.append_log(f"Pulling {name}...")
        self.pull_thread = PullThread(self.client, name)
        self.pull_thread.progress.connect(self._on_pull_event)
        self.pull_thread.finished_ok.connect(lambda: (self.append_log("Pull finished."), self.refresh_models()))
        self.pull_thread.failed.connect(lambda err: self.append_log(f"Error: {err}"))
        self.pull_thread.start()

    def _on_pull_event(self, ev: dict) -> None:
        try:
            if isinstance(ev, dict) and "error" in ev and "requires a newer version of Ollama" in str(ev.get("error", "")):
                self.append_log(str(ev))
                btn = QMessageBox.question(
                    self,
                    "Update Ollama",
                    "This model requires a newer Ollama. Open download page?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if btn == QMessageBox.StandardButton.Yes:
                    from PyQt6.QtGui import QDesktopServices
                    from PyQt6.QtCore import QUrl
                    QDesktopServices.openUrl(QUrl("https://ollama.com/download"))
                return
        except Exception:
            pass
        self.append_log(str(ev))

    def stop_pull(self) -> None:
        if self.pull_thread and self.pull_thread.isRunning():
            self.pull_thread.stop()

    def delete_selected(self) -> None:
        item = self.models_list.currentItem()
        if not item:
            QMessageBox.information(self, "Select", "Select a model to delete.")
            return
        name = item.text()
        confirm = QMessageBox.question(self, "Confirm", f"Delete model '{name}'?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self.client.delete_model(name)
            self.append_log(f"Deleted {name}")
            self.refresh_models()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete: {e}")

    def send_message(self) -> None:
        model = self.chat_model.text().strip()
        content = self.chat_input.toPlainText().strip()
        if not model or not content:
            QMessageBox.warning(self, "Input", "Enter model and a message.")
            return
        if self.chat_thread and self.chat_thread.isRunning():
            QMessageBox.information(self, "Busy", "Wait for the current response to finish.")
            return
        user_msg = {"role": "user", "content": content}
        self.messages.append(user_msg)
        self.chat_history.append(f"You: {content}")
        self.chat_input.clear()
        # Persist current chat params
        cfg = load_config()
        cfg.setdefault("chat_params", {})
        cfg["chat_params"]["temperature"] = float(self.temp_spin.value())
        cfg["chat_params"]["top_p"] = float(self.top_p_spin.value())
        cfg["chat_params"]["num_predict"] = int(self.max_tokens_spin.value())
        cfg["chat_params"]["num_ctx"] = int(self.ctx_spin.value())
        cfg["chat_params"]["use_gpu"] = bool(self.gpu_checkbox.isChecked())
        cfg["chat_params"]["system"] = self.system_prompt.toPlainText()
        cfg["default_model"] = model
        save_config(cfg)
        # Build options and messages
        options: Dict[str, Any] = {
            "temperature": float(self.temp_spin.value()),
            "top_p": float(self.top_p_spin.value()),
            "num_predict": int(self.max_tokens_spin.value()),
            "num_ctx": int(self.ctx_spin.value()),
            "num_gpu": 1 if self.gpu_checkbox.isChecked() else 0,
        }
        sys_text = self.system_prompt.toPlainText().strip()
        msgs = list(self.messages)
        if sys_text:
            msgs = [{"role": "system", "content": sys_text}] + msgs
        # Start streaming
        self.chat_history.append("Assistant: ")
        self.current_assistant = ""
        self.chat_thread = ChatThread(self.client, model, msgs, options)
        self.chat_thread.token.connect(lambda t: self._on_token(model, t))
        self.chat_thread.finished_ok.connect(lambda: self._on_chat_done(model))
        self.chat_thread.failed.connect(lambda err: QMessageBox.critical(self, "Chat Error", err))
        self.chat_thread.start()

    def _on_token(self, model: str, token: str) -> None:
        if not token:
            return
        self.chat_history.moveCursor(self.chat_history.textCursor().MoveOperation.End)
        self.chat_history.insertPlainText(token)
        self.current_assistant += token

    def _on_chat_done(self, model: str) -> None:
        # Capture last assistant message from history widget; simplistic approach
        # In a production app, we would collect tokens in thread and append once
        self.messages.append({"role": "assistant", "content": self.current_assistant})
        self.current_assistant = ""

    def stop_stream(self) -> None:
        if self.chat_thread and self.chat_thread.isRunning():
            self.chat_thread.stop()

    def save_conversation(self) -> None:
        if not self.messages:
            QMessageBox.information(self, "Save", "No conversation to save.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Conversation", filter="JSON Files (*.json)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.messages, f, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def load_conversation(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load Conversation", filter="JSON Files (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.messages = json.load(f)
            self.chat_history.clear()
            for m in self.messages:
                role = m.get("role", "")
                content = m.get("content", "")
                if role == "user":
                    self.chat_history.append(f"You: {content}")
                elif role == "assistant":
                    self.chat_history.append(f"Assistant: {content}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load: {e}")

    def clear_conversation(self) -> None:
        self.messages = []
        self.chat_history.clear()

    def check_health(self) -> None:
        try:
            ver = self.client.version()
            v = ver.get("version", "")
            self.status_label.setText(f"Connected: {v}")
        except Exception:
            self.status_label.setText("Disconnected")

    # Presets and templates helpers
    def _load_templates_into_combo(self) -> None:
        cfg = load_config()
        templates = cfg.get("prompt_templates", [])
        self.template_combo.clear()
        self.template_combo.addItem("<select>")
        for t in templates:
            name = t.get("name", "")
            if name:
                self.template_combo.addItem(name)

    def save_template(self) -> None:
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Save Template", "Template name:")
        if not ok or not name:
            return
        cfg = load_config()
        templates = cfg.get("prompt_templates", [])
        # overwrite if exists
        content = self.system_prompt.toPlainText()
        found = False
        for t in templates:
            if t.get("name") == name:
                t["content"] = content
                found = True
                break
        if not found:
            templates.append({"name": name, "content": content})
        cfg["prompt_templates"] = templates
        save_config(cfg)
        self._load_templates_into_combo()

    def apply_template(self) -> None:
        name = self.template_combo.currentText()
        if not name or name == "<select>":
            return
        cfg = load_config()
        for t in cfg.get("prompt_templates", []):
            if t.get("name") == name:
                self.system_prompt.setPlainText(t.get("content", ""))
                break

    def delete_template(self) -> None:
        name = self.template_combo.currentText()
        if not name or name == "<select>":
            return
        cfg = load_config()
        templates = [t for t in cfg.get("prompt_templates", []) if t.get("name") != name]
        cfg["prompt_templates"] = templates
        save_config(cfg)
        self._load_templates_into_combo()

    def save_preset(self) -> None:
        model = self.chat_model.text().strip()
        if not model:
            QMessageBox.information(self, "Preset", "Enter a model name first.")
            return
        cfg = load_config()
        presets = cfg.get("model_presets", {})
        presets[model] = {
            "temperature": float(self.temp_spin.value()),
            "top_p": float(self.top_p_spin.value()),
            "num_predict": int(self.max_tokens_spin.value()),
            "num_ctx": int(self.ctx_spin.value()),
            "use_gpu": bool(self.gpu_checkbox.isChecked()),
            "system": self.system_prompt.toPlainText(),
        }
        cfg["model_presets"] = presets
        save_config(cfg)
        QMessageBox.information(self, "Preset", f"Saved preset for {model}")

    def delete_preset(self) -> None:
        model = self.chat_model.text().strip()
        if not model:
            return
        cfg = load_config()
        presets = cfg.get("model_presets", {})
        if model in presets:
            del presets[model]
            cfg["model_presets"] = presets
            save_config(cfg)
            QMessageBox.information(self, "Preset", f"Deleted preset for {model}")

    def _maybe_load_preset_for_model(self) -> None:
        model = self.chat_model.text().strip()
        if not model:
            return
        cfg = load_config()
        presets = cfg.get("model_presets", {})
        preset = presets.get(model)
        if not preset:
            return
        try:
            self.temp_spin.setValue(float(preset.get("temperature", self.temp_spin.value())))
            self.top_p_spin.setValue(float(preset.get("top_p", self.top_p_spin.value())))
            self.max_tokens_spin.setValue(int(preset.get("num_predict", self.max_tokens_spin.value())))
            self.ctx_spin.setValue(int(preset.get("num_ctx", self.ctx_spin.value())))
            self.gpu_checkbox.setChecked(bool(preset.get("use_gpu", self.gpu_checkbox.isChecked())))
            self.system_prompt.setPlainText(preset.get("system", self.system_prompt.toPlainText()))
        except Exception:
            pass

    def open_models_context_menu(self, pos) -> None:
        item = self.models_list.itemAt(pos)
        if item is None:
            return
        name = item.text()
        menu = QMenu(self)
        use_act = QAction("Use in Chat", self)
        default_act = QAction("Set as Default", self)
        delete_act = QAction("Delete", self)
        use_act.triggered.connect(lambda: self.chat_model.setText(name))
        def set_default() -> None:
            cfg = load_config()
            cfg["default_model"] = name
            save_config(cfg)
            self.chat_model.setText(name)
        default_act.triggered.connect(set_default)
        delete_act.triggered.connect(self.delete_selected)
        menu.addAction(use_act)
        menu.addAction(default_act)
        menu.addSeparator()
        menu.addAction(delete_act)
        menu.exec(self.models_list.mapToGlobal(pos))


def run() -> None:
    app = QApplication(sys.argv)
    win = MainWindow()
    # Restore geometry if available
    cfg = load_config()
    geom = cfg.get("window_geometry")
    if isinstance(geom, list) and len(geom) == 4:
        x, y, w, h = geom
        try:
            win.setGeometry(int(x), int(y), int(w), int(h))
        except Exception:
            win.resize(1200, 700)
    else:
        win.resize(1200, 700)
    win.show()
    rc = app.exec()
    # Persist geometry
    g = win.geometry()
    cfg = load_config()
    cfg["window_geometry"] = [g.x(), g.y(), g.width(), g.height()]
    save_config(cfg)
    sys.exit(rc)


if __name__ == "__main__":
    run()


