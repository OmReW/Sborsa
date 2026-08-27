import requests
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

prompt = """Aşağıdaki KAP bildirimini analiz et.
Şirket: THYAO
Başlık: Yeni Uçak Alımı ve Filo Genişlemesi
İçerik: Şirketimiz 50 adet yeni nesil A350 uçak alımı için anlaşmaya varmıştır.

Bu bildirimin hisse fiyatına kısa vadede etkisi ne yönde olabilir? 
SADECE şu JSON formatında cevap ver: 
{"recommendation": "AL/SAT/NÖTR", "reasoning": "kısa gerekçe", "confidence": 1-5}"""

payload = {
    "model": "ozel-qwen:latest",
    "prompt": prompt,
    "stream": False,
    "format": "json",
}

if __name__ == "__main__":
    print("Ollama'ya istek gönderiliyor...")
    try:
        r = requests.post("http://localhost:11434/api/generate", json=payload, timeout=120)
        print(f"Status: {r.status_code}")
        res_text = r.json().get("response")
        print(f"Model Yanıtı:\n{res_text}")
        parsed = json.loads(res_text)
        print("\nBaşarıyla JSON Parse Edildi:")
        print(parsed)
    except Exception as e:
        print(f"Ollama bağlantı hatası: {e}")
