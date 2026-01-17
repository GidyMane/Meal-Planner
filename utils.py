import sys
from loguru import logger

# Remove default handler
logger.remove()

logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>node={extra[node]}</cyan> | <cyan>request_id={extra[request_id]}</cyan> | <level>{message}</level>",
    level="INFO",
    colorize=True,
    enqueue=False,
    # This ensures that missing extra fields don't cause errors
    catch=True
)

logger = logger.bind(node=None, request_id=None)
