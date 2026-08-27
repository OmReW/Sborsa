import hashlib
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class KapNotification(BaseModel):
    """
    KAP (Kamuyu Aydınlatma Platformu) bildirim veri modeli.
    Gerçek KAP REST API alanları ile tam uyumludur.
    """
    id: str = Field(
        description="Bildirimin benzersiz kimliği (disclosureIndex veya hash)"
    )
    disclosure_index: Optional[int] = Field(
        default=None,
        description="KAP benzersiz bildirim indeksi (örn. 609961)"
    )
    stock_code: str = Field(
        default="GENEL",
        description="Birincil BIST hisse kodu (örn. THYAO, ASELS)"
    )
    stock_codes: Optional[str] = Field(
        default="",
        description="Bildirimle ilişkili tüm hisse kodları (örn. 'TCELL, TTKOM')"
    )
    company_name: Optional[str] = Field(
        default="",
        description="Şirket unvanı / kurum adı (kapTitle)"
    )
    title: str = Field(
        description="Bildirim konusu / başlığı"
    )
    subject: Optional[str] = Field(
        default="",
        description="KAP bildirim konusu kategorisi (örn. Özel Durum Açıklaması (Genel))"
    )
    disclosure_class: Optional[str] = Field(
        default="ODA",
        description="Bildirim sınıfı (ODA: Özel Durum Açıklaması, FR: Finansal Rapor, DUY: Duyuru)"
    )
    disclosure_type: Optional[str] = Field(
        default="",
        description="Bildirim tür kodu (örn. ODA, CA, FR)"
    )
    disclosure_category: Optional[str] = Field(
        default="",
        description="Bildirim kategori kodu (örn. ODA, STT)"
    )
    publish_date: str = Field(
        description="Bildirimin yayınlanma tarihi ve saati"
    )
    summary: Optional[str] = Field(
        default="",
        description="Bildirimin metin özeti / açıklaması"
    )
    raw_content: Optional[str] = Field(
        default="",
        description="Ham JSON formatındaki bildirim gövdesi"
    )
    link: Optional[str] = Field(
        default="",
        description="KAP bildirimine yönlendiren web adresi"
    )
    is_processed: bool = Field(
        default=False,
        description="Bildirimin downstream analiz/işleme tarafından işlenip işlenmediği"
    )
    recommendation: Optional[str] = Field(
        default=None,
        description="LLM analiz önerisi (AL, SAT, NÖTR)"
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="LLM analiz gerekçesi"
    )
    confidence: Optional[int] = Field(
        default=None,
        description="Öneri güven seviyesi (1-5)"
    )
    analyzed_at: Optional[str] = Field(
        default=None,
        description="Analizin tamamlandığı zaman damgası"
    )
    created_at: Optional[str] = Field(
        default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        description="Sisteme kaydedilme zamanı (UTC)"
    )

    @field_validator("stock_code")
    @classmethod
    def clean_stock_code(cls, v: str) -> str:
        if not v or not v.strip():
            return "GENEL"
        # Çoğul kod varsa birincisini al
        first = v.split(",")[0].strip().upper()
        return first or "GENEL"

    @classmethod
    def generate_hash_id(cls, stock_code: str, title: str, publish_date: str) -> str:
        """
        KAP ID mevcut olmadığında deterministik bir MD5 karması üretir.
        """
        payload = f"{stock_code.strip().upper()}|{title.strip()}|{publish_date.strip()}".encode("utf-8")
        return hashlib.md5(payload).hexdigest()
