# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Command-line tools (and importable library) for printing labels on the Brother P-Touch Cube PT-P710BT over Bluetooth (pybluez, RFCOMM) or USB (pyusb), based on Brother's "Raster Command Reference". Rendered labels can alternatively be sent to a CUPS printer via `lp` for layout testing.

## Development

- Install: `pip install -e .` (a `venv/` exists in the repo root). `setup.py` is the source of truth for dependencies; `requirements.txt` is stale. pybluez is installed from a pinned git commit and needs bluez dev headers (`libbluetooth-dev`).
- There is no test suite, linter config, or CI. Verify rendering changes without hardware using `-s/--save-only` (writes a PNG; requires `-U`, `-B`, or `-L` to satisfy the required mutually-exclusive arg group) or `-P/--preview`, e.g.:
  - `pt-label-maker -U -s --filename out.png 'foo'`
  - `pt-barcode-label -U -s --filename out.png -T 24 --maxlen-inches 2 ABC123`
- Version lives in `pt_p710bt_label_maker/version.py`.

## Entry points (setup.py `console_scripts`)

- `pt-label-printer` → `label_printer:main` — prints existing PNG files.
- `pt-label-maker` → `label_maker:main` — renders text to PNG (`LabelImageGenerator`, `patch_panel_label_generator`) then prints.
- `pt-barcode-label` → `barcode_label:main` — renders barcodes via python-barcode (`BarcodeLabelGenerator`, `FlagModeGenerator` for wire-wrap "flag" labels) then prints.

The `main()` functions of `label_maker` and `barcode_label` duplicate the connector/printer dispatch from `label_printer.main()` (marked "Begin code copied from label_printer.py"); keep them in sync when changing it. Shared CLI args (`-v`, `-B/-U/-L`, `-C`, `-c`, `-T`) come from `utils.add_printer_args`.

## Architecture / data flow

1. **Image generation** (`label_maker.py`, `barcode_label.py`): Pillow draws a label image whose **height** is the printable tape width in pixels (`media_info.TAPE_MM_TO_PX`, or `--lp-width-px` for lp) and whose **width** is the label length. Printer resolution is 180 DPI (`DPI` class attrs); `--maxlen-*` options are converted to px using that (or `--lp-dpi`). Text is fit by searching font sizes for the largest that fits the box; `pil_autowrap.py` is a vendored copy of atomicparade/pil_autowrap used for `--wrap`.
2. **Printed pixels are determined by the PNG alpha channel** — any pixel with alpha > 0 prints. Generators must therefore produce transparent backgrounds (e.g. `BarcodeLabelGenerator._white_to_transparent`). Images are passed around as in-memory PNG `BytesIO` (`file_obj` property).
3. **Rasterization** (`label_rasterizer.py`): `encode_png` validates image height against the tape size (raises `InvalidImageHeightException`), rotates the image 90°, pads each line with `TAPE_MM_TO_MARGIN_PX` margins, and packs to 1 bit/pixel; `rasterize` splits into 16-byte lines, PackBits-compressed (`G` command) or a zero-line (`Z`).
4. **Printer protocol** (`label_printer.PtP710LabelPrinter.print_images`): sends invalidate/initialize, requests and parses status, sets modes/margin/compression, then per image sends print-info + raster data + print command (feed only after the last image), and loops reading status until `PrintingCompleted`. Status bytes are parsed in `status_message.py`; printer error bits map to exception classes in `exceptions.py` (in `_receive_status_information_response`).
5. **Transport** (`connectors.py`): `BluetoothConnector` and `UsbConnector` (VID 0x04F9 / PID 0x20AF) share a `send`/`receive` interface. On Linux the kernel `usblp` driver often claims the device; `UsbConnector` detaches it, and the README documents an alternative udev rule. `lp_printer.LpPrinter` bypasses all of this and shells out to `lp`.

Tape sizes are keyed by mm in `media_info.py`; `4` means 3.5mm tape.
