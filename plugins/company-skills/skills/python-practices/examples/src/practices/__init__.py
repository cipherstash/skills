"""Examples quoted by the python-practices references."""

# Package-level configuration
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
