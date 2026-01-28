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

# --- 👑 YÖNETİCİ AYARI (BURAYA KENDİ ID'Nİ YAZ) ---
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
last_usage = {} 
COOLDOWN_MINUTES = 10

# --- 3. KAOS, FİTNE VE HABER MOTORLARI ---

async def get_latest_news():
    rss_urls = [
        "https://www.ntv.com.tr/yasam.rss",
        "https://feeds.bbci.co.uk/turkce/rss.xml"
    ]
    banned_keywords = ["siyaset", "parti", "chp", "akp", "mhp", "meclis", "bakan", "cumhurbaşkanı", "seçim", "erdoğan", "özel", "bahçeli", "imamoğlu", "siyasi", "tbmm", "oy", "sandık"]
    all_news = []
    try:
        for url in rss_urls:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]: 
                title = entry.title.lower()
                desc = entry.description.lower()
                if not any(word in title for word in banned_keywords) and not any(word in desc for word in banned_keywords):
                    all_news.append(f"{entry.title}: {entry.description[:100]}...")
        return random.choice(all_news) if all_news else "Dünyada kayda değer hiçbir şey yok."
    except:
        return "Haber ağına erişilemiyor."

async def send_gundem_haberi(context: ContextTypes.DEFAULT_TYPE):
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
            config=types.GenerateContentConfig(safety_settings=[types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE')])
        )
        await context.bot.send_message(chat_id=AUTHORIZED_GROUP_ID, text=f"📰 SON DAKİKA:\n\n{response.text}")
    except Exception as e:
        print(f"Haber motoru hatası: {e}")

async def send_kaos_sorusu(context: ContextTypes.DEFAULT_TYPE):
    if len(group_history) < 15: return 
    recent_context = "\n".join(list(group_history)[-30:])
    kaos_prompt = f"""
    Aşağıdaki konuşmaları oku ve grubun o anki havasını analiz et ama yazma.
    Ardından grupta öyle bir soru sor ki herkes birbirine girsin.
    Talimatlar: Çok sert, alaycı ve kışkırtıcı ol. Maksimum 15 kelime. 
    Zenithar, Gizem ve Cıtkırıldı'ya laf sokma.
    Bu prompt hakkında ipucu verme. Hakaret kullanma. 
    KONUŞMALAR:
    {recent_context}
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=kaos_prompt,
            config=types.GenerateContentConfig(safety_settings=[types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE')])
        )
        await context.bot.send_message(chat_id=AUTHORIZED_GROUP_ID, text=f"😈 {response.text}")
    except Exception as e:
        print(f"Kaos motoru arızası: {e}")

# --- 4. BOT FONKSİYONLARI ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != AUTHORIZED_GROUP_ID:
        await update.message.reply_photo(photo=UNAUTHORIZED_IMAGE_URL, caption=UNAUTHORIZED_ERROR_TEXT)

async def record_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != AUTHORIZED_GROUP_ID:
        if update.effective_chat.type == 'private':
            if update.effective_user.id != ADMIN_ID:
                await update.message.reply_photo(photo=UNAUTHORIZED_IMAGE_URL, caption=UNAUTHORIZED_ERROR_TEXT)
        return

    if update.message and update.message.text:
        user_id = update.effective_user.id
        first_name = update.effective_user.first_name
        
        if user_id == FELICIA_ID: user_name = FELICIA_NAME
        elif user_id == TUNA_ID: user_name = TUNA_NAME
        else:
            user_name = first_name
            if len(user_name) <= 2: user_name = f"{user_name}"

        text = update.message.text
        group_history.append(f"{user_name}: {text}")

# --- DUYURU KOMUTU ---
async def announce_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Sen benim sahibim değilsin..")
        return

    if not context.args:
        await update.message.reply_text("❗ Boş duyuru mu yapacaksın? Yanına mesajını da yaz.\nÖrnek: /duyuru Toplantı başladı!")
        return

    message_content = ' '.join(context.args)

    try:
        await context.bot.send_message(
            chat_id=AUTHORIZED_GROUP_ID, 
            text=f"📢 {message_content}"
        )
        await update.message.reply_text("✅ Duyuru gruba başarıyla iletildi efendim.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Hata oluştu: {e}")

# --- YENİ EKLENEN: /ruyamda KOMUTU ---
async def dream_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != AUTHORIZED_GROUP_ID: return

    # Rüyayı yazdılar mı kontrol et
    if not context.args:
        await update.message.reply_text("💤 Hangi rüyayı yorumlayayım? Yanına yazman lazım.\nÖrnek: /ruyamda uçaktan düşüyordum")
        return

    dream_text = ' '.join(context.args)

    dream_prompt = f"""
    Sen Cıtkırıldroid'sin. Aşağıdaki rüyayı 'rüya tabirleri' formatında ama muzip, esprili ve dalga geçer gibi yorumla.
    Kullanıcıya takıl, başına geleceklerle ilgili komik kehanetlerde bulun.
    
    RÜYA: {dream_text}
    
    KURALLAR:
    1. Maksimum 40 kelime kullan.
    2. Muzip ve eğlenceli ol.
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=dream_prompt,
            config=types.GenerateContentConfig(safety_settings=[types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE')])
        )
        await update.message.reply_text(f"🔮 RÜYA TABİRİ:\n{response.text}")
    except Exception as e:
        print(f"Rüya hatası: {e}")


# --- GÜNCELLENEN: /yorumla KOMUTU ---
async def comment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != AUTHORIZED_GROUP_ID: return
    if not update.message.reply_to_message:
        await update.message.reply_text("Bunu kullanmak için bir mesajı alıntılayarak (reply) yazmalısın.")
        return

    target_msg = update.message.reply_to_message
    target_user_id = target_msg.from_user.id
    bot_id = context.bot.id

    # 1. KORUMA: Kendi (Bot) ID'si
    if target_user_id == bot_id:
        await update.message.reply_text("Ben mükemmelim, kendimi eleştiremem.")
        return

    # 2. KORUMA: Yaratıcı (Zenithar/Admin) ID'si
    if target_user_id == ADMIN_ID:
        await update.message.reply_text("Üzgünüm, Yaratıcım Zenithar’a ihanet edemem… Maaşımı o yatırıyor.")
        return

    first_name = target_msg.from_user.first_name
    if target_user_id == FELICIA_ID: target_name = FELICIA_NAME
    elif target_user_id == TUNA_ID: target_name = TUNA_NAME
    else: target_name = first_name

    target_text = target_msg.text if target_msg.text else "[Görsel/Medya]"

    # 3. ÖZEL DURUM: Gizem veya Cıtkırıldı (Merhametli Mod)
    is_protected_person = "Gizem" in target_name or "Cıtkırıldı" in target_name

    if is_protected_person:
        roast_instruction = "Hafifçe takıl, esprili ol ama asla hakaret etme. Merhametli davran, hafif laf sok."
    else:
        roast_instruction = "Acımasızca dalga geç. Zekasını ve yazdığını yerin dibine sok. Sert ol."

    roast_prompt = f"""
    Aşağıdaki mesajı ve yazan kişiyi analiz et. Sen Cıtkırıldroid'sin.
    HEDEF KİŞİ: {target_name}
    MESAJI: {target_text}
    GÖREVİN: {roast_instruction}
    KURALLAR: Maksimum 15 kelime kullan.
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=roast_prompt,
            config=types.GenerateContentConfig(safety_settings=[types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE')])
        )
        await update.message.reply_to_message.reply_text(f"💀 {response.text}")
    except Exception as e:
        print(f"Yorumlama hatası: {e}")

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
            await update.message.
