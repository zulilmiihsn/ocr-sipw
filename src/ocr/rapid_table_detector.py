"""
Wrapper untuk RapidTableDetection sebagai alternative table detection
"""

import sys
from pathlib import Path
import cv2
import numpy as np
from typing import Optional, Tuple

# Add RapidTableDetection to path
RAPID_PATH = Path(__file__).parent.parent.parent / "experiments" / "references" / "table_detection" / "RapidTableDetection"
if RAPID_PATH.exists():
    sys.path.insert(0, str(RAPID_PATH))
    try:
        from rapid_table_det.inference import TableDetector
        RAPID_AVAILABLE = True
    except ImportError:
        RAPID_AVAILABLE = False
        TableDetector = None
else:
    RAPID_AVAILABLE = False
    TableDetector = None


class RapidTableDetectorWrapper:
    """
    Wrapper untuk RapidTableDetection
    Provides perspective correction dan rotation handling
    """
    
    def __init__(self, use_cuda: bool = False):
        """Initialize RapidTableDetection"""
        self.use_cuda = use_cuda
        self.detector = None
        
        if RAPID_AVAILABLE:
            try:
                self.detector = TableDetector(
                    use_cuda=use_cuda,
                    obj_model_type="yolo_obj_det",
                    edge_model_type="yolo_edge_det",
                    cls_model_type="paddle_cls_det"
                )
                print("✓ RapidTableDetection initialized successfully")
            except Exception as e:
                print(f"⚠ Warning: RapidTableDetection initialization failed: {e}")
                print("Falling back to standard table detection")
                self.detector = None
        else:
            print("⚠ RapidTableDetection not available, using standard pyl detection")
    
    def detect_and_crop_table(
        self, 
        image: np.ndarray,
        return_perspective_corrected: bool = True
    ) -> Optional[Tuple[np.ndarray, dict]]:
        """
        Detect dan crop table dari image
        
        Args:
            image: Input image
            return_perspective_corrected: If True, return perspective-corrected crop
            
        Returns:
            Tuple of (cropped_table, metadata) atau None jika tidak ditemukan
        """
        if not self.detector:
            return None
        
        try:
            # Save temporary image untuk RapidTableDetection
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                cv2.imwrite(tmp.name, image)
                temp_path = tmp.name
            
            try:
                # Detect table
                results, elapse = self.detector(
                    temp_path,
                    det_accuracy=0.6,
                    use_obj_det=True,
                    use_edge_det=True,
                    use_cls_det=True
                )
                
                if not results:
                    return None
                
                # Get first table result
                result = results[0]
                metadata = {
                    'box': result.get('box'),
                    'lt': result.get('lt'),
                    'rt': result.get('rt'),
                    'rb': result.get('rb'),
                    'lb': result.get('lb'),
                    'orientation': result.get('orientation', 'up'),
                    'elapse': elapse
                }
                
                # Perspective correction
                if return_perspective_corrected and all(key in result for key in ['lt', 'rt', 'rb', 'lb']):
                    # Extract table with perspective correction
                    from rapid_table_det.utils.visuallize import extract_table_img
                    corrected = extract_table_img(image.copy(), 
                                                   result['lt'], result['rt'], 
                                                   result['rb'], result['lb'])
                    return corrected, metadata
                else:
                    # Just crop using bounding box
                    box = result.get('box')
                    if box is not None:
                        xmin, ymin, xmax, ymax = box
                        cropped = image[int(ymin):int(ymax), int(xmin):int(xmax)]
                        return cropped, metadata
                
                return None
                
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
        except Exception as e:
            print(f"Error in RapidTableDetection: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if RapidTableDetection is available"""
        return self.detector is not None
    
    def __bool__(self) -> bool:
        """Allow truthiness check"""
        return self.is_available()
