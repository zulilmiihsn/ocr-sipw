#!/usr/bin/env python3
"""
Script untuk test setup dan dependencies
Jalankan script ini untuk memastikan semua dependencies terinstall dengan benar
"""

import sys

def test_imports():
    """Test semua import yang diperlukan"""
    print("Testing imports...")
    errors = []
    
    # Test PyQt5
    try:
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import Qt
        print("✓ PyQt5 imported successfully")
    except ImportError as e:
        errors.append(f"PyQt5: {e}")
        print(f"✗ PyQt5 import failed: {e}")
    
    # Test OpenCV
    try:
        import cv2
        print(f"✓ OpenCV imported successfully (version: {cv2.__version__})")
    except ImportError as e:
        errors.append(f"OpenCV: {e}")
        print(f"✗ OpenCV import failed: {e}")
    
    # Test NumPy
    try:
        import numpy as np
        print(f"✓ NumPy imported successfully (version: {np.__version__})")
    except ImportError as e:
        errors.append(f"NumPy: {e}")
        print(f"✗ NumPy import failed: {e}")
    
    # Test PaddleOCR
    try:
        from paddleocr import PaddleOCR
        print("✓ PaddleOCR imported successfully")
    except ImportError as e:
        errors.append(f"PaddleOCR: {e}")
        print(f"✗ PaddleOCR import failed: {e}")
    
    # Test QtAwesome
    try:
        import qtawesome as qta
        print("✓ QtAwesome imported successfully")
    except ImportError as e:
        errors.append(f"QtAwesome: {e}")
        print(f"✗ QtAwesome import failed: {e}")
    
    # Test openpyxl
    try:
        import openpyxl
        print(f"✓ openpyxl imported successfully (version: {openpyxl.__version__})")
    except ImportError as e:
        errors.append(f"openpyxl: {e}")
        print(f"✗ openpyxl import failed: {e}")
    
    # Test application modules
    try:
        from config.settings import app_settings
        print("✓ config.settings imported successfully")
    except ImportError as e:
        errors.append(f"config.settings: {e}")
        print(f"✗ config.settings import failed: {e}")
    
    try:
        from gui.loading_screen import LoadingScreen
        print("✓ gui.loading_screen imported successfully")
    except ImportError as e:
        errors.append(f"gui.loading_screen: {e}")
        print(f"✗ gui.loading_screen import failed: {e}")
    
    try:
        from gui.main_window import MainWindow
        print("✓ gui.main_window imported successfully")
    except ImportError as e:
        errors.append(f"gui.main_window: {e}")
        print(f"✗ gui.main_window import failed: {e}")
    
    return errors

def test_pyqt5():
    """Test PyQt5 bisa membuat window"""
    print("\nTesting PyQt5 GUI...")
    try:
        from PyQt5.QtWidgets import QApplication, QLabel
        from PyQt5.QtCore import Qt
        
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # Create a simple window
        label = QLabel("PyQt5 test - If you see this, PyQt5 is working!")
        label.setAlignment(Qt.AlignCenter)
        label.resize(400, 100)
        label.show()
        
        print("✓ PyQt5 window created successfully")
        print("  (Window should appear briefly)")
        
        # Process events briefly
        app.processEvents()
        
        return True
    except Exception as e:
        print(f"✗ PyQt5 GUI test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 60)
    print("OCR SiPW - Setup Test Script")
    print("=" * 60)
    print()
    
    # Test imports
    errors = test_imports()
    
    # Test PyQt5
    pyqt5_ok = test_pyqt5()
    
    print()
    print("=" * 60)
    if errors:
        print("✗ SETUP TEST FAILED")
        print()
        print("Errors found:")
        for error in errors:
            print(f"  - {error}")
        print()
        print("Please install missing dependencies:")
        print("  pip install -r requirements.txt")
        return 1
    elif not pyqt5_ok:
        print("✗ SETUP TEST FAILED")
        print("PyQt5 GUI test failed. Please check PyQt5 installation.")
        return 1
    else:
        print("✓ SETUP TEST PASSED")
        print("All dependencies are installed correctly!")
        print("You can now run: python app.py")
        return 0

if __name__ == '__main__':
    sys.exit(main())

