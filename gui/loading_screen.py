# loading screen untuk inisialisasi model paddleocr

from PyQt5.QtWidgets import QSplashScreen
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRect
from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont

from utils.logging_config import get_logger
from utils.exceptions import OCRProcessingError

logger = get_logger(__name__)


class ModelLoaderWorker(QThread):
    # worker untuk load model paddleocr di background
    
    progress = pyqtSignal(int, str)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def run(self):
        """Load PaddleOCR model in background."""
        try:
            logger.info("Loading PaddleOCR model...")
            self.progress.emit(10, "Menginisialisasi mesin PaddleOCR...")
            from pipeline.ocr_engine import PaddleOCREngine
            
            self.progress.emit(30, "Memuat model PP-LCNet...")
            self.progress.emit(50, "Memuat model UVDoc...")
            self.progress.emit(70, "Memuat model deteksi PP-OCRv5...")
            self.progress.emit(90, "Memuat model pengenalan PP-OCRv5...")
            
            ocr = PaddleOCREngine.get_instance()
            logger.info("PaddleOCR model loaded successfully")
            self.progress.emit(100, "Model berhasil dimuat!")
            self.finished.emit()
            
        except Exception as e:
            error_msg = f"Failed to load PaddleOCR model: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.error.emit(error_msg)


class LoadingScreen(QSplashScreen):
    # splash screen modern dengan progress bar dan animasi
    
    def __init__(self):
        # buat pixmap lebih besar dan modern
        pixmap = QPixmap(600, 400)
        pixmap.fill(QColor("#FFFFFF"))  # background putih untuk modern look
        
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
    
    def paintEvent(self, event):
        # custom paint untuk loading screen yang lebih menarik dan jelas
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # background putih bersih
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        
        # header area dengan gradient biru (lebih tinggi untuk title)
        header_height = 140
        header_rect = QRect(0, 0, self.width(), header_height)
        painter.fillRect(header_rect, QColor("#2563EB"))
        
        # icon/logo area di tengah header
        center_x = self.width() // 2
        icon_y = 50
        
        # icon circle putih di header biru
        painter.setBrush(QColor("#FFFFFF"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center_x - 35, icon_y - 35, 70, 70)
        
        # icon text/emoji di dalam circle
        painter.setPen(QColor("#2563EB"))
        icon_font = QFont("Segoe UI", 28, QFont.Bold)
        painter.setFont(icon_font)
        painter.drawText(center_x - 20, icon_y + 10, "📄")
        
        # title di dalam header biru (putih di biru = jelas terlihat)
        title_font = QFont("Segoe UI", 15, QFont.Bold)
        painter.setFont(title_font)
        painter.setPen(QColor("#FFFFFF"))
        title_rect = QRect(0, 90, self.width(), 35)
        painter.drawText(title_rect, Qt.AlignCenter, "OCR Sistem Informasi Pencatat Wilayah")
        
        # subtitle di bawah header (di area putih, pakai warna gelap)
        subtitle_font = QFont("Segoe UI", 10, QFont.Normal)
        painter.setFont(subtitle_font)
        painter.setPen(QColor("#475569"))  # warna lebih gelap untuk kontras
        subtitle_rect = QRect(0, header_height + 10, self.width(), 25)
        painter.drawText(subtitle_rect, Qt.AlignCenter, "Memuat model PaddleOCR...")
        
        # progress bar background (lebih ke bawah)
        progress_y = header_height + 50
        progress_bg_rect = QRect(50, progress_y, self.width() - 100, 24)
        painter.setBrush(QColor("#F1F5F9"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(progress_bg_rect, 12, 12)
        
        # progress bar fill dengan gradient biru
        if self.progress_value > 0:
            progress_width = int((self.width() - 100) * self.progress_value / 100)
            progress_rect = QRect(50, progress_y, progress_width, 24)
            
            # gradient biru
            painter.setBrush(QColor("#2563EB"))
            painter.drawRoundedRect(progress_rect, 12, 12)
            
            # progress text (putih di biru untuk kontras)
            painter.setPen(QColor("#FFFFFF"))
            progress_font = QFont("Segoe UI", 9, QFont.Bold)
            painter.setFont(progress_font)
            painter.drawText(progress_bg_rect, Qt.AlignCenter, f"{self.progress_value}%")
        
        # status message (di bawah progress bar, warna gelap)
        status_y = progress_y + 40
        status_font = QFont("Segoe UI", 9, QFont.Normal)
        painter.setFont(status_font)
        painter.setPen(QColor("#1E293B"))  # warna lebih gelap untuk kontras lebih baik
        status_rect = QRect(0, status_y, self.width(), 30)
        painter.drawText(status_rect, Qt.AlignCenter, self.status_message)
        
        # footer info (di paling bawah, warna abu-abu)
        footer_font = QFont("Segoe UI", 8, QFont.Normal)
        painter.setFont(footer_font)
        painter.setPen(QColor("#64748B"))  # warna abu-abu untuk info tambahan
        footer_rect = QRect(0, self.height() - 35, self.width(), 20)
        painter.drawText(footer_rect, Qt.AlignCenter, "Mohon tunggu, proses ini hanya terjadi sekali saat pertama kali menjalankan aplikasi")
    
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

