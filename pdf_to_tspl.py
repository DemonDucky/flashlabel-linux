#!/usr/bin/env python3
"""
PDF to TSPL converter for YXWL 318Pro
- Input:  Shopee PDF (bất kỳ size nào)
- Output: fit vào A7 (74x105mm), căn giữa, to nhất có thể
"""

import sys
import os
import tempfile
import subprocess
import dataclasses

# Khổ giấy A7
LABEL_W_MM = 74
LABEL_H_MM = 105
DPI = 203.2
GAP_MM = 3

@dataclasses.dataclass
class Image:
    width: int
    height: int
    data: bytes

def convert_pdf(pdfname, extra_args=[]):
    """Convert PDF to monochrome bitmap via pdftoppm"""
    with tempfile.NamedTemporaryFile(suffix='.pbm', delete=False) as pbmfile:
        pbm_base = pbmfile.name.removesuffix('.pbm')

    try:
        subprocess.check_call(
            ["pdftoppm", "-mono", "-singlefile"] + extra_args + [pdfname, pbm_base],
            stderr=subprocess.DEVNULL
        )
        with open(pbm_base + '.pbm', 'rb') as f:
            header = f.readline().strip()
            if header != b'P4':
                raise ValueError(f"Unrecognised PBM format: {header}")
            dims = f.readline().decode('ascii').strip()
            # XOR 0xFF để invert màu (PBM: 1=đen, TSPL: 1=in mực)
            data = bytes(x ^ 0xFF for x in f.read())
        width, height = map(int, dims.split())
        return Image(width, height, data)
    finally:
        for ext in ['.pbm', '']:
            try:
                os.unlink(pbm_base + ext)
            except FileNotFoundError:
                pass

def convert_pdf_scaled(pdfname, max_width_px, max_height_px):
    """
    Scale PDF để fit vào max_width x max_height pixels,
    giữ đúng aspect ratio, to nhất có thể.
    """
    # Render lần 1 để lấy aspect ratio gốc
    im = convert_pdf(pdfname)
    aspect = im.width / im.height
    max_aspect = max_width_px / max_height_px

    if aspect < max_aspect:
        # PDF cao hơn → giới hạn bởi height
        target_w = int(max_height_px * aspect) - 1
        target_h = max_height_px
    else:
        # PDF rộng hơn → giới hạn bởi width
        target_w = max_width_px - 1  # pdftoppm hay lệch 1px
        target_h = int(max_width_px / aspect)

    # Render lần 2 với đúng kích thước
    im = convert_pdf(pdfname, ['-scale-to-x', str(target_w), '-scale-to-y', str(target_h)])
    return im

def pdf2tspl(pdf_path, label_w_mm=LABEL_W_MM, label_h_mm=LABEL_H_MM, dpi=DPI, copies=1):
    """Convert PDF → TSPL bytes, fit vào label, căn giữa"""
    label_w_px = int(round(label_w_mm / 25.4 * dpi))
    label_h_px = int(round(label_h_mm / 25.4 * dpi))

    print(f"Label size: {label_w_px}x{label_h_px}px ({label_w_mm}x{label_h_mm}mm @ {dpi}dpi)", file=sys.stderr)
    image = convert_pdf_scaled(pdf_path, label_w_px, label_h_px)
    print(f"PDF rendered: {image.width}x{image.height}px", file=sys.stderr)
    print(f"Paste offset: x={( label_w_px - image.width) // 2}, y={(label_h_px - image.height) // 2}", file=sys.stderr)

    # Căn giữa ảnh trên label, thêm padding top 3mm
    PADDING_TOP_MM = 3
    padding_top_px = int(round(PADDING_TOP_MM / 25.4 * dpi))
    paste_x = (label_w_px - image.width) // 2
    paste_y = max((label_h_px - image.height) // 2, padding_top_px)

    row_bytes = (image.width + 7) // 8

    tspl = (
        f"\r\nSIZE {label_w_mm} mm,{label_h_mm} mm\r\n"
        f"GAP {GAP_MM} mm,0 mm\r\n"
        f"DIRECTION 0\r\n"
        f"CLS\r\n"
        f"BITMAP {paste_x},{paste_y},{row_bytes},{image.height},0,"
    ).encode()
    tspl += image.data
    tspl += f"\r\nPRINT {copies},1\r\n".encode()
    return tspl

def cups_filter_mode():
    """CUPS gọi: filter job-id user title copies options [file]"""
    if len(sys.argv) < 6:
        print(f"Usage: {sys.argv[0]} job-id user title copies options [file]",
              file=sys.stderr)
        sys.exit(1)

    copies = int(sys.argv[4]) if sys.argv[4].isdigit() else 1

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name
        if len(sys.argv) >= 7:
            with open(sys.argv[6], "rb") as f:
                tmp.write(f.read())
        else:
            tmp.write(sys.stdin.buffer.read())

    try:
        print(f"Converting {tmp_path}...", file=sys.stderr)
        tspl = pdf2tspl(tmp_path, copies=copies)
        print(f"Sending {len(tspl)} bytes...", file=sys.stderr)
        sys.stdout.buffer.write(tspl)
        sys.stdout.buffer.flush()
        print("Done!", file=sys.stderr)
    finally:
        os.unlink(tmp_path)

if __name__ == "__main__":
    # CUPS gọi filter với đúng 6 hoặc 7 arguments:
    # filter job-id user title copies options [file]
    # argv:   [0]    [1]  [2]  [3]   [4]    [5]    [6]
    if len(sys.argv) in (6, 7):
        cups_filter_mode()
    else:
        # CLI mode: pdf_to_tspl.py input.pdf /dev/usb/lp0
        import argparse
        parser = argparse.ArgumentParser(description='Convert PDF to TSPL for YXWL 318Pro')
        parser.add_argument('pdf_file', help='Input PDF')
        parser.add_argument('output', help='Output file, device (/dev/usb/lp0), or "-" for stdout')
        parser.add_argument('-x', '--width', type=int, default=LABEL_W_MM, help='Label width mm')
        parser.add_argument('-y', '--height', type=int, default=LABEL_H_MM, help='Label height mm')
        parser.add_argument('-d', '--dpi', type=float, default=DPI)
        parser.add_argument('-n', '--copies', type=int, default=1)
        args = parser.parse_args()

        tspl = pdf2tspl(args.pdf_file, args.width, args.height, args.dpi, args.copies)

        if args.output == '-':
            sys.stdout.buffer.write(tspl)
        else:
            with open(args.output, 'wb') as f:
                f.write(tspl)
