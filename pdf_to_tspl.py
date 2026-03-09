#!/usr/bin/env python3
"""
PDF to TSPL converter for YXWL 318Pro
- Input:  Shopee PDF (bất kỳ size, bất kỳ số trang)
- Output: mỗi page → 1 label, fit vào A7 (74x105mm), căn giữa
"""

import sys
import os
import glob
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

def count_pdf_pages(pdfname):
    """Đếm số trang trong PDF"""
    result = subprocess.run(
        ["pdfinfo", pdfname],
        capture_output=True, text=True
    )
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split()[1])
    return 1

def render_page(pdfname, page_num, extra_args=[], tmpdir=None):
    """Render 1 trang PDF thành PBM, trả về Image"""
    base = os.path.join(tmpdir, f"page")
    subprocess.check_call(
        ["pdftoppm", "-mono",
         "-f", str(page_num), "-l", str(page_num),
         "-singlefile"] + extra_args + [pdfname, base],
        stderr=subprocess.DEVNULL
    )
    pbm_path = base + ".pbm"
    with open(pbm_path, "rb") as f:
        header = f.readline().strip()
        if header != b"P4":
            raise ValueError(f"Unrecognised PBM format: {header}")
        dims = f.readline().decode("ascii").strip()
        data = bytes(x ^ 0xFF for x in f.read())
    os.unlink(pbm_path)
    width, height = map(int, dims.split())
    return Image(width, height, data)

def render_page_scaled(pdfname, page_num, max_w_px, max_h_px, tmpdir):
    """Render 1 trang, scale fit vào max_w x max_h, giữ aspect ratio"""
    # Lần 1: lấy kích thước gốc
    im = render_page(pdfname, page_num, tmpdir=tmpdir)
    aspect = im.width / im.height
    max_aspect = max_w_px / max_h_px

    if aspect < max_aspect:
        target_w = int(max_h_px * aspect) - 1
        target_h = max_h_px
    else:
        target_w = max_w_px - 1
        target_h = int(max_w_px / aspect)

    # Lần 2: render đúng kích thước
    im = render_page(pdfname, page_num,
                     extra_args=["-scale-to-x", str(target_w),
                                 "-scale-to-y", str(target_h)],
                     tmpdir=tmpdir)
    return im

def page_to_tspl(image, label_w_mm, label_h_mm, label_w_px, label_h_px, copies=1):
    """Đóng gói 1 Image thành TSPL cho 1 nhãn"""
    paste_x = (label_w_px - image.width) // 2
    paste_y = (label_h_px - image.height) // 2
    row_bytes = (image.width + 7) // 8

    tspl = (
        f"SIZE {label_w_mm} mm,{label_h_mm} mm\r\n"
        f"GAP {GAP_MM} mm,0 mm\r\n"
        f"DIRECTION 0\r\n"
        f"CLS\r\n"
        f"BITMAP {paste_x},{paste_y},{row_bytes},{image.height},0,"
    ).encode()
    tspl += image.data
    tspl += f"\r\nPRINT {copies},1\r\n".encode()
    return tspl

def pdf2tspl_all(pdf_path, label_w_mm=LABEL_W_MM, label_h_mm=LABEL_H_MM,
                 dpi=DPI, copies=1):
    """Convert tất cả trang PDF → TSPL, mỗi trang = 1 nhãn"""
    label_w_px = int(round(label_w_mm / 25.4 * dpi))
    label_h_px = int(round(label_h_mm / 25.4 * dpi))

    num_pages = count_pdf_pages(pdf_path)
    print(f"PDF has {num_pages} page(s), label {label_w_mm}x{label_h_mm}mm @ {dpi}dpi",
          file=sys.stderr)

    all_tspl = b""
    with tempfile.TemporaryDirectory() as tmpdir:
        for page_num in range(1, num_pages + 1):
            print(f"Rendering page {page_num}/{num_pages}...", file=sys.stderr)
            image = render_page_scaled(pdf_path, page_num, label_w_px, label_h_px, tmpdir)
            print(f"  → {image.width}x{image.height}px, paste ({(label_w_px-image.width)//2},{(label_h_px-image.height)//2})",
                  file=sys.stderr)
            all_tspl += page_to_tspl(image, label_w_mm, label_h_mm,
                                     label_w_px, label_h_px, copies)

    return all_tspl

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
        tspl = pdf2tspl_all(tmp_path, copies=copies)
        print(f"Sending {len(tspl)} bytes total...", file=sys.stderr)
        sys.stdout.buffer.write(tspl)
        sys.stdout.buffer.flush()
        print("Done!", file=sys.stderr)
    finally:
        os.unlink(tmp_path)

if __name__ == "__main__":
    if len(sys.argv) in (6, 7):
        cups_filter_mode()
    else:
        import argparse
        parser = argparse.ArgumentParser(description="Convert PDF to TSPL for YXWL 318Pro")
        parser.add_argument("pdf_file", help="Input PDF")
        parser.add_argument("output", help="Output file, /dev/usb/lp0, or '-' for stdout")
        parser.add_argument("-x", "--width", type=int, default=LABEL_W_MM)
        parser.add_argument("-y", "--height", type=int, default=LABEL_H_MM)
        parser.add_argument("-d", "--dpi", type=float, default=DPI)
        parser.add_argument("-n", "--copies", type=int, default=1)
        args = parser.parse_args()

        tspl = pdf2tspl_all(args.pdf_file, args.width, args.height, args.dpi, args.copies)

        if args.output == "-":
            sys.stdout.buffer.write(tspl)
        else:
            with open(args.output, "wb") as f:
                f.write(tspl)
