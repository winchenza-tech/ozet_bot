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
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# --- 2. AYARLAR VE HAFIZA ---
nest_asyncio.apply()

# Hassas veriler Render Environment'tan çekiliyor
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# --- GRUP KİLİDİ VE HATA MESAJI AYARLARI ---
AUTHORIZED_GROUP_ID = -1003297262036 

# Buraya GitHub'a yüklediğin görselin "Raw" linkini yapıştırabilirsin.
# Şimdilik örnek şeffaf görsel linki duruyor.
UNAUTHORIZED_IMAGE_URL = "https://i.ibb.co/zWKH9qDH/MG-8095.jpg"

# Emojisiz, sert ve net hata metni
UNAUTHORIZED_ERROR_TEXT = (
    "Sadece ES JUSTO grubunda çalışacağını söylemiştim.\n"
    "Eğer okuduğunu anlamadıysan aşağıdaki linke tıkla.\n\n"
    "https://www.mentalup.net/blog/zeka-gelistirici-oyunlar"
)

client = genai.Client(api_key=GOOGLE_API_KEY)

group_history = deque(maxlen=300)
last_usage = {} 
COOLDOWN_MINUTES = 10

# --- 3. BOT FONKSİYONLARI ---

async def record_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
   
    # Güvenlik Kontrolü
    if update.effective_chat.id != AUTHORIZED_GROUP_ID:
        # Sadece özel mesajda (DM) görsel + metin ile cevap ver
        if update.effective_chat.type == 'private':
            await update.message.reply_photo(
               
                caption=UNAUTHORIZED_ERROR_TEXT,
                 photo=UNAUTHORIZED_IMAGE_URL
            )
        return

    # Mesaj kaydetme (Sadece yetkili grupta)
    if update.message and update.message.text:
        user = update.effective_user.first_name
        text = update.message.text
        group_history.append(f"{user}: {text}")

async def summarize_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Özet komutunu işler."""
    
    # Güvenlik Kontrolü
    if update.effective_chat.id != AUTHORIZED_GROUP_ID:
        await update.message.reply_photo(
           
            caption=UNAUTHORIZED_ERROR_TEXT,
             photo=UNAUTHORIZED_IMAGE_URL
        )
        return

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

    # --- KOMUT ANALİZİ ---
    msg_text = update.message.text.lower()
    count = 300 if "300" in msg_text else 200

    if len(group_history) < 10:
        await update.message.reply_text("❌ Hafızada yeterli mesaj yok (En az 10 mesaj gerekli).")
        return

    status_msg = await update.message.reply_text("⏳ Yukarıdaki mesajları okuyorum. Lütfen bekle...")

    # --- PROMPT ---
    full_text = "\n".join(list(group_history)[-count:])
   

    prompt = f"""
    Aşağıdaki konuşmaları samimi, esprili ve muzip bir dille özetle. Özel kurallar:
    1: Mesajlar arasında Zenithar, Gizem veya Cıtkırıldı varsa bunları özete mutlaka dahil et ama hep de onlardan bahsetme diğerleriyle eşit derecede olsun. Bu özeti bana verdiğin saat tek sayı ise ve özette Gizem varsa ondan Kralicemiz Gizem diyerek bahset, Çift sayı ise sadece Gizem diyebilirsin.
    2: Özette Felicia ya da Tuna varsa onları alaya al ve onlara biraz laf sok ama abartma sadece hafif dokundur. Eğer yoklarsa isimlerini anma.
    3: Özet içerisinde asla * (yıldız) işareti kullanma.
    4: Yazılanların hepsini 'o şunu dedi bu bunu dedi' gibi aynen yazmak yerine daha çok olay olarak özetle. Daha çok ince espri kat. 
    5: Bir kişinin ismi tek ya da iki harften oluşabilir örneğin 'F' veya 'E' ile diğer kişileri karıştırma,
    6: özet maksimum 200 kelimelik olsun. Olayları 5 paragrafa bölerek okunabilirliği artır, paragrafların başında anlatılan olaya uygun emoji kullanabilirsin, olay anlatımını uzatmadan kısa kısa özetle böylece Mümkün olduğunca daha fazla olaya ve kişiye değinebilirsin.
    
    KONUŞMALAR:
    {full_text}
    """

    # --- GEMINI ÜRETİM (SANSÜRSÜZ) ---
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt,
            config=types.GenerateContentConfig(
                safety_settings=[
                    
                    types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE'),
                ]
            )
        )
        
        # Bekleme mesajını sil ve özeti gönder
        await status_msg.delete()
        await update.message.reply_text(f"📝 CHAT ÖZETİ:\n{response.text}")
        
        last_usage[chat_id] = now

    except Exception as e:
        print(f"Hata Detayı: {e}")
        if status_msg: await status_msg.delete()
        await update.message.reply_text(f"⚠️ Hata: {e}")

# --- 4. ANA ÇALIŞTIRICI ---
async def main():
    keep_alive()
    
    if not TELEGRAM_TOKEN or not GOOGLE_API_KEY:
        print("❌ HATA: Environment Değişkenleri (TOKEN veya KEY) eksik!")
        return

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Handlerlar
    application.add_handler(MessageHandler(
        filters.Regex(r'(?i)^/son(200|300)(@chat_ozet_bot)?$'), 
        summarize_command
    ))
    
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), record_message))

    print(f"🚀 Zenithar Nihai Sürüm Aktif. Hedef Grup: {AUTHORIZED_GROUP_ID}")
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
