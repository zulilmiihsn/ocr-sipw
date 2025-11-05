"""Custom exceptions for Lab OCR application."""


class OCRException(Exception):
    """Base exception for OCR-related errors."""
    pass


class ImageLoadError(OCRException):
    """Raised when image cannot be loaded."""
    pass


class TableDetectionError(OCRException):
    """Raised when table region detection fails."""
    pass


class OCRProcessingError(OCRException):
    """Raised when OCR processing fails."""
    pass


class ValidationError(OCRException):
    """Raised when data validation fails."""
    pass


class ExportError(OCRException):
    """Raised when export operation fails."""
    pass

