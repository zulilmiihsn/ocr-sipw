#!/usr/bin/env python3
# lab-untuk-ocr gui application
# ==============================
# bloK iii table extraction system dengan interactive gui

import sys
import os
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')
os.environ['PYTHONWARNINGS'] = 'ignore'

# setup environment untuk suppress log dan optimize performance
try:
    import multiprocessing as _mp
    _cpu = str(max(1, _mp.cpu_count()))
except Exception:
    _cpu = '4'

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
from utils.logging_config import setup_logging
setup_logging(level=logging.INFO, log_to_console=True)

logger = logging.getLogger(__name__)

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt
from gui.loading_screen import LoadingScreen
from gui.main_window import MainWindow
from config.settings import app_settings


def main():
    """Entry point aplikasi."""
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


if __name__ == '__main__':
    main()
