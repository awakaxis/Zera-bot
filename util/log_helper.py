import logging


class ProjectLogFilter(logging.Filter):
    def filter(self, record):
        return record.name.startswith('zerabot')


class ColorFormatter(logging.Formatter):
    WHITE = "\033[97m"
    SLIGHTLY_DARKER_WHITE = "\033[38;5;250m"
    YELLOW = "\033[93m"
    ORANGE = "\033[33m"
    RED = "\033[91m"
    DARK_RED = "\033[31m"
    RESET = "\033[0m"

    COLORS = {
        logging.INFO: SLIGHTLY_DARKER_WHITE,
        logging.DEBUG: ORANGE,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: DARK_RED,
        'DEFAULT': WHITE
    }

    def __init__(self, fmt='%(message)s', datefmt='%Y-%m-%d %H:%M:%S', style='%'):
        super().__init__(fmt, datefmt, style)

    def format(self, record):
        log = super().format(record)
        color = self.COLORS.get(record.levelno, self.COLORS['DEFAULT'])
        return f'{color}{log}{self.RESET}'


def get_logger(name):
    logger = logging.getLogger(f'zerabot.{name}')
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(ColorFormatter(fmt='%(asctime)s - AT %(lineno)d - %(levelname)s - %(name)s - %(message)s'))
    handler.addFilter(ProjectLogFilter())
    logger.addHandler(handler)
    return logger
