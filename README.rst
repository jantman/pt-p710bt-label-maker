P-Touch Cube (PT-P710BT) label maker
====================================

This is a small application script to allow printing from the command line on the Brother P-Touch Cube (PT-P710BT). It is based on the "Raster Command Reference" made available by Brother on their support website. Theoretically, it should also work with other label printers that use the same command set, such as the PT-E550W and PT-P750W, but since I don't have access to these devices, I have not been able to verify this.

The script converts a PNG image to the raster format expected by the label printer, and communicates this to the printer over Bluetooth or USB.

Rationale
---------

I wrote this script because of layout limitations encountered in the smartphone apps provided by the manufacturer. While they do make a desktop application available that seems to be more full-featured, it is only available for Microsoft Windows and Mac OS X, neither of which is my operating system of choice. In addition, I wanted the ability to execute label printing operations from the command-line to allow for easy integration with various pipelines.

Similar scripts that exist for the older P-Touch Cube (PT-P300BT), as can be found `here <https://gist.github.com/stecman/ee1fd9a8b1b6f0fdd170ee87ba2ddafd>`__ and `here <https://gist.github.com/dogtopus/64ae743825e42f2bb8ec79cea7ad2057>`__, didn't completely suit my purpose, but provided helpful reference material.

Requirements and installation
-----------------------------

The application script depends on the following packages:

* `pybluez <https://github.com/pybluez/pybluez>`__, for Bluetooth communication. **NOTE** that as of July 13, 2022 this project requires changes that have been merged to master in the `pybluez GitHub repo <https://github.com/pybluez/pybluez>`__ since the ``0.23`` release but have not yet been released `on PyPI <https://pypi.org/project/PyBluez/>`__. As a result, this dependency must be installed from git.
* `pypng <https://github.com/drj11/pypng>`__, to read PNG images
* `packbits <https://github.com/psd-tools/packbits>`__, to compress data to TIFF format
* `pyusb <https://github.com/pyusb/pyusb>`__ for connecting to USB devices.
* `pillow <https://python-pillow.org/>`__ for rendering text.

The application and all dependencies can be installed by cloning the git repository and then running:

    pip install -e .

Note that the installation of ``pybluez`` requires the presence of the `bluez <http://www.bluez.org/>`__ development libraries and ``libbluetooth`` header files (``libbluetooth3-dev``). For most Linux distributions, these should be available through your regular package management system.

Additional Requirements for USB Connection
++++++++++++++++++++++++++++++++++++++++++

When connected via USB, the PT-P710BT identifies itself as a USB printer, presumably for use with Brother's Windows and Mac software. As a result, on any Linux computer (such as many desktop Linux distributions) with ``usblp`` support built-in, the device will generally be claimed by the ``usblp`` driver and assigned a port such as ``/dev/usb/lp0``. This will prevent any other software (such as this application) from communicating with the device over USB (because it's bound to the usblp driver). To remedy this, use one of the following two methods:

1. Remove the ``usblp`` module from your kernel with ``rmmod usblp`` (after plugging the device in). This will disable support for *all* USB printers until the device (or any other USB printer) is plugged in again. You will have to do this every time you plug the device in.
2. Create a ``udev`` rule to unbind the device from the ``usblp`` driver. This is a bit of a hack as the ``usblp`` driver will still be bound to the device when it's plugged in, and then quickly unbound. Aside from the possible noise from the binding/unbinding (such as your OS briefly telling you that a new printer was attached), this will provide a simple user experience where nothing specific needs to be done when the device is plugged in.

To create the udev rule, create a file (e.g. ``/etc/udev/rules.d/99-brother-pt-p710.rules``) with the following contents (largely based on `this StackExchange answer <https://unix.stackexchange.com/a/165686>`__ :

::

    # prevent usblb driver from binding Brother PT-P710BT label printer
    ACTION=="add", ATTR{idVendor}=="04f9", ATTR{idProduct}=="20af", TAG-="systemd", ENV{SYSTEMD_WANTS}=""
    ACTION=="add", ATTR{idVendor}=="04f9", ATTR{idProduct}=="20af", RUN="/bin/sh -c '/bin/echo -n $kernel:1.0 > /sys/bus/usb/drivers/usblp/unbind'"
    ACTION=="add", ATTR{idVendor}=="04f9", ATTR{idProduct}=="20af", OWNER="YourUsername", GROUP="YourGroup"

Then, run ``udevadm control --reload-rules`` to load the new rule and try plugging the printer in.

Usage
-----

Printing Images
+++++++++++++++

``pt-label-printer --help`` shows us the options for the image printing entrypoint:

::

    $ pt-label-printer -h
    usage: pt-label-printer [-h] [-v] [-C BT_CHANNEL] [-c NUM_COPIES] (-B BT_ADDRESS | -U) [-T {24,18,12,9,6,4}] IMAGE_PATH [IMAGE_PATH ...]

    Brother PT-P710BT Label Printer controller

    positional arguments:
      IMAGE_PATH            Paths to images to print

    options:
      -h, --help            show this help message and exit
      -v, --verbose         debug-level output.
      -C BT_CHANNEL, --bt-channel BT_CHANNEL
                            BlueTooth Channel (default: 1)
      -c NUM_COPIES, --copies NUM_COPIES
                            Print this number of copies of each image (default: 1)
      -B BT_ADDRESS, --bluetooth-address BT_ADDRESS
                            BlueTooth device (MAC) address to connect to; must already be paired
      -U, --usb             Use USB instead of bluetooth
      -T {24,18,12,9,6,4}, --tape-mm {24,18,12,9,6,4}
                            Width of tape in mm. Use 4 for 3.5mm tape.

A typical invocation for BlueTooth is:

::

    pt-label-printer -B <BT_ADDRESS> <IMAGE_PATH> [<IMAGE_PATH> ...]

The expected parameters are the following:

* **IMAGE_PATH(s)** The path(s) to one or more PNG files to be printed. The images need to be the proper height for the tape size (see below), while the width is variable depending on how long you want your label to be. The script bases itself on the PNG image's alpha channel, and prints all pixels that are not fully transparent (alpha channel value greater than 0).
* **BT_ADDRESS** The Bluetooth address of the printer. The ``bluetoothctl`` application (part of the aforementioned ``bluez`` stack; on some distributions such as Arch, it may be part of a separate package like ``bluez-utils``) can be used to discover the printer's address, and pair with it from the command line:

    ::

        $> bluetoothctl
        [bluetooth]# scan on
        [NEW] Device A0:66:10:CA:E9:22 PT-P710BT6522
        [bluetooth]# pair A0:66:10:CA:E7:42
        [bluetooth]# exit
        $>

* **BT_CHANNEL** If you need to specify a Bluetooth RFCOMM port number other than the default of ``1``, that can be done with the ``-C <channel>`` or ``--channel <channel>`` option.
* **NUM_COPIES** You can print N copies of the label(s) with the ``-c N`` or ``--copies N`` options. If you specify multiple images to print, you will get N copies of **each** image.
* **-T** / **--tape-mm** - Tape width in mm to print on (the printer must be loaded with this size tape). Use 4 for 3.5mm tape (which the underlying API does). This program does not currently support detection of the current tape; if you try to print to a tape size other than what is in the printer, an exception will be raised.

A typical invocation for printing over USB is:

::

    pt-label-printer -U <image-path>

Omit all of the bluetooth-related options (BT_ADDRESS, BT_CHANNEL, etc.) and specify the ``-U`` / ``--usb`` option instead. This currently only supports one printer at a time (i.e. if you plug multiple PT-P710BT printers in via USB at the same time, the first one found will be used for printing).

Image File Height
^^^^^^^^^^^^^^^^^

To determine the proper image file height for a given label size, see ``TAPE_MM_TO_PX`` in ``media_info.py``. This maps the label with in mm to pixels high for the image.

Rendering and Printing Text
+++++++++++++++++++++++++++

The ``pt-label-maker`` entrypoint will render specified text as a PNG image and print it, all in one command.

::

    usage: pt-label-maker [-h] [-v] [-C BT_CHANNEL] [-c NUM_COPIES] (-B BT_ADDRESS | -U | -L) [-T {24,18,12,9,6,4}] [--lp-dpi LP_DPI] [--lp-width-px LP_WIDTH_PX] [--lp-options LP_OPTIONS] [-s] [--filename FILENAME] [-P]
                          [--maxlen-px MAXLEN_PX | --maxlen-inches MAXLEN_IN | --maxlen-mm MAXLEN_MM] [--max-font-size MAX_FONT_SIZE] [-r | -R | -p] [-F] [--cable-diameter-mm CABLE_DIAMETER_MM | --cable-diameter-inches CABLE_DIAMETER_IN] [--no-fold-marks] [-f FONT_FILENAME] [-a {center,left,right}]
                          LABEL_TEXT [LABEL_TEXT ...]

    Brother PT-P710BT Label Maker

    positional arguments:
      LABEL_TEXT            Text to print on label

    options:
      -h, --help            show this help message and exit
      -v, --verbose         debug-level output.
      -C BT_CHANNEL, --bt-channel BT_CHANNEL
                            BlueTooth Channel (default: 1)
      -c NUM_COPIES, --copies NUM_COPIES
                            Print this number of copies of each image (default: 1)
      -B BT_ADDRESS, --bluetooth-address BT_ADDRESS
                            BlueTooth device (MAC) address to connect to; must already be paired
      -U, --usb             Use USB instead of bluetooth
      -L, --lp              Instead of printing to PT-P710 via BT or USB, print to a regular lp printer, i.e. for testing or for CUPS-supported label printers
      -T {24,18,12,9,6,4}, --tape-mm {24,18,12,9,6,4}
                            Width of tape in mm. Use 4 for 3.5mm tape. Default: 24
      --lp-dpi LP_DPI       DPI for lp printing; defaults to 203dpi
      --lp-width-px LP_WIDTH_PX
                            Width in pixels for printing via LP; default 203
      --lp-options LP_OPTIONS
                            Options to pass to lp when printing
      -s, --save-only       Save generates image to current directory and exit
      --filename FILENAME   Filename to save image to; default: 20230526T094723.png
      -P, --preview         Preview image after generating and ask if it should be printed
      --maxlen-px MAXLEN_PX
                            Maximum label length in pixels
      --maxlen-inches MAXLEN_IN
                            Maximum label length in inches
      --maxlen-mm MAXLEN_MM
                            Maximum label length in mm
      --max-font-size MAX_FONT_SIZE
                            Maximum font size to use
      -r, --rotate          Rotate text 90°, printing once at start of label. Use the --maxlen options to set label length.
      -R, --rotate-repeat   Rotate text 90° and print repeatedly along length of label. Use the --maxlen options to set label length.
      -p, --patch-panel     Generate a patch panel label, for ports that are spaced maxlen on center and as many ports as arguments are specified
      -F, --flag            Flag mode: print the text in each half of the label with a blank section in the middle to wrap around a cable, so the halves can be stuck together to form a flag. Use the --maxlen options to set the total label length. Combine with -r to rotate the text in each half 90°.
      --cable-diameter-mm CABLE_DIAMETER_MM
                            Flag mode only: cable diameter in mm, used to size the wrap section; default: wrap section is 10% of label length
      --cable-diameter-inches CABLE_DIAMETER_IN
                            Flag mode only: cable diameter in inches, used to size the wrap section; default: wrap section is 10% of label length
      --no-fold-marks       Flag mode only: do not print fold guide marks at the edges of the wrap section
      -W, --wrap            Attempt to automatically word-wrap text for best fit on label
      -f FONT_FILENAME, --font-filename FONT_FILENAME
                            Font filename; Default: /usr/local/share/fonts/ttf/Overpass/Overpass_Regular.ttf (default taken from PT_FONT_FILE env var if set)
      -a {center,left,right}, --align {center,left,right}
                            Text alignment; default: center

This command accepts the same Bluetooth/USB and NUM_COPIES options as ``pt-label-printer`` plus a number of options specific to text rendering:

* **LABEL_TEXT** - Instead of accepting IMAGE_PATHs to print, this command accepts strings of text to render and print. Text will be printed in the largest font size that fits. You can specify multiple arguments to print multiple labels; ``pt-label-maker -U foo bar baz`` will print three (3) labels, one with the word "foo", one with "bar", and one with "baz". You can also specify newlines/linebreaks in the text to generate multi-line labels; do this however your shell handles it (i.e. in Bash to print a 3-line label with "foo", "bar", and "baz" on separate lines you could run ``pt-label-maker -U $'foo\nbar\nbaz'``.
* **-s** / **--save-only** - Instead of printing the label, just render the text to PNG and save it to disk. You can specify a filename with **--filename** or use the default which is named after the current timestamp. Note that **save-only does not currently support multiple labels**; only the last one will be saved.
* **-P** / **--preview** - When run with this option, each image will be displayed before printing. The user will be asked with an interactive y/N prompt if they want to print the previewed image.
* **--maxlen-px** / **--maxlen-inches** / **--maxlen-mm** - These options, mutually exclusive, allow specifying a maximum label length which the text will be fit to. Length can be specified in pixels (px), inches, or millimeters (mm), respectively. The PT-P710BT prints at 180 pixels per inch (PPI).
* **-r** / **--rotate** - Print the specified text rotated 90°, as large as will fit across the width of the label. Text is printed once along the leading edge of the label. Label length will be determined by the ``--maxlen`` arguments.
* **-R** / **--rotate-repeat** - Print the specified text rotated 90°, as large as will fit across the width of the label. Text is printed repeated along the length of the label, as many times as will fit with the default line spacing of the font. Label length will be determined by the ``--maxlen`` arguments. This option replicates a standard cable wrap label (for average Cat6 cable, maxlen should be 1.4 inches).
* **-p** / **--patch-panel** - Print a single long patch panel-style label, where each ``LABEL_TEXT`` argument is in a maxlen-length block, separated by vertical lines.
* **-F** / **--flag** - Print a flag-style cable label. The text is printed once in each half of the label, with a blank wrap section in the middle. Wrap the middle section around the cable and stick the two halves together back-to-back to form a flag with the text visible on both sides. The total label length is set by the ``--maxlen`` arguments. The wrap section is sized to the cable using **--cable-diameter-mm** or **--cable-diameter-inches** (wrap length is π × diameter), or defaults to 10% of the label length. By default the text runs along the length of the label, which reads upright on a vertical cable. Combined with **-r** / **--rotate**, the text in each half is rotated 90° with its top toward the cable, which reads upright when the flag hangs below a horizontal cable. Short fold guide marks are printed at the top and bottom edges of the label at each end of the wrap section; disable them with **--no-fold-marks**. Cannot be combined with ``-R``, ``-p``, or ``--fixed-len-px``. Example for a 6mm Cat6 cable on 12mm tape: ``pt-label-maker -U -T 12 -F --maxlen-inches 3 --cable-diameter-mm 6 PP-12``
* **-f** / **--font-filename** - The filename of the TrueType/OpenType font to render text in. This file must already be installed in your system font paths. This parameter is passed directly to Pillow's `ImageFont.truetype() method <https://pillow.readthedocs.io/en/stable/reference/ImageFont.html#PIL.ImageFont.truetype>`__. The default value of ``DejaVuSans.ttf`` can be overridden with the ``PT_FONT_FILE`` environment variable.
* **-a** / **--align** - This sets the text alignment within the space of the label. Valid values are ``center`` (default), ``left``, or ``right``.
* **-W** / **--wrap** - Automatically word-wrap text for best fit using the largest possible font. Uses the awesome `atomicparade/pil_autowrap <https://github.com/atomicparade/pil_autowrap>`__ library.

Rendering and Printing Barcodes
+++++++++++++++++++++++++++++++

The ``pt-barcode-label`` entrypoint renders one or more values as barcodes (using `python-barcode <https://github.com/WhyNotHugo/python-barcode>`__), by default with the value printed as human-readable text below the barcode, and prints them, all in one command.

::

    usage: pt-barcode-label [-h] [-v] [-C BT_CHANNEL] [-c NUM_COPIES] (-B BT_ADDRESS | -U | -L) [-T {24,18,12,9,6,4}] [--lp-dpi LP_DPI] [--lp-width-px LP_WIDTH_PX] [--lp-options LP_OPTIONS] [-s] [--filename FILENAME] [-P]
                            [-S {CODABAR,Code128,Code39,EuropeanArticleNumber13,ITF,UniversalProductCodeA}] [-t] [-R BARCODE_RATIO] [-W] [-M] [--min-bar-height-mm MIN_BAR_HEIGHT_MM] [-F] [--maxlen-px MAXLEN_PX | --maxlen-inches MAXLEN_IN |
                            --maxlen-mm MAXLEN_MM] [--fixed-len-px FIXED_LEN_PX] [-f FONT_FILENAME]
                            BARCODE_VALUE [BARCODE_VALUE ...]
    
    Brother PT-P710BT Barcode Label Maker
    
    positional arguments:
      BARCODE_VALUE         Value for barcode
    
    options:
      -h, --help            show this help message and exit
      -v, --verbose         debug-level output.
      -C, --bt-channel BT_CHANNEL
                            BlueTooth Channel (default: 1)
      -c, --copies NUM_COPIES
                            Print this number of copies of each image (default: 1)
      -B, --bluetooth-address BT_ADDRESS
                            BlueTooth device (MAC) address to connect to; must already be paired
      -U, --usb             Use USB instead of bluetooth
      -L, --lp              Instead of printing to PT-P710 via BT or USB, print to a regular lp printer, i.e. for testing or for CUPS-supported label printers
      -T, --tape-mm {24,18,12,9,6,4}
                            Width of tape in mm. Use 4 for 3.5mm tape. Default: 24
      --lp-dpi LP_DPI       DPI for lp printing; defaults to 203dpi
      --lp-width-px LP_WIDTH_PX
                            Width in pixels for printing via LP; default 203
      --lp-options LP_OPTIONS
                            Options to pass to lp when printing
      -s, --save-only       Save generates image to current directory and exit
      --filename FILENAME   Filename to save image to; default: 20261006T053237.png
      -P, --preview         Preview image after generating and ask if it should be printed
      -S, --symbology {CODABAR,Code128,Code39,EuropeanArticleNumber13,ITF,UniversalProductCodeA}
                            Barcode symbology to use
      -t, --no-text         Do not show text below barcode
      -R, --barcode-ratio BARCODE_RATIO
                            Fraction of the label height (greater than 0, less than 1) to use for the barcode itself; default 0.5. The remaining height is used for the text below the barcode, so a smaller value gives the text a larger font. Useful on
                            large labels, where the default gives the barcode more height than it needs; e.g. 0.25 on a 2x4 inch label.
      -W, --wrap            Word-wrap the text below the barcode onto multiple lines if that allows a larger font. Text is broken at whitespace or after any of: -_/.:
      -M, --max-text        Make the text as large as possible while keeping a scannable barcode: shrinks the bars to --min-bar-height-mm, gives the text all of the remaining label height, and implies --wrap. Cannot be combined with --barcode-ratio.
      --min-bar-height-mm MIN_BAR_HEIGHT_MM
                            Height of the bars themselves with --max-text; default 6.35mm (0.25 inch). Raise this if your scanner has trouble reading the labels.
      -F, --flag            Flag mode: place two rotated barcodes at opposite ends of the label for wrapping around wires. Requires maxlen to be specified.
      --maxlen-px MAXLEN_PX
                            Maximum label length in pixels
      --maxlen-inches MAXLEN_IN
                            Maximum label length in inches
      --maxlen-mm MAXLEN_MM
                            Maximum label length in mm
      --fixed-len-px FIXED_LEN_PX
                            Center barcode in fixed length image of this many pixels long
      -f, --font-filename FONT_FILENAME
                            Font filename; Default: DejaVuSans.ttf (default taken from PT_FONT_FILE env var if set)

This command accepts the same Bluetooth/USB, NUM_COPIES, ``-T`` / ``--tape-mm``, lp, **-s** / **--save-only**, **--filename**, **-P** / **--preview**, and **-f** / **--font-filename** options as ``pt-label-maker``, plus a number of options specific to barcodes:

* **BARCODE_VALUE** - One or more values to encode. Each value is printed as a separate label; ``pt-barcode-label -U A1 A2 A3`` prints three labels. The value must be valid for the chosen symbology (e.g. numeric only, of the correct length, for EAN-13 and UPC-A).
* **-S** / **--symbology** - The barcode symbology to use; default ``Code128``. The available choices are the symbologies provided by python-barcode, as shown in the usage output above.
* **-t** / **--no-text** - Print only the barcode, using the full height of the label for the bars, without the value as text below it.
* **--maxlen-px** / **--maxlen-inches** / **--maxlen-mm** - These options, mutually exclusive, set a maximum label length. The text below the barcode is fit (and, with **--wrap**, wrapped) to this length. The barcode itself is drawn at its minimum printable module (narrow bar) width with quiet zones on each end, so for long values it may be longer than this. Required for flag mode.
* **--fixed-len-px** - Center the barcode (and text) in a label of exactly this many pixels long. In flag mode, this sets the total label length.
* **-R** / **--barcode-ratio** - The fraction of the label height, greater than 0 and less than 1, used for the bars themselves; default ``0.5``. The text is vertically centered in the remaining height and gets half of it, so a smaller value gives the text a larger font. This is useful on large labels, where the default gives the barcode far more height than it needs to scan; e.g. ``0.25`` on a 2x4 inch label. A warning is logged if the resulting bars are shorter than 6.35mm (0.25 inch), below which scanners tend to have trouble. In flag mode, the text in each end gets ``(1 - ratio) / 2`` of that end's height.
* **-W** / **--wrap** - Word-wrap the text below the barcode onto multiple lines when that allows a larger font. The largest font size at which the wrapped text fits within the text area and ``--maxlen`` is used. Since barcode values often contain no spaces, text can be broken at whitespace or after any of the characters ``-``, ``_``, ``/``, ``.``, and ``:`` (e.g. ``SERVER-RACK-01`` can be printed as ``SERVER-`` / ``RACK-01``). Has no effect without one of the ``--maxlen`` options. Not supported in flag mode or with ``--no-text``.
* **-M** / **--max-text** - Print the text as large as possible while keeping a scannable barcode. The bars are shrunk to the minimum height set by **--min-bar-height-mm**, the text is allowed to use all of the label height below the barcode (instead of only half of what's left, as with **--barcode-ratio**), and **--wrap** is enabled. This is intended for labels that need to be readable at a distance, such as on large tapes or with ``-L`` on 2x4 inch labels. Note that on narrow tapes (e.g. 12mm) the default layout already prints bars shorter than the minimum, so ``--max-text`` will make the text *smaller* in order to keep the barcode scannable; an error is printed if the minimum bar height does not fit on the label at all. Cannot be combined with ``--barcode-ratio``, ``--no-text``, or flag mode.
* **--min-bar-height-mm** - The height of the bars themselves when using **--max-text**; default 6.35mm (0.25 inch). Raise this if your scanner has trouble reading the labels.
* **-F** / **--flag** - Print a flag-style barcode label for wrapping around wires or cables. A barcode (with text, unless ``--no-text`` is given) is printed rotated 90° at each end of the label, with blank space in the middle to wrap around the cable. Requires one of the ``--maxlen`` options; the total label length is ``--fixed-len-px`` if given, otherwise the maxlen.

Examples:

* A Code128 barcode on 24mm tape, at most 2 inches long: ``pt-barcode-label -U -T 24 --maxlen-inches 2 SERVER-RACK-01``
* The same, with the largest readable text that still leaves a scannable barcode: ``pt-barcode-label -U -T 24 --maxlen-inches 2 -M SERVER-RACK-01``
* Test the layout of a 2x4 inch label without printing, saving it as a PNG: ``pt-barcode-label -L --lp-dpi 203 --lp-width-px 406 --maxlen-inches 4 -M -s --filename out.png 'rack 12 shelf 3'``
* A flag label for a cable on 12mm tape: ``pt-barcode-label -U -T 12 -F --maxlen-inches 3 PP-12``

Printing With lp
^^^^^^^^^^^^^^^^

With the ``-L`` / ``--lp`` option, it's possible to print rendered labels to a standard printer via ``lp`` instead of printing to the PT-P710. This is useful for testing layout, or for printing to generic label printers that are supported via CUPS. In this case the ``-T`` / ``--tape-mm`` option is ignored and the ``--lp-dpi``, ``--lp-width-px``, and ``--lp-options`` options should be used.

Usage as a Library
------------------

Both the image printing and the text rendering and printing classes can be used from other Python scripts/applications as libraries. Detailed documentation is not currently available, but see the ``main()`` methods of ``label_maker.py`` and ``label_printer.py`` for examples of how to use the relevant classes.

License
-------

.. image:: https://i.creativecommons.org/l/by/4.0/88x31.png
   :alt: This work is licensed under a Creative Commons Attribution 4.0 International License
   :target: http://creativecommons.org/licenses/by/4.0/

This work is licensed under a `Creative Commons Attribution 4.0 International License <http://creativecommons.org/licenses/by/4.0/>`__
