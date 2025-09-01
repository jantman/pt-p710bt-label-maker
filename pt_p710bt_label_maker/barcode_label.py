import sys
import os
import argparse
import logging
from typing import Optional, Tuple, Dict, Any, List, Literal, Callable
from datetime import datetime
from math import ceil, floor
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from barcode.writer import ImageWriter
from barcode.base import Barcode

from pt_p710bt_label_maker.utils import (
    set_log_debug, set_log_info, add_printer_args
)
from pt_p710bt_label_maker.label_printer import (
    Connector, UsbConnector, BluetoothConnector, PtP710LabelPrinter
)
from pt_p710bt_label_maker.media_info import TAPE_MM_TO_PX
from pt_p710bt_label_maker.lp_printer import LpPrinter

Alignment = Literal["center", "left", "right"]

BARCODE_CLASSES: Dict[str, Callable] = {
    x.__name__: x for x in Barcode.__subclasses__()
}

FORMAT = "[%(asctime)s %(levelname)s] %(message)s"
logging.basicConfig(level=logging.WARNING, format=FORMAT)
logger = logging.getLogger()


class BarcodeLabelGenerator:

    # Printer DPI
    DPI: int = 180

    def __init__(
        self, value: str, height_px: int, maxlen_px: Optional[int] = None,
        font_filename: str = 'DejaVuSans.ttf',
        barcode_class_name: str = 'Code128', show_text: bool = True,
        fixed_len_px: Optional[int] = None
    ):
        self.value: str = value
        self.show_text: bool = show_text
        self.font_filename: str = font_filename
        self.symbology: str = barcode_class_name
        self.maxlen_px: Optional[int] = maxlen_px
        self.barcode_cls: Callable = BARCODE_CLASSES[self.symbology]
        # for height, see media_info.TAPE_MM_TO_PX
        self.height_px: int = height_px
        self.fonts: Dict[int, ImageFont.FreeTypeFont] = self._get_fonts(
            font_file=font_filename
        )
        logger.debug('Loaded %d font options', len(self.fonts))
        logger.debug(
            'Initializing BarcodeLabelGenerator value="%s", symbology="%s" (%s)'
            ', height_px=%d, maxlen_px=%s, show_text=%s',
            self.value, self.symbology, self.barcode_cls, self.height_px,
            maxlen_px, show_text
        )
        self.num_modules: int
        self.mod_width_px: int
        self.num_modules, self.mod_width_px = self._get_num_modules()
        if self.mod_width_px > 2:
            # 11 quiet modules on each end
            self.mod_width_px = floor(self.maxlen_px / (self.num_modules + 22))
        logger.debug('Module width: %spx', self.mod_width_px)
        self._barcode_image: Image = self._generate_barcode_image(
            self.maxlen_px
        )
        logger.info(
            'Generated barcode image of %spx wide x %spx high',
            self._barcode_image.width, self._barcode_image.height
        )
        self._image: Image
        if self.show_text:
            self._image = self._generate_combined_image()
        else:
            self._image = self._barcode_image
        if fixed_len_px:
            self._image = self._center_in_width(self._image, fixed_len_px)

    def _white_to_transparent(self, img: Image) -> Image:
        img = img.convert("RGBA")
        datas = img.getdata()
        newData = []
        for item in datas:
            if item[0] == 255 and item[1] == 255 and item[2] == 255:
                newData.append((255, 255, 255, 0))
            else:
                newData.append(item)
        img.putdata(newData)
        return img

    def _generate_combined_image(self) -> Image:
        font: ImageFont.FreeTypeFont
        text_w: int
        text_h: int
        font, text_w, text_h = self._fit_text_to_box(
            self.height_px / 4, self.maxlen_px
        )
        width = max([self._barcode_image.width, text_w])
        logger.debug(
            'Generating %d x %d RGBA image', width, self.height_px
        )
        img: Image = Image.new(
            'RGBA',
            (width, self.height_px),
            (255, 255, 255, 0)
        )
        # paste the barcode at the top left
        img.paste(
            self._barcode_image,
            box=(
                floor((width - self._barcode_image.width) / 2),
                0
            )
        )
        # now add the text
        draw: ImageDraw = ImageDraw.Draw(img)
        pos: Tuple[int, int] = (
            floor(width / 2),
            self._barcode_image.height +
            floor((self.height_px - self._barcode_image.height) / 2)
        )
        kwargs: Dict[str, Any] = {
            'xy': pos,
            'text': self.value,
            'fill': (0, 0, 0, 255),
            'font': font,
            'anchor': 'mm'
        }
        draw.text(**kwargs)
        return img

    def _generate_barcode_image(self, maxlen_px: Optional[int]) -> Image:
        self.writer: ImageWriter = ImageWriter(format='PNG')
        logger.debug('Writing image at %d DPI', self.DPI)
        self.writer.dpi = self.DPI
        writer_opts: Dict = self._writer_opts()
        logger.debug('Setting writer options: %s', writer_opts)
        self.writer.set_options(writer_opts)
        logger.debug('Generating barcode image')
        self.barcode: Barcode = self.barcode_cls(self.value, writer=self.writer)
        return self._white_to_transparent(
            self.barcode.render(writer_options=writer_opts)
        )

    def _get_num_modules(self, _mod_width: int = 2) -> Tuple[int, int]:
        logger.debug(
            'Calculating number of modules for "%s" with DPI=%s, module_width=%s',
            self.value, self.DPI, self.px2mm(1)
        )
        writer: ImageWriter = ImageWriter(format='PNG')
        writer.dpi = self.DPI
        writer_opts: Dict = dict(self.barcode_cls.default_writer_options)
        writer_opts['module_width'] = self.px2mm(_mod_width)
        writer_opts['quiet_zone'] = 0
        writer.set_options(writer_opts)
        try:
            barcode: Barcode = self.barcode_cls(self.value, writer=writer)
            _image: Image = barcode.render(writer_options=writer_opts)
        except ValueError:
            logger.warning(
                'Invalid minimum barcode module width; increasing to %spx',
                _mod_width
            )
            return self._get_num_modules(_mod_width=_mod_width + 1)
        logger.debug(
            'Minimum barcode width (1 module == %s px): %s', _mod_width, _image.width
        )
        return _image.width, _mod_width

    def _get_fonts(
        self, font_file: str = 'DejaVuSans.ttf', min_size: int = 4,
        max_size: int = 144, size_step: int = 2
    ) -> Dict[int, ImageFont.FreeTypeFont]:
        logger.debug(
            'Generating font options for TrueType font %s: min_size=%d, '
            'max_size=%d, size_step=%d',
            font_file, min_size, max_size, size_step
        )
        return {
            i: ImageFont.truetype(font_file, size=i)
            for i in range(min_size, max_size, size_step)
        }

    def _get_text_dimensions(
        self, font: ImageFont.FreeTypeFont, draw: ImageDraw, text: str
    ) -> Tuple[int, int]:
        """Returns text dimensions (width, height) for a given font and text."""
        bbox = font.getbbox(text)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        return width, height

    def _fit_text_to_box(
        self, max_height: int, max_width: Optional[int] = None
    ) -> Tuple[ImageFont.FreeTypeFont, int, int]:
        """
        Find the largest ImageFont that fits the label height and optionally a
        maximum width. Return a 3-tuple of that ImageFont and the resulting text
        width (int) and height (int).
        """
        # temporary image and draw
        img: Image = Image.new("RGB", (2, 2), (255, 255, 255))
        draw: ImageDraw = ImageDraw.Draw(img)
        logger.debug(
            'Finding maximum font size that fits "%s" in %d pixels high and '
            '%s pixels wide', self.value, max_height, max_width
        )
        last: int = min(self.fonts.keys())
        last_width: int = self._get_text_dimensions(
            self.fonts[last], draw, self.value
        )[0]
        last_height: int = self._get_text_dimensions(
            self.fonts[last], draw, self.value
        )[1]
        for i in sorted(self.fonts.keys(), reverse=True):
            try:
                w, h = self._get_text_dimensions(
                    self.fonts[i], draw, self.value
                )
            except OSError as ex:
                logger.debug('Error on font size %d: %s', i, ex, exc_info=True)
                continue
            logger.debug('Text dimensions for size %d: %d x %d', i, w, h)
            if h <= max_height and (max_width is None or w <= max_width):
                last = i
                last_width = w
                last_height = h
                break
        last_width = ceil(last_width)
        logger.debug(
            'Font size %d is largest to fit; resulting width: %dpx; height: '
            '%dpx', last, last_width, last_height
        )
        return self.fonts[last], last_width, last_height

    def mm2px(self, mm: float) -> float:
        # copied from barcode.writer
        return (mm / 25.4) * self.DPI

    def px2mm(self, px: float) -> float:
        return (px / self.DPI) * 25.4

    def pt2mm(self, pt: float) -> float:
        return pt * 0.352777778

    def mm2pt(self, mm: float) -> float:
        return mm / 0.352777778

    def _writer_opts(self) -> Dict:
        result: Dict = dict(self.barcode_cls.default_writer_options)
        result['font_path'] = self.font_filename
        result['write_text'] = False
        result['module_width'] = self.px2mm(self.mod_width_px)
        result['quiet_zone'] = self.px2mm(11)
        if self.show_text:
            result['module_height'] = self.px2mm(floor(self.height_px / 2))
        else:
            result['module_height'] = self.px2mm(self.height_px)
        return result

    def save(self, filename: str):
        logger.info('Saving image to: %s', filename)
        self._image.save(filename)

    def show(self):
        self._image.show()
        i = input('Print this image? [y|N]').strip()
        if i not in ['y', 'Y']:
            raise SystemExit(1)

    def _center_in_width(self, img: Image, width_px: int) -> Image:
        img_w, img_h = img.size
        background: Image = Image.new(
            'RGBA',
            (width_px, img_h),
            (255, 255, 255, 0)
        )
        bg_w, bg_h = background.size
        offset = ((bg_w - img_w) // 2, (bg_h - img_h) // 2)
        background.paste(img, offset)
        return background

    @property
    def file_obj(self) -> BytesIO:
        i: BytesIO = BytesIO()
        self._image.save(i, format='PNG')
        i.seek(0)
        return i


class FlagModeGenerator:
    """
    Generates flag-style barcode labels with two rotated barcodes at opposite ends
    for wrapping around wires/cables.
    """
    
    def __init__(
        self, value: str, height_px: int, maxlen_px: int,
        font_filename: str = 'DejaVuSans.ttf',
        barcode_class_name: str = 'Code128', show_text: bool = True,
        fixed_len_px: Optional[int] = None
    ):
        self.value = value
        self.height_px = height_px
        self.maxlen_px = maxlen_px
        self.font_filename = font_filename
        self.barcode_class_name = barcode_class_name
        self.show_text = show_text
        self.fixed_len_px = fixed_len_px
        
        if maxlen_px is None:
            raise ValueError("Flag mode requires maxlen to be specified")
        
        logger.debug(
            'Initializing FlagModeGenerator value="%s", height_px=%d, maxlen_px=%d, fixed_len_px=%s',
            value, height_px, maxlen_px, fixed_len_px
        )
        
        self._image = self._generate_flag_image()
    
    def _generate_flag_image(self) -> Image:
        """Generate the flag-style image with rotated barcodes at each end."""
        
        # Use fixed_len_px if provided, otherwise use maxlen_px
        total_width = self.fixed_len_px if self.fixed_len_px is not None else self.maxlen_px
        
        # Calculate dimensions for the rotated barcodes
        # When rotated 90°, the barcode height becomes width, and width becomes height
        # So we need the barcode to fit within the tape height when rotated
        barcode_max_width_when_rotated = self.height_px
        
        # We'll allocate roughly 1/3 of the total length for each barcode
        # But ensure minimum viable barcode length
        single_barcode_length = max(total_width // 3, 150)  # minimum 150px
        
        logger.debug(
            'Flag mode: total_width=%dpx, single_barcode_length=%dpx, '
            'barcode_max_width_when_rotated=%dpx',
            total_width, single_barcode_length, barcode_max_width_when_rotated
        )
        
        # Generate a single barcode that will fit when rotated
        # The height_px for the generator should be what will become the width after rotation
        # Use None for maxlen to let the barcode size itself optimally, then we'll constrain it
        barcode_gen = BarcodeLabelGenerator(
            value=self.value,
            height_px=barcode_max_width_when_rotated,
            maxlen_px=single_barcode_length,
            font_filename=self.font_filename,
            barcode_class_name=self.barcode_class_name,
            show_text=self.show_text
        )
        
        # Get the generated barcode image
        barcode_img = barcode_gen._image
        
        # If the barcode is too wide for our allocation, we'll scale it down
        if barcode_img.width > single_barcode_length:
            scale_factor = single_barcode_length / barcode_img.width
            new_width = int(barcode_img.width * scale_factor)
            new_height = int(barcode_img.height * scale_factor)
            barcode_img = barcode_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            logger.debug('Scaled barcode from original size to %dx%d', new_width, new_height)
        
        # Rotate the barcode images
        left_barcode = barcode_img.rotate(-90, expand=True)
        right_barcode = barcode_img.rotate(90, expand=True)
        
        logger.debug(
            'Generated barcode: %dx%d, rotated left: %dx%d, rotated right: %dx%d',
            barcode_img.width, barcode_img.height,
            left_barcode.width, left_barcode.height,
            right_barcode.width, right_barcode.height
        )
        
        # Create the main flag image
        flag_img = Image.new(
            'RGBA',
            (total_width, self.height_px),
            (255, 255, 255, 0)
        )
        
        # Paste left barcode at the left edge, centered vertically
        left_y_offset = (self.height_px - left_barcode.height) // 2
        flag_img.paste(left_barcode, (0, left_y_offset))
        
        # Paste right barcode at the right edge, centered vertically
        right_x_offset = total_width - right_barcode.width
        right_y_offset = (self.height_px - right_barcode.height) // 2
        flag_img.paste(right_barcode, (right_x_offset, right_y_offset))
        
        logger.info(
            'Generated flag mode image: %dx%d with barcodes at positions '
            '(0,%d) and (%d,%d)',
            flag_img.width, flag_img.height,
            left_y_offset, right_x_offset, right_y_offset
        )
        
        return flag_img
    
    def save(self, filename: str):
        logger.info('Saving flag mode image to: %s', filename)
        self._image.save(filename)
    
    def show(self):
        self._image.show()
        i = input('Print this image? [y|N]').strip()
        if i not in ['y', 'Y']:
            raise SystemExit(1)
    
    @property
    def file_obj(self) -> BytesIO:
        i: BytesIO = BytesIO()
        self._image.save(i, format='PNG')
        i.seek(0)
        return i


def main():
    fname: str = datetime.now().strftime('%Y%m%dT%H%M%S') + '.png'
    p = argparse.ArgumentParser(
        description='Brother PT-P710BT Barcode Label Maker'
    )
    add_printer_args(p)
    p.add_argument(
        '--lp-dpi', dest='lp_dpi', action='store', type=int, default=203,
        help='DPI for lp printing; defaults to 203dpi'
    )
    p.add_argument(
        '--lp-width-px', dest='lp_width_px', action='store', type=int,
        default=203,
        help='Width in pixels for printing via LP; default 203'
    )
    p.add_argument(
        '--lp-options', dest='lp_options', action='store', type=str, default='',
        help='Options to pass to lp when printing'
    )
    p.add_argument(
        '-s', '--save-only', dest='save_only', action='store_true',
        default=False, help='Save generates image to current directory and exit'
    )
    p.add_argument(
        '--filename', dest='filename', action='store', type=str,
        help=f'Filename to save image to; default: {fname}', default=fname
    )
    p.add_argument('-P', '--preview', dest='preview', action='store_true',
                   default=False,
                   help='Preview image after generating and ask if it should '
                        'be printed')
    p.add_argument(
        '-S', '--symbology', dest='symbology', action='store', type=str,
        help='Barcode symbology to use', choices=sorted(BARCODE_CLASSES.keys()),
        default='Code128'
    )
    p.add_argument(
        '-t', '--no-text', dest='show_text', action='store_false', default=True,
        help='Do not show text below barcode'
    )
    p.add_argument(
        '-F', '--flag', dest='flag_mode', action='store_true', default=False,
        help='Flag mode: place two rotated barcodes at opposite ends of the label '
             'for wrapping around wires. Requires maxlen to be specified.'
    )
    maxlen = p.add_mutually_exclusive_group()
    maxlen.add_argument('--maxlen-px', dest='maxlen_px', action='store',
                        type=int, help='Maximum label length in pixels')
    maxlen.add_argument('--maxlen-inches', dest='maxlen_in', action='store',
                        type=float, help='Maximum label length in inches')
    maxlen.add_argument('--maxlen-mm', dest='maxlen_mm', action='store',
                        type=float, help='Maximum label length in mm')
    p.add_argument(
        '--fixed-len-px', dest='fixed_len_px', action='store', type=int,
        default=None, help='Center barcode in fixed length image of this many pixels long'
    )
    def_font: str = os.environ.get('PT_FONT_FILE', 'DejaVuSans.ttf')
    p.add_argument('-f', '--font-filename', dest='font_filename', type=str,
                   action='store', default=def_font,
                   help=f'Font filename; Default: {def_font} ('
                        'default taken from PT_FONT_FILE env var if set)')
    p.add_argument(
        'BARCODE_VALUE', action='store', type=str, help='Value for barcode',
        nargs='+'
    )
    args = p.parse_args(sys.argv[1:])
    dpi: int = BarcodeLabelGenerator.DPI
    height: int = TAPE_MM_TO_PX[args.tape_mm]
    if args.lp:
        dpi = args.lp_dpi
        height = args.lp_width_px
    if args.maxlen_in:
        args.maxlen_px = int(args.maxlen_in * dpi)
    elif args.maxlen_mm:
        args.maxlen_px = int((args.maxlen_mm / 25.4) * dpi)
    # set logging level
    if args.verbose:
        set_log_debug(logger)
    else:
        set_log_info(logger)

    # BEGIN generating images
    images: List[BytesIO] = []
    for i in args.BARCODE_VALUE:
        if args.flag_mode:
            # generate an image for a barcode in flag mode
            if args.maxlen_px is None:
                raise ValueError("Flag mode requires maxlen to be specified (use --maxlen-px, --maxlen-inches, or --maxlen-mm)")
            g = FlagModeGenerator(
                i, height_px=height, maxlen_px=args.maxlen_px,
                font_filename=args.font_filename, barcode_class_name=args.symbology,
                show_text=args.show_text, fixed_len_px=args.fixed_len_px
            )
        else:
            g = BarcodeLabelGenerator(
                i, height_px=height, maxlen_px=args.maxlen_px,
                font_filename=args.font_filename, barcode_class_name=args.symbology,
                show_text=args.show_text, fixed_len_px=args.fixed_len_px
            )
        if args.save_only:
            g.save(args.filename)
        if args.preview:
            g.show()
        images.append(g.file_obj)
    # END generating images

    if args.save_only:
        raise SystemExit(0)
    if args.lp:
        return LpPrinter(args.lp_options).print_images(
            images, num_copies=args.num_copies
        )
    # Begin code copied from label_printer.py
    device: Connector
    if args.usb:
        device = UsbConnector()
    else:
        device = BluetoothConnector(
            args.bt_address, bt_channel=args.bt_channel
        )
    PtP710LabelPrinter(device, tape_mm=args.tape_mm).print_images(
        images, num_copies=args.num_copies
    )


if __name__ == "__main__":
    main()
