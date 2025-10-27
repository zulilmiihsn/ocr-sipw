"""
Test Stage 7: CSV Export
Test data mapping dan CSV generation
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.utils.csv_exporter import export_to_csv
from src.models.table_schema import COLUMN_NAMES
import csv


def test_csv_export():
    """Test CSV export functionality"""
    
    print("=" * 60)
    print("STAGE 7: CSV EXPORT TEST")
    print("=" * 60)
    
    # Create mock OCR results (10 rows × 17 columns)
    print("\n📝 Creating mock OCR results...")
    
    mock_data = {}
    
    # Sample data for first 3 rows
    sample_rows = [
        {
            (0, 0): "1",  # No
            (0, 1): "JAKARTA",  # Kota/Kab Asal
            (0, 2): "JAKARTA BARAT",  # Kecamatan Asal
            (0, 3): "CENGKARENG",  # Kelurahan Asal
            (0, 4): "3,1",  # Dewasa Laki (decimal)
            (0, 5): "2",  # Dewasa Perempuan
            (0, 6): "1",  # Anak Laki
            (0, 7): "0",  # Anak Perempuan
            (0, 8): "6,1",  # Jumlah (decimal)
            (0, 9): "KAPAL-001",  # Nama Kapal
            (0, 10): "GT-123",  # GT
            (0, 11): "KM",  # Satuan
            (0, 12): "PELABUHAN-A",  # Pelabuhan Tujuan
            (0, 13): "08:00-16:00",  # Jam Berangkat-Tiba
            (0, 14): "01/01/2024",  # Tanggal
            (0, 15): "Catatan 1",  # Keterangan
            (0, 16): "NORMAL",  # Status
        },
        {
            (1, 0): "2",
            (1, 1): "BANDUNG",
            (1, 2): "BANDUNG UTARA",
            (1, 3): "CIBEUNYING",
            (1, 4): "5",
            (1, 5): "4",
            (1, 6): "2",
            (1, 7): "1",
            (1, 8): "12",
            (1, 9): "KAPAL-002",
            (1, 10): "GT-456",
            (1, 11): "KM",
            (1, 12): "PELABUHAN-B",
            (1, 13): "09:00-17:00",
            (1, 14): "02/01/2024",
            (1, 15): "",  # empty cell
            (1, 16): "NORMAL",
        },
        {
            (2, 0): "3",
            (2, 1): "SURABAYA",
            (2, 2): "",  # empty cell
            (2, 3): "",  # empty cell
            (2, 4): "10,5",  # decimal
            (2, 5): "8,2",  # decimal
            (2, 6): "",  # empty cell
            (2, 7): "",  # empty cell
            (2, 8): "18,7",  # decimal
            (2, 9): "KAPAL-003",
            (2, 10): "GT-789",
            (2, 11): "KM",
            (2, 12): "PELABUHAN-C",
            (2, 13): "10:00-18:00",
            (2, 14): "03/01/2024",
            (2, 15): "Catatan 3",
            (2, 16): "CHECKED",
        },
    ]
    
    # Merge sample data
    for row_data in sample_rows:
        mock_data.update(row_data)
    
    # Fill remaining rows with empty data (row 3-9)
    for row in range(3, 10):
        for col in range(17):
            if (row, col) not in mock_data:
                mock_data[(row, col)] = ""
    
    print(f"  ✅ Created {len(mock_data)} cell entries")
    
    # Export to CSV
    results_dir = "experiments/results"
    os.makedirs(results_dir, exist_ok=True)
    output_path = f"{results_dir}/stage7_test_output.csv"
    
    print(f"\n💾 Exporting to CSV...")
    try:
        exported_path = export_to_csv(mock_data, output_path)
        print(f"  ✅ CSV exported: {exported_path}")
        
        # Verify export
        print(f"\n📊 Verifying CSV content...")
        with open(exported_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            rows = list(reader)
            
            print(f"  ✅ Total rows: {len(rows)} (1 header + {len(rows)-1} data)")
            print(f"  ✅ Columns: {len(rows[0])}")
            
            # Display header
            print(f"\n📋 CSV Header:")
            for i, col_name in enumerate(rows[0]):
                print(f"  {i+1:2}. {col_name}")
            
            # Display first 3 data rows
            print(f"\n📋 First 3 Data Rows:")
            for i, row in enumerate(rows[1:4]):
                print(f"\n  Row {i+1}:")
                for j, value in enumerate(row):
                    if value:  # only show non-empty
                        print(f"    - {rows[0][j]:20}: {value}")
        
        # Test with pandas (if available)
        try:
            import pandas as pd
            df = pd.read_csv(exported_path)
            print(f"\n📊 Pandas verification:")
            print(f"  ✅ Shape: {df.shape}")
            print(f"  ✅ Columns: {list(df.columns)}")
            print(f"\n  Sample data:")
            print(df.head(3).to_string())
            
        except ImportError:
            print(f"\n  ℹ️  Pandas not available (optional)")
        
    except Exception as e:
        print(f"  ❌ Export failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Stage 7 testing completed!")
    print("=" * 60)


if __name__ == "__main__":
    test_csv_export()


