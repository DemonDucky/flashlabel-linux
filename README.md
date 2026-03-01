# yxwl-318pro-linux

**CUPS driver for YXWL 318Pro (and compatible) USB label printers on Linux.**

Converts any PDF to TSPL commands and sends directly to the printer — no proprietary driver needed. Works with any app that prints via CUPS: browsers, document viewers, LibreOffice, etc.

---

## Background

The official Linux driver provided by YXWL is broken on modern CUPS (the filter crashes with "No Available Printer" due to a bug in how it queries the CUPS daemon). This project replaces it entirely with a simple Python script that:

1. Receives the PDF from CUPS
2. Renders it to a monochrome bitmap via `pdftoppm`
3. Scales and centers it to fit the label size
4. Encodes it as a [TSPL](https://www.tscprinters.com/cms/upload/download_tc/TSPL_TSPL2_programming%20language.pdf) BITMAP command
5. Sends it to the printer via the CUPS USB backend

## Compatibility

Tested on:
- **Printer:** YXWL 318Pro (USB ID `5958:0318`)
- **OS:** Arch Linux
- **CUPS:** 2.x / 3.x
- **Label size:** A6 (105×148mm), A7 (74×105mm)

Should work with other TSPL-based label printers (YXWL Y480, Y528, RH40, etc.) with minor config changes.

## Requirements

- `cups`
- `poppler` (for `pdftoppm`)
- `python3` (stdlib only, no pip packages needed)

```bash
# Arch Linux
sudo pacman -S cups poppler python

# Ubuntu/Debian
sudo apt install cups poppler-utils python3
```

## Installation

```bash
git clone https://github.com/yourname/yxwl-318pro-linux
cd yxwl-318pro-linux
sudo bash install.sh
```

The install script will:
- Copy `pdf_to_tspl.py` to `/usr/local/bin/`
- Install the CUPS filter `pdftolabel` to `/usr/lib/cups/filter/`
- Install the PPD file to `/usr/share/ppd/`
- Create a CUPS printer named `Shopee318Pro`
- Set it as the system default printer
- Restart CUPS

## Usage

### From a browser or document viewer

Select **Shopee318Pro** as your printer. Set paper size to match your label (e.g. A6 for Shopee Express labels). Print as normal.

> **Tip:** Set the default paper size in CUPS so you don't have to pick it each time:
> ```bash
> lpadmin -p Shopee318Pro -o media=iso_a6_105x148mm
> ```

### From the command line

```bash
# Print to printer
python3 /usr/local/bin/pdf_to_tspl.py label.pdf /dev/usb/lp0

# Write TSPL to stdout (for debugging)
python3 /usr/local/bin/pdf_to_tspl.py label.pdf -

# Custom label size
python3 /usr/local/bin/pdf_to_tspl.py label.pdf /dev/usb/lp0 -x 74 -y 105

# Print multiple copies
python3 /usr/local/bin/pdf_to_tspl.py label.pdf /dev/usb/lp0 -n 3
```

## Configuration

Edit the constants at the top of `pdf_to_tspl.py`:

| Variable | Default | Description |
|---|---|---|
| `LABEL_W_MM` | `74` | Label width in mm |
| `LABEL_H_MM` | `105` | Label height in mm |
| `DPI` | `203.2` | Printer resolution (203 DPI standard for most label printers) |
| `GAP_MM` | `3` | Gap between labels |

## How it works

The core of the project is `pdf_to_tspl.py`. When CUPS receives a print job it calls the `pdftolabel` filter, which runs the Python script with the PDF as input.

The script renders the PDF to a raw monochrome PBM bitmap using `pdftoppm`, then wraps the bitmap data in a TSPL `BITMAP` command. The image is automatically scaled to fit the label while preserving aspect ratio and centered with `paste_x`/`paste_y` offsets.

TSPL output looks like:

```
SIZE 74 mm,105 mm
GAP 3 mm,0 mm
DIRECTION 0
CLS
BITMAP 0,0,<row_bytes>,<height>,0,<raw bitmap data>
PRINT 1,1
```

## Troubleshooting

**Permission denied on `/dev/usb/lp0`**
```bash
sudo usermod -aG lp $USER
newgrp lp
```

**Filter failed / no output**
```bash
sudo tail -30 /var/log/cups/error_log
```

**Content too small**

Make sure your document viewer is not scaling the PDF up to A4 before printing. Set the paper size to match the actual PDF size (e.g. A6 for Shopee Express).

**Colors inverted (black/white swapped)**

Toggle the `INVERT` flag in `pdf_to_tspl.py`:
```python
INVERT = True  # change to False
```

## License

MIT
