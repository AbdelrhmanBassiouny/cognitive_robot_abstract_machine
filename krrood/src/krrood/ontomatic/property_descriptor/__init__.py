import logging

logger = logging.Logger("PropertyDescriptor")
logger.setLevel(logging.DEBUG)

# Handler
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)  # <-- this filters out DEBUG messages
logger.addHandler(handler)
