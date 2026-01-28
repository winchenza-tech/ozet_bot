import asyncio
import nest_asyncio
import datetime
import os
import feedparser
import random
from collections import deque
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
from google import genai
from google.genai import types
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from gtts import gTTS
import pytz 

# --- 1. WEB SUNUCUSU (Render İçin) ---
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Zenithar Sistemi Aktif."

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# --- 2. AYARLAR ---
nest_asyncio.apply()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

AUTHORIZED_GROUP_ID = -1003297262036

# 👑 YÖNETİCİ ID (Bunu mutlaka gir)
ADMIN_ID = 0 

UNAUTHORIZED_IMAGE_URL = "https://i.ibb.co/zTjGk8rv/MG-8095.jpg"
UNAUTHORIZED_ERROR_TEXT = "Yetkisiz erişim."

# 🔥 ÖZEL KİŞİLER
FELICIA_ID = 0
TUNA_ID = 0
FELICIA_NAME = "Felicia"
TUNA_NAME = "Tuna"

client = genai.Client(api_key=GOOGLE_API_KEY)

group_history = deque(maxlen=350)
last_usage = {}
COOLDOWN_MINUTES = 10

# --- 3. İÇERİK MOTORLARI ---

async def get_latest_news():
    rss_urls = [
        "https://www.ntv.com.tr/yasam.rss",
        "https://www.ntv.com.tr/teknoloji.rss",
        "https://feeds.bbci.co.uk/turkce/rss.xml"
    ]
    banned = ["siyaset", "parti", "seçim", "erdoğan", "bakan", "meclis", "chp", "akp"]
    all_news = []
    try:
        for url in rss_urls:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                if not any(w in entry.title.lower() for w in banned):
                    all_news.append(f"{entry.title}: {entry.description[:100]}...")
        return random.choice(all_news) if all_news else "Gündem boş."
    except: return "Haber ağı koptu."

async def send_gundem_haberi(context: ContextTypes.DEFAULT_TYPE):
    news = await get_latest_news()
    prompt = f"Sen Zenithar'sın. Bu haberi alaycı ve iğneleyici yorumla (max 25 kelime): {news}"
    try:
        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        await context.bot.send_message(chat_id=AUTHORIZED_GROUP_ID, text=f"📰 SON DAKİKA:\n\n{res.text}")
    except: pass

async def send_kaos_sorusu(context: ContextTypes.DEFAULT_TYPE):
    if len(group_history) < 15: return
    recent = "\n".join(list(group_history)[-30:])
    prompt = f"Konuşmaları analiz et ve kaos çıkaracak bir soru sor (max 15 kelime). Zenithar ol: {recent}"
    try:
        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        await context.bot.send_message(chat_id=AUTHORIZED_GROUP_ID, text=f"😈 {res.text}")
    except: pass

# --- 🎙️ OTOMATİK SESLİ İNFAZ (ZAMANLAYICI İLE) ---
async def send_auto_roast(context: ContextTypes.DEFAULT_TYPE):
    if len(group_history) < 3: return 

    selected_msg = random.choice(list(group_history)[-15:]) 
    target_name = selected_msg.split(": ")[0] if ": " in selected_msg else "Biri"
    
    prompt = f"""
    Sen Zenithar'sın. Gruptan şu mesajı yakaladın: "{selected_msg}".
    Bunu yazan kişiyi ({target_name}) sesli okunacak şekilde acımasızca, alaycı bir dille aşağıla.
    Kısa ve vurucu ol (Max 2 cümle). Emoji kullanma.
    """
    try:
        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        audio_text = "Muah ha ha ha! " + res.text 
        
        def create_audio_file(text):
            tts = gTTS(text=text, lang='tr', slow=False)
            fn = f"auto_{random.randint(100,999)}.mp3"
            tts.save(fn); return fn

        fn = await asyncio.to_thread(create_audio_file, audio_text)
        await context.bot.send_voice(chat_id=AUTHORIZED_GROUP_ID, voice=open(fn, 'rb'), caption=f"🎙️ Hedef: {target_name}")
        os.remove(fn)
    except Exception as e:
        print(f"Auto Roast Hatası: {e}")

# --- 4. KOMUT FONKSİYONLARI ---

async def record_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id == AUTHORIZED_GROUP_ID and update.message.text:
        u_id = update.effective_user.id
        u_name = FELICIA_NAME if u_id == FELICIA_ID else (TUNA_NAME if u_id == TUNA_ID else update.effective_user.first_name)
        group_history.append(f"{u_name}: {update.message.text}")

# 1️⃣ MANUEL TEXT ROAST (/yorumla) -> GRUP İÇİ
async def comment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != AUTHORIZED_GROUP_ID: return
    if not update.message.reply_to_message:
        await update.message.reply_text("Bir mesaja yanıt vererek yazmalısın.")
        return

    target = update.message.reply_to_message
    if target.from_user.id == context.bot.id:
        await update.message.reply_text("Kendime laf etmem.")
        return
    
    prompt = f"""
    Aşağıdaki mesajı yazılı olarak aşağıla. Çok sert, zekice ve alaycı ol. Zenithar karakterindesin.
    Mesaj: {target.text}
    Yazan: {target.from_user.first_name}
    """
    try:
        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        await target.reply_text(f"💀 {res.text}")
    except: pass

# 2️⃣ ADMIN ÖZEL SESLİ YANIT (/yanıtla) -> SADECE ÖZEL MESAJ (DM)
async def admin_voice_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Eğer grupta yazıldıysa görmezden gel veya uyar
    if update.effective_chat.type != 'private':
        return 

    # Sadece Admin
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Sen benim sahibim değilsin.")
        return 

    if not context.args:
        await update.message.reply_text("❗ Kullanım: `/yanıtla <mesaj_linki>`")
        return
    
    link = context.args[0]
    status_msg = await update.message.reply_text("🕵️ Mesaj analiz ediliyor...")

    try:
        # Linkten Mesaj ID'sini çek
        # Format genelde: https://t.me/c/12345678/999 veya https://t.me/grupadi/999
        msg_id = int(link.split('/')[-1])
        
        # Bot mesajı okumak için önce gruptan kendine (Forward) alır
        forwarded_msg = await context.bot.forward_message(
            chat_id=ADMIN_ID,
            from_chat_id=AUTHORIZED_GROUP_ID,
            message_id=msg_id
        )

        # Hedef Bilgileri
        target_name = "Biri"
        if forwarded_msg.forward_origin:
            try: target_name = forwarded_msg.forward_origin.sender_user.first_name
            except: pass
        else:
            target_name = forwarded_msg.from_user.first_name
        
        target_text = forwarded_msg.text if forwarded_msg.text else "[Medya]"

        # Roast Üret
        prompt = f"""
        Sen Zenithar'sın. Sahibin sana özelden bir hedef gösterdi.
        HEDEF: {target_name}
        MESAJI: "{target_text}"
        GÖREV: Bu kişiyi sesli okunacak şekilde yerin dibine sok. Çok ağır konuş.
        Admin emriyle olduğunu hissettir. Emoji yok.
        """
        
        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        audio_text = "Emredersiniz! " + res.text 
        
        def create_audio_file(text):
            tts = gTTS(text=text, lang='tr', slow=False)
            fn = f"remote_{update.update_id}.mp3"
            tts.save(fn); return fn

        fn = await asyncio.to_thread(create_audio_file, audio_text)
        
        # Gruba Git ve Orijinal Mesaja Yanıt Ver
        await context.bot.send_voice(
            chat_id=AUTHORIZED_GROUP_ID,
            voice=open(fn, 'rb'),
            reply_to_message_id=msg_id,
            caption="💀 Yargı Dağıtıldı."
        )
        
        await status_msg.edit_text("✅ İnfaz gruba iletildi.")
        os.remove(fn)
        
        # Temizlik (Forward edilen kopyayı sil)
        try: await forwarded_msg.delete()
        except: pass

    except Exception as e:
        await status_msg.edit_text(f"⚠️ Hata: Link hatalı veya mesaj çok eski/silinmiş.\nDetay: {e}")

async def announce_command(update, context):
    if update.effective_user.id == ADMIN_ID and context.args:
        await context.bot.send_message(chat_id=AUTHORIZED_GROUP_ID, text=f"📢 {' '.join(context.args)}")

async def summarize_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != AUTHORIZED_GROUP_ID: return
    
    # Bekleme süresi kontrolü
    chat_id = update.effective_chat.id
    now = datetime.datetime.now()
    if chat_id in last_usage:
        diff = now - last_usage[chat_id]
        rem = (COOLDOWN_MINUTES * 60) - diff.total_seconds()
        if rem > 0:
            await update.message.reply_text(f"🛑 {int(rem)} sn bekle.")
            return

    msg_text = update.message.text.lower()
    count = 300 if "300" in msg_text else 200
    if len(group_history) < 10: 
        await update.message.reply_text("Veri yok.")
        return
        
    status = await update.message.reply_text("Analiz ediliyor...")
    full_text = "\n".join(list(group_history)[-count:])
    
    prompt = f"""
    Konuşmaları Zenithar diliyle (alaycı, zeki) özetle.
    Kurallar: 
    1. {FELICIA_NAME} ve {TUNA_NAME} varsa göm.
    2. * kullanma.
    3. 5 madde halinde özetle.
    4. Max 200 kelime.
    METİN: {full_text}
    """
    try:
        res = await asyncio.to_thread(client.models.generate_content, model='gemini-2.5-flash', contents=prompt)
        await status.edit_text(f"📝 ÖZET:\n{res.text}")
        last_usage[chat_id] = now
    except: await status.edit_text("Hata.")

# --- 5. ANA ÇALIŞTIRICI ---

async def main():
    keep_alive()
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # 🇹🇷 ZAMANLAYICI (İstanbul Saati)
    scheduler = AsyncIOScheduler(timezone=pytz.timezone("Europe/Istanbul"))
    
    # Çalışma Saatleri: 09:00 - 03:00
    target_hours = '9-23,0-3' 

    # 1. OTO SESLİ İNFAZ (Saat Başlarında: 14:00, 15:00...)
    scheduler.add_job(send_auto_roast, 'cron', hour=target_hours, minute=0, args=[application])

    # 2. KAOS (Buçuklarda)
    scheduler.add_job(send_kaos_sorusu, 'cron', hour=target_hours, minute=30, args=[application])

    # 3. HABER (Çeyreklerde)
    scheduler.add_job(send_gundem_haberi, 'cron', hour=target_hours, minute=15, args=[application])

    scheduler.start()

    # Handlerlar
    application.add_handler(CommandHandler("start", lambda u,c: u.message.reply_text("Zenithar Aktif.")))
    application.add_handler(CommandHandler("duyuru", announce_command))
    application.add_handler(CommandHandler("yorumla", comment_command)) # Sadece Grup, Metin
    application.add_handler(CommandHandler("yanitla", admin_voice_reply)) # Sadece DM, Sesli
    application.add_handler(MessageHandler(filters.Regex(r'(?i)^/son(200|300)'), summarize_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), record_message))
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    try: asyncio.run(main())
    except: pass
