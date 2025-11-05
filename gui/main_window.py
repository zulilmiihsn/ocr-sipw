# main window aplikasi ocr

import sys
import json
from pathlib import Path

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QTableWidget, QTableWidgetItem, QLabel, QProgressBar,
    QStatusBar, QMessageBox, QHeaderView, QGroupBox,
    QStyledItemDelegate, QLineEdit, QListWidget, QListWidgetItem, QAbstractItemView,
    QStyle
)
from PyQt5.QtCore import Qt, QEvent, QRect, QSize
from PyQt5.QtGui import QColor, QFont, QPainter, QFontMetrics

import qtawesome as qta

sys.path.insert(0, str(Path(__file__).parent.parent))

from gui.workers.ocr_worker import OCRWorker
from utils.logging_config import get_logger
from config.settings import gui_settings
from config.constants import DEFAULT_MIN_COLUMN_WIDTHS

logger = get_logger(__name__)


class HeaderDelegate(QStyledItemDelegate):
    # delegate untuk header tabel dengan word wrap
    
    def paint(self, painter, option, index):
        # gambar header dengan word wrapping
        painter.save()
        
        text = index.data(Qt.DisplayRole) or ""
        
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        
        if option.state & QStyle.State_MouseOver:
            painter.fillRect(option.rect, QColor("#F1F5F9"))
        else:
            painter.fillRect(option.rect, QColor("#F8FAFC"))
        
        painter.setPen(QColor("#E2E8F0"))
        painter.drawLine(option.rect.topRight(), option.rect.bottomRight())
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        
        painter.setPen(QColor("#475569"))
        text_rect = option.rect.adjusted(8, 4, -8, -4)
        painter.drawText(
            text_rect,
            Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap,
            text
        )
        
        painter.restore()
    
    def sizeHint(self, option, index):
        # hitung ukuran untuk text yg di-wrap
        text = index.data(Qt.DisplayRole)
        if not text:
            return QSize(100, 50)
        
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        
        fm = QFontMetrics(font)
        text_rect = fm.boundingRect(
            QRect(0, 0, option.rect.width() - 16, 1000),
            Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap,
            text
        )
        
        return QSize(option.rect.width(), max(50, text_rect.height() + 8))


class CellDelegate(QStyledItemDelegate):
    # delegate untuk cell tabel, handle enter key untuk navigasi
    
    def createEditor(self, parent, option, index):
        # buat editor untuk cell
        editor = QLineEdit(parent)
        editor.setFrame(False)
        return editor
    
    def setEditorData(self, editor, index):
        # set data awal di editor
        value = index.model().data(index, Qt.EditRole)
        editor.setText(str(value) if value else "")
    
    def setModelData(self, editor, model, index):
        # simpan data dari editor ke model
        model.setData(index, editor.text(), Qt.EditRole)
    
    def updateEditorGeometry(self, editor, option, index):
        # atur ukuran editor sesuai cell
        editor.setGeometry(option.rect)
    
    def eventFilter(self, editor, event):
        # handle enter key untuk commit dan pindah ke cell berikutnya
        if event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.commitData.emit(editor)
                self.closeEditor.emit(editor, QStyledItemDelegate.NoHint)
                return True
        return super().eventFilter(editor, event)


class CustomTableWidget(QTableWidget):
    # table widget dengan navigasi keyboard dan kontrol row
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._moving_after_edit = False
        self.hovered_row = -1
        self.parent_window = None
        
        # Floating buttons (akan dibuat oleh parent window)
        self.add_row_floating_btn = None
        self.remove_row_floating_btn = None
        
        # aktifkan tracking mouse untuk header vertikal
        self.verticalHeader().setMouseTracking(True)
        self.verticalHeader().viewport().setMouseTracking(True)
        
        # Install event filter on vertical header
        self.verticalHeader().viewport().installEventFilter(self)
    
    def eventFilter(self, obj, event):
        # handle event hover header vertikal
        if obj == self.verticalHeader().viewport():
            if event.type() == event.MouseMove:
                # ambil baris dari posisi mouse
                pos = event.pos()
                row = self.verticalHeader().logicalIndexAt(pos)
                
                if row >= 0 and row < self.rowCount():
                    if self.hovered_row != row:
                        self.hovered_row = row
                        self.show_floating_buttons(row)
                else:
                    self.hide_floating_buttons()
            
            elif event.type() == event.Leave:
                # sembunyikan tombol ketika mouse keluar dari header vertikal
                self.hide_floating_buttons()
        
        return super().eventFilter(obj, event)
    
    def show_floating_buttons(self, row):
        # tampilkan tombol floating untuk baris yang di-hover
        if self.add_row_floating_btn and self.remove_row_floating_btn:
            header_rect = self.verticalHeader().sectionViewportPosition(row)
            header_height = self.verticalHeader().sectionSize(row)
            x = 2
            y = header_rect + (header_height - 24) // 2
            self.add_row_floating_btn.setParent(self.verticalHeader().viewport())
            self.remove_row_floating_btn.setParent(self.verticalHeader().viewport())
            
            self.add_row_floating_btn.setGeometry(x, y, 12, 24)
            self.remove_row_floating_btn.setGeometry(x + 12, y, 12, 24)
            
            self.add_row_floating_btn.show()
            self.remove_row_floating_btn.show()
    
    def hide_floating_buttons(self):
        # sembunyikan floating buttons
        self.hovered_row = -1
        if self.add_row_floating_btn:
            self.add_row_floating_btn.hide()
        if self.remove_row_floating_btn:
            self.remove_row_floating_btn.hide()
    
    def keyPressEvent(self, event):
        # handle keyboard untuk navigasi cell
        current_row = self.currentRow()
        current_col = self.currentColumn()
        is_editing = self.state() == QTableWidget.EditingState
        
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if is_editing:
                self.closeEditor(self.itemDelegate().createEditor(self, None, self.model().index(current_row, current_col)), QStyledItemDelegate.NoHint)
            
            total_cols = self.columnCount()
            total_rows = self.rowCount()
            
            if current_col < total_cols - 1:
                self.setCurrentCell(current_row, current_col + 1)
            elif current_row < total_rows - 1:
                self.setCurrentCell(current_row + 1, 0)
            else:
                self.setCurrentCell(0, 0)
            
            event.accept()
            return
        
        elif event.key() == Qt.Key_Up and not is_editing:
            total_rows = self.rowCount()
            new_row = current_row - 1 if current_row > 0 else total_rows - 1
            self.setCurrentCell(new_row, current_col)
            event.accept()
            return
        
        elif event.key() == Qt.Key_Down and not is_editing:
            total_rows = self.rowCount()
            new_row = current_row + 1 if current_row < total_rows - 1 else 0
            self.setCurrentCell(new_row, current_col)
            event.accept()
            return
        
        super().keyPressEvent(event)


class MainWindow(QMainWindow):
    # window utama aplikasi
    
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.ocr_results = None
        self.ocr_worker = None
        self.edited_cells = {}
        # data existing untuk append mode (menyimpan data yang sudah ada sebelum scan baru)
        self.existing_table_data = []
        
        self.init_ui()
    
    def _get_icon(self, name: str, **kwargs):
        # ambil icon dari qtawesome
        return qta.icon(name, **kwargs)
    
    def load_stylesheet(self):
        # load stylesheet jika ada
        style_path = Path(__file__).parent / 'styles.qss'
        if style_path.exists():
            with open(style_path, 'r', encoding='utf-8') as f:
                self.setStyleSheet(f.read())
    
    def init_ui(self):
        # setup tampilan ui dengan design modern dan clean
        self.setWindowTitle("OCR Sistem Informasi Pencatat Wilayah")
        self.setMinimumSize(1400, 900)  # lebih lebar untuk memanfaatkan layar
        self.setWindowIcon(self._get_icon('fa5s.table', color='#2563EB'))
        
        # muat stylesheet QSS
        self.load_stylesheet()
        
        # bikin widget utama (ga pakai menu bar biar interface lebih bersih)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout - professional spacing dengan margin lebih lebar
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(32, 28, 32, 24)  # margin lebih lebar untuk breathing room
        main_layout.setSpacing(24)  # spacing lebih besar untuk visual hierarchy
        
        # File selection area (simplified)
        file_group = self.create_file_selection_group()
        main_layout.addWidget(file_group)
        
        # Table area (full width, no image preview)
        table_group = self.create_table_group()
        main_layout.addWidget(table_group)
        
        # Progress bar - lebih modern
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMinimumHeight(40)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border-radius: 10px;
                font-size: 9.5pt;
                font-weight: 600;
            }
        """)
        main_layout.addWidget(self.progress_bar)
        
        # tombol ekspor - lebih besar dan menonjol
        export_btn = QPushButton(" Ekspor Hasil")
        export_btn.setIcon(self._get_icon('fa5s.file-export', color='white'))
        export_btn.setObjectName("exportButton")
        export_btn.clicked.connect(self.export_results)
        export_btn.setEnabled(False)
        export_btn.setMinimumHeight(52)
        export_btn.setStyleSheet("""
            QPushButton {
                font-size: 10.5pt;
                font-weight: 600;
            }
        """)
        self.export_button = export_btn
        main_layout.addWidget(export_btn)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status("Siap - Pilih file untuk memulai")
    
    
    def create_file_selection_group(self):
        # buat grup UI pilihan file dengan design modern dan clean
        group = QGroupBox("Pilih File & Proses")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: 600;
                font-size: 11pt;
                color: #1E293B;
                border: 2px solid #E2E8F0;
                border-radius: 12px;
                margin-top: 12px;
                padding-top: 20px;
                background-color: #FFFFFF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px;
                background-color: #FFFFFF;
            }
        """)
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Top row: Browse button dengan layout yang lebih lebar
        top_row = QHBoxLayout()
        top_row.setSpacing(20)
        
        # Browse button - lebih besar dan modern
        browse_btn = QPushButton(" Pilih File Gambar")
        browse_btn.setIcon(self._get_icon('fa5s.folder-open', color='#64748B'))
        browse_btn.setObjectName("browse_btn")
        browse_btn.clicked.connect(self.browse_file)
        browse_btn.setMinimumWidth(200)
        browse_btn.setMinimumHeight(48)
        browse_btn.setStyleSheet("""
            QPushButton {
                font-size: 10pt;
                font-weight: 600;
            }
        """)
        top_row.addWidget(browse_btn)
        
        # Info label - lebih jelas
        info_label = QLabel("💡 Drag & drop untuk mengubah urutan file")
        info_label.setStyleSheet("""
            font-size: 9pt; 
            color: #64748B; 
            font-style: italic;
            padding: 8px 0px;
        """)
        top_row.addWidget(info_label, 1)
        
        layout.addLayout(top_row)
        
        # Interactive file list (drag & drop enabled) - lebih modern
        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(140)  # sedikit lebih tinggi
        self.file_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_list.setStyleSheet("""
            QListWidget {
                background-color: #F8FAFC;
                border: 2px solid #E2E8F0;
                border-radius: 8px;
                padding: 8px;
                font-size: 9pt;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-radius: 6px;
                margin: 3px 0px;
                background-color: #FFFFFF;
                border: 1px solid transparent;
            }
            QListWidget::item:hover {
                background-color: #EFF6FF;
                border: 1px solid #DBEAFE;
            }
            QListWidget::item:selected {
                background-color: #DBEAFE;
                color: #1E293B;
                border: 1px solid #2563EB;
                font-weight: 500;
            }
        """)
        self.file_list.setVisible(False)  # disembunyikan sampai file dipilih
        layout.addWidget(self.file_list)
        
        # Bottom row: Action buttons dengan spacing yang lebih baik
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)
        
        # tombol mulai ocr - lebih besar dan menonjol
        self.start_btn = QPushButton(" Mulai OCR")
        self.start_btn.setIcon(self._get_icon('fa5s.play', color='white'))
        self.start_btn.setObjectName("start_btn")
        self.start_btn.clicked.connect(self.start_ocr)
        self.start_btn.setEnabled(False)  # dinonaktifkan sampai file dipilih
        self.start_btn.setMinimumWidth(160)
        self.start_btn.setMinimumHeight(48)
        self.start_btn.setStyleSheet("""
            QPushButton {
                font-size: 10pt;
                font-weight: 600;
            }
        """)
        bottom_row.addWidget(self.start_btn)
        
        # sort button
        self.sort_btn = QPushButton(" Urutkan")
        self.sort_btn.setIcon(self._get_icon('fa5s.sort-amount-down', color='#2563EB'))
        self.sort_btn.setObjectName("sort_btn")
        self.sort_btn.clicked.connect(self.sort_table)
        self.sort_btn.setEnabled(False)  # dinonaktifkan sampai OCR selesai
        self.sort_btn.setMinimumWidth(140)
        self.sort_btn.setMinimumHeight(48)
        self.sort_btn.setToolTip("Urutkan tabel berdasarkan Kode SLS (↑) dan Sub-SLS (↓)")
        bottom_row.addWidget(self.sort_btn)
        
        # reset button
        self.reset_btn = QPushButton(" Reset")
        self.reset_btn.setIcon(self._get_icon('fa5s.redo', color='#64748B'))
        self.reset_btn.setObjectName("reset_btn")
        self.reset_btn.clicked.connect(self.reset_all)
        self.reset_btn.setEnabled(False)  # dinonaktifkan awalnya
        self.reset_btn.setMinimumWidth(140)
        self.reset_btn.setMinimumHeight(48)
        bottom_row.addWidget(self.reset_btn)
        
        bottom_row.addStretch()  # push buttons ke kiri
        
        layout.addLayout(bottom_row)
        
        group.setLayout(layout)
        return group
    
    def create_table_group(self):
        # buat grup UI tabel dengan design modern
        group = QGroupBox("Hasil Ekstraksi Tabel")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: 600;
                font-size: 11pt;
                color: #1E293B;
                border: 2px solid #E2E8F0;
                border-radius: 12px;
                margin-top: 12px;
                padding-top: 20px;
                background-color: #FFFFFF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px;
                background-color: #FFFFFF;
            }
        """)
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(12)
        
        # bikin widget tabel kustom dengan navigasi tombol panah dan kontrol mengambang
        self.table = CustomTableWidget()
        self.table.parent_window = self
        self.table.setColumnCount(16)
        self.table.setRowCount(10)
        
        # set delegate kustom buat editing cell yang lebih baik
        self.table.setItemDelegate(CellDelegate())
        
        # set header (nama kolom) - dengan line break manual biar lebih pas
        headers = [
            "Kode\nSLS/Non-SLS",
            "Kode\nSub-SLS",
            "Nama\nSLS/Non-SLS",
            "Perkiraan\nJumlah Muatan\nKK (Keluarga)",
            "Bangunan\nTempat Tinggal\n(BTT)",
            "Bangunan\nTempat Tinggal\nKosong\n(BTT Kosong)",
            "Bangunan\nKhusus Usaha\n(BKU)",
            "Bangunan\nBukan Tempat\nTinggal\nnon Usaha",
            "Perkiraan\nJumlah Muatan\nUsaha",
            "Total\nMuatan",
            "Nama Wilayah\nKonsentrasi\nEkonomi",
            "Jumlah Shift\nPola Kerja\nKonsentrasi\nEkonomi",
            "Jam\nOperasional",
            "Contact Person\nTelepon/Email",
            "Muatan\nDominan",
            "Perubahan\nbatas (reko)?\n1 = Ya\n2 = Tidak"
        ]
        self.table.setHorizontalHeaderLabels(headers)
        
        # Apply custom header delegate for word wrapping
        header_delegate = HeaderDelegate(self.table)
        self.table.horizontalHeader().setItemDelegate(header_delegate)
        
        # set header vertikal (nomor baris 1-10) - auto-generated
        for i in range(10):
            self.table.setVerticalHeaderItem(i, QTableWidgetItem(str(i + 1)))
        
        # set lebar header vertikal (nomor baris) - kompak
        self.table.verticalHeader().setFixedWidth(40)
        
        # Configure horizontal header for responsive behavior
        header = self.table.horizontalHeader()
        
        # set mode resize: rentangkan biar mengisi lebar window secara proporsional
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        
        # Enable text wrapping in headers for long labels
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        # set lebar kolom minimum (responsif) - menggunakan constants
        for i, min_width in enumerate(DEFAULT_MIN_COLUMN_WIDTHS):
            header.setMinimumSectionSize(min_width)
            header.resizeSection(i, min_width)
        
        # Enable single-click editing
        self.table.setEditTriggers(
            QTableWidget.CurrentChanged |  # Single-click to edit
            QTableWidget.SelectedClicked |  # Click on selected cell
            QTableWidget.EditKeyPressed |   # Any key press
            QTableWidget.AnyKeyPressed      # mulai ketik langsung
        )
        self.table.itemChanged.connect(self.on_cell_edited)
        
        # Navigation handled by CustomTableWidget.keyPressEvent
        
        # bikin tombol mengambang buat kontrol baris (disembunyikan secara default)
        self.create_floating_row_buttons()
        
        layout.addWidget(self.table)
        
        group.setLayout(layout)
        return group
    
    def create_floating_row_buttons(self):
        # buat tombol floating tambah/hapus untuk baris tabel
        # tombol tambah (kecil, mengambang)
        add_btn = QPushButton()
        add_btn.setIcon(self._get_icon('fa5s.plus', color='#10B981', scale_factor=0.6))
        add_btn.setToolTip("Tambah baris di bawah")
        add_btn.setObjectName("floating_btn")
        add_btn.clicked.connect(self.add_row_at_hover)
        add_btn.hide()
        
        # Remove button (tiny, floating)
        remove_btn = QPushButton()
        remove_btn.setIcon(self._get_icon('fa5s.minus', color='#EF4444', scale_factor=0.6))
        remove_btn.setToolTip("Hapus baris ini")
        remove_btn.setObjectName("floating_btn")
        remove_btn.clicked.connect(self.remove_row_at_hover)
        remove_btn.hide()
        
        # Assign to table
        self.table.add_row_floating_btn = add_btn
        self.table.remove_row_floating_btn = remove_btn
    
    
    def browse_file(self):
        # buka dialog browser file (support multi-select gambar saja)
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Pilih File Gambar (Multi-select untuk batch)",
            str(Path.home()),
            "File Gambar (*.png *.jpg *.jpeg);;Semua File (*.*)"
        )
        
        if file_paths:
            self.current_files = file_paths
            
            # Populate interactive file list
            self.populate_file_list(file_paths)
            
            # Show file list
            self.file_list.setVisible(True)
            
            # Update status
            if len(file_paths) == 1:
                self.update_status(f"✓ 1 file dimuat - Klik 'Mulai OCR' untuk memproses")
            else:
                self.update_status(f"✓ {len(file_paths)} file dimuat - Drag & drop untuk mengubah urutan")
            
            # Enable Start and Reset buttons
            self.start_btn.setEnabled(True)
            self.reset_btn.setEnabled(True)
    
    def populate_file_list(self, file_paths):
        # isi daftar file dengan icon dan nama
        self.file_list.clear()
        
        for file_path in file_paths:
            file_name = Path(file_path).name
            item = QListWidgetItem()
            
            # Set icon based on file extension
            ext = Path(file_path).suffix.lower()
            if ext in ['.png']:
                icon = self._get_icon('fa5s.file-image', color='#8B5CF6')  # Purple for PNG
            elif ext in ['.jpg', '.jpeg']:
                icon = self._get_icon('fa5s.file-image', color='#3B82F6')  # Blue for JPG
            else:
                icon = self._get_icon('fa5s.file', color='#64748B')  # Gray for others
            
            item.setIcon(icon)
            item.setText(file_name)
            item.setData(Qt.UserRole, file_path)  # Store full path in data
            item.setToolTip(file_path)  # Show full path on hover
            
            self.file_list.addItem(item)
    
    def get_ordered_file_paths(self):
        # ambil path file sesuai urutan di list (setelah drag & drop)
        file_paths = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            file_path = item.data(Qt.UserRole)
            file_paths.append(file_path)
        return file_paths
    
    
    def start_ocr(self):
        # mulai proses OCR (support multi-file/multi-page dan append mode)
        if not hasattr(self, 'current_files') or not self.current_files:
            return
        
        # Get file paths in current list order (respects drag & drop reorder)
        ordered_files = self.get_ordered_file_paths()
        
        # Disable Start button and export button during processing
        self.start_btn.setEnabled(False)
        self.enable_export_buttons(False)
        
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Menginisialisasi...")
        
        # simpan data existing sebelum scan baru (untuk append mode)
        self._save_existing_table_data()
        
        # Start worker thread with ordered list of files (after drag & drop)
        self.ocr_worker = OCRWorker(ordered_files)
        self.ocr_worker.progress.connect(self.on_progress)
        self.ocr_worker.finished.connect(self.on_ocr_finished)
        self.ocr_worker.error.connect(self.on_ocr_error)
        self.ocr_worker.start()
        
        self.update_status("Memproses...")
    
    def on_progress(self, percentage: int, stage: str):
        # update progress bar
        self.progress_bar.setValue(percentage)
        self.progress_bar.setFormat(f"{percentage}% - {stage}")
        self.update_status(stage)
    
    def on_ocr_finished(self, results: dict):
        # handle penyelesaian OCR dengan append mode
        new_table_data = results['table']
        
        # gabungkan data baru dengan data existing (append mode)
        if self.existing_table_data:
            # gabungkan data existing dengan data baru
            combined_data = self.existing_table_data + new_table_data
            
            # update metadata untuk tracking total
            new_rows = len(new_table_data)
            existing_rows = len(self.existing_table_data)
            total_rows = len(combined_data)
            
            # update metadata dengan info gabungan
            results['metadata']['new_rows'] = new_rows
            results['metadata']['existing_rows'] = existing_rows
            results['metadata']['total_rows'] = total_rows
            results['metadata']['num_rows'] = total_rows  # untuk backward compatibility
            
            # simpan data gabungan sebagai data existing untuk scan berikutnya
            self.existing_table_data = combined_data
            results['table'] = combined_data
            
            status_msg = (
                f"✓ Ditambahkan {new_rows} baris baru! "
                f"Total: {total_rows} baris (existing: {existing_rows} + baru: {new_rows}) | Siap ekspor"
            )
        else:
            # scan pertama kali, simpan sebagai data existing
            self.existing_table_data = new_table_data
            status_msg = (
                f"✓ Selesai! {results['metadata']['num_rows']} baris diekstrak dalam "
                f"{results['metadata']['total_time']:.1f} detik | Siap ekspor"
            )
        
        # simpan hasil ke ocr_results
        self.ocr_results = results
        
        # Hide progress bar
        self.progress_bar.setVisible(False)
        
        # Populate table dengan data gabungan (atau data baru kalau first scan)
        self.populate_table(results['table'])
        
        # Re-enable Start button, Sort button, and export button
        self.start_btn.setEnabled(True)
        self.sort_btn.setEnabled(True)
        self.enable_export_buttons(True)
        
        # Update status
        self.update_status(status_msg)
        
        # Show success message
        num_files = results['metadata'].get('num_files', 1)
        file_text = f"{num_files} berkas" if num_files > 1 else "1 berkas"
        
        if self.existing_table_data and len(self.existing_table_data) > len(new_table_data):
            # append mode
            QMessageBox.information(
                self,
                "OCR Selesai",
                f"Berhasil menambahkan {len(new_table_data)} baris baru dari {file_text}!\n\n"
                f"Total data sekarang: {len(self.existing_table_data)} baris\n"
                f"Waktu proses: {results['metadata']['total_time']:.1f} detik\n\n"
                "Data sudah diurutkan otomatis:\n"
                "• Kode SLS (naik)\n"
                "• Kode Sub-SLS (turun)\n\n"
                "Anda dapat menambahkan gambar lagi atau mengekspor hasil."
            )
        else:
            # first scan
            QMessageBox.information(
                self,
                "OCR Selesai",
                f"Berhasil mengekstrak {results['metadata']['num_rows']} baris dari {file_text}!\n\n"
                f"Waktu proses: {results['metadata']['total_time']:.1f} detik\n\n"
                "Data sudah diurutkan otomatis:\n"
                "• Kode SLS (naik)\n"
                "• Kode Sub-SLS (turun)\n\n"
                "Anda dapat mengedit tabel, menambahkan gambar lagi, atau mengekspor hasil."
            )
    
    def on_ocr_error(self, error_msg: str):
        # handle error OCR
        self.progress_bar.setVisible(False)
        
        # Re-enable Start button on error
        self.start_btn.setEnabled(True)
        
        self.update_status(f"✗ Error: {error_msg}")
        
        QMessageBox.critical(
            self,
            "Kesalahan OCR",
            f"Terjadi kesalahan saat memproses OCR:\n\n{error_msg}"
        )
    
    def populate_table(self, table_data, append_mode=False):
        # isi tabel dengan hasil OCR (support multi-page, jumlah baris dinamis, dan append mode)
        # param:
        #   table_data: data tabel yang akan diisi
        #   append_mode: True untuk append (tambah di akhir), False untuk replace semua
        # Block signals to avoid triggering itemChanged
        self.table.blockSignals(True)
        
        if append_mode:
            # append mode: tambah baris di akhir
            # hitung baris yang punya data (skip baris kosong)
            current_row_count = 0
            for row_idx in range(self.table.rowCount()):
                has_data = False
                for col_idx in range(16):
                    item = self.table.item(row_idx, col_idx)
                    if item and item.text().strip():
                        has_data = True
                        break
                if has_data:
                    current_row_count += 1
            
            num_new_rows = len(table_data)
            total_rows = current_row_count + num_new_rows
            
            # expand table untuk baris baru
            self.table.setRowCount(total_rows)
            
            # populate baris baru mulai dari akhir data existing (baris yang punya data)
            start_row = current_row_count
        else:
            # replace mode: ganti semua data, mulai dari baris 0
            # clear semua data dulu
            self.table.clearContents()
            num_rows = len(table_data)
            self.table.setRowCount(num_rows)
            start_row = 0
        
        # Update vertical headers (row numbers 1, 2, 3, ...)
        total_rows = self.table.rowCount()
        for i in range(total_rows):
            self.table.setVerticalHeaderItem(i, QTableWidgetItem(str(i + 1)))
        
        # Populate cells (hanya untuk data baru kalau append mode)
        for data_idx, row_data in enumerate(table_data):
            row_idx = start_row + data_idx
            
            # Skip column 0 (No), start from column 1 (Kode SLS/Non-SLS)
            for ocr_col_idx in range(1, 17):  # OCR columns 1-16
                gui_col_idx = ocr_col_idx - 1  # GUI columns 0-15 (shifted left)
                
                cell_data = row_data['cells'].get(ocr_col_idx, {})
                text = cell_data.get('text_final', cell_data.get('text', ''))
                confidence = cell_data.get('confidence', 0.0)
                
                # Create item
                item = QTableWidgetItem(text)
                
                # Set background color based on confidence
                if text.strip():
                    if confidence >= 0.8:
                        item.setBackground(QColor(200, 255, 200))  # Green
                    elif confidence >= 0.5:
                        item.setBackground(QColor(255, 255, 200))  # Yellow
                    else:
                        item.setBackground(QColor(255, 200, 200))  # Red
                else:
                    item.setBackground(QColor(240, 240, 240))  # Gray
                
                # Set tooltip with confidence
                item.setToolTip(f"Confidence: {confidence*100:.1f}%")
                
                self.table.setItem(row_idx, gui_col_idx, item)
        
        # Re-enable signals
        self.table.blockSignals(False)
        
        # scroll ke baris terakhir kalau append mode
        if append_mode and table_data:
            self.table.scrollToItem(self.table.item(total_rows - 1, 0))
    
    def _save_existing_table_data(self):
        # simpan data tabel yang sudah ada ke format yang bisa di-append
        # ini dipanggil sebelum scan baru untuk menyimpan data existing
        # hanya simpan baris yang punya data (skip baris kosong)
        if self.table.rowCount() == 0:
            self.existing_table_data = []
            return
        
        # extract data dari tabel yang ada, hanya baris yang punya data
        existing_data = []
        num_rows = self.table.rowCount()
        
        for row_idx in range(num_rows):
            # cek apakah baris ini punya data (setidaknya satu cell tidak kosong)
            has_data = False
            row_data = {
                'row_index': len(existing_data),  # index baru untuk data yang valid
                'cells': {}
            }
            
            # extract setiap cell (kolom 0-15 di GUI = kolom 1-16 di OCR)
            for gui_col_idx in range(16):
                ocr_col_idx = gui_col_idx + 1  # GUI col 0 = OCR col 1
                item = self.table.item(row_idx, gui_col_idx)
                
                if item:
                    text = item.text().strip()
                    if text:  # hanya simpan cell yang punya text
                        has_data = True
                        # extract confidence dari tooltip kalau ada
                        tooltip = item.toolTip()
                        confidence = 0.0
                        if 'Confidence:' in tooltip:
                            try:
                                conf_text = tooltip.split('Confidence:')[1].split('%')[0].strip()
                                confidence = float(conf_text) / 100.0
                            except:
                                pass
                        
                        row_data['cells'][ocr_col_idx] = {
                            'text': text,
                            'text_final': text,
                            'confidence': confidence
                        }
            
            # hanya tambahkan baris yang punya data
            if has_data:
                existing_data.append(row_data)
        
        self.existing_table_data = existing_data
    
    def on_cell_edited(self, item: QTableWidgetItem):
        # track cell yang sudah diedit
        row = item.row()
        col = item.column()
        self.edited_cells[(row, col)] = item.text()
        
        # Mark edited cell with different color
        item.setBackground(QColor(220, 220, 255))  # Light blue
        
        # Update status
        self.update_status(f"Sel diedit ({row+1}, {col+1}) | Total edit: {len(self.edited_cells)}")
    
    def add_row_at_hover(self):
        # tambah baris baru di bawah baris yang di-hover
        hovered_row = self.table.hovered_row
        if hovered_row < 0:
            return
        
        # Insert row below hovered row
        insert_pos = hovered_row + 1
        self.table.insertRow(insert_pos)
        
        # Initialize empty cells with white background
        for col in range(self.table.columnCount()):
            item = QTableWidgetItem("")
            item.setBackground(QColor(255, 255, 255))
            self.table.setItem(insert_pos, col, item)
        
        # Update all vertical headers (row numbers)
        for i in range(self.table.rowCount()):
            self.table.setVerticalHeaderItem(i, QTableWidgetItem(str(i + 1)))
        
        # Update status
        self.update_status(f"✓ Baris ditambahkan di posisi {insert_pos + 1} (Total: {self.table.rowCount()} baris)")
        
        # Scroll to new row
        self.table.scrollToItem(self.table.item(insert_pos, 0))
        
        # Hide floating buttons after action
        self.table.hide_floating_buttons()
    
    def remove_row_at_hover(self):
        # hapus baris yang di-hover (langsung, tanpa konfirmasi)
        hovered_row = self.table.hovered_row
        if hovered_row < 0:
            return
        
        # Hide buttons first
        self.table.hide_floating_buttons()
        
        # Delete row instantly
        self.table.removeRow(hovered_row)
        
        # Update vertical headers (row numbers)
        for i in range(self.table.rowCount()):
            self.table.setVerticalHeaderItem(i, QTableWidgetItem(str(i + 1)))
        
        # Update status
        self.update_status(f"✓ Baris {hovered_row + 1} dihapus (Total: {self.table.rowCount()} baris)")
    
    def sort_table(self):
        # urutkan tabel berdasarkan Kode SLS (ASC) dan Sub-SLS (DESC)
        # Block signals to prevent triggering itemChanged during sorting
        self.table.blockSignals(True)
        
        # Extract all rows data
        rows_data = []
        num_rows = self.table.rowCount()
        num_cols = self.table.columnCount()
        
        for row in range(num_rows):
            row_data = []
            for col in range(num_cols):
                item = self.table.item(row, col)
                row_data.append({
                    'text': item.text() if item else '',
                    'background': item.background() if item else QColor(255, 255, 255),
                    'tooltip': item.toolTip() if item else ''
                })
            rows_data.append(row_data)
        
        # Sort rows by Kode SLS (col 0) ASC, then Sub-SLS (col 1) DESC
        def sort_key(row):
            # Column 0: Kode SLS (ascending)
            col0_text = row[0]['text']
            col0_val = int(''.join(c for c in col0_text if c.isdigit()) or '0')
            
            # Column 1: Kode Sub-SLS (descending - negative for DESC)
            col1_text = row[1]['text']
            col1_val = int(''.join(c for c in col1_text if c.isdigit()) or '0')
            
            return (col0_val, -col1_val)  # ASC, DESC
        
        rows_data.sort(key=sort_key)
        
        # Repopulate table with sorted data
        for row_idx, row_data in enumerate(rows_data):
            # Update row number in vertical header
            self.table.setVerticalHeaderItem(row_idx, QTableWidgetItem(str(row_idx + 1)))
            
            for col_idx, cell_data in enumerate(row_data):
                item = QTableWidgetItem(cell_data['text'])
                item.setBackground(cell_data['background'])
                item.setToolTip(cell_data['tooltip'])
                self.table.setItem(row_idx, col_idx, item)
        
        # Re-enable signals
        self.table.blockSignals(False)
        
        # Update status
        self.update_status("✓ Tabel diurutkan otomatis (Kode SLS ↑, Sub-SLS ↓)")
    
    def enable_export_buttons(self, enabled: bool):
        # enable atau disable tombol ekspor
        self.export_button.setEnabled(enabled)
    
    def export_results(self):
        # ekspor hasil OCR dengan dialog pilihan format
        if not self.ocr_results:
            QMessageBox.warning(self, "Tidak Ada Data", "Silakan jalankan OCR terlebih dahulu sebelum mengekspor.")
            return
        
        # Format selection dialog
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QRadioButton, QDialogButtonBox, QLabel
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Pilih Format Ekspor")
        dialog.setMinimumWidth(350)
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Pilih format ekspor:"))
        layout.addSpacing(8)
        
        # Format options
        excel_radio = QRadioButton("Excel (.xlsx) - Disarankan")
        excel_radio.setChecked(True)
        csv_radio = QRadioButton("CSV (.csv) - Teks biasa")
        json_radio = QRadioButton("JSON (.json) - Dengan metadata")
        html_radio = QRadioButton("HTML (.html) - Tampilan interaktif")
        
        layout.addWidget(excel_radio)
        layout.addWidget(csv_radio)
        layout.addWidget(json_radio)
        layout.addWidget(html_radio)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec_() != QDialog.Accepted:
            return
        
        # Determine selected format
        if excel_radio.isChecked():
            format_name = "excel"
            ext = "xlsx"
        elif csv_radio.isChecked():
            format_name = "csv"
            ext = "csv"
        elif json_radio.isChecked():
            format_name = "json"
            ext = "json"
        else:
            format_name = "html"
            ext = "html"
        
        # File dialog for saving
        format_label = "Excel" if format_name == "excel" else "CSV" if format_name == "csv" else "JSON"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Ekspor Hasil {format_label}",
            str(Path.home() / f"blok3_results.{ext}"),
            f"File {format_label} (*.{ext});;Semua File (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            if format_name == 'excel':
                self.export_to_excel(file_path)
            elif format_name == 'csv':
                self.export_to_csv(file_path)
            elif format_name == 'json':
                self.export_to_json(file_path)
            elif format_name == 'html':
                self.export_to_html(file_path)
            
            self.update_status(f"✓ Diekspor ke {Path(file_path).name}")
            QMessageBox.information(self, "Ekspor Berhasil", f"Hasil diekspor ke:\n{file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Kesalahan Ekspor", f"Gagal mengekspor:\n{str(e)}")
    
    def export_to_excel(self, file_path: str):
        # ekspor ke Excel dengan formatting (termasuk kolom No)
        from openpyxl import Workbook
        from openpyxl.styles import PatternFill, Font, Alignment
        
        wb = Workbook()
        ws = wb.active
        ws.title = "BLOK III"
        
        # Headers - prepend "No" column
        headers = ["No"] + [self.table.horizontalHeaderItem(i).text() for i in range(16)]
        
        # Write headers
        for col, header in enumerate(headers, 1):
            cell = ws.cell(1, col, header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            cell.alignment = Alignment(horizontal="center")
        
        # Write data (dynamic row count)
        num_rows = self.table.rowCount()
        for row in range(num_rows):
            # tulis nomor baris (kolom No)
            ws.cell(row + 2, 1, row + 1)
            
            # tulis kolom sisanya
            for col in range(16):
                item = self.table.item(row, col)
                if item:
                    ws.cell(row + 2, col + 2, item.text())
        
        wb.save(file_path)
    
    def export_to_csv(self, file_path: str):
        # ekspor ke CSV (termasuk kolom No)
        import csv
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # header - tambahkan "No" di depan
            headers = ["No"] + [self.table.horizontalHeaderItem(i).text() for i in range(16)]
            writer.writerow(headers)
            
            # data (jumlah baris dinamis)
            num_rows = self.table.rowCount()
            for row in range(num_rows):
                row_data = [row + 1]  # mulai dengan nomor baris
                for col in range(16):
                    item = self.table.item(row, col)
                    row_data.append(item.text() if item else '')
                writer.writerow(row_data)
    
    def export_to_json(self, file_path: str):
        # ekspor ke JSON (termasuk kolom No)
        data = {
            'metadata': self.ocr_results['metadata'],
            'table': []
        }
        
        # jumlah baris dinamis
        num_rows = self.table.rowCount()
        for row in range(num_rows):
            row_data = {'row_number': row + 1, 'cells': {}}
            
            # tambahkan "No" sebagai kolom 0
            row_data['cells'][0] = {
                'text': str(row + 1),
                'edited': False
            }
            
            # tambahkan kolom sisanya (digeser 1)
            for col in range(16):
                item = self.table.item(row, col)
                if item and item.text().strip():
                    row_data['cells'][col + 1] = {
                        'text': item.text(),
                        'edited': (row, col) in self.edited_cells
                    }
            data['table'].append(row_data)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def export_to_html(self, file_path: str):
        # ekspor ke HTML
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>BLOK III Results</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #2c3e50; }
        table { border-collapse: collapse; width: 100%; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #4472C4; color: white; font-weight: bold; }
        tr:nth-child(even) { background-color: #f2f2f2; }
        .metadata { background: #f0f0f0; padding: 10px; border-radius: 5px; margin-bottom: 20px; }
    </style>
</head>
<body>
    <h1>BLOK III Table - Extraction Results</h1>
    <div class="metadata">
"""
        
        metadata = self.ocr_results['metadata']
        html += f"        <p><strong>Processing Time:</strong> {metadata['total_time']:.1f}s</p>\n"
        html += f"        <p><strong>Total Files:</strong> {metadata.get('num_files', 1)}</p>\n"
        html += f"        <p><strong>Total Rows:</strong> {metadata['num_rows']}</p>\n"
        html += "    </div>\n"
        
        html += "    <table>\n        <tr>\n"
        
        # Headers - prepend "No"
        headers = ["No"] + [self.table.horizontalHeaderItem(i).text() for i in range(16)]
        for header in headers:
            html += f"            <th>{header}</th>\n"
        html += "        </tr>\n"
        
        # Data (dynamic row count)
        num_rows = self.table.rowCount()
        for row in range(num_rows):
            html += "        <tr>\n"
            # tambahkan nomor baris
            html += f"            <td>{row + 1}</td>\n"
            # tambahkan kolom sisanya
            for col in range(16):
                item = self.table.item(row, col)
                text = item.text() if item else ''
                html += f"            <td>{text}</td>\n"
            html += "        </tr>\n"
        
        html += """    </table>
</body>
</html>"""
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html)
    
    def update_status(self, message: str):
        # update status bar
        self.status_bar.showMessage(message)
    
    def reset_all(self):
        # reset semua data dan UI ke kondisi awal
        # konfirmasi reset
        reply = QMessageBox.question(
            self,
            "Konfirmasi Reset",
            "Apakah Anda yakin ingin mereset?\n\nIni akan menghapus:\n• File yang dipilih\n• Hasil OCR\n• Data tabel\n• Semua editan",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
        
        # hentikan worker OCR kalau masih jalan
        if self.ocr_worker and self.ocr_worker.isRunning():
            self.ocr_worker.cancel()
            self.ocr_worker.wait()
        
        # bersihkan pilihan file
        self.current_files = []
        self.file_list.clear()
        self.file_list.setVisible(False)
        
        # bersihkan hasil OCR
        self.ocr_results = None
        self.edited_cells.clear()
        self.existing_table_data = []  # clear data existing untuk append mode
        
        # bersihkan tabel dan reset ke default 10 baris
        self.table.clearContents()
        self.table.setRowCount(10)
        for i in range(10):
            self.table.setVerticalHeaderItem(i, QTableWidgetItem(str(i + 1)))
        
        # Hide progress bar
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        
        # nonaktifkan tombol
        self.start_btn.setEnabled(False)
        self.sort_btn.setEnabled(False)
        self.reset_btn.setEnabled(False)
        self.enable_export_buttons(False)
        
        # Update status
        self.update_status("Siap - Pilih file untuk memulai")
        
        QMessageBox.information(
            self,
            "Reset Selesai",
            "Semua data telah dihapus.\n\nAnda dapat memilih file baru untuk diproses."
        )
    
    
    def closeEvent(self, event):
        # handle penutupan window
        if self.ocr_worker and self.ocr_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "OCR Sedang Berjalan",
                "Proses OCR masih berjalan. Apakah Anda yakin ingin keluar?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.ocr_worker.cancel()
                self.ocr_worker.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
