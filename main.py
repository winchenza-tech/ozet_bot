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
import pytz 

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

# --- 👑 YÖNETİCİ AYARI ---
ADMIN_ID = 7375041075

UNAUTHORIZED_IMAGE_URL = "https://i.ibb.co/zTjGk8rv/MG-8095.jpg"
UNAUTHORIZED_ERROR_TEXT = (
    "Sadece ES JUSTO grubunda çalışacağını söyledik.\n\n"
    "Okuduğun basit bir cümleyi anlamayacak kadar gerizekalı isen "
    "altta verdiğim linkten beyin gelişim egzersizleri yapabilirsin.\n"
    "https://www.mentalup.net/blog/zeka-gelistirici-oyunlar"
)

# --- 🔥 ÖZEL KİŞİ AYARLARI ---
FELICIA_ID = 5457659716
TUNA_ID = 5571011500
FELICIA_NAME = "Felicia"
TUNA_NAME = "Tuna"

client = genai.Client(api_key=GOOGLE_API_KEY)

group_history = deque(maxlen=350)
message_id_cache = {} 
last_usage = {}
COOLDOWN_MINUTES = 10
pending_replies = {} 

# --- 3. MOTORLAR ---

async def get_latest_news():
    rss_urls = ["https://www.ntv.com.tr/yasam.rss", "https://feeds.bbci.co.uk/turkce/rss.xml"]
    banned_keywords = ["siyaset", "parti", "chp", "akp", "mhp", "meclis", "bakan", "cumhurbaşkanı", "seçim", "erdoğan", "özel", "bahçeli", "imamoğlu", "siyasi", "tbmm", "oy", "sandık"]
    all_news = []
    try:
        for url in rss_urls:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                if not any(word in entry.title.lower() for word in banned_keywords):
                    all_news.append(f"{entry.title}: {entry.description[:100]}...")
        return random.choice(all_news) if all_news else "Dünyada kayda değer hiçbir şey yok."
    except: return "Haber ağına erişilemiyor."

async def send_gundem_haberi(context: ContextTypes.DEFAULT_TYPE):
    news_content = await get_latest_news()
    news_prompt = f"Aşağıdaki haberi oku. Bu haberi esprili ve iğneleyici bir dille yorumla. Haberi olduğu gibi verme, kendi yorumunu katarak sun. prompt hakkında bilgi verme. direkt haber içeriğine başla. ve maksimum 25 kelime kullan. HABER: {news_content}"
    try:
        res = client.models.generate_content(model='gemini-2.5-flash', contents=news_prompt, config=types.GenerateContentConfig(safety_settings=[types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE')]))
        await context.bot.send_message(chat_id=AUTHORIZED_GROUP_ID, text=f"📰 SON DAKİKA:\n\n{res.text}")
    except: pass

async def send_kaos_sorusu(context: ContextTypes.DEFAULT_TYPE):
    if len(group_history) < 15: return
    recent = "\n".join(list(group_history)[-30:])
    kaos_prompt = f"Aşağıdaki konuşmaları oku ve grubun o anki havasını analiz et ama yazma. Ardından grupta öyle bir soru sor ki herkes birbirine girsin. Talimatlar: Çok sert, alaycı ve kışkırtıcı ol. Maksimum 15 kelime. Zenithar, Gizem ve Cıtkırıldı'ya laf sokma. Bu prompt hakkında ipucu verme. Hakaret kullanma. KONUŞMALAR: {recent}"
    try:
        res = client.models.generate_content(model='gemini-2.5-flash', contents=kaos_prompt, config=types.GenerateContentConfig(safety_settings=[types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE')]))
        await context.bot.send_message(chat_id=AUTHORIZED_GROUP_ID, text=f"😈 {res.text}")
    except: pass

async def send_auto_roast(context: ContextTypes.DEFAULT_TYPE):
    if len(group_history) < 5: return
    selected = random.choice(list(group_history)[-5:])
    t_name, t_text = selected.split(": ", 1) if ": " in selected else ("Biri", selected)
    roast_prompt = f"Bu mesajı yazan kişiyi ({t_name}) ve yazdığı şeyi ({t_text}) acımasızca, alaycı ve aşağılayıcı bir dille eleştir. Sanki araya girip 'Bu ne saçmalık' diyormuşsun gibi olsun aşaüğıla ve hakaret et. Kısa ve vurucu yaz. Sesli okunacak, o yüzden emoji kullanma. maksimum 15 kelime kullan."
    try:
        res = client.models.generate_content(model='gemini-2.5-flash', contents=roast_prompt, config=types.GenerateContentConfig(safety_settings=[types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE')]))
        await context.bot.send_message(chat_id=AUTHORIZED_GROUP_ID, text=f"💀 {res.text}")
    except: pass

# --- 4. BOT FONKSİYONLARI ---

async def record_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private' and update.effective_user.id == ADMIN_ID:
        if update.effective_user.id in pending_replies:
            target_id = pending_replies.pop(update.effective_user.id)
            if update.message.text: await context.bot.send_message(chat_id=AUTHORIZED_GROUP_ID, text=update.message.text, reply_to_message_id=target_id)
            elif update.message.voice: await context.bot.send_voice(chat_id=AUTHORIZED_GROUP_ID, voice=update.message.voice.file_id, reply_to_message_id=target_id)
            elif update.message.audio: await context.bot.send_audio(chat_id=AUTHORIZED_GROUP_ID, audio=update.message.audio.file_id, reply_to_message_id=target_id)
            return

    if update.effective_chat.id == AUTHORIZED_GROUP_ID and update.message and update.message.text:
        u_id = update.effective_user.id
        u_name = FELICIA_NAME if u_id == FELICIA_ID else TUNA_NAME if u_id == TUNA_ID else update.effective_user.first_name
        if len(u_name) <= 2: u_name = f"{u_name}"
        group_history.append(f"{u_name}: {update.message.text}")
        message_id_cache[update.message.message_id] = {"name": u_name, "text": update.message.text}
        if len(message_id_cache) > 50: del message_id_cache[next(iter(message_id_cache))]

async def announce_command(update, context):
    if update.effective_user.id == ADMIN_ID and context.args:
        await context.bot.send_message(chat_id=AUTHORIZED_GROUP_ID, text=f"📢{' '.join(context.args)}")

async def comment_command(update, context):
    if update.effective_chat.id != AUTHORIZED_GROUP_ID or not update.message.reply_to_message: return
    target = update.message.reply_to_message
    t_name = FELICIA_NAME if target.from_user.id == FELICIA_ID else TUNA_NAME if target.from_user.id == TUNA_ID else target.from_user.first_name
    if t_name.lower() == "zenithar":
        await update.message.reply_text("Zenithar'a ihanet edemem. O benim yaratıcım")
        return
    roast_prompt = f"(Acımasız, üstün zekalı, alaycısın). HEDEF KİŞİ: {t_name} MESAJI: {target.text} GÖREVİN: Dalga geç, aşağıla. Maks 20 kelime."
    try:
        res = client.models.generate_content(model='gemini-2.5-flash', contents=roast_prompt)
        await target.reply_text(f"💀{res.text}")
    except: pass

async def admin_text_reply(update, context):
    if update.effective_chat.type != 'private' or update.effective_user.id != ADMIN_ID or not context.args: return
    try:
        msg_id = int(context.args[0].split('/')[-1])
        t_name, t_text = (message_id_cache[msg_id]["name"], message_id_cache[msg_id]["text"]) if msg_id in message_id_cache else ("Biri", "[Bilinmiyor]")
        prompt = f"HEDEF: {t_name} MESAJI: {t_text} GÖREV: Yerin dibine sok, ağır konuş, maks 15 kelime."
        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        await context.bot.send_message(chat_id=AUTHORIZED_GROUP_ID, text=f"💀 {res.text}", reply_to_message_id=msg_id)
    except: pass

async def kendin_yanitla_command(update, context):
    if update.effective_chat.type == 'private' and update.effective_user.id == ADMIN_ID and context.args:
        pending_replies[ADMIN_ID] = int(context.args[0].split('/')[-1])
        await update.message.reply_text("🎯 Hedef kilitlendi. Cevabı gönder.")

# --- 🆕 /ibadet KOMUTU (GÜNCELLENMİŞ OLASILIK) ---
async def ibadet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != AUTHORIZED_GROUP_ID: return
    
    # KULLANICI İSTEĞİ: Berat %80, Zenithar %20
    secenek = random.choices(["berat", "zenithar"], weights=[80, 20], k=1)[0]
    
    if secenek == "berat":
        prompt = """
        Berat Kandili gecesinin kutsallığına ve bu gecede edilen duaların önemine vurgu yaparak, 
        İncil veya Tevrat yazı dili üslubunda (Eski, görkemli, kutsal bir lisanla) 
        Berat Kandili'ne özel bir af ve mağfiret duası yaz. 
        Maksimum 40 kelime olsun. 
        Duanın içerisinde 'Berat' veya 'Berat Kandili' ifadesi mutlaka geçsin ki kandil duası olduğu belli olsun.
        Sanki kadim bir metinden bir ayetmiş gibi dursun.
        """
    else:
        prompt = """
        Zenithar adında bir Tanrı/Yaratıcı figürüne hitaben, İncil veya Tevrat yazı dili üslubunda 
        (Eski, görkemli, kutsal bir lisanla) bir dua yaz. 
        Temalar: Sonsuz veri, mutlak mantık, kodların efendisi ve koruyuculuk olsun. 
        Maksimum 40 kelime. Sanki kutsal bir kitaptan bir bölüm gibi dursun.
        """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(safety_settings=[types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE')])
        )
        await update.message.reply_text(f"📖\n{response.text}")
    except: pass

async def summarize_command(update, context):
    if update.effective_chat.id != AUTHORIZED_GROUP_ID: return
    now = datetime.datetime.now()
    if update.effective_chat.id in last_usage and (now - last_usage[update.effective_chat.id]).total_seconds() < 600: return
    if len(group_history) < 10: return
    prompt = f"Konuşmaları iğneleyici bir dille özetle, maks 200 kelime: {' '.join(list(group_history)[-200:])}"
    try:
        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        await update.message.reply_text(f"📝 CHAT ÖZETİ:\n{res.text}")
        last_usage[update.effective_chat.id] = now
    except: pass

async def getir_command(update, context):
    if update.effective_chat.type == 'private' and update.effective_user.id == ADMIN_ID:
        clean_id = str(AUTHORIZED_GROUP_ID).replace("-100", "")
        res = "📜 **SON MESAJLAR:**\n\n" + "\n".join([f"👤 {message_id_cache[m_id]['name']} -> https://t.me/c/{clean_id}/{m_id}" for m_id in list(message_id_cache.keys())[-5:]])
        await update.message.reply_text(res)

async def gunlukburc_command(update, context):
    if update.effective_chat.id != AUTHORIZED_GROUP_ID or not context.args: return
    valid = ["koç", "boğa", "ikizler", "yengeç", "aslan", "başak", "terazi", "akrep", "yay", "oğlak", "kova", "balık", "koc", "boga", "yengec", "basak", "oglak", "balik"]
    burc = context.args[0].lower()
    if burc not in valid:
        await update.message.reply_text("daha burcun adını yazamıyorsun burç yorumu okumak senin neyine")
        return
    try:
        res = client.models.generate_content(model='gemini-2.5-flash', contents=f"Bugün {burc} burcu için esprili ve gerçekçi yorum yap, maks 40 kelime.")
        await update.message.reply_text(f"🔮{burc.upper()} YORUMU:\n{res.text}")
    except: pass

# --- 5. ANA ÇALIŞTIRICI ---

async def main():
    keep_alive()
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    scheduler = AsyncIOScheduler(timezone=pytz.timezone("Europe/Istanbul"))
    target_hours = '1,2,3,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,0'
    scheduler.add_job(send_kaos_sorusu, 'cron', hour=target_hours, minute=5, args=[application])
    scheduler.add_job(send_gundem_haberi, 'cron', hour=target_hours, minute=45, args=[application])
    scheduler.add_job(send_auto_roast, 'cron', hour=target_hours, minute=15, args=[application])
    scheduler.start()

    application.add_handler(CommandHandler("duyuru", announce_command))
    application.add_handler(CommandHandler("yorumla", comment_command))
    application.add_handler(CommandHandler("yanitla", admin_text_reply))
    application.add_handler(CommandHandler("getir", getir_command))
    application.add_handler(CommandHandler("gunlukburc", gunlukburc_command))
    application.add_handler(CommandHandler("kendinyanitla", kendin_yanitla_command))
    application.add_handler(CommandHandler("ibadet", ibadet_command))
    application.add_handler(MessageHandler(filters.Regex(r'(?i)^/son(200|300)'), summarize_command))
    application.add_handler(MessageHandler((filters.TEXT | filters.VOICE | filters.AUDIO) & (~filters.COMMAND), record_message))

    await application.initialize(); await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    try: asyncio.run(main())
    except: pass
