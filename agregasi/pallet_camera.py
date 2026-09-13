"""Decode real barcode frames captured by a camera scanner."""
from PySide6.QtGui import QImage


def decode_frame(image):
    if image is None or image.isNull():return []
    import zxingcpp
    from PIL import Image
    gray=image.convertToFormat(QImage.Format.Format_Grayscale8)
    frame=Image.frombytes('L',(gray.width(),gray.height()),bytes(gray.constBits()),'raw','L',gray.bytesPerLine())
    return list(dict.fromkeys(code.text for code in zxingcpp.read_barcodes(frame) if code.text))
