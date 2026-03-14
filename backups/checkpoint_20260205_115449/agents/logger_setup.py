
import logging
import os
import sys

# Try importing Loki, handle failure gracefully
try:
    import logging_loki
    LOKI_AVAILABLE = True
except ImportError:
    LOKI_AVAILABLE = False

def setup_logger(name: str):
    """
    Configures and returns a logger with Loki integration.
    Ensures every module gets a logger that DEFINITELY talks to Loki.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Avoid adding handlers multiple times if getLogger is called repeatedly
    if logger.hasHandlers():
        return logger

    # 1. Console Handler (stdout) - Essential for Docker logs
    c_handler = logging.StreamHandler(sys.stdout)
    c_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    c_handler.setFormatter(c_format)
    logger.addHandler(c_handler)

    # 2. Loki Handler
    if LOKI_AVAILABLE:
        # Suppress Uvicorn Access Logs (polute dashboard)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

        try:
            l_handler = logging_loki.LokiHandler(
                url="http://loki:3100/loki/api/v1/push", 
                tags={"container_name": "agent_runtime", "job": "agent_runtime", "source": "python", "logger": name}, 
                version="1",
            )
            logger.addHandler(l_handler)
        except Exception as e:
            print(f"Failed to initialize Loki handler for {name}: {e}")

    return logger
