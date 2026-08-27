import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from config.settings import settings


def setup_logger(
    name: Optional[str] = "borsa_ai",
    log_level: Optional[str] = None,
    log_file: Optional[Path] = None,
) -> logging.Logger:
    """
    Zaman damgalı, konsol ve dosyaya eşzamanlı yazan merkezi loglayıcıyı yapılandırır.
    
    Format:
    [2026-08-26 20:30:15] [INFO] [ingestion.kap_feed:45] - 12 bildirim başarıyla çekildi.
    """
    settings.ensure_directories()
    
    level_name = log_level or settings.LOG_LEVEL
    level = getattr(logging, level_name, logging.INFO)
    target_log_file = log_file or settings.LOG_FILE

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Handler'ların mükerrer eklenmesini önle
    if logger.hasHandlers():
        return logger

    # Log formatı
    log_format = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)-8s] [%(name)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 1. Konsol Çıktısı (StreamHandler - Windows konsol UTF-8 uyumluluğu)
    try:
        if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    # 2. Dosya Çıktısı (RotatingFileHandler - 10MB x 5 yedek)
    try:
        file_handler = RotatingFileHandler(
            filename=str(target_log_file),
            maxBytes=settings.LOG_MAX_BYTES,
            backupCount=settings.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(log_format)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Dosya loglayıcı başlatılamadı ({target_log_file}): {e}")

    # Alt modüllerin root logger'a çift göndermesini engelle
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Belirli bir modül adı için yapılandırılmış logger döner.
    """
    return logging.getLogger(f"borsa_ai.{name}")
