# loading screen untuk inisialisasi model paddleocr

from PyQt5.QtWidgets import QSplashScreen
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont


class ModelLoaderWorker(QThread):
    # worker untuk load model paddleocr di background
    
    progress = pyqtSignal(int, str)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def run(self):
        # load model paddleocr
        try:
            self.progress.emit(10, "Menginisialisasi mesin PaddleOCR...")
            from pipeline.ocr_engine import PaddleOCREngine
            
            self.progress.emit(30, "Memuat model PP-LCNet...")
            self.progress.emit(50, "Memuat model UVDoc...")
            self.progress.emit(70, "Memuat model deteksi PP-OCRv5...")
            self.progress.emit(90, "Memuat model pengenalan PP-OCRv5...")
            
            ocr = PaddleOCREngine.get_instance()
            self.progress.emit(100, "Model berhasil dimuat!")
            self.finished.emit()
            
        except Exception as e:
            self.error.emit(str(e))


class LoadingScreen(QSplashScreen):
    # splash screen dengan progress bar saat loading
    
    def __init__(self):
        pixmap = QPixmap(500, 300)
        pixmap.fill(QColor("#1E293B"))
        
        super().__init__(pixmap, Qt.WindowStaysOnTopHint)
        
        self.setup_ui()
        
        self.loader = ModelLoaderWorker()
        self.loader.progress.connect(self.update_progress)
        self.loader.finished.connect(self.on_finished)
        self.loader.error.connect(self.on_error)
        
        self.is_finished = False
        self.error_msg = None
    
    def setup_ui(self):
        # setup tampilan loading screen
        self.progress_value = 0
        self.status_message = "Menginisialisasi..."
    
    def update_progress(self, value, message):
        # update progress bar dan pesan
        self.progress_value = value
        self.status_message = message
        self.repaint()
    
    def on_finished(self):
        # dipanggil saat loading selesai
        self.is_finished = True
    
    def on_error(self, error_msg):
        # dipanggil saat loading gagal
        self.error_msg = error_msg
        self.is_finished = True
    
    def start_loading(self):
        # mulai proses loading
        self.loader.start()

