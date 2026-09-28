"""Exercise the real Qt window and installed translation models; save UI evidence."""
import importlib.machinery
import importlib.util
import time
import tempfile
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

root = Path(__file__).resolve().parent
loader = importlib.machinery.SourceFileLoader('translator', str(root / 'translator.pyw'))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)
app = QApplication([])
settings_dir = tempfile.TemporaryDirectory()
QApplication.setOrganizationName('QuickTranslatorTest')
QApplication.setApplicationName('QuickTranslatorTest')
from PySide6.QtCore import QSettings
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings_dir.name)
QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, 'Veitnemed', 'QuickTranslator').clear()
module.QSettings = lambda *_args: QSettings(
    QSettings.Format.IniFormat, QSettings.Scope.UserScope, 'Veitnemed', 'QuickTranslator')
app.setStyle('Fusion')
app.setStyleSheet(module.STYLE)
window = module.Window()
window.show()

def wait_for(predicate, timeout=90):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError('Timed out')
        app.processEvents()
        time.sleep(.03)

try:
    wait_for(lambda: window.prepared)
    window.input.setPlainText('TypeError: list indices must be integers, not str')
    wait_for(lambda: window.copyable)
    assert window.copyable and any('\u0400' <= c <= '\u04ff' for c in window.output.toPlainText()), repr((window.detail.text(), window.output.toPlainText()))
    print('EN-RU:', window.output.toPlainText(), window.detail.text())
    window.grab().save(str(root / 'preview.png'))
    window.mode.setCurrentIndex(2)
    window.input.setPlainText('Получить список пользователей')
    wait_for(lambda: window.copyable and bool(window.output.toPlainText()))
    assert window.copyable and any(c.isascii() and c.isalpha() for c in window.output.toPlainText())
    print('RU-EN:', window.output.toPlainText(), window.detail.text())
    persisted_result = window.output.toPlainText()
    restored = module.Window()
    assert restored.input.toPlainText() == 'Получить список пользователей'
    assert restored.output.toPlainText() == persisted_result and restored.copyable
    restored.thread.quit()
    restored.thread.wait()
    restored.tray.hide()
    print('PASS: previous input and translated text are restored on reopen')
    print('CACHED:', window.detail.text())
    window.input.setFocus()
    before = window.input.toPlainText()
    window.input.insertPlainText('\nNext line')
    assert window.input.toPlainText().count('\n') > before.count('\n')
    window.clear()
    wait_for(lambda: not window.busy)
    assert not window.output.toPlainText() and not window.copyable
    window.hide()
    window.toggle()
    assert window.isVisible()
    window.resize(400, 300)
    app.processEvents()
    window.grab().save(str(root / 'preview-small.png'))
    print('PASS: translation, clipboard, cache, shortcuts, stale-result rejection, visibility')
finally:
    window.thread.quit()
    window.thread.wait()
    window.tray.hide()
