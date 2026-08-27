import time
from typing import Optional, List
from config.logger import get_logger

logger = get_logger("rate_limiter")


class ExponentialBackoffRateLimiter:
    """
    HTTP 429 ve aşırı istek engellerine karşı yeniden kullanılabilir
    üstel geri çekilme (exponential backoff) ve oran sınırlayıcı modülü.
    
    Örnek kullanım:
        limiter = ExponentialBackoffRateLimiter(name="KAP", initial_delay=300, max_delay=1800)
        
        if limiter.is_in_cooldown():
            # Bekleme süresi dolmadı
            await asyncio.sleep(limiter.remaining_cooldown())
            
        # İstek sonrası:
        if response.status_code == 429:
            limiter.record_rate_limit()
        elif response.status_code == 200:
            limiter.record_success()
    """

    def __init__(
        self,
        name: str = "DEFAULT",
        delays: Optional[List[int]] = None,
        default_interval: int = 180,  # Normal çekme aralığı (3 dakika)
    ):
        self.name = name
        # Kademeli bekleme süreleri (saniye cinsinden): 5 dk, 15 dk, 30 dk
        self.delays = delays or [300, 900, 1800]
        self.default_interval = default_interval
        
        self.attempt = 0
        self.cooldown_until = 0.0
        self.last_failure_time: Optional[float] = None

    def record_rate_limit(self) -> int:
        """
        429 yanıtı alındığında çağrılır. Deneme sayısını artırır ve soğuma süresini başlatır.
        
        Returns:
            int: Beklenecek süre (saniye)
        """
        self.attempt += 1
        idx = min(self.attempt - 1, len(self.delays) - 1)
        wait_seconds = self.delays[idx]
        wait_minutes = wait_seconds // 60

        now = time.time()
        self.last_failure_time = now
        self.cooldown_until = now + wait_seconds

        logger.warning(
            f"[{self.name}][RATE_LIMIT] {wait_minutes} dakika ({wait_seconds}s) bekleniyor, "
            f"deneme #{self.attempt}. Güvenlik duvarı soğuma süresi devrede."
        )
        return wait_seconds

    def record_success(self) -> None:
        """
        İstek başarılı olduğunda (200 OK) çağrılır. Hata sayacını sıfırlar.
        """
        if self.attempt > 0:
            logger.info(
                f"[{self.name}][RATE_LIMIT_RESOLVED] Bağlantı normale döndü. "
                f"Hata sayacı sıfırlandı."
            )
        self.attempt = 0
        self.cooldown_until = 0.0
        self.last_failure_time = None

    def is_in_cooldown(self) -> bool:
        """
        Şu an sistemin 429 soğuma süresinde olup olmadığını döner.
        """
        return time.time() < self.cooldown_until

    def remaining_cooldown(self) -> float:
        """
        Kalan soğuma süresini (saniye) döner.
        """
        remaining = self.cooldown_until - time.time()
        return max(0.0, remaining)

    def get_next_interval(self) -> int:
        """
        Bir sonraki döngüde beklenmesi gereken süreyi döner.
        Eğer soğuma varsa kalan süreyi, yoksa varsayılan periyodu döner.
        """
        if self.is_in_cooldown():
            return int(self.remaining_cooldown())
        return self.default_interval
