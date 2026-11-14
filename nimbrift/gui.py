"""Qt desktop frontend. Network work stays in a worker thread."""

import sys
from pathlib import Path
from threading import Event

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .model import Connection, Direction, Transfer, TransferCancelled
from .service import TransferService


STYLE = """
QWidget { font-family: "Inter", "SF Pro Display", "Segoe UI", sans-serif; color: #18243A; font-size: 13px; }
QWidget#shell { background: #F4F7FB; }
QFrame#sidebar { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #101B34,stop:1 #19345B); }
QLabel#wordmark { color: white; font-size: 19px; font-weight: 750; letter-spacing: 1px; }
QLabel#sidebarMuted { color: #A9BDD8; font-size: 12px; }
QLabel#sidebarLabel { color: #DDE9FA; font-size: 13px; font-weight: 600; }
QLabel#hero { color: #14213A; font-size: 27px; font-weight: 750; }
QLabel#subtitle { color: #62718A; font-size: 13px; }
QLabel#sectionTitle { color: #15233C; font-size: 16px; font-weight: 700; }
QLabel#sectionHint { color: #708099; font-size: 12px; }
QLabel#fieldLabel { color: #41516A; font-size: 12px; font-weight: 600; }
QLabel#status { color: #4C5F7B; font-size: 12px; }
QFrame#card { background: white; border: 1px solid #E0E8F3; border-radius: 16px; }
QFrame#footer { background: #F4F7FB; border-top: 1px solid #DFE7F1; }
QLineEdit { background: #F8FAFD; border: 1px solid #D8E2EE; border-radius: 9px; padding: 9px 11px; selection-background-color: #3E6DE0; }
QLineEdit:focus { border: 1px solid #5279E6; background: white; }
QPushButton { border-radius: 9px; padding: 9px 13px; font-weight: 650; }
QPushButton#primary { color: white; background: #365FD6; border: 1px solid #365FD6; padding: 11px 20px; }
QPushButton#primary:hover { background: #2B50C3; }
QPushButton#primary:disabled { background: #9EB2E8; border-color: #9EB2E8; }
QPushButton#secondary { color: #355079; background: #F2F6FC; border: 1px solid #D9E4F1; }
QPushButton#secondary:hover { background: #E9F0FA; }
QPushButton#secondary:disabled { color: #A8B4C5; }
QPushButton#mode { color: #52627A; background: #F2F5FA; border: 1px solid #E0E7F0; }
QPushButton#mode:checked { color: #244DB9; background: #E7EEFF; border: 1px solid #AFC3FB; }
QProgressBar { background: #EAF0F8; border: 0; border-radius: 5px; height: 10px; text-align: center; }
QProgressBar::chunk { background: #496FE0; border-radius: 5px; }
QCheckBox { spacing: 8px; color: #51627D; }
QScrollArea { border: 0; background: transparent; }
"""


def app_icon(size: int = 128) -> QIcon:
    """Draw the same simple mark used by the packaged macOS app icon."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0, QColor("#365FD6"))
    gradient.setColorAt(1, QColor("#33B8C5"))
    painter.setBrush(gradient)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, size, size, size * 0.23, size * 0.23)
    font = QFont("Arial", int(size * 0.56), QFont.Weight.Black)
    painter.setFont(font)
    painter.setPen(QColor("#FFFFFF"))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "N")
    painter.end()
    return QIcon(pixmap)


class TransferWorker(QThread):
    progress = Signal(str, int, int)
    succeeded = Signal()
    cancelled = Signal()
    failed = Signal(str)

    def __init__(self, connection: Connection, request: Transfer, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.request = request
        self.stop_event = Event()

    def run(self) -> None:
        try:
            TransferService().run(
                self.connection,
                self.request,
                lambda p: self.progress.emit(p.path, p.transferred, p.total),
                self.stop_event,
            )
        except TransferCancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nimbrift — Secure file transfer")
        self.setWindowIcon(app_icon())
        self.resize(1000, 760)
        self.setMinimumSize(820, 640)
        self.direction = Direction.UPLOAD
        self.worker: TransferWorker | None = None
        self.close_after_transfer = False
        self._result: tuple[str, str | None] | None = None
        self._build_ui()
        self._set_direction(Direction.UPLOAD)

    def _build_ui(self) -> None:
        shell = QWidget()
        shell.setObjectName("shell")
        self.setCentralWidget(shell)
        outer = QHBoxLayout(shell)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(224)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(24, 30, 24, 26)
        side.setSpacing(9)
        brand = QLabel("◆  NIMBRIFT")
        brand.setObjectName("wordmark")
        side.addWidget(brand)
        side.addWidget(self._label("Secure file transfer", "sidebarMuted"))
        side.addSpacing(48)
        side.addWidget(self._label("TRANSFER WORKSPACE", "sidebarMuted"))
        side.addSpacing(8)
        side.addWidget(self._label("↗    File transfer", "sidebarLabel"))
        side.addStretch()
        side.addWidget(self._label("●  SFTP over SSH", "sidebarLabel"))
        side.addWidget(self._label("Host keys are verified before connecting.", "sidebarMuted", wrap=True))
        outer.addWidget(sidebar)

        right_panel = QWidget()
        right_panel.setObjectName("shell")
        outer.addWidget(right_panel, 1)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setObjectName("shell")
        scroll.setWidget(content)
        right_layout.addWidget(scroll, 1)
        body = QVBoxLayout(content)
        body.setContentsMargins(30, 30, 30, 28)
        body.setSpacing(18)

        body.addWidget(self._label("Move files with confidence", "hero"))
        body.addWidget(self._label("A focused workspace for secure SSH transfers.", "subtitle"))
        body.addSpacing(2)

        connection_card, connection_layout = self._card("Connection", "Choose the SSH host and how you authenticate.")
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(13)
        self.host = self._input("example.com")
        self.username = self._input("Your SSH username")
        self.port = self._input("22")
        self.port.setText("22")
        self.key_file = self._input("Optional · use SSH agent by default")
        self.jump_host = self._input("Optional · e.g. user@jump1,user@jump2 or uses ~/.ssh/config")
        self.known_hosts = self._input("Optional · uses ~/.ssh/known_hosts")
        self.password = self._input("Optional · never saved")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        grid.addLayout(self._field("Host", self.host), 0, 0)
        grid.addLayout(self._field("Username", self.username), 0, 1)
        grid.addLayout(self._field("Port", self.port), 0, 2)
        grid.addLayout(self._field("Jump host (ProxyJump)", self.jump_host), 1, 0, 1, 3)
        grid.addLayout(self._field("Private key", self.key_file, self._browse_key), 2, 0, 1, 2)
        grid.addLayout(self._field("Known hosts", self.known_hosts, self._browse_known_hosts), 2, 2)
        grid.addLayout(self._field("Password", self.password), 3, 0, 1, 3)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        connection_layout.addLayout(grid)
        body.addWidget(connection_card)

        transfer_card, transfer_layout = self._card("Transfer", "Select a direction and enter the source and destination.")
        modes = QHBoxLayout()
        self.upload_mode = self._button("↑  Upload", "mode")
        self.download_mode = self._button("↓  Download", "mode")
        for button in (self.upload_mode, self.download_mode):
            button.setCheckable(True)
            modes.addWidget(button)
        modes.addStretch()
        self.upload_mode.clicked.connect(lambda: self._set_direction(Direction.UPLOAD))
        self.download_mode.clicked.connect(lambda: self._set_direction(Direction.DOWNLOAD))
        transfer_layout.addLayout(modes)
        transfer_layout.addSpacing(6)
        self.source = self._input()
        self.destination = self._input()
        self.source_label = self._label("", "fieldLabel")
        self.destination_label = self._label("", "fieldLabel")
        transfer_layout.addWidget(self.source_label)
        source_row = QHBoxLayout()
        source_row.addWidget(self.source, 1)
        self.source_file_button = self._button("Choose file", "secondary")
        self.source_folder_button = self._button("Choose folder", "secondary")
        self.source_file_button.clicked.connect(self._browse_source_file)
        self.source_folder_button.clicked.connect(self._browse_source_folder)
        source_row.addWidget(self.source_file_button)
        source_row.addWidget(self.source_folder_button)
        transfer_layout.addLayout(source_row)
        transfer_layout.addSpacing(6)
        transfer_layout.addWidget(self.destination_label)
        destination_row = QHBoxLayout()
        destination_row.addWidget(self.destination, 1)
        self.destination_button = self._button("Choose folder", "secondary")
        self.destination_button.clicked.connect(self._browse_destination)
        destination_row.addWidget(self.destination_button)
        transfer_layout.addLayout(destination_row)
        self.overwrite = QCheckBox("Overwrite existing files")
        transfer_layout.addWidget(self.overwrite)
        body.addWidget(transfer_card)

        progress_card, progress_layout = self._card("Activity", "Progress for the current file.")
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        self.status = self._label("Ready to transfer", "status", wrap=True)
        progress_layout.addWidget(self.status)
        body.addWidget(progress_card)

        footer = QFrame()
        footer.setObjectName("footer")
        actions = QHBoxLayout(footer)
        actions.setContentsMargins(30, 12, 30, 12)
        actions.addStretch()
        self.cancel_button = self._button("Cancel", "secondary")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel)
        self.start_button = self._button("Start transfer  →", "primary")
        self.start_button.clicked.connect(self._start)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.start_button)
        right_layout.addWidget(footer)
        body.addStretch()

    @staticmethod
    def _label(text: str, name: str, wrap: bool = False) -> QLabel:
        label = QLabel(text)
        label.setObjectName(name)
        label.setWordWrap(wrap)
        return label

    @staticmethod
    def _input(placeholder: str = "") -> QLineEdit:
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        return field

    @staticmethod
    def _button(text: str, name: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(name)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def _card(self, title: str, hint: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(10)
        layout.addWidget(self._label(title, "sectionTitle"))
        layout.addWidget(self._label(hint, "sectionHint"))
        layout.addSpacing(3)
        return card, layout

    def _field(self, title: str, field: QLineEdit, browse=None) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(5)
        column.addWidget(self._label(title, "fieldLabel"))
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(field, 1)
        if browse is not None:
            button = self._button("Browse", "secondary")
            button.clicked.connect(browse)
            row.addWidget(button)
        column.addLayout(row)
        return column

    def _set_direction(self, direction: Direction) -> None:
        self.direction = direction
        self.upload_mode.setChecked(direction == Direction.UPLOAD)
        self.download_mode.setChecked(direction == Direction.DOWNLOAD)
        uploading = direction == Direction.UPLOAD
        self.source_label.setText("Local source" if uploading else "Remote source")
        self.destination_label.setText("Remote destination" if uploading else "Local destination")
        self.source.setPlaceholderText("/Users/me/Documents/report.csv" if uploading else "/home/me/results")
        self.destination.setPlaceholderText("/home/me/report.csv" if uploading else "/Users/me/Downloads")
        self.source_file_button.setVisible(uploading)
        self.source_folder_button.setVisible(uploading)
        self.destination_button.setVisible(not uploading)

    def _browse_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose private key")
        if path:
            self.key_file.setText(path)

    def _browse_known_hosts(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose known_hosts file")
        if path:
            self.known_hosts.setText(path)

    def _browse_source_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose file to upload")
        if path:
            self.source.setText(path)

    def _browse_source_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose folder to upload")
        if path:
            self.source.setText(path)

    def _browse_destination(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose download destination")
        if path:
            self.destination.setText(path)

    def _start(self) -> None:
        try:
            connection = Connection(
                host=self.host.text().strip(),
                username=self.username.text().strip(),
                port=int(self.port.text()),
                key_file=Path(self.key_file.text()).expanduser() if self.key_file.text() else None,
                known_hosts=Path(self.known_hosts.text()).expanduser() if self.known_hosts.text() else None,
                password=self.password.text() or None,
                jump_host=self.jump_host.text().strip() or None,
            )
            request = Transfer(
                self.direction,
                self.source.text().strip(),
                self.destination.text().strip(),
                self.overwrite.isChecked(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Check your details", str(exc))
            return
        self.progress_bar.setValue(0)
        self.status.setText("Connecting to host…")
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self._result = None
        self.worker = TransferWorker(connection, request, self)
        self.worker.progress.connect(self._on_progress)
        self.worker.succeeded.connect(self._on_succeeded)
        self.worker.cancelled.connect(self._on_cancelled)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    @Slot(str, int, int)
    def _on_progress(self, path: str, transferred: int, total: int) -> None:
        self.progress_bar.setValue(100 if total == 0 else min(100, transferred * 100 // total))
        self.status.setText(f"{Path(path).name}  ·  {transferred:,} / {total:,} bytes")

    @Slot()
    def _on_succeeded(self) -> None:
        self._result = ("Transfer complete", None)

    @Slot()
    def _on_cancelled(self) -> None:
        self._result = ("Transfer cancelled", None)

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self._result = ("Transfer failed", message)

    @Slot()
    def _worker_finished(self) -> None:
        status, error = self._result or ("Transfer stopped", None)
        self.status.setText(status)
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        if self.close_after_transfer:
            self.close()
        elif error:
            QMessageBox.critical(self, "Transfer failed", error)

    def _cancel(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.stop_event.set()
            self.cancel_button.setEnabled(False)
            self.status.setText("Stopping transfer…")

    def closeEvent(self, event) -> None:
        if self.worker and self.worker.isRunning():
            self.close_after_transfer = True
            self._cancel()
            event.ignore()
        else:
            event.accept()


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Nimbrift")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
