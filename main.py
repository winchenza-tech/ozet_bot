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

# --- 1. WEB SUNUCUSU (KEEP ALIVE) BÖLÜMÜ ---
# Render'ın "uyku" moduna geçmesini engelleyen Flask sunucusu
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Zenithar Bot Aktif ve 7/24 Uyanık!"

def run_flask():
    # Render'ın atadığı portu alıyoruz, bulamazsak 8080 kullanıyoruz
    port = int(os.environ.get("PORT", 8080))
    print(f"✅ Flask sunucusu {port} portunda başlatılıyor...")
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    # Flask'ı ana kodu bloklamaması için ayrı bir kanalda (Thread) başlatıyoruz
    t = Thread(target=run_flask)
    t.start()

# --- 2. AYARLAR VE HAFIZA ---
nest_asyncio.apply()

# BURAYI GÜNCELLEYİN (BotFather'dan aldığınız YENİ token)
TELEGRAM_TOKEN = "8531416366:AAEIuoU7VZKgkceMmw21bXzHVvLic6AtjmM"
GOOGLE_API_KEY = "AIzaSyBtAQLG5jw-nIG83Pa1w2oDi5GvOKZ-CPQ"

# Gemini İstemcisi
client = genai.Client(api_key=GOOGLE_API_KEY)

group_history = deque(maxlen=500)
last_usage = {}  # {chat_id: son_kullanim_zamani}
COOLDOWN_MINUTES = 10

# --- 3. BOT FONKSİYONLARI ---

async def record_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gruptaki mesajları hafızaya kaydeder."""
    if update.message and update.message.text:
        user = update.effective_user.first_name
        text = update.message.text
        group_history.append(f"{user}: {text}")

async def summarize_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Özet komutunu işler."""
    chat_id = update.effective_chat.id
    now = datetime.datetime.now()
    
    # 1. BEKLEME SÜRESİ KONTROLÜ
    if chat_id in last_usage:
        gecen_sure = now - last_usage[chat_id]
        kalan_saniye = (COOLDOWN_MINUTES * 60) - gecen_sure.total_seconds()
        
        if kalan_saniye > 0:
            dakika = int(kalan_saniye // 60)
            saniye = int(kalan_saniye % 60)
            await update.message.reply_text(
                f"🛑 Henüz hazır değilim!\n\nTekrar özet çıkarabilmek için {dakika} dakika {saniye} saniye daha beklemeniz gerekiyor. Zenithar'ı kızdırmamalıyım."
            )
            return

    # 2. MESAJ SAYISI VE KOMUT KONTROLÜ
    msg_text = update.message.text.lower().replace(" ", "")
    count = 200 if "200" in msg_text else 400 if "400" in msg_text else 0
    if count == 0: return

    if len(group_history) < 10:
        await update.message.reply_text("❌ Hafızada yeterli mesaj yok (En az 10 mesaj gerekli).")
        return

    status_msg = await update.message.reply_text("⏳ Yukaridaki mesajları okuyorum, lütfen bekle...")

    # 3. PROMPT HAZIRLAMA
    full_text = "\n".join(list(group_history)[-count:])
    prompt = f"""
    Aşağıdaki konuşmaları samimi ve esprili bir dille özetle. 
    Özel kurallar:
    1: Mesajlar arasında Zenithar, Gizem veya Cıtkırıldı varsa bunları özete mutlaka dahil et. 
    2: Şu anki dakika ({now.minute}) tek sayı ise Gizem'den 'Kralicemiz Gizem' şeklinde bahset, çift sayı ise sadece 'Gizem' de.
    3: Özette Felicia ya da Tuna varsa onlarla hafifçe dalga geç ve laf sok ama hafifçe yap bunu. Yoklarsa isimlerini anma.
    4: Özet içerisinde asla *(yıldız) işareti kullanma.
    5: Bir kişinin ismi tek ya da iki harften de oluşabilir (örneğin 'F'), bunu diğer isimlerle karıştırma.
    6: Olay odaklı ve ince esprili bir özet olsun. Maksimum 500 kelime.
    
    KONUŞMALAR:
    {full_text}
    """

    # 4. ÜRETİM
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        await status_msg.edit_text(f"📝 CHAT ÖZETİ:\n{response.text}")
        last_usage[chat_id] = now
        
    except Exception as e:
        print(f"Hata oluştu: {e}")
        await status_msg.edit_text(f"⚠️ Özet oluşturulurken bir hata oluştu.")

# --- 4. ANA ÇALIŞTIRICI ---

async def main():
    # Önce Keep-Alive sunucusunu başlatıyoruz
    keep_alive()
    
    # Telegram Uygulamasını kuruyoruz
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Handlerları (Komut ve Mesaj dinleyicileri) ekliyoruz
    application.add_handler(MessageHandler(filters.Regex(r'(?i)^/son\s*(200|400)$'), summarize_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), record_message))
    
    print("✅ Zenithar Bot ve Web Sunucusu Başarıyla Başlatıldı.")
    
    # Botu çalıştırıyoruz
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    
    # Uygulamanın kapanmaması için sonsuz döngü
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    # Scripti asenkron olarak güvenli bir şekilde başlatıyoruz
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot kapatılıyor...")

