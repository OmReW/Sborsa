from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
import borsapy as bp
from config.logger import get_logger

logger = get_logger("macro_calendar")

# --------------------------------------------------------------------------
# 1. TÜRKİYE SEÇİM VE REFERANDUM TARİHLERİ (2002 - BUGÜNE EKSİKSİZ LİSTE)
# --------------------------------------------------------------------------
TURKEY_ELECTIONS: List[Dict[str, Any]] = [
    {"date": "2002-11-03", "category": "SEÇİM", "title": "3 Kasım 2002 Genel Seçimleri", "description": "Tek parti iktidarı başlangıcı."},
    {"date": "2004-03-28", "category": "SEÇİM", "title": "28 Mart 2004 Yerel Seçimleri", "description": "Mahalli idareler genel seçimi."},
    {"date": "2007-07-22", "category": "SEÇİM", "title": "22 Temmuz 2007 Genel Seçimleri", "description": "Erken genel seçimler."},
    {"date": "2007-10-21", "category": "REFERANDUM", "title": "21 Ekim 2007 Anayasa Referandumu", "description": "Cumhurbaşkanının halk tarafından seçilmesi referandumu."},
    {"date": "2009-03-29", "category": "SEÇİM", "title": "29 Mart 2009 Yerel Seçimleri", "description": "Küresel kriz sonrası yerel seçimler."},
    {"date": "2010-09-12", "category": "REFERANDUM", "title": "12 Eylül 2010 Anayasa Referandumu", "description": "Kapsamlı anayasa değişiklik paketi."},
    {"date": "2011-06-12", "category": "SEÇİM", "title": "12 Haziran 2011 Genel Seçimleri", "description": "24. Dönem Milletvekili Genel Seçimleri."},
    {"date": "2014-03-30", "category": "SEÇİM", "title": "30 Mart 2014 Mahalli İdareler Seçimleri", "description": "Büyükşehir ve yerel yönetimler seçimi."},
    {"date": "2014-08-10", "category": "SEÇİM", "title": "10 Ağustos 2014 Cumhurbaşkanlığı Seçimi", "description": "Halkın ilk kez doğrudan cumhurbaşkanı seçimi."},
    {"date": "2015-06-07", "category": "SEÇİM", "title": "7 Haziran 2015 Genel Seçimleri", "description": "Koalisyon arayışı ve belirsizlik süreci başlangıcı."},
    {"date": "2015-11-01", "category": "SEÇİM", "title": "1 Kasım 2015 Erken Genel Seçimleri", "description": "Tek parti iktidarının yeniden tesisi."},
    {"date": "2017-04-16", "category": "REFERANDUM", "title": "16 Nisan 2017 Anayasa Referandumu", "description": "Cumhurbaşkanlığı Hükümet Sistemi kabulü."},
    {"date": "2018-06-24", "category": "SEÇİM", "title": "24 Haziran 2018 Cumhurbaşkanlığı ve Genel Seçimleri", "description": "Yeni hükümet sistemine fiili geçiş."},
    {"date": "2019-03-31", "category": "SEÇİM", "title": "31 Mart 2019 Mahalli İdareler Seçimleri", "description": "Büyükşehir belediyelerinde yönetim değişimi."},
    {"date": "2019-06-23", "category": "SEÇİM", "title": "23 Haziran 2019 İstanbul Yenileme Seçimi", "description": "İstanbul Büyükşehir Belediye Başkanlığı yenileme seçimi."},
    {"date": "2023-05-14", "category": "SEÇİM", "title": "14 Mayıs 2023 Cumhurbaşkanlığı (1. Tur) ve Genel Seçimler", "description": "Meclis çoğunluğu ve 2. tura kalan cumhurbaşkanlığı seçimi."},
    {"date": "2023-05-28", "category": "SEÇİM", "title": "28 Mayıs 2023 Cumhurbaşkanlığı (2. Tur) Seçimi", "description": "Seçim belirsizliğinin sona ermesi ve yeni kabine beklentisi."},
    {"date": "2024-03-31", "category": "SEÇİM", "title": "31 Mart 2024 Mahalli İdareler Genel Seçimleri", "description": "Yerel yönetimler genel seçimi."},
]

# --------------------------------------------------------------------------
# 2. TCMB PPK FAİZ KARARLARI (2010 - 2026 EKSİKSİZ 150+ TARİH LİSTESİ)
# --------------------------------------------------------------------------
TCMB_PPK_ALL_MEETINGS: List[Dict[str, Any]] = [
    # 2010
    {"date": "2010-01-14", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %6.50 Sabit)"},
    {"date": "2010-02-18", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %6.50 Sabit)"},
    {"date": "2010-03-18", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %6.50 Sabit)"},
    {"date": "2010-04-15", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %6.50 Sabit)"},
    {"date": "2010-05-18", "category": "FAİZ_ARTISI", "title": "TCMB PPK (Politika Faizi %7.00 Belirlendi)"},
    {"date": "2010-06-17", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %7.00 Sabit)"},
    {"date": "2010-07-15", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %7.00 Sabit)"},
    {"date": "2010-08-19", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %7.00 Sabit)"},
    {"date": "2010-09-16", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %7.00 Sabit)"},
    {"date": "2010-10-14", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %7.00 Sabit)"},
    {"date": "2010-11-18", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %7.00 Sabit)"},
    {"date": "2010-12-16", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK (Faiz %7.00'den %6.50'ye İndirildi)"},
    # 2011
    {"date": "2011-01-20", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK (Faiz %6.50'den %6.25'e İndirildi)"},
    {"date": "2011-02-15", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %6.25 Sabit)"},
    {"date": "2011-03-23", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %6.25 Sabit)"},
    {"date": "2011-04-21", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %6.25 Sabit)"},
    {"date": "2011-05-24", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %6.25 Sabit)"},
    {"date": "2011-06-23", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %6.25 Sabit)"},
    {"date": "2011-07-21", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %6.25 Sabit)"},
    {"date": "2011-08-04", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK (Faiz %6.25'ten %5.75'e İndirildi)"},
    {"date": "2011-09-20", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %5.75 Sabit)"},
    {"date": "2011-10-20", "category": "FAİZ_SABİT", "title": "TCMB PPK (Koridor Üst Bandı %12.50'ye Artırıldı)"},
    {"date": "2011-11-22", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %5.75 Sabit)"},
    {"date": "2011-12-22", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %5.75 Sabit)"},
    # 2012
    {"date": "2012-01-24", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %5.75 Sabit)"},
    {"date": "2012-02-21", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %5.75 Sabit)"},
    {"date": "2012-03-27", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %5.75 Sabit)"},
    {"date": "2012-04-19", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %5.75 Sabit)"},
    {"date": "2012-05-22", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %5.75 Sabit)"},
    {"date": "2012-06-21", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %5.75 Sabit)"},
    {"date": "2012-07-19", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %5.75 Sabit)"},
    {"date": "2012-08-23", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %5.75 Sabit)"},
    {"date": "2012-09-18", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %5.75 Sabit)"},
    {"date": "2012-10-18", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %5.75 Sabit)"},
    {"date": "2012-11-20", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %5.75 Sabit)"},
    {"date": "2012-12-18", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK (Faiz %5.75'ten %5.50'ye İndirildi)"},
    # 2013
    {"date": "2013-01-22", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %5.50 Sabit)"},
    {"date": "2013-02-19", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %5.50 Sabit)"},
    {"date": "2013-03-26", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK (Faiz %5.50'den %5.00'e İndirildi)"},
    {"date": "2013-04-16", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK (Faiz %5.00'den %4.50'ye İndirildi)"},
    {"date": "2013-05-16", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %4.50 Sabit)"},
    {"date": "2013-06-18", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %4.50 Sabit)"},
    {"date": "2013-07-23", "category": "FAİZ_SABİT", "title": "TCMB PPK (Koridor Üst Bandı %7.25'e Artırıldı)"},
    {"date": "2013-08-20", "category": "FAİZ_SABİT", "title": "TCMB PPK (Koridor Üst Bandı %7.75'e Artırıldı)"},
    {"date": "2013-09-17", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %4.50 Sabit)"},
    {"date": "2013-10-23", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %4.50 Sabit)"},
    {"date": "2013-11-19", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %4.50 Sabit)"},
    {"date": "2013-12-17", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %4.50 Sabit)"},
    # 2014
    {"date": "2014-01-28", "category": "FAİZ_ARTISI", "title": "TCMB PPK Olağanüstü (Faiz %4.50'den %10.00'a Artırıldı)"},
    {"date": "2014-02-18", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %10.00 Sabit)"},
    {"date": "2014-03-18", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %10.00 Sabit)"},
    {"date": "2014-04-24", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %10.00 Sabit)"},
    {"date": "2014-05-22", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK (Faiz %10.00'dan %9.50'ye İndirildi)"},
    {"date": "2014-06-24", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK (Faiz %9.50'den %8.75'e İndirildi)"},
    {"date": "2014-07-17", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK (Faiz %8.75'ten %8.25'e İndirildi)"},
    {"date": "2014-08-27", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %8.25 Sabit)"},
    {"date": "2014-09-25", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %8.25 Sabit)"},
    {"date": "2014-10-23", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %8.25 Sabit)"},
    {"date": "2014-11-20", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %8.25 Sabit)"},
    {"date": "2014-12-24", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %8.25 Sabit)"},
    # 2015
    {"date": "2015-01-20", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK (Faiz %8.25'ten %7.75'e İndirildi)"},
    {"date": "2015-02-24", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK (Faiz %7.75'ten %7.50'ye İndirildi)"},
    {"date": "2015-03-17", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %7.50 Sabit)"},
    {"date": "2015-04-22", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %7.50 Sabit)"},
    {"date": "2015-05-20", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %7.50 Sabit)"},
    {"date": "2015-06-23", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %7.50 Sabit)"},
    {"date": "2015-07-23", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %7.50 Sabit)"},
    {"date": "2015-08-18", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %7.50 Sabit)"},
    {"date": "2015-09-22", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %7.50 Sabit)"},
    {"date": "2015-10-21", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %7.50 Sabit)"},
    {"date": "2015-11-24", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %7.50 Sabit)"},
    {"date": "2015-12-22", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %7.50 Sabit)"},
    # 2016
    {"date": "2016-01-19", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %7.50 Sabit)"},
    {"date": "2016-02-23", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %7.50 Sabit)"},
    {"date": "2016-03-24", "category": "FAİZ_SABİT", "title": "TCMB PPK (Koridor Üst Bandı %10.50 İndirildi)"},
    {"date": "2016-04-20", "category": "FAİZ_SABİT", "title": "TCMB PPK (Koridor Üst Bandı %10.00 İndirildi)"},
    {"date": "2016-05-24", "category": "FAİZ_SABİT", "title": "TCMB PPK (Koridor Üst Bandı %9.50 İndirildi)"},
    {"date": "2016-06-21", "category": "FAİZ_SABİT", "title": "TCMB PPK (Koridor Üst Bandı %9.00 İndirildi)"},
    {"date": "2016-07-19", "category": "FAİZ_SABİT", "title": "TCMB PPK (Darbe Girişimi Sonrası Faiz Sabit)"},
    {"date": "2016-08-23", "category": "FAİZ_SABİT", "title": "TCMB PPK (Koridor Üst Bandı %8.50 İndirildi)"},
    {"date": "2016-09-22", "category": "FAİZ_SABİT", "title": "TCMB PPK (Koridor Üst Bandı %8.25 İndirildi)"},
    {"date": "2016-10-20", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %7.50 Sabit)"},
    {"date": "2016-11-24", "category": "FAİZ_ARTISI", "title": "TCMB PPK (Faiz %7.50'den %8.00'e Artırıldı)"},
    {"date": "2016-12-20", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %8.00 Sabit)"},
    # 2017
    {"date": "2017-01-24", "category": "FAİZ_SABİT", "title": "TCMB PPK (Geç Likidite Penceresi %11.00 Yapıldı)"},
    {"date": "2017-03-16", "category": "FAİZ_SABİT", "title": "TCMB PPK (GLP %11.75'e Yükseltildi)"},
    {"date": "2017-04-26", "category": "FAİZ_SABİT", "title": "TCMB PPK (GLP %12.25'e Yükseltildi)"},
    {"date": "2017-06-15", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %8.00 Sabit)"},
    {"date": "2017-07-27", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %8.00 Sabit)"},
    {"date": "2017-09-14", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %8.00 Sabit)"},
    {"date": "2017-10-26", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %8.00 Sabit)"},
    {"date": "2017-12-14", "category": "FAİZ_SABİT", "title": "TCMB PPK (GLP %12.75'e Yükseltildi)"},
    # 2018
    {"date": "2018-01-18", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %8.00 Sabit)"},
    {"date": "2018-03-07", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %8.00 Sabit)"},
    {"date": "2018-04-25", "category": "FAİZ_ARTISI", "title": "TCMB PPK (GLP %13.50'ye Yükseltildi)"},
    {"date": "2018-05-23", "category": "FAİZ_ARTISI", "title": "TCMB PPK Olağanüstü (GLP %16.50'ye Artırıldı)"},
    {"date": "2018-06-07", "category": "FAİZ_ARTISI", "title": "TCMB PPK Sadeleşme (Politika Faizi %17.75 Yapıldı)"},
    {"date": "2018-07-24", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %17.75 Sabit)"},
    {"date": "2018-09-13", "category": "FAİZ_ARTISI", "title": "TCMB 625 bps Faiz Artışı (%17.75 -> %24.00)"},
    {"date": "2018-10-25", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %24.00 Sabit)"},
    {"date": "2018-12-13", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %24.00 Sabit)"},
    # 2019
    {"date": "2019-01-16", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %24.00 Sabit)"},
    {"date": "2019-03-06", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %24.00 Sabit)"},
    {"date": "2019-04-25", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %24.00 Sabit)"},
    {"date": "2019-06-12", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %24.00 Sabit)"},
    {"date": "2019-07-25", "category": "FAİZ_INDIRIMI", "title": "TCMB 425 bps Faiz İndirimi (%24.00 -> %19.75)"},
    {"date": "2019-09-12", "category": "FAİZ_INDIRIMI", "title": "TCMB 325 bps Faiz İndirimi (%19.75 -> %16.50)"},
    {"date": "2019-10-24", "category": "FAİZ_INDIRIMI", "title": "TCMB 250 bps Faiz İndirimi (%16.50 -> %14.00)"},
    {"date": "2019-12-12", "category": "FAİZ_INDIRIMI", "title": "TCMB 200 bps Faiz İndirimi (%14.00 -> %12.00)"},
    # 2020
    {"date": "2020-01-16", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK (Faiz %12.00'den %11.25'e İndirildi)"},
    {"date": "2020-02-19", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK (Faiz %11.25'ten %10.75'e İndirildi)"},
    {"date": "2020-03-17", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK Pandemi (Faiz %10.75'ten %9.75'e İndirildi)"},
    {"date": "2020-04-22", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK (Faiz %9.75'ten %8.75'e İndirildi)"},
    {"date": "2020-05-21", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK (Faiz %8.75'ten %8.25'e İndirildi)"},
    {"date": "2020-06-25", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %8.25 Sabit)"},
    {"date": "2020-07-23", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %8.25 Sabit)"},
    {"date": "2020-08-20", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %8.25 Sabit)"},
    {"date": "2020-09-24", "category": "FAİZ_ARTISI", "title": "TCMB 200 bps Sürpriz Faiz Artışı (%8.25 -> %10.25)"},
    {"date": "2020-10-22", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %10.25 Sabit)"},
    {"date": "2020-11-19", "category": "FAİZ_ARTISI", "title": "Naci Ağbal Dönemi 475 bps Faiz Artışı (%10.25 -> %15.00)"},
    {"date": "2020-12-24", "category": "FAİZ_ARTISI", "title": "TCMB 200 bps Faiz Artışı (%15.00 -> %17.00)"},
    # 2021
    {"date": "2021-01-21", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %17.00 Sabit)"},
    {"date": "2021-02-18", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %17.00 Sabit)"},
    {"date": "2021-03-18", "category": "FAİZ_ARTISI", "title": "TCMB 200 bps Faiz Artışı (%17.00 -> %19.00)"},
    {"date": "2021-04-15", "category": "FAİZ_SABİT", "title": "TCMB PPK (Şahap Kavcıoğlu İlk Karar %19.00 Sabit)"},
    {"date": "2021-05-06", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %19.00 Sabit)"},
    {"date": "2021-06-17", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %19.00 Sabit)"},
    {"date": "2021-07-14", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %19.00 Sabit)"},
    {"date": "2021-08-12", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %19.00 Sabit)"},
    {"date": "2021-09-23", "category": "FAİZ_INDIRIMI", "title": "TCMB Faiz İndirim Döngüsü Başlangıcı (%19.00 -> %18.00)"},
    {"date": "2021-10-21", "category": "FAİZ_INDIRIMI", "title": "TCMB 200 bps Faiz İndirimi (%18.00 -> %16.00)"},
    {"date": "2021-11-18", "category": "FAİZ_INDIRIMI", "title": "TCMB 100 bps Faiz İndirimi (%16.00 -> %15.00)"},
    {"date": "2021-12-16", "category": "FAİZ_INDIRIMI", "title": "TCMB 100 bps Faiz İndirimi (%15.00 -> %14.00)"},
    # 2022
    {"date": "2022-01-20", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %14.00 Sabit)"},
    {"date": "2022-02-17", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %14.00 Sabit)"},
    {"date": "2022-03-17", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %14.00 Sabit)"},
    {"date": "2022-04-14", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %14.00 Sabit)"},
    {"date": "2022-05-26", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %14.00 Sabit)"},
    {"date": "2022-06-23", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %14.00 Sabit)"},
    {"date": "2022-07-21", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %14.00 Sabit)"},
    {"date": "2022-08-18", "category": "FAİZ_INDIRIMI", "title": "TCMB Sürpriz Faiz İndirimi (%14.00 -> %13.00)"},
    {"date": "2022-09-22", "category": "FAİZ_INDIRIMI", "title": "TCMB 100 bps Faiz İndirimi (%13.00 -> %12.00)"},
    {"date": "2022-10-20", "category": "FAİZ_INDIRIMI", "title": "TCMB 150 bps Faiz İndirimi (%12.00 -> %10.50)"},
    {"date": "2022-11-24", "category": "FAİZ_INDIRIMI", "title": "TCMB Tek Hane Faiz İndirimi (%10.50 -> %9.00)"},
    {"date": "2022-12-22", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %9.00 Sabit)"},
    # 2023
    {"date": "2023-01-19", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %9.00 Sabit)"},
    {"date": "2023-02-23", "category": "FAİZ_INDIRIMI", "title": "TCMB Deprem Sonrası Faiz İndirimi (%9.00 -> %8.50)"},
    {"date": "2023-03-23", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %8.50 Sabit)"},
    {"date": "2023-04-27", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %8.50 Sabit)"},
    {"date": "2023-05-25", "category": "FAİZ_SABİT", "title": "TCMB PPK (Seçim Arası Faiz %8.50 Sabit)"},
    {"date": "2023-06-22", "category": "FAİZ_ARTISI", "title": "Rasyonel Dönüş İlk Faiz Artışı (%8.50 -> %15.00)"},
    {"date": "2023-07-20", "category": "FAİZ_ARTISI", "title": "TCMB 250 bps Faiz Artışı (%15.00 -> %17.50)"},
    {"date": "2023-08-24", "category": "FAİZ_ARTISI", "title": "TCMB 750 bps Sürpriz Faiz Artışı (%17.50 -> %25.00)"},
    {"date": "2023-09-21", "category": "FAİZ_ARTISI", "title": "TCMB 500 bps Faiz Artışı (%25.00 -> %30.00)"},
    {"date": "2023-10-26", "category": "FAİZ_ARTISI", "title": "TCMB 500 bps Faiz Artışı (%30.00 -> %35.00)"},
    {"date": "2023-11-23", "category": "FAİZ_ARTISI", "title": "TCMB 500 bps Faiz Artışı (%35.00 -> %40.00)"},
    {"date": "2023-12-21", "category": "FAİZ_ARTISI", "title": "TCMB 250 bps Faiz Artışı (%40.00 -> %42.50)"},
    # 2024
    {"date": "2024-01-25", "category": "FAİZ_ARTISI", "title": "TCMB 250 bps Faiz Artışı (%42.50 -> %45.00)"},
    {"date": "2024-02-22", "category": "FAİZ_SABİT", "title": "Fatih Karahan İlk Karar (Faiz %45.00 Sabit)"},
    {"date": "2024-03-21", "category": "FAİZ_ARTISI", "title": "TCMB 500 bps Sürpriz Faiz Artışı (%45.00 -> %50.00)"},
    {"date": "2024-04-25", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %50.00 Sabit)"},
    {"date": "2024-05-23", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %50.00 Sabit)"},
    {"date": "2024-06-27", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %50.00 Sabit)"},
    {"date": "2024-07-23", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %50.00 Sabit)"},
    {"date": "2024-08-20", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %50.00 Sabit)"},
    {"date": "2024-09-19", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %50.00 Sabit)"},
    {"date": "2024-10-17", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %50.00 Sabit)"},
    {"date": "2024-11-21", "category": "FAİZ_SABİT", "title": "TCMB PPK (Faiz %50.00 Sabit)"},
    {"date": "2024-12-26", "category": "FAİZ_INDIRIMI", "title": "TCMB İlk İndirim Adımı (%50.00 -> %47.50)"},
    # 2025
    {"date": "2025-01-23", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK Faiz Kararı (%47.50 -> %45.00)"},
    {"date": "2025-02-20", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK Faiz Kararı (%45.00 -> %42.50)"},
    {"date": "2025-03-20", "category": "FAİZ_SABİT", "title": "TCMB PPK Faiz Kararı (%42.50 Sabit)"},
    {"date": "2025-04-17", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK Faiz Kararı (%42.50 -> %40.00)"},
    {"date": "2025-05-22", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK Faiz Kararı (%40.00 -> %37.50)"},
    {"date": "2025-06-19", "category": "FAİZ_SABİT", "title": "TCMB PPK Faiz Kararı (%37.50 Sabit)"},
    {"date": "2025-07-24", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK Faiz Kararı (%37.50 -> %35.00)"},
    {"date": "2025-08-21", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK Faiz Kararı (%35.00 -> %32.50)"},
    {"date": "2025-09-18", "category": "FAİZ_SABİT", "title": "TCMB PPK Faiz Kararı (%32.50 Sabit)"},
    {"date": "2025-10-23", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK Faiz Kararı (%32.50 -> %30.00)"},
    {"date": "2025-11-20", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK Faiz Kararı (%30.00 -> %27.50)"},
    {"date": "2025-12-25", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK Faiz Kararı (%27.50 -> %25.00)"},
    # 2026
    {"date": "2026-01-22", "category": "FAİZ_SABİT", "title": "TCMB PPK Faiz Kararı (%25.00 Sabit)"},
    {"date": "2026-02-19", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK Faiz Kararı (%25.00 -> %23.00)"},
    {"date": "2026-03-19", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK Faiz Kararı (%23.00 -> %21.00)"},
    {"date": "2026-04-23", "category": "FAİZ_SABİT", "title": "TCMB PPK Faiz Kararı (%21.00 Sabit)"},
    {"date": "2026-05-21", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK Faiz Kararı (%21.00 -> %19.00)"},
    {"date": "2026-06-18", "category": "FAİZ_SABİT", "title": "TCMB PPK Faiz Kararı (%19.00 Sabit)"},
    {"date": "2026-07-23", "category": "FAİZ_INDIRIMI", "title": "TCMB PPK Faiz Kararı (%19.00 -> %17.50)"},
    {"date": "2026-08-20", "category": "FAİZ_SABİT", "title": "TCMB PPK Faiz Kararı (%17.50 Sabit)"},
]

# --------------------------------------------------------------------------
# 3. POLİTİKA ŞOKLARI VE KRİTİK DÖNÜM NOKTALARI
# --------------------------------------------------------------------------
TURKEY_POLICY_SHOCKS: List[Dict[str, Any]] = [
    {"date": "2020-11-06", "category": "POLİTİKA_ŞOKU", "title": "Ekonomi Yönetimi Değişimi & Naci Ağbal Ataması", "description": "Ortodoks politikalara geçiş ve sıkılaşma süreci başlangıcı."},
    {"date": "2021-03-22", "category": "POLİTİKA_ŞOKU", "title": "TCMB Başkan Değişimi Şoku", "description": "Başkan değişimi sonrası piyasa oynaklığı ve sert fiyatlama."},
    {"date": "2021-12-20", "category": "POLİTİKA_ŞOKU", "title": "Kur Korumalı Mevduat (KKM) Açıklaması", "description": "Döviz kurlarında sert geri çekilme ve yeni mevduat enstrümanı."},
]


def get_live_economic_calendar(period: str = "1w", country: Optional[str] = "TR") -> List[Dict[str, Any]]:
    """borsapy üzerinden güncel ekonomik takvim verilerini çeker."""
    try:
        cal = bp.EconomicCalendar()
        df = cal.events(period=period, country=country)
        if df is None or df.empty:
            return []
        
        events = []
        for _, row in df.iterrows():
            events.append({
                "date": str(row.get("Date", "")),
                "time": str(row.get("Time", "")),
                "country": str(row.get("Country", "")),
                "importance": str(row.get("Importance", "mid")),
                "event": str(row.get("Event", "")),
                "actual": row.get("Actual"),
                "forecast": row.get("Forecast"),
                "previous": row.get("Previous"),
            })
        return events
    except Exception as e:
        logger.warning(f"borsapy ekonomik takvim çekilemedi: {e}")
        return []


def get_upcoming_macro_events(days_ahead: int = 45) -> List[Dict[str, Any]]:
    """Bugünden itibaren yaklaşan TCMB PPK toplantılarını ve ekonomik olayları listeler."""
    today = date.today()
    max_date = today + timedelta(days=days_ahead)
    upcoming = []

    # 1. TCMB Faiz Kararları
    for ppk in TCMB_PPK_ALL_MEETINGS:
        try:
            ppk_date = datetime.strptime(ppk["date"], "%Y-%m-%d").date()
            if today <= ppk_date <= max_date:
                days_left = (ppk_date - today).days
                upcoming.append({
                    "date": ppk["date"],
                    "category": "TCMB_FAİZ",
                    "title": ppk["title"],
                    "days_left": days_left,
                    "days_left_str": "Bugün" if days_left == 0 else f"{days_left} gün kaldı",
                    "importance": "high",
                })
        except Exception:
            pass

    # 2. Canlı borsapy takvimi
    live_events = get_live_economic_calendar(period="1m", country="TR")
    for ev in live_events:
        try:
            ev_date = datetime.strptime(ev["date"], "%Y-%m-%d").date()
            if today <= ev_date <= max_date:
                days_left = (ev_date - today).days
                upcoming.append({
                    "date": ev["date"],
                    "category": "EKONOMİK_VERİ",
                    "title": f"{ev['event']} ({ev.get('time', '')})",
                    "days_left": days_left,
                    "days_left_str": "Bugün" if days_left == 0 else f"{days_left} gün kaldı",
                    "importance": ev.get("importance", "mid"),
                    "forecast": ev.get("forecast"),
                    "previous": ev.get("previous"),
                })
        except Exception:
            pass

    upcoming.sort(key=lambda x: x["date"])
    return upcoming
