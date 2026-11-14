import importlib.util
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtWidgets import QApplication, QLineEdit
    from nimbrift.gui import MainWindow, STYLE
    from nimbrift.model import Direction


@unittest.skipUnless(importlib.util.find_spec("PySide6") is not None, "PySide6 GUI extra is not installed")
class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.app.setStyleSheet(STYLE)

    def setUp(self):
        self.window = MainWindow()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.window = None
        self.app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.app.quit()
        cls.app = None

    def test_direction_changes_local_and_remote_fields(self):
        self.assertEqual(self.window.direction, Direction.UPLOAD)
        self.assertTrue(self.window.source_file_button.isVisible())
        self.assertFalse(self.window.destination_button.isVisible())
        self.window._set_direction(Direction.DOWNLOAD)
        self.app.processEvents()
        self.assertEqual(self.window.source_label.text(), "Remote source")
        self.assertFalse(self.window.source_file_button.isVisible())
        self.assertTrue(self.window.destination_button.isVisible())

    def test_password_is_masked_and_invalid_connection_never_starts_worker(self):
        self.assertEqual(self.window.password.echoMode(), QLineEdit.EchoMode.Password)
        with patch("nimbrift.gui.QMessageBox.warning") as warning:
            self.window._start()
        warning.assert_called_once()
        self.assertIsNone(self.window.worker)
        self.assertTrue(self.window.start_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
