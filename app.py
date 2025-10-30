#!/usr/bin/env python3
"""
Lab-untuk-OCR GUI Application
==============================

BLOK III Table Extraction System with Interactive GUI

Usage:
    python app.py

Requirements:
    pip install -r requirements.txt
"""

import sys
import os
import warnings
from pathlib import Path

# Suppress all warnings and debug logs for clean terminal output
warnings.filterwarnings('ignore')
os.environ['PYTHONWARNINGS'] = 'ignore'

# Suppress PaddlePaddle/PaddleOCR logs and optimize threading
try:
    import multiprocessing as _mp
    _cpu = str(max(1, _mp.cpu_count()))
except Exception:
    _cpu = '4'

# Threading/BLAS env for better CPU performance
os.environ.setdefault('OMP_NUM_THREADS', _cpu)
os.environ.setdefault('MKL_NUM_THREADS', _cpu)
os.environ.setdefault('KMP_AFFINITY', 'granularity=fine,compact,1,0')

# Paddle threads
os.environ['FLAGS_paddle_num_threads'] = _cpu
os.environ['FLAGS_allocator_strategy'] = 'auto_growth'
os.environ['GLOG_minloglevel'] = '3'  # Suppress GLOG (Paddle uses glog)
os.environ['PPOCR_LOG_LEVEL'] = 'ERROR'  # Only show errors

# Suppress PaddleX model loading messages
os.environ['PADDLEX_VERBOSITY'] = 'ERROR'

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt
from gui.loading_screen import LoadingScreen
from gui.main_window import MainWindow


def main():
    """Main application entry point"""
    # Enable high DPI scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("OCR SiPW")
    app.setApplicationVersion("6.2")
    app.setOrganizationName("Lab OCR Team")
    
    # Show loading screen while initializing PaddleOCR models
    splash = LoadingScreen()
    splash.show()
    app.processEvents()  # Ensure splash is shown
    
    # Start loading models in background
    splash.start_loading()
    
    # Wait for loading to complete (with event processing)
    while not splash.is_finished:
        app.processEvents()
    
    # Check if loading failed
    if splash.error_msg:
        splash.close()
        QMessageBox.critical(
            None,
            "Initialization Error",
            f"Failed to load PaddleOCR models:\n\n{splash.error_msg}\n\nApplication will exit."
        )
        sys.exit(1)
    
    # Close splash and show main window
    splash.finish(None)
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Run application
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
