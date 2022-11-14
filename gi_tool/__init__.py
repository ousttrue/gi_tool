import pathlib
import logging

logger = logging.getLogger(__name__)


def process(path: pathlib.Path):
    if not path.exists():
        logger.warning('prefix not exists')
        return

    for e in path.iterdir():
        if e.suffix == '.gir':
            print(e)
