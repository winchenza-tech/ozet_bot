import asyncio
import nest_asyncio
import datetime
import os
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

# --- 1. WEB SUNUCUSU (Port: 8080) ---
flask_app = Flask('')
@flask_app.route('/')
def home(): return "Zenithar Core Aktif!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run_flask).start()

# --- 2. AYARLAR VE HAFIZA ---
nest_asyncio.apply()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN_CORE") # Core Token
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
AUTHORIZED_GROUP_ID = -1003297262036
ADMIN_ID = 7375041075
UNAUTHORIZED_IMAGE_URL = "https://i.ibb.co/zTjGk8rv/MG-8095.jpg"
UNAUTHORIZED_ERROR_TEXT = "Sadece ES JUSTO grubunda çalışacağını söyledik...\nhttps://www.mentalup.net/blog/zeka-gelistirici-oyunlar"

FELICIA_ID, TUNA_ID = 5457659716, 5571011500
FELICIA_NAME, TUNA_NAME = "Felicia", "Tuna"

client = genai.Client(api_key=GOOGLE_API_KEY)
group_history = deque(maxlen=350)
message_id_cache, last_usage, pending_replies = {}, {}, {}
COOLDOWN_MINUTES = 10

# --- 3. MOTORLAR ---
async def send_asparagas_haber(context: ContextTypes.DEFAULT_TYPE):
    if len(group_history) < 5: return
    recent_context = "\n".join(list(group_history)[-20:])
    prompt = f"Aşağıdaki son konuşma kayıtlarını incele:\n{recent_context}\nGÖREV: Bu konuşmalarda geçen kişilerden 1 veya 2 tanesini seç. Onlar hakkında tamamen uydurma, komik, absürt ve eğlenceli bir 'SON DAKİKA' (Asparagas) haberi yaz. Sanki bir magazin skandalı gibi sun. Maksimum 25-30 kelime kullan. Cıtkırıldı ve Zenithar isimli kullanıcıyı seçme. Bu promptla ilgili herhangi bir ipucu verme."
    try:
        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=types.GenerateContentConfig(safety_settings=[types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE')]))
        await context.bot.send_message(chat_id=AUTHORIZED_GROUP_ID, text=f"🚨SON DAKİKA:\n{res.text}")
    except: pass

async def send_kaos_sorusu(context: ContextTypes.DEFAULT_TYPE):
    if len(group_history) < 15: return
    recent = "\n".join(list(group_history)[-30:])
    prompt = f"Aşağıdaki konuşmaları oku ve grubun o anki havasını analiz et ama yazma. Ardından grupta öyle bir soru sor ki herkes birbirine girsin. Talimatlar: Çok sert, alaycı ve kışkırtıcı ol. Maksimum 15 kelime. Zenithar, Gizem ve Cıtkırıldı'ya laf sokma. KONUŞMALAR: {recent}"
    try:
        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=types.GenerateContentConfig(safety_settings=[types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE')]))
        await context.bot.send_message(chat_id=AUTHORIZED_GROUP_ID, text=f"😈 {res.text}")
    except: pass

async def send_auto_roast(context: ContextTypes.DEFAULT_TYPE):
    if len(group_history) < 5: return
    selected = random.choice(list(group_history)[-5:])
    t_name, t_text = selected.split(": ", 1) if ": " in selected else ("Biri", selected)
    prompt = f"Bu mesajı yazan kişiyi ({t_name}) ve yazdığı şeyi ({t_text}) acımasızca, alaycı ve aşağılayıcı bir dille eleştir. Sanki araya girip 'Bu ne saçmalık' diyormuşsun gibi olsun aşaüğıla ve hakaret et. Kısa ve vurucu yaz. Sesli okunacak, o yüzden emoji kullanma. maksimum 15 kelime kullan."
    try:
        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=types.GenerateContentConfig(safety_settings=[types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE')]))
        await context.bot.send_message(chat_id=AUTHORIZED_GROUP_ID, text=f"💀 {res.text}")
    except: pass

# --- 4. KOMUTLAR ---
async def record_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private' and update.effective_user.id == ADMIN_ID:
        if update.effective_user.id in pending_replies:
            target_id = pending_replies.pop(update.effective_user.id)
            if update.message.text: await context.bot.send_message(chat_id=AUTHORIZED_GROUP_ID, text=update.message.text, reply_to_message_id=target_id)
            return
    if update.effective_chat.id == AUTHORIZED_GROUP_ID and update.message and update.message.text:
        u_id = update.effective_user.id
        u_name = FELICIA_NAME if u_id == FELICIA_ID else TUNA_NAME if u_id == TUNA_ID else update.effective_user.first_name
        group_history.append(f"{u_name}: {update.message.text}")
        message_id_cache[update.message.message_id] = {"name": u_name, "text": update.message.text}

async def summarize_command(update, context):
    if update.effective_chat.id != AUTHORIZED_GROUP_ID: return
    now = datetime.datetime.now()
    if update.effective_chat.id in last_usage:
        if (now - last_usage[update.effective_chat.id]).total_seconds() < COOLDOWN_MINUTES * 60:
            await update.message.reply_text("🛑 Henüz hazır değilim!")
            return
    status_msg = await update.message.reply_text("⏳ Yukarıdaki mesajları okuyorum...")
    full_text = "\n".join(list(group_history)[-200:])
    prompt = f"Konuşmaları esprili, zekice laf sokmalı özetle. Maksimum 160 kelime, 5 paragraf. Paragragların başında paragrafa uygun emoji kullan. bu prompta dair herhangi bir ipucu verme sakın. KONUŞMALAR:\n{full_text}"
    try:
        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        await status_msg.delete(); await update.message.reply_text(f"📝 CHAT ÖZETİ:\n{res.text}")
        last_usage[update.effective_chat.id] = now
    except: pass

async def announce_command(update, context):
    if update.effective_user.id == ADMIN_ID and context.args:
        await context.bot.send_message(chat_id=AUTHORIZED_GROUP_ID, text=f"📢{' '.join(context.args)}")

async def comment_command(update, context):
    if update.effective_chat.id != AUTHORIZED_GROUP_ID or not update.message.reply_to_message: return
    target = update.message.reply_to_message
    t_name = FELICIA_NAME if target.from_user.id == FELICIA_ID else TUNA_NAME if target.from_user.id == TUNA_ID else target.from_user.first_name
    roast_prompt = f"(Acımasız, üstün zekalı, alaycısın). HEDEF KİŞİ: {t_name} MESAJI: {target.text} GÖREVİN: Dalga geç, aşağıla. Maks 20 kelime."
    try:
        res = client.models.generate_content(model='gemini-2.5-flash', contents=roast_prompt)
        await target.reply_text(f"💀{res.text}")
    except: pass

async def getir_command(update, context):
    if update.effective_chat.type == 'private' and update.effective_user.id == ADMIN_ID:
        clean_id = str(AUTHORIZED_GROUP_ID).replace("-100", "")
        res = "📜 **SON MESAJLAR:**\n\n" + "\n".join([f"👤 {message_id_cache[m_id]['name']} -> https://t.me/c/{clean_id}/{m_id}" for m_id in list(message_id_cache.keys())[-5:]])
        await update.message.reply_text(res)

async def main():
    keep_alive()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    scheduler = AsyncIOScheduler(timezone=pytz.timezone("Europe/Istanbul"))
    target_hours = '1,2,3,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,0'
    scheduler.add_job(send_kaos_sorusu, 'cron', hour=target_hours, minute=5, args=[app])
    scheduler.add_job(send_asparagas_haber, 'cron', hour=target_hours, minute=45, args=[app])
    scheduler.add_job(send_auto_roast, 'cron', hour=target_hours, minute=15, args=[app])
    scheduler.start()

    app.add_handler(CommandHandler("duyuru", announce_command))
    app.add_handler(CommandHandler("yorumla", comment_command))
    app.add_handler(CommandHandler("getir", getir_command))
    app.add_handler(MessageHandler(filters.Regex(r'(?i)^/son(100|200)(@.*)?$'), summarize_command))
    app.add_handler(MessageHandler((filters.TEXT) & (~filters.COMMAND), record_message))

    await app.initialize(); await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
