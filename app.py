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

# Suppress PaddlePaddle/PaddleOCR logs
os.environ['FLAGS_paddle_num_threads'] = '1'
os.environ['FLAGS_allocator_strategy'] = 'auto_growth'
os.environ['GLOG_minloglevel'] = '3'  # Suppress GLOG (Paddle uses glog)
os.environ['PPOCR_LOG_LEVEL'] = 'ERROR'  # Only show errors

# Suppress PaddleX model loading messages
os.environ['PADDLEX_VERBOSITY'] = 'ERROR'

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from gui.main_window import MainWindow


def main():
    """Main application entry point"""
    # Enable high DPI scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("Lab-untuk-OCR")
    app.setApplicationVersion("3.1.0")
    app.setOrganizationName("Lab OCR Team")
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Run application
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
