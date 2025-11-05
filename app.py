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

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt
from gui.loading_screen import LoadingScreen
from gui.main_window import MainWindow


def main():
    # entry point aplikasi
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setApplicationName("OCR SiPW")
    app.setApplicationVersion("6.2")
    app.setOrganizationName("Lab OCR Team")
    
    splash = LoadingScreen()
    splash.show()
    app.processEvents()
    
    splash.start_loading()
    
    while not splash.is_finished:
        app.processEvents()
    
    if splash.error_msg:
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
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
