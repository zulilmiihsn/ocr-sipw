"""
Main entry point untuk OCR Form Scanner Application
"""

import sys
import tkinter as tk
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import customtkinter as ctk
    from src.gui.main_window import MainWindow
    
    # Set appearance mode and default color theme
    ctk.set_appearance_mode("System")  # "System" (default), "Dark", "Light"
    ctk.set_default_color_theme("blue")  # "blue" (default), "green", "dark-blue"
    
    def main():
        """Main function"""
        app = MainWindow()
        app.mainloop()
        
    if __name__ == "__main__":
        main()
        
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Please make sure all dependencies are installed: pip install -r requirements.txt")
    sys.exit(1)

