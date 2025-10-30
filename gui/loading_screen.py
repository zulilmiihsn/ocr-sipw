"""
Loading Screen for PaddleOCR Model Initialization
Shows splash screen with progress while loading models
"""

from PyQt5.QtWidgets import QSplashScreen, QVBoxLayout, QLabel, QProgressBar, QWidget
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont
import qtawesome as qta


class ModelLoaderWorker(QThread):
    """Background worker to load PaddleOCR models"""
    
    progress = pyqtSignal(int, str)  # (percentage, message)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def run(self):
        """Load PaddleOCR models in background"""
        try:
            self.progress.emit(10, "Initializing PaddleOCR engine...")
            
            # Import and initialize PaddleOCR (this is the slow part)
            from pipeline.ocr_engine import PaddleOCREngine
            
            self.progress.emit(30, "Loading PP-LCNet model...")
            self.progress.emit(50, "Loading UVDoc model...")
            self.progress.emit(70, "Loading PP-OCRv5 detection model...")
            self.progress.emit(90, "Loading PP-OCRv5 recognition model...")
            
            # Force initialization (singleton pattern)
            ocr = PaddleOCREngine.get_instance()
            
            self.progress.emit(100, "Models loaded successfully!")
            self.finished.emit()
            
        except Exception as e:
            self.error.emit(f"Failed to load models: {str(e)}")


class LoadingScreen(QSplashScreen):
    """Professional loading screen with progress bar"""
    
    def __init__(self):
        # Create a custom pixmap for splash screen
        pixmap = QPixmap(500, 300)
        pixmap.fill(QColor("#1E293B"))  # Dark blue background
        
        super().__init__(pixmap, Qt.WindowStaysOnTopHint)
        
        # Setup UI
        self.setup_ui()
        
        # Start loading
        self.loader = ModelLoaderWorker()
        self.loader.progress.connect(self.update_progress)
        self.loader.finished.connect(self.on_finished)
        self.loader.error.connect(self.on_error)
        
        self.is_finished = False
        self.error_msg = None
    
    def setup_ui(self):
        """Setup loading screen UI"""
        # This is a workaround since QSplashScreen doesn't support layouts directly
        self.progress_value = 0
        self.status_message = "Initializing..."
    
    def update_progress(self, value, message):
        """Update progress bar and message"""
        self.progress_value = value
        self.status_message = message
        self.repaint()
    
    def on_finished(self):
        """Called when loading is complete"""
        self.is_finished = True
    
    def on_error(self, error_msg):
        """Called when loading fails"""
        self.error_msg = error_msg
        self.is_finished = True
    
    def start_loading(self):
        """Start the loading process"""
        self.loader.start()
    
    def drawContents(self, painter):
        """Custom paint for splash screen"""
        painter.save()
        
        # Title
        painter.setPen(QColor("#FFFFFF"))
        title_font = QFont("Segoe UI", 24, QFont.Bold)
        painter.setFont(title_font)
        painter.drawText(20, 60, "OCR SiPW")
        
        # Subtitle
        painter.setPen(QColor("#94A3B8"))
        subtitle_font = QFont("Segoe UI", 10)
        painter.setFont(subtitle_font)
        painter.drawText(20, 85, "Ekstraksi Tabel BLOK III")
        
        # Status message
        painter.setPen(QColor("#E2E8F0"))
        status_font = QFont("Segoe UI", 11)
        painter.setFont(status_font)
        painter.drawText(20, 150, self.status_message)
        
        # Progress bar background
        bar_x = 20
        bar_y = 180
        bar_width = 460
        bar_height = 30
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#334155"))
        painter.drawRoundedRect(bar_x, bar_y, bar_width, bar_height, 4, 4)
        
        # Progress bar fill
        if self.progress_value > 0:
            fill_width = int(bar_width * (self.progress_value / 100))
            painter.setBrush(QColor("#3B82F6"))  # Blue
            painter.drawRoundedRect(bar_x, bar_y, fill_width, bar_height, 4, 4)
        
        # Progress percentage
        painter.setPen(QColor("#FFFFFF"))
        percent_font = QFont("Segoe UI", 9)
        painter.setFont(percent_font)
        percent_text = f"{self.progress_value}%"
        painter.drawText(bar_x + bar_width//2 - 15, bar_y + bar_height//2 + 5, percent_text)
        
        # Info text
        painter.setPen(QColor("#94A3B8"))
        info_font = QFont("Segoe UI", 8)
        painter.setFont(info_font)
        painter.drawText(20, 240, "Memuat model PaddleOCR untuk pertama kali...")
        painter.drawText(20, 260, "Proses ini hanya dilakukan sekali saat aplikasi dibuka.")
        
        painter.restore()

