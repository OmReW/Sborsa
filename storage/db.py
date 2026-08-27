import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from contextlib import contextmanager

from config.settings import settings
from config.logger import get_logger
from ingestion.models import KapNotification

logger = get_logger("storage")


class DatabaseManager:
    """
    SQLite tabanlı bildirim depolama, LLM analizleri ve Paper Trading günlüğü yöneticisi.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    @contextmanager
    def get_connection(self):
        """Bağlantıyı güvenli açıp kapatan context manager."""
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Veritabanı işlem hatası: {e}")
            raise
        finally:
            conn.close()

    def init_db(self) -> None:
        """
        Gerekli tabloları, indeksleri ve yeni kolon migrasyonlarını otomatik oluşturur.
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 1. KAP Bildirimleri Tablosu
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS kap_notifications (
                        id TEXT PRIMARY KEY,
                        disclosure_index INTEGER,
                        stock_code TEXT NOT NULL,
                        stock_codes TEXT DEFAULT '',
                        company_name TEXT DEFAULT '',
                        title TEXT NOT NULL,
                        subject TEXT DEFAULT '',
                        disclosure_class TEXT DEFAULT 'ODA',
                        disclosure_type TEXT DEFAULT '',
                        disclosure_category TEXT DEFAULT '',
                        publish_date TEXT NOT NULL,
                        summary TEXT DEFAULT '',
                        raw_content TEXT DEFAULT '',
                        link TEXT DEFAULT '',
                        is_processed INTEGER DEFAULT 0,
                        recommendation TEXT DEFAULT NULL,
                        reasoning TEXT DEFAULT NULL,
                        confidence INTEGER DEFAULT NULL,
                        analyzed_at TIMESTAMP DEFAULT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )

                # 2. Paper Trading Tablosu
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS paper_trades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        notification_id TEXT UNIQUE,
                        stock_code TEXT NOT NULL,
                        recommendation TEXT NOT NULL,
                        confidence INTEGER,
                        reasoning TEXT,
                        recommended_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        entry_price REAL DEFAULT NULL,
                        entry_date TEXT DEFAULT NULL,
                        entry_note TEXT DEFAULT '',
                        price_1d REAL DEFAULT NULL,
                        checked_1d INTEGER DEFAULT 0,
                        outcome_1d TEXT DEFAULT 'BEKLEMEDE',
                        pnl_1d REAL DEFAULT NULL,
                        price_5d REAL DEFAULT NULL,
                        checked_5d INTEGER DEFAULT 0,
                        outcome_5d TEXT DEFAULT 'BEKLEMEDE',
                        pnl_5d REAL DEFAULT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (notification_id) REFERENCES kap_notifications (id)
                    );
                    """
                )

                # 3. Otomatik Kolon Migrasyonu (kap_notifications)
                cursor.execute("PRAGMA table_info(kap_notifications);")
                existing_columns = {row["name"] for row in cursor.fetchall()}

                new_columns = {
                    "disclosure_index": "INTEGER DEFAULT NULL",
                    "stock_codes": "TEXT DEFAULT ''",
                    "subject": "TEXT DEFAULT ''",
                    "disclosure_class": "TEXT DEFAULT 'ODA'",
                    "disclosure_type": "TEXT DEFAULT ''",
                    "disclosure_category": "TEXT DEFAULT ''",
                    "recommendation": "TEXT DEFAULT NULL",
                    "reasoning": "TEXT DEFAULT NULL",
                    "confidence": "INTEGER DEFAULT NULL",
                    "analyzed_at": "TIMESTAMP DEFAULT NULL",
                }

                for col_name, col_def in new_columns.items():
                    if col_name not in existing_columns:
                        logger.info(f"Veritabanına yeni kolon ekleniyor: {col_name}")
                        cursor.execute(f"ALTER TABLE kap_notifications ADD COLUMN {col_name} {col_def};")

                # 4. Otomatik Kolon Migrasyonu (paper_trades)
                cursor.execute("PRAGMA table_info(paper_trades);")
                existing_pt_columns = {row["name"] for row in cursor.fetchall()}
                pt_new_columns = {
                    "pnl_1d": "REAL DEFAULT NULL",
                    "pnl_5d": "REAL DEFAULT NULL",
                    "entry_date": "TEXT DEFAULT NULL",
                    "entry_note": "TEXT DEFAULT ''",
                }
                for col_name, col_def in pt_new_columns.items():
                    if col_name not in existing_pt_columns:
                        logger.info(f"paper_trades tablosuna yeni kolon ekleniyor: {col_name}")
                        cursor.execute(f"ALTER TABLE paper_trades ADD COLUMN {col_name} {col_def};")

                # 4. Atlanan İşlemler (Sermaye Yetersizliği vb.)
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS skipped_trades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        notification_id TEXT,
                        stock_code TEXT NOT NULL,
                        recommendation TEXT NOT NULL,
                        confidence INTEGER,
                        reasoning TEXT,
                        attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        skip_reason TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )

                # 5. Sistem Durumu & Heartbeat Tablosu
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS system_state (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )

                # 6. İndeksler
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_code ON kap_notifications(stock_code);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_disclosure_index ON kap_notifications(disclosure_index);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_publish_date ON kap_notifications(publish_date);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_is_processed ON kap_notifications(is_processed);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_recommendation ON kap_notifications(recommendation);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_analyzed_at ON kap_notifications(analyzed_at);")

                cursor.execute("CREATE INDEX IF NOT EXISTS idx_pt_stock ON paper_trades(stock_code);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_pt_checked_1d ON paper_trades(checked_1d);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_pt_checked_5d ON paper_trades(checked_5d);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_pt_recommended_at ON paper_trades(recommended_at);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_skipped_stock ON skipped_trades(stock_code);")

            logger.info(f"Veritabanı ve Paper Trading şeması hazırlandı: {self.db_path}")
        except Exception as e:
            logger.error(f"Veritabanı ilklendirilirken hata oluştu: {e}")
            raise

    def save_notification(self, notif: KapNotification) -> bool:
        """Tek bir bildirimi kaydeder (idempotent)."""
        query = """
            INSERT OR IGNORE INTO kap_notifications (
                id, disclosure_index, stock_code, stock_codes, company_name,
                title, subject, disclosure_class, disclosure_type, disclosure_category,
                publish_date, summary, raw_content, link, is_processed,
                recommendation, reasoning, confidence, analyzed_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    notif.id,
                    notif.disclosure_index,
                    notif.stock_code,
                    notif.stock_codes or "",
                    notif.company_name or "",
                    notif.title,
                    notif.subject or "",
                    notif.disclosure_class or "ODA",
                    notif.disclosure_type or "",
                    notif.disclosure_category or "",
                    notif.publish_date,
                    notif.summary or "",
                    notif.raw_content or "",
                    notif.link or "",
                    1 if notif.is_processed else 0,
                    notif.recommendation,
                    notif.reasoning,
                    notif.confidence,
                    notif.analyzed_at,
                    notif.created_at,
                ),
            )
            return cursor.rowcount > 0

    def save_notifications_batch(
        self, notifications: List[KapNotification]
    ) -> Tuple[int, int]:
        """Birden fazla bildirimi toplu (batch) olarak kaydeder."""
        if not notifications:
            return 0, 0

        query = """
            INSERT OR IGNORE INTO kap_notifications (
                id, disclosure_index, stock_code, stock_codes, company_name,
                title, subject, disclosure_class, disclosure_type, disclosure_category,
                publish_date, summary, raw_content, link, is_processed,
                recommendation, reasoning, confidence, analyzed_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        inserted_count = 0

        with self.get_connection() as conn:
            cursor = conn.cursor()
            for notif in notifications:
                cursor.execute(
                    query,
                    (
                        notif.id,
                        notif.disclosure_index,
                        notif.stock_code,
                        notif.stock_codes or "",
                        notif.company_name or "",
                        notif.title,
                        notif.subject or "",
                        notif.disclosure_class or "ODA",
                        notif.disclosure_type or "",
                        notif.disclosure_category or "",
                        notif.publish_date,
                        notif.summary or "",
                        notif.raw_content or "",
                        notif.link or "",
                        1 if notif.is_processed else 0,
                        notif.recommendation,
                        notif.reasoning,
                        notif.confidence,
                        notif.analyzed_at,
                        notif.created_at,
                    ),
                )
                if cursor.rowcount > 0:
                    inserted_count += 1

        return inserted_count, len(notifications)

    def get_unprocessed_notifications(
        self, limit: int = 50, max_age_hours: Optional[int] = 48
    ) -> List[KapNotification]:
        """
        Henüz LLM analizinden geçmemiş (is_processed = 0) bildirimleri getirir.
        max_age_hours (varsayılan 48 saat): Canlı döngünün eski/tarihsel kuyrukları işlemesini engeller.
        """
        query = """
            SELECT * FROM kap_notifications 
            WHERE is_processed = 0 
            ORDER BY created_at DESC, publish_date DESC;
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()

        now = datetime.utcnow()
        cutoff_dt = now - timedelta(hours=max_age_hours) if max_age_hours else None
        valid_notifs: List[KapNotification] = []
        stale_ids_to_mark: List[str] = []

        for row in rows:
            if len(valid_notifs) >= limit:
                break

            p_str = row["publish_date"] or ""
            c_str = row["created_at"] or ""
            parsed_dt = None

            for fmt in ("%d.%m.%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y", "%Y-%m-%d"):
                try:
                    parsed_dt = datetime.strptime(p_str.strip(), fmt)
                    break
                except Exception:
                    pass

            if not parsed_dt and c_str:
                try:
                    parsed_dt = datetime.strptime(c_str.strip(), "%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass

            if cutoff_dt and parsed_dt and parsed_dt < cutoff_dt:
                stale_ids_to_mark.append(row["id"])
                continue

            valid_notifs.append(
                KapNotification(
                    id=row["id"],
                    disclosure_index=row["disclosure_index"],
                    stock_code=row["stock_code"],
                    stock_codes=row["stock_codes"],
                    company_name=row["company_name"],
                    title=row["title"],
                    subject=row["subject"],
                    disclosure_class=row["disclosure_class"],
                    disclosure_type=row["disclosure_type"],
                    disclosure_category=row["disclosure_category"],
                    publish_date=row["publish_date"],
                    summary=row["summary"],
                    raw_content=row["raw_content"],
                    link=row["link"],
                    is_processed=bool(row["is_processed"]),
                    recommendation=row["recommendation"],
                    reasoning=row["reasoning"],
                    confidence=row["confidence"],
                    analyzed_at=row["analyzed_at"],
                    created_at=row["created_at"],
                )
            )

        if stale_ids_to_mark:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany("UPDATE kap_notifications SET is_processed = 1 WHERE id = ?;", [(i,) for i in stale_ids_to_mark])

        return valid_notifs

    def save_analysis_result(
        self,
        notification_id: str,
        recommendation: str,
        reasoning: str,
        confidence: int,
    ) -> bool:
        """LLM tarafından üretilen öneri ve gerekçeyi veritabanına kaydeder."""
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        query = """
            UPDATE kap_notifications 
            SET 
                recommendation = ?, 
                reasoning = ?, 
                confidence = ?, 
                analyzed_at = ?, 
                is_processed = 1 
            WHERE id = ?;
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    recommendation.strip().upper(),
                    reasoning.strip(),
                    int(confidence),
                    now_str,
                    notification_id,
                ),
            )
            return cursor.rowcount > 0

    # =========================================================================
    # PAPER TRADING GÜNLÜĞÜ METOTLARI
    # =========================================================================

    def save_paper_trade(
        self,
        notification_id: str,
        stock_code: str,
        recommendation: str,
        confidence: int,
        reasoning: str,
        entry_price: Optional[float] = None,
        recommended_at: Optional[str] = None,
        entry_date: Optional[str] = None,
        entry_note: str = "",
    ) -> bool:
        """
        Mükerrer kontrolü yaparak yeni bir paper trade kaydı açar.
        """
        # Mükerrer kontrolü ve Sermaye Kapasitesi Kontrolü
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM paper_trades WHERE notification_id = ?;",
                (notification_id,),
            )
            if cursor.fetchone():
                logger.debug(f"[PaperTrade] Bildirim {notification_id} için zaten kayıt mevcut, atlandı.")
                return False

            # Sermaye Kapasitesi Kontrolü
            start_capital = getattr(settings, "SIMULATION_START_CAPITAL", 100000.0)
            alloc_pct = getattr(settings, "POSITION_ALLOCATION_PCT", 0.10)
            pos_size = start_capital * alloc_pct

            cursor.execute("SELECT COUNT(*) FROM paper_trades WHERE checked_5d = 0;")
            open_count = cursor.fetchone()[0]
            allocated_capital = open_count * pos_size

            if allocated_capital + pos_size > start_capital:
                skip_msg = (
                    f"Yetersiz Sermaye: {open_count} açık pozisyon (₺{allocated_capital:,.0f} bağlı). "
                    f"Maksimum sermaye kapasitesine (₺{start_capital:,.0f}) ulaşıldığı için işlem atlandı."
                )
                logger.warning(f"⚠️ [Sermaye Yetersiz] {stock_code} {recommendation} atlandı: {skip_msg}")
                cursor.execute(
                    """
                    INSERT INTO skipped_trades (
                        notification_id, stock_code, recommendation, confidence, reasoning, skip_reason
                    ) VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (
                        notification_id,
                        stock_code.strip().upper(),
                        recommendation.strip().upper(),
                        int(confidence),
                        reasoning.strip(),
                        skip_msg,
                    ),
                )
                return False

            now_str = recommended_at or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            query = """
                INSERT INTO paper_trades (
                    notification_id, stock_code, recommendation, confidence,
                    reasoning, recommended_at, entry_price, entry_date, entry_note,
                    outcome_1d, outcome_5d
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'BEKLEMEDE', 'BEKLEMEDE');
            """
            cursor.execute(
                query,
                (
                    notification_id,
                    stock_code.strip().upper(),
                    recommendation.strip().upper(),
                    int(confidence),
                    reasoning.strip(),
                    now_str,
                    entry_price,
                    entry_date or now_str.split()[0],
                    entry_note,
                ),
            )
            logger.info(
                f"📝 [PaperTrade Kaydedildi] {stock_code} - {recommendation} "
                f"(Giriş Fiyatı: {entry_price or 'Bilinmiyor'})"
            )
            return cursor.rowcount > 0

    def get_pending_paper_trades(self) -> List[Dict[str, Any]]:
        """
        1G veya 5G doğrulama bekleyen (checked_1d = 0 veya checked_5d = 0) işlemleri getirir.
        """
        query = """
            SELECT pt.*, kn.publish_date, kn.title, kn.summary, kn.link
            FROM paper_trades pt
            LEFT JOIN kap_notifications kn ON pt.notification_id = kn.id
            WHERE pt.checked_1d = 0 OR pt.checked_5d = 0
            ORDER BY pt.recommended_at ASC;
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]

    def update_paper_trade_1d(
        self,
        trade_id: int,
        price_1d: float,
        outcome_1d: str,
        pnl_1d: Optional[float] = None,
    ) -> bool:
        """1 günlük kontrol sonucunu ve simüle PnL'ini günceller."""
        query = """
            UPDATE paper_trades 
            SET price_1d = ?, outcome_1d = ?, pnl_1d = ?, checked_1d = 1 
            WHERE id = ?;
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (price_1d, outcome_1d, pnl_1d, trade_id))
            return cursor.rowcount > 0

    def update_paper_trade_5d(
        self,
        trade_id: int,
        price_5d: float,
        outcome_5d: str,
        pnl_5d: Optional[float] = None,
    ) -> bool:
        """5 günlük kontrol sonucunu ve simüle PnL'ini günceller."""
        query = """
            UPDATE paper_trades 
            SET price_5d = ?, outcome_5d = ?, pnl_5d = ?, checked_5d = 1 
            WHERE id = ?;
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (price_5d, outcome_5d, pnl_5d, trade_id))
            return cursor.rowcount > 0

    def get_all_paper_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Tüm paper trading kayıtlarını ve ilişkili bildirim detaylarını döner."""
        query = """
            SELECT pt.*, 
                   kn.company_name, kn.title, kn.subject, kn.summary, 
                   kn.raw_content, kn.link, kn.publish_date, kn.analyzed_at
            FROM paper_trades pt
            LEFT JOIN kap_notifications kn ON pt.notification_id = kn.id
            ORDER BY pt.recommended_at DESC, pt.id DESC
            LIMIT ?;
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_paper_trade_detail(self, trade_id: int) -> Optional[Dict[str, Any]]:
        """Tek bir işlemin tam detayını ve bildirim içeriğini döner."""
        query = """
            SELECT pt.*, 
                   kn.company_name, kn.title, kn.subject, kn.summary, 
                   kn.raw_content, kn.link, kn.publish_date, kn.analyzed_at,
                   kn.disclosure_class, kn.disclosure_type
            FROM paper_trades pt
            LEFT JOIN kap_notifications kn ON pt.notification_id = kn.id
            WHERE pt.id = ?;
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (trade_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_paper_trades_stats(self) -> Dict[str, Any]:
        """
        Paper trading istatistik özetini ve toplam simüle P&L'i döner.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM paper_trades;")
            total_trades = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM paper_trades WHERE recommendation = 'AL';")
            total_al = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM paper_trades WHERE recommendation = 'SAT';")
            total_sat = cursor.fetchone()[0]

            # 1G İstatistikleri
            cursor.execute("SELECT COUNT(*) FROM paper_trades WHERE checked_1d = 1;")
            resolved_1d = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM paper_trades WHERE checked_1d = 1 AND outcome_1d = 'DOĞRU';")
            correct_1d = cursor.fetchone()[0]

            hit_rate_1d = (correct_1d / resolved_1d * 100) if resolved_1d > 0 else 0.0

            cursor.execute("SELECT COALESCE(SUM(pnl_1d), 0.0) FROM paper_trades WHERE checked_1d = 1;")
            total_pnl_1d = cursor.fetchone()[0]

            # 5G İstatistikleri
            cursor.execute("SELECT COUNT(*) FROM paper_trades WHERE checked_5d = 1;")
            resolved_5d = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM paper_trades WHERE checked_5d = 1 AND outcome_5d = 'DOĞRU';")
            correct_5d = cursor.fetchone()[0]

            hit_rate_5d = (correct_5d / resolved_5d * 100) if resolved_5d > 0 else 0.0

            cursor.execute("SELECT COALESCE(SUM(pnl_5d), 0.0) FROM paper_trades WHERE checked_5d = 1;")
            total_pnl_5d = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM paper_trades WHERE checked_1d = 0 OR checked_5d = 0;")
            pending_count = cursor.fetchone()[0]

            # Güven Seviyesine Göre 5G İsabet Dağılımı
            confidence_stats: Dict[str, Any] = {}
            for conf_level in range(1, 6):
                cursor.execute(
                    "SELECT COUNT(*) FROM paper_trades WHERE confidence = ? AND checked_5d = 1;",
                    (conf_level,),
                )
                conf_total = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM paper_trades WHERE confidence = ? AND checked_5d = 1 AND outcome_5d = 'DOĞRU';",
                    (conf_level,),
                )
                conf_correct = cursor.fetchone()[0]

                conf_hit_rate = (
                    round((conf_correct / conf_total * 100), 1) if conf_total > 0 else 0.0
                )
                confidence_stats[str(conf_level)] = {
                    "confidence": conf_level,
                    "sample_count": conf_total,
                    "correct_count": conf_correct,
                    "hit_rate_5d": conf_hit_rate,
                    "has_sufficient_data": conf_total >= 10,
                }

            return {
                "total_trades": total_trades,
                "total_al": total_al,
                "total_sat": total_sat,
                "resolved_1d": resolved_1d,
                "correct_1d": correct_1d,
                "hit_rate_1d": round(hit_rate_1d, 1),
                "total_pnl_1d": round(float(total_pnl_1d), 2),
                "resolved_5d": resolved_5d,
                "correct_5d": correct_5d,
                "hit_rate_5d": round(hit_rate_5d, 1),
                "total_pnl_5d": round(float(total_pnl_5d), 2),
                "pending_count": pending_count,
                "confidence_stats": confidence_stats,
                "position_size": getattr(settings, "SIMULATED_POSITION_SIZE", 10000.0),
            }

    def get_recent_recommendations(
        self, limit: int = 50, recommendation_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Yapay zeka tarafından analiz edilmiş en son önerileri döner."""
        query = """
            SELECT id, disclosure_index, stock_code, stock_codes, company_name,
                   title, subject, publish_date, summary, link,
                   recommendation, reasoning, confidence, analyzed_at, created_at
            FROM kap_notifications 
            WHERE recommendation IS NOT NULL
        """
        params: List[Any] = []

        if recommendation_filter:
            query += " AND recommendation = ?"
            params.append(recommendation_filter.strip().upper())

        query += " ORDER BY analyzed_at DESC, created_at DESC LIMIT ?;"
        params.append(limit)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_recent_notifications(
        self, limit: int = 50, stock_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """En son eklenen bildirimleri getirir."""
        query = "SELECT * FROM kap_notifications"
        params: List[Any] = []

        if stock_code:
            query += " WHERE stock_code LIKE ?"
            params.append(f"%{stock_code}%")

        query += " ORDER BY created_at DESC, publish_date DESC LIMIT ?"
        params.append(limit)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def mark_as_processed(self, notification_id: str) -> bool:
        """Belirtilen bildirimi işlendi (is_processed = 1) olarak işaretler."""
        query = "UPDATE kap_notifications SET is_processed = 1 WHERE id = ?;"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (notification_id,))
            return cursor.rowcount > 0

    def reset_paper_trading_simulation(self) -> Dict[str, Any]:
        """
        Paper Trading ve Portföy Simülasyonunu sıfırlar:
        - paper_trades tablosundaki tüm kayıtları temizler.
        - skipped_trades tablosunu temizler.
        - system_state tablosunu günceller.
        - Portföy bakiyesi ₺100.000,00 nakite döner.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM paper_trades;")
            pt_deleted = cursor.rowcount
            cursor.execute("DELETE FROM skipped_trades;")
            st_deleted = cursor.rowcount
            cursor.execute("DELETE FROM system_state;")
            try:
                cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('paper_trades', 'skipped_trades');")
            except Exception:
                pass

        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        self.record_heartbeat()
        logger.info(f"🔄 Portföy simülasyonu sıfırlandı: {pt_deleted} işlem temizlendi, bakiye ₺100.000 nakite döndü.")
        return {
            "status": "success",
            "message": "Portföy simülasyonu başarıyla sıfırlandı. Kasa ₺100.000,00 nakite döndü.",
            "deleted_trades": pt_deleted,
            "deleted_skipped": st_deleted,
            "reset_at": now_str,
        }

    def delete_test_notifications(self) -> int:
        """Test amaçlı eklenmiş sahte bildirimleri veritabanından temizler."""
        query = """
            DELETE FROM kap_notifications 
            WHERE id LIKE 'TEST-%' OR title LIKE '%TEST VERİSİ%' OR summary LIKE '%TEST VERİSİ%';
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            deleted_count = cursor.rowcount
            logger.info(f"Veritabanından {deleted_count} adet test kaydı temizlendi.")
            return deleted_count

    def get_stats(self) -> Dict[str, Any]:
        """Sistem durumunu ve istatistikleri döner."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM kap_notifications;")
            total_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM kap_notifications WHERE is_processed = 0;")
            unprocessed_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM kap_notifications WHERE recommendation IS NOT NULL;")
            analyzed_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT stock_code) FROM kap_notifications;")
            unique_companies = cursor.fetchone()[0]

            cursor.execute("SELECT MAX(created_at) FROM kap_notifications;")
            last_created = cursor.fetchone()[0]

            return {
                "total_notifications": total_count,
                "unprocessed_notifications": unprocessed_count,
                "analyzed_notifications": analyzed_count,
                "processed_notifications": total_count - unprocessed_count,
                "unique_companies_tracked": unique_companies,
                "last_update": last_created or "Henüz veri yok",
            }

    # =========================================================================
    # SİSTEM DURUMU, ÇALIŞMA SÜRESİ (HEARTBEAT) & PORTFÖY SİMÜLASYONU
    # =========================================================================

    def record_heartbeat(self):
        """
        Sistemin canlı olduğunu ve en son döngü aktivite anını veritabanına kaydeder.
        """
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO system_state (key, value, updated_at) VALUES ('last_heartbeat', ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at;
                """,
                (now_str, now_str),
            )
            cursor.execute(
                """
                INSERT OR IGNORE INTO system_state (key, value, updated_at) VALUES ('started_at', ?, ?);
                """,
                (now_str, now_str),
            )

    def get_system_state(self) -> Dict[str, Any]:
        """
        Sistemin çalışma süresi, son kalp atışı ve aktiflik durumunu döner.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM system_state;")
            state_dict = {row["key"]: row["value"] for row in cursor.fetchall()}

        now = datetime.utcnow()
        last_hb_str = state_dict.get("last_heartbeat")
        started_str = state_dict.get("started_at")

        is_active = False
        uptime_str = "0 saat 0 dk"
        last_active_str = "Bilinmiyor"

        if last_hb_str:
            try:
                last_hb_dt = datetime.strptime(last_hb_str, "%Y-%m-%d %H:%M:%S")
                diff_sec = (now - last_hb_dt).total_seconds()
                is_active = diff_sec < 300  # 5 dakikadan yeniyse aktif
                last_active_str = last_hb_str
            except Exception:
                pass

        if started_str:
            try:
                start_dt = datetime.strptime(started_str, "%Y-%m-%d %H:%M:%S")
                total_sec = max(0, (now - start_dt).total_seconds())
                days = int(total_sec // 86400)
                hours = int((total_sec % 86400) // 3600)
                mins = int((total_sec % 3600) // 60)
                if days > 0:
                    uptime_str = f"{days} gün {hours} saat"
                else:
                    uptime_str = f"{hours} saat {mins} dk"
            except Exception:
                pass

        return {
            "started_at": started_str,
            "last_heartbeat": last_hb_str,
            "is_active": is_active,
            "uptime_str": uptime_str,
            "last_active_str": last_active_str,
        }

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Portföy simülasyonunu güncel AL/SAT eşleştirme mantığıyla hesaplar:
        1. AL önerisi -> Nakitten pozisyon açılır, SAT gelene kadar SÜRESİZ açık kalır.
        2. SAT önerisi -> O hissede açık AL varsa kapatır, kâr/zararı nakite ekler.
           Açık AL yoksa -> 'ATLANDI (Elde Pozisyon Yok)' olarak loglar.
        3. Açık pozisyonlar anlık yfinance fiyatıyla gerçekleşmemiş PnL olarak hesaplanır.
        """
        import yfinance as yf
        from ingestion.market_calendar import fetch_bist_price_safe

        start_capital = getattr(settings, "SIMULATION_START_CAPITAL", 100000.0)
        alloc_pct = getattr(settings, "POSITION_ALLOCATION_PCT", 0.10)
        pos_size = start_capital * alloc_pct  # örn. 10.000 TL

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT pt.*, kn.company_name, kn.title, kn.publish_date
                FROM paper_trades pt
                LEFT JOIN kap_notifications kn ON pt.notification_id = kn.id
                ORDER BY pt.recommended_at ASC, pt.id ASC;
                """
            )
            trades = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT COUNT(*) FROM skipped_trades;")
            db_skipped_count = cursor.fetchone()[0]

        open_positions: Dict[str, List[Dict[str, Any]]] = {}
        all_positions: List[Dict[str, Any]] = []
        skipped_positions: List[Dict[str, Any]] = []
        total_realized_pnl = 0.0

        for trade in trades:
            stock = trade["stock_code"]
            rec = trade["recommendation"]
            entry_p = trade["entry_price"] or 0.0
            rec_at = trade["recommended_at"] or ""

            if rec == "AL":
                pos = {
                    "id": trade["id"],
                    "stock_code": stock,
                    "company_name": trade.get("company_name") or stock,
                    "recommendation": "AL",
                    "entry_price": round(entry_p, 2),
                    "current_or_exit_price": None,
                    "position_size": pos_size,
                    "status": "AÇIK",
                    "date": rec_at,
                    "exit_date": None,
                    "pnl": 0.0,
                    "return_pct": 0.0,
                }
                open_positions.setdefault(stock, []).append(pos)
                all_positions.append(pos)
            elif rec == "SAT":
                if open_positions.get(stock):
                    # O hissede açık AL pozisyonunu kapat
                    open_pos = open_positions[stock].pop(0)
                    open_pos["status"] = "KAPANDI"
                    open_pos["current_or_exit_price"] = round(entry_p, 2)
                    open_pos["exit_date"] = rec_at
                    
                    if open_pos["entry_price"] > 0:
                        raw_ret = (entry_p - open_pos["entry_price"]) / open_pos["entry_price"]
                        pnl = pos_size * raw_ret
                        ret_pct = raw_ret * 100.0
                    else:
                        pnl = 0.0
                        ret_pct = 0.0

                    open_pos["pnl"] = round(pnl, 2)
                    open_pos["return_pct"] = round(ret_pct, 2)
                    total_realized_pnl += pnl
                else:
                    # Elde hisse yokken gelen SAT sinyali -> Atlandı
                    skipped_positions.append({
                        "id": trade["id"],
                        "stock_code": stock,
                        "company_name": trade.get("company_name") or stock,
                        "recommendation": "SAT",
                        "entry_price": round(entry_p, 2),
                        "current_or_exit_price": round(entry_p, 2),
                        "position_size": 0.0,
                        "status": "ATLANDI (Elde Pozisyon Yok)",
                        "date": rec_at,
                        "exit_date": None,
                        "pnl": 0.0,
                        "return_pct": 0.0,
                    })

        # Açık kalan tüm pozisyonların anlık PnL'ini hesapla
        total_unrealized_pnl = 0.0
        for pos in all_positions:
            if pos["status"] == "AÇIK":
                live_p = fetch_bist_price_safe(pos["stock_code"], datetime.now()) or pos["entry_price"]
                if pos["entry_price"] > 0 and live_p > 0:
                    raw_ret = (live_p - pos["entry_price"]) / pos["entry_price"]
                    pnl = pos["position_size"] * raw_ret
                    ret_pct = raw_ret * 100.0
                else:
                    pnl = 0.0
                    ret_pct = 0.0

                pos["current_or_exit_price"] = round(live_p, 2)
                pos["pnl"] = round(pnl, 2)
                pos["return_pct"] = round(ret_pct, 2)
                total_unrealized_pnl += pnl

        total_pnl = total_realized_pnl + total_unrealized_pnl
        current_balance = start_capital + total_pnl
        total_return_pct = round((total_pnl / start_capital) * 100.0, 2) if start_capital > 0 else 0.0

        # BIST100 Kıyaslaması (XU100.IS)
        bist100_return_pct = 0.0
        try:
            xu100 = yf.Ticker("XU100.IS")
            hist = xu100.history(period="1mo")
            if not hist.empty and len(hist) >= 2:
                p_start = float(hist["Close"].iloc[0])
                p_now = float(hist["Close"].iloc[-1])
                if p_start > 0:
                    bist100_return_pct = round(((p_now - p_start) / p_start) * 100.0, 2)
        except Exception as x_err:
            logger.debug(f"BIST100 getirisi hesaplanamadı: {x_err}")

        beats_bist100 = total_return_pct >= bist100_return_pct
        system_state = self.get_system_state()

        open_count = sum(1 for p in all_positions if p["status"] == "AÇIK")
        closed_count = sum(1 for p in all_positions if p["status"] == "KAPANDI")
        total_skipped_count = db_skipped_count + len(skipped_positions)

        # Tabloda gösterilecek birleşik liste
        combined_positions = all_positions + skipped_positions

        return {
            "start_capital": start_capital,
            "current_balance": round(current_balance, 2),
            "total_pnl": round(total_pnl, 2),
            "total_return_pct": total_return_pct,
            "realized_pnl": round(total_realized_pnl, 2),
            "unrealized_pnl": round(total_unrealized_pnl, 2),
            "open_positions_count": open_count,
            "closed_positions_count": closed_count,
            "skipped_trades_count": total_skipped_count,
            "bist100_return_pct": bist100_return_pct,
            "beats_bist100": beats_bist100,
            "system_state": system_state,
            "positions": combined_positions,
        }


# Singleton veritabanı yöneticisi
db = DatabaseManager()
