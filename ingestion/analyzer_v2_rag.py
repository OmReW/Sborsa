import asyncio
import json
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
import pandas as pd
import requests

from config.settings import settings
from config.logger import get_logger
from ingestion.models import KapNotification

logger = get_logger("analyzer_v2_rag")

BASE_DIR = Path(__file__).resolve().parent.parent


class MacroEventRetriever:
    """
    KAP bildirimlerinin içeriğine göre geçmişteki benzer makro olayları,
    seçimleri, faiz kararlarını ve BIST100 tarihsel tepkilerini bulan RAG alıcısı.
    """

    def __init__(self, csv_path: Optional[Path] = None):
        self.csv_path = csv_path or (BASE_DIR / "scripts" / "event_study_results.csv")
        self.events_df = pd.DataFrame()
        self._load_events()

    def _load_events(self):
        if self.csv_path.exists():
            try:
                self.events_df = pd.read_csv(self.csv_path, encoding="utf-8-sig")
            except Exception as e:
                logger.warning(f"Event study CSV yüklenemedi: {e}")

    def retrieve_context(self, notification: KapNotification) -> Dict[str, Any]:
        """
        Bildirim metnindeki anahtar kelimelere göre en alakalı tarihsel piyasa olaylarını döner.
        """
        text_corpus = f"{notification.title} {notification.summary or ''} {notification.raw_content or ''}".lower()

        matched_category = None
        relevance_reason = ""

        # Kategori tespiti
        if any(w in text_corpus for w in ["seçim", "secim", "sandık", "yerel yönetim", "belediye"]):
            matched_category = "SEÇİM"
            relevance_reason = "Bildirim seçim/siyasi takvim ilişkili."
        elif any(w in text_corpus for w in ["faiz", "tcmb", "ppk", "enflasyon", "sıkılaşma", "politika faizi", "para politikası"]):
            matched_category = "FAİZ_KARARI"
            relevance_reason = "Bildirim faiz/para politikası ve makro ekonomik gösterge ilişkili."
        elif any(w in text_corpus for w in ["kkm", "döviz", "kur korumalı", "başkan değişimi", "şok", "regülasyon", "yönetim değişimi"]):
            matched_category = "POLİTİKA_ŞOKU"
            relevance_reason = "Bildirim olağanüstü politika/regülasyon veya makro şok ilişkili."
        elif any(w in text_corpus for w in ["referandum", "anayasa"]):
            matched_category = "REFERANDUM"
            relevance_reason = "Bildirim anayasal/yapısal oylama ilişkili."

        retrieved_events = []

        if not self.events_df.empty and matched_category:
            cat_df = self.events_df[self.events_df["category"] == matched_category]
            if not cat_df.empty:
                # En güncel ve çarpıcı 2 olayı al
                for _, row in cat_df.tail(2).iterrows():
                    retrieved_events.append({
                        "date": str(row["date"]),
                        "title": str(row["title"]),
                        "pre_30d_return_pct": row.get("pre_30d_return_pct"),
                        "event_jump_pct": row.get("event_jump_pct"),
                        "post_5d_return_pct": row.get("post_5d_return_pct"),
                        "post_30d_return_pct": row.get("post_30d_return_pct"),
                    })

        # Metin formatı oluştur
        if retrieved_events:
            lines = [f"İlgili Makro Kategori: {matched_category} ({relevance_reason})"]
            for ev in retrieved_events:
                lines.append(
                    f"• {ev['date']} | {ev['title']}: "
                    f"Olay Günü Tepkisi: %{ev['event_jump_pct']:+.2f}, "
                    f"Sonrası 5G: %{ev['post_5d_return_pct']:+.2f}, "
                    f"Sonrası 30G: %{ev['post_30d_return_pct']:+.2f}"
                )
            context_text = "\n".join(lines)
        else:
            context_text = "Doğrudan makro kategori eşleşmesi bulunamadı (Şirket özel/operasyonel bildirim)."

        return {
            "matched_category": matched_category,
            "events_count": len(retrieved_events),
            "context_text": context_text,
            "raw_events": retrieved_events,
        }


class KAPAnalyzerV2RAG:
    """
    RAG Destekli Deneysel Bildirim Analiz Motoru.
    Geçmiş makro olay tepkilerini ve piyasa hafızasını bağlam olarak modele enjekte eder.
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
        self.retriever = MacroEventRetriever()

    def build_prompt(self, notification: KapNotification, rag_context: Dict[str, Any]) -> str:
        """
        RAG bağlamı ile zenginleştirilmiş sistem istemi oluşturur.
        """
        content_preview = notification.summary or notification.raw_content or "İçerik detayı bulunmuyor."
        if len(content_preview) > 1500:
            content_preview = content_preview[:1500] + "... (kısaltıldı)"

        prompt = f"""Sen Borsa İstanbul (BIST) hisse senetleri konusunda uzman, disiplinli ve piyasa hafızasına sahip bir finansal analistsin.
Aşağıda verilen KAP bildirimini ve ilgili olabilecek tarihsel piyasa hafızası referanslarını incele.

BİLDİRİM BİLGİLERİ:
- Şirket Kodu: {notification.stock_code}
- Şirket Unvanı: {notification.company_name or 'Bilinmiyor'}
- Bildirim Başlığı / Konusu: {notification.title}
- Yayın Tarihi: {notification.publish_date}
- Bildirim Özeti / İçeriği:
\"\"\"
{content_preview}
\"\"\"

GEÇMİŞ TARİHSEL PİYASA REFERANSLARI (RAG BAĞLAMI):
\"\"\"
{rag_context['context_text']}
\"\"\"
ÖNEMLİ KURAL: Yukarıdaki tarihsel veriler küçük bir referans örneklemidir, kesin bir kural değil sadece piyasa hafızası olarak sunulmuştur. Şirketin kendi bildirimindeki somut finansal/operasyonel gelişmeyi ana odak yap; geçmiş örnekleri körü körüne takip etme, akılcı bir süzgeçten geçir.

GÖREV:
1. Bu bildirimin şirket operasyonlarına, finansal sağlığına veya hisse algısına etkisini analiz et.
2. Kesinlikle şu 3 öneriden birini seç: "AL", "SAT", "NÖTR"
3. Analizin güven seviyesini 1 ile 5 arasında bir tam sayı olarak belirle (1: Çok Düşük / Belirsiz, 5: Çok Yüksek / Kesin).
4. İnsan yatırımcı için 1-2 cümlelik Türkçe kısa ve net bir gerekçe yaz (Varsa tarihsel piyasa dinamiklerine veya şirket gerçeklerine rasyonel referans ver).

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
        try:
            cleaned = raw_text.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)
                cleaned = cleaned.strip()

            json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if json_match:
                cleaned = json_match.group(0)

            data = json.loads(cleaned)
            rec = str(data.get("recommendation", "")).strip().upper()
            if rec not in ["AL", "SAT", "NÖTR"]:
                rec = "NÖTR"

            conf = data.get("confidence", 3)
            try:
                conf = max(1, min(5, int(conf)))
            except (ValueError, TypeError):
                conf = 3

            reasoning = str(data.get("reasoning", "")).strip() or "Gerekçe belirtilmedi."

            return {
                "recommendation": rec,
                "confidence": conf,
                "reasoning": reasoning,
            }
        except Exception as e:
            logger.error(f"LLM yanıtı ayrıştırılamadı: {e}")
            return None

    def analyze_notification_sync(self, notification: KapNotification) -> Dict[str, Any]:
        """
        Senkron olarak tek bir bildirimi RAG ile analiz eder (Test scriptleri için).
        """
        rag_context = self.retriever.retrieve_context(notification)
        prompt = self.build_prompt(notification, rag_context)

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
            },
        }

        try:
            url = f"{self.base_url.rstrip('/')}/api/generate"
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()

            raw_response = response.json().get("response", "")
            parsed = self._parse_llm_response(raw_response)

            if parsed:
                return {
                    "recommendation": parsed["recommendation"],
                    "confidence": parsed["confidence"],
                    "reasoning": parsed["reasoning"],
                    "rag_context": rag_context,
                    "status": "success",
                }
            else:
                return {
                    "recommendation": "NÖTR",
                    "confidence": 1,
                    "reasoning": "Model yanıtı ayrıştırılamadı.",
                    "rag_context": rag_context,
                    "status": "parse_error",
                }
        except Exception as e:
            logger.error(f"RAG analiz hatası: {e}")
            return {
                "recommendation": "NÖTR",
                "confidence": 1,
                "reasoning": f"Bağlantı hatası: {e}",
                "rag_context": rag_context,
                "status": "network_error",
            }
