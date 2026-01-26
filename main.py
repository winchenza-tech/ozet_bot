import asyncio
import nest_asyncio
import datetime
import os
from collections import deque
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from google import genai
from google.genai import types

# --- 1. WEB SUNUCUSU (7/24 UYANIK TUTMA) ---
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Zenithar 7/24 Görev Başında!"

def run_flask():
    # Render'ın portunu yakala
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# --- 2. AYARLAR VE HAFIZA ---
nest_asyncio.apply()

# Token ve API Key (Burayı kontrol etmeyi unutma)
TELEGRAM_TOKEN = "8531416366:AAHRKn0pkd-wrRGeYafN7bB_vNNKjSaDr-k"
GOOGLE_API_KEY = "AIzaSyBtAQLG5jw-nIG83Pa1w2oDi5GvOKZ-CPQ"

client = genai.Client(api_key=GOOGLE_API_KEY)

group_history = deque(maxlen=450)
last_usage = {} 
COOLDOWN_MINUTES = 10

# --- 3. BOT FONKSİYONLARI ---

async def record_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gruptaki normal mesajları hafızaya kaydeder."""
    if update.message and update.message.text:
        user = update.effective_user.first_name
        text = update.message.text
        group_history.append(f"{user}: {text}")

async def summarize_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Özet komutunu işler."""
    chat_id = update.effective_chat.id
    now = datetime.datetime.now()

    # --- BEKLEME SÜRESİ KONTROLÜ ---
    if chat_id in last_usage:
        gecen_sure = now - last_usage[chat_id]
        kalan_saniye = (COOLDOWN_MINUTES * 60) - gecen_sure.total_seconds()
        if kalan_saniye > 0:
            dakika, saniye = int(kalan_saniye // 60), int(kalan_saniye % 60)
            await update.message.reply_text(f"🛑 Henüz hazır değilim! {dakika} dk {saniye} sn bekle. Zenithar'ı kızdırmamalıyım.")
            return

    # --- KOMUT VE MESAJ SAYISI ANALİZİ ---
    msg_text = update.message.text.lower()
    count = 400 if "400" in msg_text else 200

    if len(group_history) < 10:
        await update.message.reply_text("❌ Hafızada yeterli mesaj yok (En az 10 mesaj gerekli).")
        return

    # Geçici mesaj gönderilir
    status_msg = await update.message.reply_text("⏳ Yukarıdaki mesajları okuyorum. Lütfen bekle...")

    # --- PROMPT HAZIRLIĞI ---
    full_text = "\n".join(list(group_history)[-count:])
    
    # Gizem için dinamik isim kuralı (Dakika tek ise Kralicemiz)
    gizem_adi = "Kralicemiz Gizem" if now.minute % 2 != 0 else "Gizem"

    prompt = f"""
    Aşağıdaki konuşmaları samimi ve esprili bir dille özetle. Özel kurallar:
    1: Mesajlar arasında Zenithar, Gizem veya Cıtkırıldı varsa bunları özete mutlaka dahil et ama hep de onlardan bahsetme diğerleriyle eşit derecede olsun. Bu özeti bana verdiğin saat tek sayı ise ve özette Gizem varsa ondan Kralicemiz Gizem diyerek bahset, Çift sayı ise sadece Gizem diyebilirsin.
    2: Özette Felicia ya da Tuna varsa onlarla dalga geç ve onlara biraz laf sok ama abartma sadece hafif dokundur. Eğer yoklarsa isimlerini anma.
    3: Özet içerisinde asla *(yıldız) işareti kullanma.
    4: Yazılanların hepsini 'o şunu dedi bu bunu dedi' gibi aynen yazmak yerine daha çok olay olarak özetle. Daha çok ince espri kat. 
    5: Bir kişinin ismi tek harften oluşabilir örneğin 'F' ile 'Felicia'yı karıştırma, özet maksimum 500 kelimelik olsun.
    
    KONUŞMALAR:
    {full_text}
    """

    # --- GEMINI ÜRETİM ---
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt,
            config=types.GenerateContentConfig(
                safety_settings=[
                    
                    types.SafetySetting(category='DANGEROUS_CONTENT', threshold='BLOCK_NONE'),
                ]
            )
        )
        
        # --- MESAJ YÖNETİMİ ---
        # 1. "Bekleyin" mesajını siliyoruz
        await status_msg.delete()
        
        # 2. Özeti YENİ bir mesaj olarak gönderiyoruz
        await update.message.reply_text(f"📝 CHAT ÖZETİ:\n{response.text}")
        
        # Başarılı olursa süreyi kaydet
        last_usage[chat_id] = now

    except Exception as e:
        print(f"Hata Detayı: {e}")
        # Hata olursa da "bekleyin" mesajını silip hatayı yeni mesajla bildiriyoruz
        await status_msg.delete()
        await update.message.reply_text(f"⚠️ Hata: {e}")

# --- 4. ANA ÇALIŞTIRICI ---
async def main():
    # Flask'ı başlat
    keep_alive()
    
    # Telegram Botu Kur
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Handlerlar (Regex: /son200, /son400 ve @chat_ozet_bot desteği)
    application.add_handler(MessageHandler(
        filters.Regex(r'(?i)^/son(200|400)(@chat_ozet_bot)?$'), 
        summarize_command
    ))
    
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), record_message))

    print("🚀 Zenithar Nihai Sürüm Aktif. 7/24 Render dinlemesinde...")
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    
    # Uygulamanın kapanmaması için sonsuz döngü
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Sistem kapatıldı.")
