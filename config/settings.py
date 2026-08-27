import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

# Proje kök dizini (c:\Website\Sborsa)
BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    """
    Borsa-AI Yapılandırma Ayarları.
    """

    # --------------------------------------------------------------------------
    # pykap & KAP Veri Çekme Ayarları
    # --------------------------------------------------------------------------
    # Takip edilecek hisse kodları (Varsayılan olarak BIST 30 öncü hisseleri)
    # Ortam değişkeninden virgülle ayrılmış olarak da verilebilir: WATCHLIST="THYAO,GARAN,ASELS"
    DEFAULT_WATCHLIST: List[str] = field(
        default_factory=lambda: [
            "THYAO", "GARAN", "ASELS", "EREGL", "BIMAS", 
            "KCHOL", "SISE", "AKBNK", "TUPRS", "FROTO", 
            "SAHOL", "ISCTR", "YKBNK", "TRALT", "PGSUS", 
            "PETKM", "TCELL", "ENKAI", "EKGYO", "TOASO"
        ]
    )

    # Sorgulanacak pykap bildirim türleri
    # FAR: Faaliyet Raporu, UNV: Unvan Değişikliği, SYI: Şirket Genel Bilgi Formu,
    # KYUR: Kurumsal Yönetim, KDP: Kar Payı/Temettü Politikası, SUR: Sürdürülebilirlik, DEG: Değerleme Raporu
    DISCLOSURE_TYPES: List[str] = field(
        default_factory=lambda: ["FAR", "UNV", "SYI", "KYUR", "KDP", "SUR", "DEG"]
    )

    # Periyodik çekme sıklığı (saniye cinsinden)
    FETCH_INTERVAL_SECONDS: int = int(os.getenv("FETCH_INTERVAL_SECONDS", "60"))
    SCRAPE_INTERVAL_SECONDS: int = int(os.getenv("SCRAPE_INTERVAL_SECONDS", str(FETCH_INTERVAL_SECONDS)))

    # İstek zaman aşımı süresi (saniye)
    REQUEST_TIMEOUT_SECONDS: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20.0"))

    # --------------------------------------------------------------------------
    # Yerel LLM / Ollama Analiz Ayarları
    # --------------------------------------------------------------------------
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "ozel-qwen:latest")
    OLLAMA_TIMEOUT_SECONDS: float = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120.0"))
    ANALYSIS_BATCH_SIZE: int = int(os.getenv("ANALYSIS_BATCH_SIZE", "5"))

    # --------------------------------------------------------------------------
    # Paper Trading & Simülasyon Ayarları
    # --------------------------------------------------------------------------
    SIMULATION_START_CAPITAL: float = float(os.getenv("SIMULATION_START_CAPITAL", "100000.0"))  # Başlangıç sermayesi (TL)
    POSITION_ALLOCATION_PCT: float = float(os.getenv("POSITION_ALLOCATION_PCT", "0.10"))        # Pozisyon başına sermaye payı (%10)
    SIMULATED_POSITION_SIZE: float = float(os.getenv("SIMULATED_POSITION_SIZE", str(SIMULATION_START_CAPITAL * POSITION_ALLOCATION_PCT)))  # İşlem başına TL

    # --------------------------------------------------------------------------
    # Veritabanı Ayarları
    # --------------------------------------------------------------------------
    DB_PATH: Path = field(
        default_factory=lambda: Path(
            os.getenv("DB_PATH", str(BASE_DIR / "storage" / "borsa.db"))
        )
    )

    # --------------------------------------------------------------------------
    # Loglama Ayarları
    # --------------------------------------------------------------------------
    LOG_DIR: Path = field(
        default_factory=lambda: Path(
            os.getenv("LOG_DIR", str(BASE_DIR / "logs"))
        )
    )
    LOG_FILE: Path = field(
        default_factory=lambda: Path(
            os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "borsa_ai.log"))
        )
    )
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Log dosyasının boyutu ve yedek sayısı (RotatingFileHandler)
    LOG_MAX_BYTES: int = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))  # 10 MB
    LOG_BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    # --------------------------------------------------------------------------
    # Dashboard / Web Arayüz Ayarları
    # --------------------------------------------------------------------------
    DASHBOARD_HOST: str = os.getenv("DASHBOARD_HOST", "127.0.0.1")
    DASHBOARD_PORT: int = int(os.getenv("DASHBOARD_PORT", "8000"))

    @property
    def watchlist(self) -> Optional[List[str]]:
        """Ortam değişkeninden takip listesini döner, tanımlı değilse None (Tüm BIST)."""
        env_watchlist = os.getenv("WATCHLIST")
        if env_watchlist and env_watchlist.strip().upper() != "ALL":
            return [t.strip().upper() for t in env_watchlist.split(",") if t.strip()]
        return None

    def ensure_directories(self) -> None:
        """Gerekli storage ve logs dizinlerinin varlığını garanti eder."""
        self.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)


# Singleton yapılandırma nesnesi
settings = Settings()
settings.ensure_directories()
