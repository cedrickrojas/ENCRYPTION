from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from ironvault.crypto.core import CryptoError, decrypt_text, encrypt_text, password_strength
from ironvault.file_operations.encrypted_file import decrypt_file, encrypt_file
from ironvault.services.activity import ActivityLog


class VaultIllustration(QWidget):
    """A native, resolution-independent vault dial for the welcome panel."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(230, 210)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        for radius, color in ((92, "#48443c"), (72, "#71634c"), (51, "#dba854")):
            painter.setPen(QPen(QColor(color), 1.5))
            painter.drawEllipse(-radius, -radius, radius * 2, radius * 2)
        painter.setPen(QPen(QColor("#dba854"), 2))
        for _ in range(12):
            painter.drawLine(0, -80, 0, -86)
            painter.rotate(30)
        painter.setPen(QPen(QColor("#edc47d"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for _ in range(3):
            painter.drawLine(0, -11, 0, -36)
            painter.rotate(120)
        painter.setBrush(QColor("#edc47d"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(-9, -9, 18, 18)
        painter.end()


class FileWorker(QObject):
    progress = Signal(int)
    finished = Signal()
    failed = Signal(str)

    def __init__(self, action: str, source: str, destination: str, password: str) -> None:
        super().__init__()
        self.action, self.source, self.destination, self.password = action, source, destination, password

    def run(self) -> None:
        try:
            operation = encrypt_file if self.action == "encrypt" else decrypt_file
            operation(self.source, self.destination, self.password, self.progress.emit)
            self.finished.emit()
        except (CryptoError, OSError) as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    PAGE_DETAILS = [
        ("Your private workspace.", "A little privacy. A lot of peace of mind."),
        ("Make it yours to keep.", "Turn sensitive text into an encrypted package you can safely store."),
        ("Bring your words back.", "Open an IRONVAULT package with the password used to create it."),
        ("Privacy, file by file.", "Protect a document, photo, or any other file on this device."),
        ("Built on a strong foundation.", "A closer look at how your information is protected."),
        ("Settle into your workspace.", "Small preferences for the way you work. Saved for this session."),
        ("A space for your secrets.", "Meet IRONVAULT. Private by design, local by default."),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.log = ActivityLog()
        self.current_file = ""
        self.show_notifications = True
        self.clear_sensitive_fields = False
        self.output_directory = Path.home() / "Documents"
        self.setWindowTitle("IRONVAULT | Private workspace")
        self.setMinimumSize(1060, 700)
        self.resize(1280, 820)
        self._build_ui()
        self._show_page(0)

    @staticmethod
    def _label(text: str, name: str = "muted") -> QLabel:
        label = QLabel(text, objectName=name)
        label.setWordWrap(True)
        return label

    @staticmethod
    def _button(text: str, callback, primary: bool = False) -> QPushButton:
        button = QPushButton(text, objectName="primaryButton" if primary else "secondaryButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(callback)
        button.setMinimumHeight(42)
        return button

    def _build_ui(self) -> None:
        root = QWidget(objectName="root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        masthead = QFrame(objectName="masthead")
        masthead.setFixedHeight(82)
        mast = QHBoxLayout(masthead)
        mast.setContentsMargins(32, 0, 32, 0)
        monogram = QLabel("IV", objectName="monogram")
        monogram.setAlignment(Qt.AlignmentFlag.AlignCenter)
        monogram.setFixedSize(42, 42)
        mast.addWidget(monogram)
        brand = QVBoxLayout()
        brand.setSpacing(0)
        brand.addWidget(QLabel("IRONVAULT", objectName="brand"))
        brand.addWidget(QLabel("YOUR PERSONAL PRIVACY DESK", objectName="brandCaption"))
        mast.addLayout(brand)
        mast.addStretch()
        badge = QLabel("●  OFFLINE WORKSPACE", objectName="offlineBadge")
        badge.setFixedHeight(34)
        mast.addWidget(badge)
        outer.addWidget(masthead)

        navigation = QFrame(objectName="navigation")
        tabs = QHBoxLayout(navigation)
        tabs.setContentsMargins(28, 8, 28, 8)
        tabs.setSpacing(6)
        self.nav = []
        for index, title in enumerate(("Overview", "Encrypt text", "Decrypt text", "Files", "Security", "Preferences", "About")):
            button = QPushButton(title, objectName="navButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=index: self._show_page(i))
            tabs.addWidget(button)
            self.nav.append(button)
        tabs.addStretch()
        outer.addWidget(navigation)

        content = QWidget(objectName="content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(32, 24, 32, 12)
        content_layout.setSpacing(18)
        heading = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(5)
        self.page_title = QLabel(objectName="pageTitle")
        self.page_subtitle = QLabel(objectName="pageSubtitle")
        self.page_subtitle.setWordWrap(True)
        titles.addWidget(self.page_title)
        titles.addWidget(self.page_subtitle)
        heading.addLayout(titles, 1)
        heading.addWidget(QLabel("PRIVATE BY DEFAULT", objectName="eyebrow"))
        content_layout.addLayout(heading)
        self.pages = QStackedWidget()
        for page in (self._dashboard(), self._text_page(False), self._text_page(True), self._files_page(), self._security_page(), self._settings_page(), self._about_page()):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(page)
            self.pages.addWidget(scroll)
        content_layout.addWidget(self.pages, 1)
        footer = QHBoxLayout()
        footer.addWidget(QLabel("ON THIS DEVICE. UNDER YOUR CONTROL.", objectName="footer"))
        footer.addStretch()
        footer.addWidget(QLabel("IRONVAULT  /  01", objectName="footer"))
        content_layout.addLayout(footer)
        outer.addWidget(content, 1)
        self.setCentralWidget(root)

    def _card(self, title: str, subtitle: str = "", name: str = "card") -> tuple[QFrame, QVBoxLayout]:
        card = QFrame(objectName=name)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(self._label(title, "cardTitle"))
        if subtitle:
            layout.addWidget(self._label(subtitle))
        return card, layout

    @staticmethod
    def _page() -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(16)
        return page, layout

    def _dashboard(self) -> QWidget:
        page, layout = self._page()
        hero = QFrame(objectName="hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(30, 20, 24, 20)
        words = QVBoxLayout()
        words.setSpacing(12)
        words.addWidget(QLabel("THE KEY STAYS WITH YOU", objectName="heroEyebrow"))
        words.addWidget(self._label("Keep your private life\nprivate.", "heroTitle"))
        words.addWidget(self._label("A quiet place to protect your words and files.\nNo accounts, no cloud, just you and your password.", "heroDescription"))
        actions = QHBoxLayout()
        actions.addWidget(self._button("Protect some text  →", lambda: self._show_page(1), True))
        actions.addWidget(self._button("Work with a file", lambda: self._show_page(3)))
        actions.addStretch()
        words.addLayout(actions)
        hero_layout.addLayout(words, 1)
        hero_layout.addWidget(VaultIllustration())
        layout.addWidget(hero)

        workflows = QHBoxLayout()
        workflows.setSpacing(16)
        for number, title, description, action, index in (
            ("01 / PROTECT", "Lock your words", "Create an encrypted package from a note, message, or other sensitive text.", "Encrypt text  →", 1),
            ("02 / RESTORE", "Open a package", "Have encrypted text already? Bring it back with the original password.", "Decrypt text  →", 2),
            ("03 / STORE", "Safeguard a file", "Save a protected .iron copy of your file while keeping the original.", "Choose a file  →", 3),
        ):
            card, body = self._card(number)
            body.itemAt(0).widget().setObjectName("eyebrow")
            body.addWidget(self._label(title, "workflowTitle"))
            body.addWidget(self._label(description))
            body.addStretch()
            body.addWidget(self._button(action, lambda checked=False, i=index: self._show_page(i)))
            workflows.addWidget(card, 1)
        layout.addLayout(workflows)
        layout.addWidget(self._label("AES-256-GCM encryption     /     Password protected     /     Works entirely offline", "trustLine"))
        layout.addStretch()
        return page

    def _password_row(self, strength: bool = True) -> tuple[QLineEdit, QWidget]:
        wrapper = QWidget()
        wrap = QVBoxLayout(wrapper)
        wrap.setContentsMargins(0, 0, 0, 0)
        wrap.setSpacing(6)
        row = QHBoxLayout()
        password = QLineEdit()
        password.setEchoMode(QLineEdit.EchoMode.Password)
        password.setPlaceholderText("Enter your password")
        password.setMinimumHeight(42)
        toggle = QPushButton("Show", objectName="inlineButton")
        toggle.setCheckable(True)
        toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle.setMinimumHeight(42)
        toggle.toggled.connect(lambda visible: (password.setEchoMode(QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password), toggle.setText("Hide" if visible else "Show")))
        row.addWidget(password, 1)
        row.addWidget(toggle)
        wrap.addLayout(row)
        if strength:
            strength_label = self._label("Use a long, unique password.", "smallText")
            password.textChanged.connect(lambda value: strength_label.setText(f"Password strength: {password_strength(value)[0]}" if value else "Use a long, unique password."))
            wrap.addWidget(strength_label)
        return password, wrapper

    def _text_page(self, decrypt: bool) -> QWidget:
        page, layout = self._page()
        steps = QFrame(objectName="stepStrip")
        step_layout = QHBoxLayout(steps)
        step_layout.setContentsMargins(18, 12, 18, 12)
        for text in (("01  Paste encrypted package", "02  Enter original password", "03  Restore your text") if decrypt else ("01  Write your text", "02  Choose a password", "03  Keep your package")):
            step_layout.addWidget(self._label(text, "stepLabel"), 1)
        layout.addWidget(steps)

        columns = QHBoxLayout()
        columns.setSpacing(16)
        source, left = self._card("01   Encrypted package" if decrypt else "01   Your original text", "Paste the complete output from Encrypt text." if decrypt else "Write or paste the text you want to keep private.")
        editor = QPlainTextEdit()
        editor.setMinimumHeight(175)
        editor.setPlaceholderText('Paste the full package, starting with {"ciphertext": ...' if decrypt else "Your words go here…")
        editor.setAccessibleName("Encrypted package" if decrypt else "Original text")
        if decrypt:
            editor.setObjectName("packageEditor")
        left.addWidget(editor, 1)
        left.addWidget(self._label("YOUR ORIGINAL PASSWORD" if decrypt else "CREATE A PASSWORD", "fieldLabel"))
        password, password_widget = self._password_row(not decrypt)
        left.addWidget(password_widget)
        left.addWidget(self._label("Use the same password that created this package." if decrypt else "Keep this password safe. You will need it to decrypt.", "smallText"))
        buttons = QHBoxLayout()
        buttons.addWidget(self._button("Restore text  →" if decrypt else "Encrypt text  →", self._decrypt_text if decrypt else self._encrypt_text, True), 1)
        buttons.addWidget(self._button("Clear", lambda: (editor.clear(), password.clear(), output.clear())))
        left.addLayout(buttons)
        columns.addWidget(source, 1)

        result, right = self._card("02   Restored text" if decrypt else "02   Your encrypted package", "Your original words will appear below." if decrypt else "Copy the entire package. You need all of it to decrypt.")
        result.setObjectName("resultCard")
        output = QPlainTextEdit()
        output.setReadOnly(True)
        output.setMinimumHeight(200)
        output.setPlaceholderText("Waiting to restore your text…" if decrypt else "Your protected package will appear here…")
        output.setAccessibleName("Restored text" if decrypt else "Encrypted result")
        if not decrypt:
            output.setObjectName("packageEditor")
        right.addWidget(output, 1)
        right.addWidget(self._label("ONLY YOU HAVE THE KEY" if decrypt else "READY TO STORE OR SHARE", "eyebrow"))
        right.addWidget(self._label("Treat restored text as private information." if decrypt else "The package contains encrypted data. Your password is never included.", "smallText"))
        exports = QHBoxLayout()
        copy = self._button("Copy text" if decrypt else "Copy package", lambda: (QApplication.clipboard().setText(output.toPlainText()), self._notify("Copied to clipboard.")))
        copy.setEnabled(False)
        output.textChanged.connect(lambda: copy.setEnabled(bool(output.toPlainText())))
        exports.addWidget(copy, 1)
        if not decrypt:
            save = self._button("Save .txt", self._save_encrypted_text)
            save.setEnabled(False)
            output.textChanged.connect(lambda: save.setEnabled(bool(output.toPlainText())))
            exports.addWidget(save)
        right.addLayout(exports)
        if not decrypt:
            transfer = self._button("Open this package in Decrypt  →", self._open_in_decrypt)
            transfer.setEnabled(False)
            output.textChanged.connect(lambda: transfer.setEnabled(bool(output.toPlainText())))
            right.addWidget(transfer)
        columns.addWidget(result, 1)
        layout.addLayout(columns, 1)
        layout.addWidget(self._label("A package is the encrypted result, not your original text. Copy it from the Encrypt text page." if decrypt else "A fresh encrypted package is created every time, even for the same text and password.", "trustLine"))
        if decrypt:
            self.decrypt_input, self.decrypt_password, self.decrypt_output = editor, password, output
        else:
            self.encrypt_input, self.encrypt_password, self.encrypt_output = editor, password, output
        return page

    def _open_in_decrypt(self) -> None:
        self.decrypt_input.setPlainText(self.encrypt_output.toPlainText())
        self.decrypt_output.clear()
        self.decrypt_password.clear()
        self._show_page(2)
        self.decrypt_password.setFocus()

    def _files_page(self) -> QWidget:
        page, layout = self._page()
        columns = QHBoxLayout()
        columns.setSpacing(16)
        card, body = self._card("01   Pick your file", "Any regular file works. Your original stays in place.")
        self.file_label = self._label("+\n\nChoose a file to get started\nDocuments, photos, archives, and more", "fileWell")
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_label.setMinimumHeight(210)
        body.addWidget(self.file_label, 1)
        self.file_browse_button = self._button("Browse files…", self._browse_file)
        body.addWidget(self.file_browse_button)
        columns.addWidget(card, 1)
        card, body = self._card("02   Protect or restore", "Use your password to encrypt a file or open an .iron copy.")
        body.addWidget(self._label("FILE PASSWORD", "fieldLabel"))
        self.file_password, password_widget = self._password_row(False)
        body.addWidget(password_widget)
        body.addWidget(self._label("Keep your password somewhere safe. Forgotten passwords cannot be recovered.", "smallText"))
        body.addStretch()
        self.file_progress = QProgressBar()
        self.file_progress.setValue(0)
        self.file_progress.setTextVisible(False)
        body.addWidget(self.file_progress)
        self.file_status = self._label("Ready when you are.")
        body.addWidget(self.file_status)
        self.file_encrypt_button = self._button("Encrypt to .iron  →", lambda: self._start_file("encrypt"), True)
        self.file_decrypt_button = self._button("Restore an .iron file", lambda: self._start_file("decrypt"))
        body.addWidget(self.file_encrypt_button)
        body.addWidget(self.file_decrypt_button)
        columns.addWidget(card, 1)
        layout.addLayout(columns)
        layout.addWidget(self._label("You choose where the new file is saved. Processing happens entirely on this device.", "trustLine"))
        layout.addStretch()
        return page

    def _security_page(self) -> QWidget:
        page, layout = self._page()
        card, body = self._card("Your privacy, explained", "Established encryption. No external service required.")
        for label, value in (
            ("Encryption", "AES-256-GCM protects your text and file contents."),
            ("Password protection", "PBKDF2-HMAC-SHA256 derives your key using 600,000 iterations."),
            ("Integrity", "Authentication detects an incorrect password or modified encrypted data."),
            ("Fresh randomness", "Every operation uses a fresh random salt and nonce material."),
            ("Your password", "Never saved to disk or included in the activity log."),
            ("Your device", "No accounts, telemetry, or network service required."),
        ):
            row = QFrame(objectName="detailRow")
            line = QHBoxLayout(row)
            line.setContentsMargins(0, 12, 0, 12)
            key = self._label(label, "detailKey")
            key.setFixedWidth(180)
            line.addWidget(key)
            line.addWidget(self._label(value, "detailValue"), 1)
            body.addWidget(row)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _settings_page(self) -> QWidget:
        page, layout = self._page()
        card, body = self._card("Make yourself at home", "These preferences apply until you close the app.")
        for text, attribute, checked in (
            ("Show operation notifications", "show_notifications", True),
            ("Clear source text and passwords after successful operations", "clear_sensitive_fields", False),
        ):
            toggle = QCheckBox(text)
            toggle.setChecked(checked)
            toggle.toggled.connect(lambda value, name=attribute: setattr(self, name, value))
            body.addWidget(toggle)
        body.addWidget(self._label("DEFAULT SAVE LOCATION", "fieldLabel"))
        row = QHBoxLayout()
        self.directory_field = QLineEdit(str(self.output_directory))
        self.directory_field.setReadOnly(True)
        row.addWidget(self.directory_field, 1)
        row.addWidget(self._button("Choose folder…", self._choose_directory))
        body.addLayout(row)
        body.addWidget(self._label("You can still choose another location each time you save.", "smallText"))
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _choose_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Default save location", str(self.output_directory))
        if directory:
            self.output_directory = Path(directory)
            self.directory_field.setText(directory)

    def _about_page(self) -> QWidget:
        page, layout = self._page()
        card, body = self._card("IRONVAULT", "YOUR PERSONAL PRIVACY DESK  /  VERSION 1.0.0")
        body.addWidget(self._label("Your information deserves\na place of its own.", "aboutTitle"))
        body.addWidget(self._label("A focused desktop workspace for protecting sensitive text and files. Built to work offline, with your password and your device at the center.", "detailValue"))
        body.addWidget(self._label("No accounts. No telemetry. No external services.", "trustLine"))
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _show_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        title, subtitle = self.PAGE_DETAILS[index]
        self.page_title.setText(title)
        self.page_subtitle.setText(subtitle)
        for position, button in enumerate(self.nav):
            button.setChecked(position == index)

    def _error(self, message: str) -> None:
        QMessageBox.warning(self, "Unable to complete operation", message)

    def _encrypt_text(self) -> None:
        try:
            result = encrypt_text(self.encrypt_input.toPlainText(), self.encrypt_password.text())
            self.encrypt_output.setPlainText(result)
            self.log.add("Text encryption", "Text input", True)
            if self.clear_sensitive_fields:
                self.encrypt_input.clear()
                self.encrypt_password.clear()
            self._notify("Package created. Keep the entire package and remember your password.")
        except CryptoError as exc:
            self.log.add("Text encryption", "Text input", False)
            self._error(str(exc))

    def _decrypt_text(self) -> None:
        try:
            result = decrypt_text(self.decrypt_input.toPlainText(), self.decrypt_password.text())
            self.decrypt_output.setPlainText(result)
            self.log.add("Text decryption", "Text input", True)
            if self.clear_sensitive_fields:
                self.decrypt_input.clear()
                self.decrypt_password.clear()
            self._notify("Your original text has been restored.")
        except CryptoError as exc:
            self.log.add("Text decryption", "Text input", False)
            self._error(str(exc))

    def _save_encrypted_text(self) -> None:
        if not self.encrypt_output.toPlainText():
            self._error("Encrypt some text before saving a package.")
            return
        filename, _ = QFileDialog.getSaveFileName(self, "Save encrypted package", str(self.output_directory / "encrypted.txt"), "Text files (*.txt)")
        if filename:
            try:
                Path(filename).write_text(self.encrypt_output.toPlainText(), encoding="utf-8")
                self._notify("Encrypted package saved.")
            except OSError as exc:
                self._error(str(exc))

    def _browse_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Choose a file")
        if filename:
            try:
                path = Path(filename)
                size = path.stat().st_size
            except OSError as exc:
                self._error(str(exc))
                return
            self.current_file = filename
            self.file_label.setText(f"{path.name}\n\n{size:,} bytes  /  {path.suffix or 'No extension'}")
            self.file_status.setText("File selected. Choose protect or restore.")

    def _start_file(self, action: str) -> None:
        if hasattr(self, "file_thread") and self.file_thread.isRunning():
            return
        if not self.current_file:
            self._error("Choose a file before continuing.")
            return
        if not self.file_password.text():
            self._error("Enter your file password before continuing.")
            return
        source = Path(self.current_file)
        if action == "encrypt":
            destination, _ = QFileDialog.getSaveFileName(self, "Save protected file", str(self.output_directory / (source.name + ".iron")), "IRONVAULT files (*.iron)")
        else:
            destination, _ = QFileDialog.getSaveFileName(self, "Save restored file", str(self.output_directory / source.with_suffix("").name), "All files (*)")
        if not destination:
            return
        self.file_progress.setValue(0)
        self.file_status.setText("Working on your file…")
        self._set_file_busy(True)
        self.file_worker = FileWorker(action, str(source), destination, self.file_password.text())
        self.file_action, self.file_destination = action, destination
        self.file_thread = QThread(self)
        self.file_worker.moveToThread(self.file_thread)
        self.file_thread.started.connect(self.file_worker.run)
        self.file_worker.progress.connect(self.file_progress.setValue)
        self.file_worker.finished.connect(self._file_succeeded)
        self.file_worker.failed.connect(self._file_failed)
        self.file_worker.finished.connect(self.file_worker.deleteLater)
        self.file_worker.failed.connect(self.file_worker.deleteLater)
        self.file_worker.finished.connect(self.file_thread.quit)
        self.file_worker.failed.connect(self.file_thread.quit)
        self.file_thread.finished.connect(self._file_thread_finished)
        self.file_thread.start()

    def _set_file_busy(self, busy: bool) -> None:
        self.file_encrypt_button.setEnabled(not busy)
        self.file_decrypt_button.setEnabled(not busy)
        self.file_browse_button.setEnabled(not busy)
        self.file_password.setEnabled(not busy)

    def _file_thread_finished(self) -> None:
        self._set_file_busy(False)

    def _file_succeeded(self) -> None:
        self._file_done(self.file_action, self.file_destination)

    def _file_done(self, action: str, destination: str) -> None:
        self.file_status.setText(f"Saved to {destination}")
        self.log.add("File encryption" if action == "encrypt" else "File decryption", Path(self.current_file).name, True)
        if self.clear_sensitive_fields:
            self.file_password.clear()
        self._notify("Your protected file is ready." if action == "encrypt" else "Your original file has been restored.")

    def _file_failed(self, message: str) -> None:
        self.file_status.setText("Could not complete this file. Check the details and try again.")
        self.log.add("File operation", Path(self.current_file).name, False)
        self._error(message)

    def _notify(self, message: str) -> None:
        if self.show_notifications:
            self.statusBar().showMessage(message, 5000)

    def closeEvent(self, event) -> None:
        if hasattr(self, "file_thread") and self.file_thread.isRunning():
            self._notify("Please wait for your file operation to finish before closing.")
            event.ignore()
            return
        super().closeEvent(event)


def build_app() -> QApplication:
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(STYLESHEET)
    return app


STYLESHEET = """
QWidget { color: #302e29; font-family: 'Segoe UI'; font-size: 13px; }
QMainWindow, #root, #content, QScrollArea, QScrollArea > QWidget > QWidget { background: #f4f1e9; }
QLabel { background: transparent; border: none; }
#masthead { background: #292b28; }
#monogram { background: #edc47d; color: #292b28; border-radius: 12px; font-size: 22px; font-weight: 800; }
#brand { color: #faf7ee; font-size: 20px; font-weight: 800; letter-spacing: 2px; padding-left: 10px; }
#brandCaption { color: #b5b7a9; font-size: 9px; letter-spacing: 1.8px; padding-left: 11px; }
#offlineBadge { color: #edc47d; background: #373a33; border: 1px solid #505245; border-radius: 14px; padding: 8px 14px; font-size: 10px; letter-spacing: 1px; }
#navigation { background: #eae6dc; border-bottom: 1px solid #dcd7cb; }
#navButton { background: transparent; border: none; border-radius: 7px; padding: 10px 17px; color: #736f64; font-size: 12px; font-weight: 600; }
#navButton:hover { background: #dfdacd; color: #302e29; }
#navButton:checked { background: #292b28; color: #faf7ee; }
#pageTitle { font-size: 28px; font-weight: 700; letter-spacing: -0.8px; }
#pageSubtitle { color: #777469; font-size: 12px; }
#eyebrow { color: #8b7247; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
#footer { color: #8b877b; font-size: 9px; letter-spacing: 1.3px; padding-top: 4px; }
#card { background: #fffdf7; border: 1px solid #ded9cc; border-radius: 14px; }
#resultCard { background: #eeeade; border: 1px solid #d8d1c0; border-radius: 14px; }
#cardTitle { color: #37382e; font-size: 16px; font-weight: 700; }
#muted { color: #777368; font-size: 12px; }
#smallText { color: #807a6c; font-size: 11px; }
#workflowTitle { color: #35382e; font-size: 21px; font-weight: 600; }
#trustLine { color: #81755d; font-size: 11px; padding: 5px 2px; }
#hero { background: #292b28; border: 1px solid #3c3d35; border-radius: 16px; }
#heroTitle { color: #faf6e9; font-size: 37px; font-weight: 700; letter-spacing: -1px; }
#heroEyebrow { color: #edc47d; font-size: 10px; letter-spacing: 2px; }
#heroDescription { color: #babaae; font-size: 12px; }
#hero #secondaryButton { background: #373a33; border-color: #55574b; color: #f4efdf; }
#stepStrip { background: #e9e3d4; border: 1px solid #ddd4c0; border-radius: 9px; }
#stepLabel { color: #7b6844; font-size: 11px; font-weight: 600; }
#fieldLabel { color: #7b705b; font-size: 10px; font-weight: 700; letter-spacing: 1px; margin-top: 4px; }
QPlainTextEdit, QLineEdit { background: #fffef9; border: 1px solid #d6d0c2; border-radius: 9px; padding: 12px; color: #35362e; selection-background-color: #e9c47d; selection-color: #292b28; }
QPlainTextEdit { font-size: 14px; }
#packageEditor { font-family: 'Consolas'; font-size: 12px; }
QPlainTextEdit:focus, QLineEdit:focus { border: 1px solid #a8884a; background: #ffffff; }
QPlainTextEdit[readOnly='true'] { background: #f8f5ec; }
QPushButton { outline: none; }
#primaryButton, #secondaryButton, #inlineButton { border-radius: 8px; padding: 9px 16px; font-size: 12px; font-weight: 600; }
#primaryButton { background: #e7b965; border: 1px solid #d9aa55; color: #332b1d; }
#primaryButton:hover { background: #f1c87f; border-color: #c69a4e; }
#primaryButton:pressed { background: #d7a752; }
#secondaryButton, #inlineButton { background: #fffdf6; border: 1px solid #d2cbbc; color: #544b38; }
#secondaryButton:hover, #inlineButton:hover { background: #f4ecd9; border-color: #b59a65; }
#secondaryButton:disabled, #primaryButton:disabled { background: #e9e5da; color: #a49e90; border-color: #ded8cb; }
QPushButton:focus { border: 1px solid #8f7039; }
#fileWell { background: #f7f2e5; border: 1px dashed #c8b995; border-radius: 12px; color: #8b7956; font-size: 15px; padding: 24px; }
QProgressBar { background: #e1dbcc; border: none; border-radius: 5px; min-height: 9px; max-height: 9px; }
QProgressBar::chunk { background: #b18b44; border-radius: 5px; }
#detailRow { background: transparent; border-bottom: 1px solid #e8e2d5; }
#detailKey { color: #645a47; font-size: 12px; font-weight: 600; }
#detailValue { color: #69685e; font-size: 13px; }
#aboutTitle { color: #35382e; font-size: 36px; font-weight: 700; padding: 20px 0; }
QCheckBox { padding: 12px 0; spacing: 12px; color: #595849; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #b8ac94; border-radius: 5px; background: #fffdf7; }
QCheckBox::indicator:checked { background: #9a773b; border: 4px solid #e7b965; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: #c9c0ad; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QStatusBar { background: #e9e2d3; color: #76603a; font-size: 11px; }
QStatusBar::item { border: none; }
QMessageBox { background: #f4f1e9; }
QMessageBox QPushButton { background: #e7b965; border: 1px solid #d9aa55; border-radius: 6px; padding: 8px 24px; }
QToolTip { background: #292b28; color: #faf6e9; border: none; padding: 6px; }
"""
