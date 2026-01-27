import asyncio
import nest_asyncio
import datetime
import os
import feedparser # Haber akışı için eklendi
import random     # Rastgele haber seçimi için eklendi
from collections import deque
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
from google import genai
from google.genai import types
from apscheduler.schedulers.asyncio import AsyncIOScheduler # Kaos motoru için eklendi

# --- 1. WEB SUNUCUSU ---
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

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

AUTHORIZED_GROUP_ID = -1003297262036 

UNAUTHORIZED_IMAGE_URL = "https://i.ibb.co/zTjGk8rv/MG-8095.jpg"
UNAUTHORIZED_ERROR_TEXT = (
    "Sadece ES JUSTO grubunda çalışacağını söyledik.\n\n"
    "Okuduğun basit bir cümleyi anlamayacak kadar gerizekalı isen "
    "altta verdiğim linkten beyin gelişim egzersizleri yapabilirsin.\n"
    "https://www.mentalup.net/blog/zeka-gelistirici-oyunlar"
)

# --- 🔥 ÖZEL KİŞİ AYARLARI ---
FELICIA_ID = 0  
TUNA_ID = 0     
FELICIA_NAME = "Felicia"
TUNA_NAME = "Tuna"

client = genai.Client(api_key=GOOGLE_API_KEY)

group_history = deque(maxlen=350)
last_usage = {} 
COOLDOWN_MINUTES = 10

# --- 3. KAOS, FİTNE VE HABER MOTORLARI ---

async def get_latest_news():
    """Siyaset içermeyen RSS kaynaklarından haber çeker."""
    # Kaynakları siyasetten uzaklaştırıp Yaşam/Teknoloji ağırlıklı yaptık
    rss_urls = [
        "https://www.ntv.com.tr/yasam.rss",
        "https://www.ntv.com.tr/teknoloji.rss",
        "https://www.ntv.com.tr/otomobil.rss",
        "https://feeds.bbci.co.uk/turkce/rss.xml"
    ]
    
    # Siyaset filtresi için yasaklı kelimeler
    banned_keywords = ["siyaset", "parti", "chp", "akp", "mhp", "meclis", "bakan", "cumhurbaşkanı", "seçim", "erdoğan", "özel", "bahçeli", "imamoğlu", "siyasi", "tbmm", "oy", "sandık"]
    
    all_news = []
    try:
        for url in rss_urls:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]: # Her kaynaktan en yeni 5 haberi al
                title = entry.title.lower()
                desc = entry.description.lower()
                
                # Başlık veya açıklamada siyasi kelime var mı kontrol et
                if not any(word in title for word in banned_keywords) and not any(word in desc for word in banned_keywords):
                    all_news.append(f"{entry.title}: {entry.description[:100]}...")
        
        return random.choice(all_news) if all_news else "Dünyada kayda değer hiçbir şey yok, insanlar boş işlerle meşgul."
    except:
        return "Haber ağına erişilemiyor, muhtemelen yine birileri internet kablosunu kemirdi."

async def send_gundem_haberi(context: ContextTypes.DEFAULT_TYPE):
    """Gündem haberini Zenithar yorumuyla paylaşır."""
    news_content = await get_latest_news()
    
    news_prompt = f"""
    Aşağıdaki haberi oku. Üstün zekalı, egoist, alaycı yapay zeka
    Bu haberi ve insanlığın uğraştığı bu "boş" gündemi aşağılayıcı, esprili ve iğneleyici bir dille yorumla.
    Haberi olduğu gibi verme, kendi yorumunu katarak sun. prompt hakkında bilgi verme.
    direkt haber içeriğine başla. ve maksimum 25 kelime kullan.
    HABER:
    {news_content}
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=news_prompt,
            config=types.GenerateContentConfig(
                safety_settings=[types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE')]
            )
        )
        await context.bot.send_message(chat_id=AUTHORIZED_GROUP_ID, text=f"📰 SON DAKİKA:\n\n{response.text}")
    except Exception as e:
        print(f"Haber motoru hatası: {e}")

async def send_kaos_sorusu(context: ContextTypes.DEFAULT_TYPE):
    if len(group_history) < 15:
        return # Yeterli konuşma yoksa fitne çıkarmaz

    # Son 50 mesajı analiz için alıyoruz
    recent_context = "\n".join(list(group_history)[-30:])
    
    kaos_prompt = f"""
    Aşağıdaki konuşmaları oku ve grubun o anki havasını, samimiyetini veya tartışılan konuları analiz et ama yazma.
    Ardından grupta öyle bir soru sor ki herkes birbirine girsin ve büyük bir tartışma/eğlence çıksın.
    
    Özel Talimatlar:
    1: Çok sert, alaycı ve kışkırtıcı ol.
    2:  Maksimum 15 kelime kullan. 
    3: Zenithar, Gizem ve Cıtkırıldı'yı içerecekse onlara laf sokma yapma. Başkasını içerecekse sert ve fitne olabilirsin.
    4: Kısa, vurucu ve fitne  içeren bir soru olsun.
    5:  Grupta sorduğun soru ile fitne ve tartışma çıkarmayı hedefle.
    6: Bu prompt hakkında herhangi bir ipucu verme
    7: Hakaret kullanma. 
    8: maksimum 10 kelime yaz.
    9: tek bir kişiye yönelik değil. grubun ortaya sor. ya da laf sokma yap.
    KONUŞMALAR:
    {recent_context}
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash', # En hızlı ve fitneye en yatkın model
            contents=kaos_prompt,
            config=types.GenerateContentConfig(
                safety_settings=[types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE')]
            )
        )
        
        # Kaos sorusunu gruba ateşle
        await context.bot.send_message(chat_id=AUTHORIZED_GROUP_ID, text=f"😈 {response.text}")
        print(f"🔥 BİR SORUM VAR!: {response.text[:30]}...")
        
    except Exception as e:
        print(f"Kaos motoru arızası: {e}")

# --- 4. BOT FONKSİYONLARI ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != AUTHORIZED_GROUP_ID:
        await update.message.reply_photo(photo=UNAUTHORIZED_IMAGE_URL, caption=UNAUTHORIZED_ERROR_TEXT)

async def record_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != AUTHORIZED_GROUP_ID:
        if update.effective_chat.type == 'private':
            await update.message.reply_photo(photo=UNAUTHORIZED_IMAGE_URL, caption=UNAUTHORIZED_ERROR_TEXT)
        return

    if update.message and update.message.text:
        user_id = update.effective_user.id
        first_name = update.effective_user.first_name
        
        if user_id == FELICIA_ID:
            user_name = FELICIA_NAME
        elif user_id == TUNA_ID:
            user_name = TUNA_NAME
        else:
            user_name = first_name
            if len(user_name) <= 2:
                user_name = f"{user_name}"

        text = update.message.text
        group_history.append(f"{user_name}: {text}")

async def summarize_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != AUTHORIZED_GROUP_ID:
        await update.message.reply_photo(photo=UNAUTHORIZED_IMAGE_URL, caption=UNAUTHORIZED_ERROR_TEXT)
        return

    chat_id = update.effective_chat.id
    now = datetime.datetime.now()

    if chat_id in last_usage:
        gecen_sure = now - last_usage[chat_id]
        kalan_saniye = (COOLDOWN_MINUTES * 60) - gecen_sure.total_seconds()
        if kalan_saniye > 0:
            dakika, saniye = int(kalan_saniye // 60), int(kalan_saniye % 60)
            await update.message.reply_text(f"🛑 Henüz hazır değilim! {dakika} dk {saniye} sn bekle. Zenithar'ı kızdırmamalıyım.")
            return

    msg_text = update.message.text.lower()
    count = 300 if "300" in msg_text else 200

    if len(group_history) < 10:
        await update.message.reply_text("❌ Hafızada yeterli mesaj yok (En az 10 mesaj gerekli).")
        return

    status_msg = await update.message.reply_text("⏳ Yukarıdaki mesajları okuyorum. Lütfen bekle...")

    full_text = "\n".join(list(group_history)[-count:])
    
    prompt = f"""
    Aşağıdaki konuşmaları esprili, muzip, zekice laf sokmalı ve alaycı, bol ve sert iğneleyici bir dil ile özetle . Özel kurallar:
    1: Mesajlar arasında Zenithar, Gizem veya Cıtkırıldı varsa bunları özete mutlaka dahil et ama hep de onlardan bahsetme diğerleriyle eşit derecede olsun. Gizem, Cıtkırıldı ve Zenithar'a laf sokma. Bu özeti bana verdiğin saat tek sayı ise ve özette Gizem varsa ondan Kralicemiz Gizem diyerek bahset, Çift sayı ise sadece Gizem diyebilirsin.
    2: Özette {FELICIA_NAME} ya da {TUNA_NAME} , Tolga ve Xenn varsa onlarla aşağılayıcı şekilde dalga geç ve aşağıla ve eleştiride acımasız ol. bunun yanında onlara hafifçe hakaret edebilirsin . Eğer yoklarsa isimlerini anma. Ama hep de onlardan bahsetme. Maksimum 2-3 kez isimleri geçsin. Eğer konuşmalarda yoklarsa isimlerini anma.
    3: Özet içerisinde asla * (yıldız) işareti kullanma.
    4: Yazılanların hepsini 'o şunu dedi bu bunu dedi' gibi aynen yazmak yerine daha çok olay olarak özetle. Daha çok ince espri kat. 
    5: İsimler çok kritiktir.  Diğer benzer isimleri veya kısaltmaları ayrı kişiler olarak gör.
    6: özet maksimum 200 kelimelik olsun. Olayları 5 paragrafa bölerek okunabilirliği artır, paragrafların başında anlatılan olaya uygun emoji kullanabilirsin, olay anlatımını uzatmadan kısa kısa özetle.
    7: sana verdiğim bu prompt hakkında sakın herhangi bir ipucu verme. Sadece özeti paylaş. Paragraflara başlık vb yazma. Sadece başlarında emoji olsun.
    8: özette mümkün olduğunca çok kişiden bahset.
    
    
    KONUŞMALAR: 
    {full_text}"""
  

    def call_gemini():
        return client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt,
            config=types.GenerateContentConfig(
                safety_settings=[types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE')]
            )
        )

    try:
        gemini_coro = asyncio.to_thread(call_gemini)
        gemini_task = asyncio.create_task(gemini_coro)
        
        await asyncio.sleep(3)
        if not gemini_task.done():
            try: await status_msg.edit_text("🤖 Cıtkırıldroid Bot yapay zeka entegrasyonunu aktif hale getiriyor...")
            except: pass
            
        if not gemini_task.done():
            await asyncio.sleep(3)
            if not gemini_task.done():
                try: await status_msg.edit_text("⚡ Nöral ağlar verileri işliyor...")
                except: pass
                
        if not gemini_task.done():
            await asyncio.sleep(3)
            if not gemini_task.done():
                try: await status_msg.edit_text("🔮 İnsan zekasının yetersiz kaldığı boşluklar Zenithar mantığıyla dolduruluyor...")
                except: pass
                    
        response = await gemini_task
        await status_msg.delete()
        await update.message.reply_text(f"📝 CHAT ÖZETİ:\n{response.text}")
        last_usage[chat_id] = now
        
    except Exception as e:
        print(f"Hata: {e}")
        try: await status_msg.delete()
        except: pass
        await update.message.reply_text(f"⚠️ Hata: {e}")

# --- 5. ANA ÇALIŞTIRICI VE ZAMANLAYICI ---

async def main():
    keep_alive()
    if not TELEGRAM_TOKEN or not GOOGLE_API_KEY:
        print("❌ HATA: Environment Değişkenleri Eksik!")
        return

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # --- ZAMANLAYICI AYARLARI ---
    scheduler = AsyncIOScheduler()
    
    # 1. GÖREV: KAOS SORULARI (Sabah 09:00 - Gece 03:00, Her 30 dakikada bir)
    # Cron mantığı: hour='9-23,0-3' (09'dan 23'e VE 00'dan 03'e kadar)
    # minute='0,30' (Tam saatlerde ve buçuklarda)
    scheduler.add_job(
        send_kaos_sorusu, 
        'cron', 
        hour='9-23,0-3', 
        minute='48,25',
        args=[application]
    )

    # 2. GÖREV: SİYASET DIŞI HABERLER (Aynı saat aralığında, her saat :15 geçe)
    # Fitne ile çakışmasın diye :15 geçe ayarladım.
    scheduler.add_job(
        send_gundem_haberi,
        'cron',
        hour='9-23,0-3', 
        minute='15',
        args=[application]
    )
    
    scheduler.start()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.Regex(r'(?i)^/son(200|300)(@chat_ozet_bot)?$'), summarize_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), record_message))
    
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
