import os
import logging
from typing import List
from io import BytesIO
import shlex
from tempfile import mkdtemp
from shutil import which, rmtree
import subprocess

logger = logging.getLogger(__name__)


class LpPrinter:
    """
    Printer class for printing to regular CUPS/lp printers instead of the
    Brother PT-P710BT label printer.
    """

    def __init__(self, lp_options: str):
        self.lp_options: List[str] = []
        if lp_options != '':
            self.lp_options = shlex.split(lp_options)

    def print_images(self, images: List[BytesIO], num_copies: int = 1):
        tmpdir: str = mkdtemp()
        try:
            fpaths: List[str] = []
            for idx, i in enumerate(images):
                fname = os.path.join(tmpdir, f'{idx}.png')
                fpaths.append(fname)
                logger.debug('Writing image to: %s', fname)
                with open(fname, 'wb') as fh:
                    fh.write(i.getvalue())
            cmd = [which('lp')] + self.lp_options
            if num_copies > 1:
                cmd.extend(['-n', str(num_copies)])
            cmd.extend(fpaths)
            logger.debug('Calling: %s', ' '.join(cmd))
            p: subprocess.CompletedProcess = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
            logger.debug(
                'Command exited %d: %s', p.returncode, p.stdout
            )
            if p.returncode != 0:
                raise RuntimeError(
                    f'ERROR: lp command exited {p.returncode}: {p.stdout}'
                )
        finally:
            rmtree(tmpdir)
