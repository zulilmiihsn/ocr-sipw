#!/usr/bin/env python3
# ocr-sipw gui application
# ==============================
# bloK iii table extraction system dengan interactive gui

import sys
import os
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')
os.environ['PYTHONWARNINGS'] = 'ignore'

# setup environment untuk suppress log dan optimize performance
# optimasi thread untuk performa lebih baik (menggunakan semua core CPU)
try:
    import multiprocessing as _mp
    _cpu_count = _mp.cpu_count()
    # gunakan minimal 8 thread untuk performa optimal, atau semua core jika lebih dari 8
    _cpu = str(max(8, _cpu_count))  # minimal 8 thread untuk performa lebih baik
except Exception:
    _cpu = '8'  # default 8 thread jika error

os.environ.setdefault('OMP_NUM_THREADS', _cpu)
os.environ.setdefault('MKL_NUM_THREADS', _cpu)
os.environ.setdefault('KMP_AFFINITY', 'granularity=fine,compact,1,0')
os.environ['FLAGS_paddle_num_threads'] = _cpu
os.environ['FLAGS_allocator_strategy'] = 'auto_growth'
os.environ['GLOG_minloglevel'] = '3'
os.environ['PPOCR_LOG_LEVEL'] = 'ERROR'
os.environ['PADDLEX_VERBOSITY'] = 'ERROR'

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup logging before importing other modules
import logging
try:
    from utils.logging_config import setup_logging
    setup_logging(level=logging.INFO, log_to_console=True)
except Exception as e:
    print(f"WARNING: Failed to setup logging: {e}")
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

# Import PyQt5 first
try:
    from PyQt5.QtWidgets import QApplication, QMessageBox
    from PyQt5.QtCore import Qt
except ImportError as e:
    print(f"ERROR: Failed to import PyQt5: {e}")
    print("Please install PyQt5: pip install PyQt5")
    sys.exit(1)

# Import application modules
try:
    from gui.loading_screen import LoadingScreen
    from gui.main_window import MainWindow
    from config.settings import app_settings
except ImportError as e:
    print(f"ERROR: Failed to import application modules: {e}")
    print("Please ensure all dependencies are installed: pip install -r requirements.txt")
    import traceback
    traceback.print_exc()
    sys.exit(1)
except Exception as e:
    print(f"ERROR: Unexpected error during import: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


def main():
    """Entry point aplikasi."""
    try:
        logger.info("Starting OCR SiPW application")
        
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        
        app = QApplication(sys.argv)
        app.setApplicationName(app_settings.app_name)
        app.setApplicationVersion(app_settings.app_version)
        app.setOrganizationName(app_settings.organization_name)
        
        logger.info(f"Application: {app_settings.app_name} v{app_settings.app_version}")
        
        splash = LoadingScreen()
        splash.show()
        app.processEvents()
        
        splash.start_loading()
        
        while not splash.is_finished:
            app.processEvents()
        
        if splash.error_msg:
            logger.error(f"Initialization failed: {splash.error_msg}")
            splash.close()
            QMessageBox.critical(
                None,
                "Kesalahan Inisialisasi",
                f"Gagal memuat model PaddleOCR:\n\n{splash.error_msg}\n\nAplikasi akan keluar."
            )
            sys.exit(1)
        
        splash.finish(None)
        window = MainWindow()
        window.show()
        
        logger.info("Application started successfully")
        
        sys.exit(app.exec_())
        
    except Exception as e:
        error_msg = f"Failed to start application: {str(e)}"
        logger.error(error_msg, exc_info=True)
        print(f"ERROR: {error_msg}")
        import traceback
        traceback.print_exc()
        
        # Try to show error dialog if possible
        try:
            app = QApplication.instance()
            if app is None:
                app = QApplication(sys.argv)
            QMessageBox.critical(
                None,
                "Kesalahan Aplikasi",
                f"Gagal memulai aplikasi:\n\n{error_msg}\n\nSilakan periksa log untuk detail lebih lanjut."
            )
        except:
            pass
        sys.exit(1)


if __name__ == '__main__':
    main()
