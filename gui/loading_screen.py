# loading screen untuk inisialisasi model ocr
# Modern Native Desktop Professional Design

from PyQt5.QtWidgets import QSplashScreen
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRect, QTimer
from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont, QFontMetrics, QLinearGradient, QPen

from utils.logging_config import get_logger
from utils.exceptions import OCRProcessingError

logger = get_logger(__name__)


class ModelLoaderWorker(QThread):
    # worker untuk load model ocr di background
    
    progress = pyqtSignal(int, str)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def run(self):
        """Load OCR model in background."""
        try:
            logger.info("Loading OCR engine...")
            self.progress.emit(10, "Menyiapkan sistem...")
            from pipeline.ocr_engine import PaddleOCREngine
            
            self.progress.emit(25, "Menginisialisasi mesin pengenalan...")
            self.progress.emit(40, "Memuat komponen deteksi...")
            self.progress.emit(55, "Memuat komponen pengenalan karakter...")
            self.progress.emit(70, "Mengoptimalkan performa...")
            self.progress.emit(85, "Memfinalisasi konfigurasi...")
            
            ocr = PaddleOCREngine.get_instance()
            logger.info("OCR engine loaded successfully")
            self.progress.emit(100, "Siap digunakan")
            self.finished.emit()
            
        except Exception as e:
            error_msg = f"Failed to load OCR engine: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.error.emit(error_msg)


class LoadingScreen(QSplashScreen):
    # Modern Native Desktop Professional Loading Screen
    
    def __init__(self):
        # Modern size - professional and elegant
        pixmap = QPixmap(680, 380)
        pixmap.fill(QColor("#FFFFFF"))
        
        super().__init__(pixmap, Qt.WindowStaysOnTopHint)
        
        self.setup_ui()
        
        self.loader = ModelLoaderWorker()
        self.loader.progress.connect(self.update_progress)
        self.loader.finished.connect(self.on_finished)
        self.loader.error.connect(self.on_error)
        
        self.is_finished = False
        self.error_msg = None
        
        # Animation timer untuk subtle pulse effect
        self.animation_offset = 0
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.start(50)  # 20fps animation
    
    def setup_ui(self):
        # setup tampilan loading screen
        self.progress_value = 0
        self.status_message = "Menyiapkan sistem..."
    
    def update_animation(self):
        # Subtle animation untuk modern feel
        self.animation_offset = (self.animation_offset + 1) % 100
        if self.progress_value < 100:
            self.repaint()
    
    def paintEvent(self, event):
        # Modern Native Desktop Professional paint event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Background - clean subtle gray
        painter.fillRect(self.rect(), QColor("#FAFBFC"))
        
        # Main container dengan subtle shadow effect
        container_margin = 20
        container_rect = QRect(
            container_margin, 
            container_margin, 
            self.width() - container_margin * 2, 
            self.height() - container_margin * 2
        )
        
        # Container background dengan subtle border
        painter.setBrush(QColor("#FFFFFF"))
        pen = QPen(QColor("#E2E8F0"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRoundedRect(container_rect, 12, 12)
        
        # Header section - modern minimal
        header_height = 100
        header_rect = QRect(
            container_rect.x() + 1,
            container_rect.y() + 1,
            container_rect.width() - 2,
            header_height
        )
        
        # Subtle gradient header
        header_gradient = QLinearGradient(
            header_rect.x(), header_rect.y(),
            header_rect.x(), header_rect.y() + header_height
        )
        header_gradient.setColorAt(0, QColor("#F8FAFC"))
        header_gradient.setColorAt(1, QColor("#FFFFFF"))
        painter.setBrush(header_gradient)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(
            header_rect.x(), header_rect.y(),
            header_rect.width(), header_rect.height(),
            12, 12
        )
        
        # Title area - modern typography
        center_x = container_rect.center().x()
        title_y = container_rect.y() + 35
        
        # App icon/logo - modern minimal
        icon_size = 48
        icon_radius = icon_size // 2
        icon_x = center_x - icon_radius
        icon_y = title_y - icon_radius
        
        # Icon background dengan subtle gradient
        icon_gradient = QLinearGradient(icon_x, icon_y, icon_x + icon_size, icon_y + icon_size)
        icon_gradient.setColorAt(0, QColor("#2563EB"))
        icon_gradient.setColorAt(1, QColor("#1D4ED8"))
        painter.setBrush(icon_gradient)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(icon_x, icon_y, icon_size, icon_size, 10, 10)
        
        # Icon content - modern table icon
        icon_font = QFont("Segoe UI Symbol", 24, QFont.Normal)
        painter.setFont(icon_font)
        painter.setPen(QColor("#FFFFFF"))
        icon_text = "📊"
        icon_metrics = QFontMetrics(icon_font)
        icon_text_rect = icon_metrics.boundingRect(icon_text)
        painter.drawText(
            center_x - icon_text_rect.width() // 2,
            icon_y + icon_size // 2 + icon_text_rect.height() // 4,
            icon_text
        )
        
        # Title - modern typography
        title_y_pos = title_y + icon_radius + 20
        title_font = QFont("Segoe UI", 16, QFont.Bold)
        painter.setFont(title_font)
        painter.setPen(QColor("#0F172A"))
        title_text = "OCR SiPW"
        title_metrics = QFontMetrics(title_font)
        title_rect = QRect(0, title_y_pos, self.width(), 28)
        painter.drawText(title_rect, Qt.AlignCenter | Qt.AlignVCenter, title_text)
        
        # Subtitle - subtle
        subtitle_y = title_y_pos + 28
        subtitle_font = QFont("Segoe UI", 9, QFont.Normal)
        painter.setFont(subtitle_font)
        painter.setPen(QColor("#64748B"))
        subtitle_text = "Sistem Informasi Pencatat Wilayah"
        subtitle_rect = QRect(0, subtitle_y, self.width(), 20)
        painter.drawText(subtitle_rect, Qt.AlignCenter | Qt.AlignVCenter, subtitle_text)
        
        # Content area
        content_y = container_rect.y() + header_height + 30
        content_width = container_rect.width() - 80
        content_x = container_rect.x() + 40
        
        # Status message - modern typography
        status_font = QFont("Segoe UI", 10, QFont.Medium)
        painter.setFont(status_font)
        painter.setPen(QColor("#1E293B"))
        status_rect = QRect(content_x, content_y, content_width, 24)
        painter.drawText(status_rect, Qt.AlignLeft | Qt.AlignVCenter, self.status_message)
        
        # Progress bar - modern design
        progress_y = content_y + 40
        progress_bar_height = 8
        progress_bar_width = content_width
        
        # Progress bar track - subtle
        progress_track_rect = QRect(content_x, progress_y, progress_bar_width, progress_bar_height)
        painter.setBrush(QColor("#F1F5F9"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(progress_track_rect, 4, 4)
        
        # Progress bar fill - modern gradient dengan animation
        if self.progress_value > 0:
            progress_width = int(progress_bar_width * self.progress_value / 100)
            if progress_width > 0:
                progress_fill_rect = QRect(content_x, progress_y, progress_width, progress_bar_height)
                
                # Modern gradient dengan subtle animation
                progress_gradient = QLinearGradient(
                    content_x, progress_y,
                    content_x + progress_width, progress_y
                )
                # Subtle pulse effect
                pulse_alpha = 200 + int(55 * (self.animation_offset / 100))
                progress_gradient.setColorAt(0, QColor("#3B82F6"))
                progress_gradient.setColorAt(0.5, QColor("#2563EB"))
                progress_gradient.setColorAt(1, QColor("#1D4ED8"))
                
                painter.setBrush(progress_gradient)
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(progress_fill_rect, 4, 4)
        
        # Progress percentage - modern typography
        progress_text_y = progress_y + progress_bar_height + 16
        progress_font = QFont("Segoe UI", 9, QFont.Medium)
        painter.setFont(progress_font)
        painter.setPen(QColor("#475569"))
        progress_text = f"{self.progress_value}%"
        progress_text_rect = QRect(content_x, progress_text_y, content_width, 20)
        painter.drawText(progress_text_rect, Qt.AlignLeft | Qt.AlignVCenter, progress_text)
        
        # Footer info - minimal and subtle
        footer_y = container_rect.bottom() - 35
        footer_font = QFont("Segoe UI", 8, QFont.Normal)
        painter.setFont(footer_font)
        painter.setPen(QColor("#94A3B8"))
        footer_text = "Inisialisasi hanya terjadi sekali saat pertama kali menjalankan aplikasi"
        footer_rect = QRect(content_x, footer_y, content_width, 18)
        painter.drawText(footer_rect, Qt.AlignLeft | Qt.AlignVCenter, footer_text)
    
    def update_progress(self, value, message):
        # update progress bar dan pesan
        self.progress_value = value
        self.status_message = message
        self.repaint()
    
    def on_finished(self):
        # dipanggil saat loading selesai
        self.animation_timer.stop()
        self.is_finished = True
    
    def on_error(self, error_msg):
        # dipanggil saat loading gagal
        self.animation_timer.stop()
        self.error_msg = error_msg
        self.is_finished = True
    
    def start_loading(self):
        # mulai proses loading
        self.loader.start()
    
    def closeEvent(self, event):
        # cleanup saat close
        if self.animation_timer.isActive():
            self.animation_timer.stop()
        super().closeEvent(event)
