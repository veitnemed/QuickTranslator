"""Quick Translator. Local-only translation, native Qt UI, single instance."""
import os
import sys
import time
import logging
from pathlib import Path
from collections import OrderedDict

from PySide6.QtCore import QObject, Signal, Slot, QThread, QTimer, Qt
from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont, QKeySequence, QShortcut, QIcon, QPixmap, QPainter, QColor
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QPlainTextEdit, QComboBox, QFrame,
    QSystemTrayIcon, QMenu)

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'QuickTranslator'
DATA_DIR.mkdir(parents=True, exist_ok=True)
if getattr(sys, 'frozen', False):
    os.environ.setdefault('ARGOS_PACKAGES_DIR', str(DATA_DIR / 'models'))
logging.basicConfig(filename=DATA_DIR / 'translator.log', level=logging.WARNING,
                    format='%(asctime)s %(levelname)s %(message)s')
for handler in logging.getLogger().handlers:
    handler.setLevel(logging.WARNING)
SERVER = 'QuickTranslator.Local.v3'


def direction(text):
    letters = [c for c in text if c.isalpha()]
    russian = sum('\u0400' <= c <= '\u04ff' for c in letters)
    return ('ru', 'en') if russian / max(1, len(letters)) >= .25 else ('en', 'ru')


class Engine(QObject):
    ready = Signal(bool, str)
    result = Signal(int, str, float, bool)
    status = Signal(str)

    def __init__(self):
        super().__init__()
        self.models = {}
        self.cache = OrderedDict()

    @Slot()
    def prepare(self):
        try:
            # Import and model loading never block the UI or a second launch.
            import argostranslate.translate as translate
            languages = {x.code: x for x in translate.get_installed_languages()}
            required = {('en', 'ru'), ('ru', 'en')}
            missing = {
                (source, target) for source, target in required
                if source not in languages or target not in languages
                or languages[source].get_translation(languages[target]) is None
            }
            if missing:
                self.status.emit('Первичная загрузка моделей…')
                import argostranslate.package as packages
                packages.update_package_index()
                available = {(item.from_code, item.to_code): item for item in packages.get_available_packages()}
                for pair in sorted(missing):
                    item = available.get(pair)
                    if item is None:
                        raise RuntimeError(f'Model {pair[0]}->{pair[1]} is not available')
                    item.install()
                    self.status.emit('Модель загружена…')
                languages = {x.code: x for x in translate.get_installed_languages()}
            for source, target in [('en', 'ru'), ('ru', 'en')]:
                model = languages[source].get_translation(languages[target])
                if model is None:
                    raise RuntimeError('Missing language model')
                model.translate('Hello' if source == 'en' else 'Привет')
                self.models[source, target] = model
            self.ready.emit(True, 'Офлайн · готов')
        except Exception:
            logging.exception('Model initialization failed')
            self.ready.emit(False, 'Модели недоступны · см. translator.log')

    @Slot(int, str, str, str)
    def translate(self, request, text, source, target):
        started = time.perf_counter()
        try:
            key = (text, source, target)
            if key not in self.cache:
                self.cache[key] = self.models[source, target].translate(text)
                if len(self.cache) > 100:
                    self.cache.popitem(last=False)
            self.result.emit(request, self.cache[key], time.perf_counter() - started, True)
        except Exception:
            logging.exception('Translation failed')
            self.result.emit(request, 'Не удалось перевести. Подробности в translator.log.', 0, False)


STYLE = '''
QMainWindow, QWidget#root { background: #f5f6f8; color: #20242c; }
QWidget { font-family: 'Segoe UI'; font-size: 12px; color: #20242c; }
QLabel#status { color: #337950; font-size: 11px; }
QLabel#eyebrow { color: #737c89; font-size: 10px; font-weight: 600; letter-spacing: .5px; }
QLabel#muted { color: #737c89; }
QFrame#card { background: #ffffff; border: 1px solid #dfe3e9; border-radius: 9px; }
QPlainTextEdit { background: transparent; border: none; color: #20242c; font-size: 13px; selection-background-color: #cfe0ff; padding: 0px; }
QPlainTextEdit#output { color: #293b59; }
QPushButton { background: #f0f2f5; border: 1px solid #dfe3e9; border-radius: 6px; padding: 5px 8px; font-weight: 500; }
QPushButton:hover { background: #e5e9ef; border-color: #c4ccd7; }
QPushButton:pressed { background: #dce2eb; }
QPushButton:disabled { color: #a4abb5; border-color: #e5e8ed; background: #f2f3f5; }
QPushButton#primary { background: #315f9e; border: none; color: #ffffff; font-weight: 600; padding: 6px 12px; }
QPushButton#primary:hover { background: #244e89; }
QPushButton#primary:disabled { background: #aabbd2; color: #f6f8fb; }
QPushButton#quiet { background: transparent; border: none; color: #647184; }
QPushButton#quiet:hover { background: #edf1f6; color: #20242c; }
QComboBox { background: #ffffff; border: 1px solid #dfe3e9; border-radius: 6px; padding: 5px 8px; min-width: 125px; }
QComboBox QAbstractItemView { background: #ffffff; selection-background-color: #dce8fa; }
QScrollBar:vertical { background: transparent; width: 8px; }
QScrollBar::handle:vertical { background: #ccd2dc; border-radius: 4px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QMenu { background: #ffffff; border: 1px solid #dfe3e9; padding: 6px; }
QMenu::item { padding: 8px 22px; }
QMenu::item:selected { background: #dce8fa; }
'''


def app_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor('#8aafff'))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(2, 2, 60, 60, 16, 16)
    painter.setPen(QColor('#111b2d'))
    painter.setFont(QFont('Segoe UI', 26, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, 'Aa')
    painter.end()
    return QIcon(pixmap)


class InputEdit(QPlainTextEdit):
    submit = Signal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.submit.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


class Window(QMainWindow):
    requested = Signal(int, str, str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Quick Translator')
        self.resize(440, 340)
        self.setMinimumSize(400, 300)
        self.setWindowIcon(app_icon())
        self.generation = 0
        self.busy = False
        self.prepared = False
        self.copyable = False
        self.settings = QSettings('Veitnemed', 'QuickTranslator')
        self.restoring = True
        root = QWidget(objectName='root')
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        self.status = QLabel('Загрузка…', objectName='status')
        controls = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItems(['Автоопределение', 'English → Русский', 'Русский → English'])
        controls.addWidget(self.mode)
        swap = QPushButton('⇄', toolTip='Изменить направление перевода')
        swap.clicked.connect(self.swap)
        controls.addWidget(swap)
        controls.addStretch()
        controls.addWidget(self.status)
        layout.addLayout(controls)
        self.input = self.card(layout, 'ТЕКСТ', False)
        self.input.setPlaceholderText('Введите или вставьте текст…')
        self.input.setToolTip('Enter — перевод · Shift+Enter — новая строка')
        actions = QHBoxLayout()
        self.clear_button = QPushButton('Очистить', objectName='quiet')
        self.clear_button.clicked.connect(self.clear)
        actions.addWidget(self.clear_button)
        actions.addStretch()
        self.detail = QLabel('Автоперевод', objectName='muted')
        actions.addWidget(self.detail)
        layout.addLayout(actions)
        self.output = self.card(layout, 'ПЕРЕВОД', True)
        self.output.setPlaceholderText('Здесь появится перевод')
        saved_source = self.settings.value('source_text', '', type=str)
        saved_translation = self.settings.value('translated_text', '', type=str)
        translated_source = self.settings.value('translated_source', '', type=str)
        self.input.setPlainText(saved_source)
        if saved_source.strip() and saved_source.strip() == translated_source:
            self.output.setPlainText(saved_translation)
            self.copyable = bool(saved_translation)
            self.copy_button.setEnabled(self.copyable)
        self.mode.setCurrentIndex(self.settings.value('mode', 0, type=int))
        self.restoring = False
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(250)
        self.autosave_timer.timeout.connect(self.save_state)
        self.translate_timer = QTimer(self)
        self.translate_timer.setSingleShot(True)
        self.translate_timer.setInterval(450)
        self.translate_timer.timeout.connect(self.translate)
        self.input.textChanged.connect(self.invalidate)
        self.mode.currentIndexChanged.connect(self.invalidate)
        self.input.textChanged.connect(self.schedule_automatic_translation)
        self.mode.currentIndexChanged.connect(self.schedule_automatic_translation)
        self.input.submit.connect(self.translate)
        for key, callback in [('Escape', self.hide), ('Ctrl+Q', self.shutdown)]:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
        self.thread = QThread(self)
        self.engine = Engine()
        self.engine.moveToThread(self.thread)
        self.thread.started.connect(self.engine.prepare)
        self.thread.finished.connect(self.engine.deleteLater)
        self.engine.ready.connect(self.on_ready)
        self.engine.status.connect(lambda message: self.status.setText(f'● {message}'))
        self.engine.result.connect(self.on_result)
        self.requested.connect(self.engine.translate)
        self.thread.start()
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        menu = QMenu()
        menu.addAction('Открыть / скрыть', self.toggle)
        menu.addAction('Выход', self.shutdown)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip('Quick Translator · офлайн')
        self.tray.activated.connect(lambda reason: self.toggle() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()

    def card(self, layout, title, readonly):
        card = QFrame(objectName='card')
        box = QVBoxLayout(card)
        box.setContentsMargins(10, 4, 10, 8)
        box.setSpacing(2)
        heading = QHBoxLayout()
        heading.addWidget(QLabel(title, objectName='eyebrow'))
        heading.addStretch()
        button = QPushButton('Копировать' if readonly else 'Вставить', objectName='quiet')
        if readonly:
            self.copy_button = button
            button.setMinimumWidth(100)
            button.setEnabled(False)
            button.clicked.connect(self.copy)
        else:
            button.clicked.connect(self.paste)
        heading.addWidget(button)
        box.addLayout(heading)
        editor = QPlainTextEdit(objectName='output') if readonly else InputEdit(objectName='input')
        editor.setReadOnly(readonly)
        box.addWidget(editor, 1)
        layout.addWidget(card, 1)
        return editor

    def paste(self):
        self.input.insertPlainText(QApplication.clipboard().text())
        self.input.setFocus()

    def copy(self):
        if self.copyable:
            QApplication.clipboard().setText(self.output.toPlainText())
            self.copy_button.setText('Скопировано')
            QTimer.singleShot(1400, lambda: self.copy_button.setText('Копировать'))

    def invalidate(self):
        self.generation += 1
        self.copyable = False
        self.copy_button.setEnabled(False)
        if hasattr(self, 'autosave_timer') and not self.restoring:
            self.autosave_timer.start()

    def clear(self):
        self.input.clear()
        self.output.clear()
        self.input.setFocus()

    def swap(self):
        source, target = self.languages()
        previous = self.output.toPlainText() if self.copyable else ''
        self.mode.setCurrentIndex(2 if source == 'en' else 1)
        if previous:
            self.input.setPlainText(previous)

    def languages(self):
        return {1: ('en', 'ru'), 2: ('ru', 'en')}.get(self.mode.currentIndex(), direction(self.input.toPlainText()))

    def on_ready(self, success, message):
        self.prepared = success
        self.status.setText('● Офлайн' if success else '● Ошибка')
        self.status.setToolTip(message)
        if not success:
            self.detail.setText('Модель недоступна')
            self.detail.setToolTip(message)
        if success and self.input.toPlainText().strip() and not self.copyable:
            self.translate_timer.start(0)

    def schedule_automatic_translation(self, *_args):
        if self.restoring:
            return
        self.autosave_timer.start()
        if self.prepared and self.input.toPlainText().strip():
            self.translate_timer.start()
        else:
            self.translate_timer.stop()

    def save_state(self):
        self.settings.setValue('source_text', self.input.toPlainText())
        self.settings.setValue('mode', self.mode.currentIndex())
        self.settings.sync()

    def translate(self):
        text = self.input.toPlainText().strip()
        if not text or self.busy or not self.prepared:
            return
        if len(text) > 20000:
            self.detail.setText('Лимит: 20 000 знаков')
            return
        self.invalidate()
        self.busy = True
        self.detail.setText('Перевод на компьютере…')
        self.requested.emit(self.generation, text, *self.languages())

    def on_result(self, generation, text, seconds, success):
        self.busy = False
        if generation != self.generation:
            self.detail.setText('Текст изменён')
            self.translate_timer.start(0)
            return
        self.output.setPlainText(text)
        self.copyable = success
        self.copy_button.setEnabled(success)
        self.detail.setText(f'Офлайн · {seconds:.2f} с' if success else 'Ошибка перевода')
        if success:
            self.settings.setValue('translated_text', text)
            self.settings.setValue('translated_source', self.input.toPlainText().strip())
            self.settings.sync()
        self.save_state()

    def toggle(self):
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.showNormal()
            self.raise_()
            self.activateWindow()
            self.input.setFocus()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def shutdown(self):
        # Never destroy a running inference thread. Finish its current job.
        self.hide()
        self.save_state()
        self.tray.hide()
        self.thread.finished.connect(QApplication.instance().quit)
        self.thread.quit()


def main():
    if '--self-test' in sys.argv:
        import argostranslate.translate as translate
        languages = {x.code: x for x in translate.get_installed_languages()}
        for source, target, sample in [('en', 'ru', 'The list index must be an integer.'),
                                      ('ru', 'en', 'Получить список пользователей')]:
            result = languages[source].get_translation(languages[target]).translate(sample)
            if not result:
                raise SystemExit(f'Model {source}->{target} returned an empty translation')
            print(f'{source}->{target}: {result}')
        return
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    socket = QLocalSocket()
    socket.connectToServer(SERVER)
    if socket.waitForConnected(300):
        socket.write(b'toggle')
        socket.waitForBytesWritten(500)
        return
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    if not server.listen(SERVER):
        return
    window = Window()
    def receive():
        connection = server.nextPendingConnection()
        if connection:
            window.toggle()
            connection.disconnectFromServer()
            connection.deleteLater()
    server.newConnection.connect(receive)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
