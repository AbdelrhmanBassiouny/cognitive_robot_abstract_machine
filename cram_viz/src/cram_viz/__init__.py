__version__ = "1.0.0"

import logging

format = "%(levelname)s:%(filename)s::%(lineno)s %(funcName)s %(message)s"
logging.basicConfig(format=format)
logger = logging.getLogger(__name__)
