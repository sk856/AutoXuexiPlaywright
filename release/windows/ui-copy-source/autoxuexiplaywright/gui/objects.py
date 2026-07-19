from logging import Handler, LogRecord, getLogger
from traceback import format_exc
from PySide6.QtCore import Signal, SignalInstance, QObject, QWaitCondition, QMutex
# Relative imports
from ..events import EventID, find_event_by_id
from ..logger import init_logger
from ..defines import APPNAME
from ..processors import start_processor


class _QHandler(Handler):
    def __init__(self, signal: SignalInstance):
        super().__init__()
        self.signal = signal

    def emit(self, record: LogRecord):
        self.signal.emit(self.format(record))


class SubProcess(QObject):
    jobFinishedSignal = Signal(str)
    updateStatusSignal = Signal(str)
    pauseThreadSignal = Signal(tuple)
    qrControlSignal = Signal(bytes)
    updateScoreSignal = Signal(tuple)
    updateLogSignal = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.st = _QHandler(self.updateLogSignal)
        self.wait = QWaitCondition()
        self.mutex = QMutex()
        find_event_by_id(EventID.FINISHED).add_callback(
            self.jobFinishedSignal.emit)
        find_event_by_id(EventID.STATUS_UPDATED).add_callback(
            self.updateStatusSignal.emit)
        find_event_by_id(EventID.QR_UPDATED).add_callback(
            self.qrControlSignal.emit)
        find_event_by_id(EventID.SCORE_UPDATED).add_callback(
            self.updateScoreSignal.emit)
        find_event_by_id(EventID.ANSWER_REQUESTED).add_callback(self.pause)

    def start(self):
        """Start processing and always report worker failures to the GUI."""
        logger = getLogger(APPNAME)
        try:
            init_logger(self.st)
            self.updateStatusSignal.emit("正在启动处理器…")
            logger.info("处理线程已启动")
            start_processor()
        except Exception:
            details = format_exc()
            # A Python exception raised from a QThread slot is otherwise easy
            # to miss in a windowed build and leaves the Start button disabled.
            try:
                logger.exception("处理线程启动或执行失败")
            except Exception:
                pass
            self.updateLogSignal.emit(details.rstrip())
            self.updateStatusSignal.emit("处理失败")
            self.jobFinishedSignal.emit("处理失败，详细错误已显示在日志中")

    def pause(self, *args: ...):
        self.mutex.lock()
        self.pauseThreadSignal.emit(args)
        self.wait.wait(self.mutex)
        self.mutex.unlock()
