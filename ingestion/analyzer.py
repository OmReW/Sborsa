import asyncio
import json
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
import requests

from config.settings import settings
from config.logger import get_logger
from ingestion.models import KapNotification
from ingestion.market_calendar import (
    get_effective_entry_details,
    fetch_bist_price_safe,
)

logger = get_logger("analyzer")


class KAPAnalyzer:
    """
    Yerel LLM (Ollama) tabanlı bildirim analiz ve öneri üretim motoru.
    
    Özellikler:
    - SADECE öneri ve gerekçe üretir (işlem yapmaz).
    - AL ve SAT önerilerini anlık/ertesi gün fiyatıyla Paper Trading günlüğüne otomatik kaydeder.
    - JSON formatında yanıt alır, markdown etiketlerini ayıklar ve güvenli hata yönetimi sunar.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model_name = model_name or settings.OLLAMA_MODEL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT_SECONDS

    def build_prompt(self, notification: KapNotification) -> str:
        """
        Analiz edilecek bildirim için yapılandırılmış sistem istemi hazırlar.
        """
        content_preview = notification.summary or notification.raw_content or "İçerik detayı bulunmuyor."
        if len(content_preview) > 1500:
            content_preview = content_preview[:1500] + "... (kısaltıldı)"

        prompt = f"""Sen Borsa İstanbul (BIST) hisse senetleri konusunda uzman, disiplinli bir finansal analistsin.
Aşağıda verilen KAP (Kamuyu Aydınlatma Platformu) bildirimini incele ve hisse fiyatı üzerindeki olası kısa/orta vadeli etkisini değerlendir.

BİLDİRİM BİLGİLERİ:
- Şirket Kodu: {notification.stock_code}
- Şirket Unvanı: {notification.company_name or 'Bilinmiyor'}
- Bildirim Başlığı / Konusu: {notification.title}
- Yayın Tarihi: {notification.publish_date}
- Bildirim Özeti / İçeriği:
\"\"\"
{content_preview}
\"\"\"

GÖREV:
1. Bu bildirimin şirket operasyonlarına, finansal sağlığına veya hisse algısına etkisini analiz et.
2. Kesinlikle şu 3 öneriden birini seç: "AL", "SAT", "NÖTR"
   - Pozitif katalizör (kâr artışı, yeni büyük iş sözleşmesi, hisse geri alımı vb.): AL
   - Negatif gelişme (üretim duruşu, dava, ceza, zarar artışı, not indirimi vb.): SAT
   - Rutin/prosedürel bildirim (Genel kurul daveti, kupon/faiz itfası, görev dağılımı vb.) veya belirsiz durumlar: NÖTR
3. Analizin güven seviyesini 1 ile 5 arasında bir tam sayı olarak belirle (1: Çok Düşük / Belirsiz, 5: Çok Yüksek / Kesin).
4. İnsan yatırımcı için 1-2 cümlelik Türkçe kısa ve net bir gerekçe yaz.

ÇIKTI FORMATI:
SADECE aşağıdaki JSON formatında geçerli bir JSON nesnesi döndür, başka hiçbir metin veya açıklama ekleme:
{{
  "recommendation": "AL" veya "SAT" veya "NÖTR",
  "confidence": 1-5 arası tam sayı,
  "reasoning": "Kısa Türkçe gerekçe metni"
}}
"""
        return prompt

    def _parse_llm_response(self, raw_text: str) -> Optional[Dict[str, Any]]:
        """
        LLM yanıtını JSON olarak ayrıştırır ve doğrular.
        """
        try:
            cleaned = raw_text.strip()
            # Markdown kod bloklarını temizle (```json ... ```)
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)
                cleaned = cleaned.strip()

            # JSON bloğunu bul
            json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if json_match:
                cleaned = json_match.group(0)

            data = json.loads(cleaned)
            rec = str(data.get("recommendation", "")).strip().upper()
            if rec not in ["AL", "SAT", "NÖTR"]:
                logger.warning(f"Geçersiz öneri değeri: '{rec}', NÖTR olarak varsayılıyor.")
                rec = "NÖTR"

            conf = data.get("confidence", 3)
            try:
                conf = int(conf)
                conf = max(1, min(5, conf))
            except (ValueError, TypeError):
                conf = 3

            reasoning = str(data.get("reasoning", "")).strip() or "Gerekçe belirtilmedi."

            return {
                "recommendation": rec,
                "confidence": conf,
                "reasoning": reasoning,
            }
        except Exception as e:
            logger.error(f"LLM yanıtı JSON olarak ayrıştırılamadı: {e}. Ham Yanıt: {raw_text[:200]}")
            return None

    def _record_paper_trade_if_applicable(
        self, notification: KapNotification, analysis: Dict[str, Any]
    ) -> None:
        """
        Eğer öneri AL veya SAT ise, anlık/ertesi gün fiyatıyla Paper Trading günlüğüne kaydeder.
        """
        rec = analysis.get("recommendation", "NÖTR")
        if rec not in ["AL", "SAT"]:
            return

        stock = notification.stock_code
        # Bildirim tarihini ayrıştır
        pub_dt = None
        for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                pub_dt = datetime.strptime(notification.publish_date.strip(), fmt)
                break
            except ValueError:
                pass
        
        pub_dt = pub_dt or datetime.utcnow()
        effective_date, is_opening, note = get_effective_entry_details(pub_dt)

        # Fiyatı güvenli çek
        entry_price = fetch_bist_price_safe(
            ticker=stock,
            target_dt=datetime.combine(effective_date, datetime.min.time()),
            is_opening=is_opening,
        )

        # DB'ye kaydet
        from storage.db import db
        db.save_paper_trade(
            notification_id=notification.id,
            stock_code=stock,
            recommendation=rec,
            confidence=analysis.get("confidence", 3),
            reasoning=analysis.get("reasoning", ""),
            entry_price=entry_price,
            recommended_at=pub_dt.strftime("%Y-%m-%d %H:%M:%S"),
            entry_date=effective_date.strftime("%Y-%m-%d"),
            entry_note=note,
        )

    async def analyze_notification(
        self, notification: KapNotification
    ) -> Optional[Dict[str, Any]]:
        """
        Tek bir KAP bildirimini yerel LLM üzerinden analiz eder.
        """
        prompt = self.build_prompt(notification)
        endpoint = f"{self.base_url.rstrip('/')}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,  # Tutarlı çıktılar için düşük sıcaklık
            },
        }

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(endpoint, json=payload, timeout=self.timeout),
            )

            if response.status_code != 200:
                logger.error(
                    f"Ollama API HTTP {response.status_code} hatası: {response.text[:200]}"
                )
                return None

            result_json = response.json()
            raw_response = result_json.get("response", "")
            analysis = self._parse_llm_response(raw_response)

            if analysis:
                logger.info(
                    f"🤖 [ANALİZ TAMAM] {notification.stock_code} -> "
                    f"Öneri: {analysis['recommendation']} (Güven: {analysis['confidence']}/5) | {analysis['reasoning'][:60]}..."
                )
                # Paper trading günlüğü kaydı
                self._record_paper_trade_if_applicable(notification, analysis)

            return analysis

        except requests.Timeout:
            logger.warning(f"Ollama analiz isteği zaman aşımına uğradı ({self.timeout}s).")
            return None
        except requests.RequestException as e:
            logger.error(f"Ollama bağlantı hatası: {e}")
            return None
        except Exception as e:
            logger.error(f"Analiz sırasında beklenmeyen hata: {e}")
            return None

    async def analyze_unprocessed(self, limit: int = 10) -> int:
        """
        Veritabanında henüz işlenmemiş bildirimleri sırayla analiz eder.
        """
        from storage.db import db
        unprocessed = db.get_unprocessed_notifications(limit=limit)
        if not unprocessed:
            logger.debug("Analiz edilecek yeni bildirim bulunmuyor.")
            return 0

        logger.info(f"📊 {len(unprocessed)} adet işlenmemiş bildirim analiz ediliyor...")
        processed_count = 0

        for notif in unprocessed:
            analysis = await self.analyze_notification(notif)
            if analysis:
                db.save_analysis_result(
                    notification_id=notif.id,
                    recommendation=analysis["recommendation"],
                    reasoning=analysis["reasoning"],
                    confidence=analysis["confidence"],
                )
                processed_count += 1
            else:
                # Başarısız olsa da döngünün kilitlenmemesi için işlendi işaretle
                db.mark_as_processed(notif.id)

        logger.info(f"✅ {processed_count} adet bildirim analiz edildi ve sonuçlar kaydedildi.")
        return processed_count
