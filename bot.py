import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp
import asyncio

API_TOKEN = '7528727334:AAE5ic0kN8BSRpEB1IFpzHOOQoQjImk7Ays'
bot = telebot.TeleBot(API_TOKEN)

# رابط قناتك
channel_link = "https://t.me/drgg8"

async def download_and_send_video(chat_id, video_url, message_id, success_message):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(video_url) as response:
                if response.status == 200:
                    video_data = await response.read()
                    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=success_message)
                    bot.send_video(chat_id, video_data)
                    bot.delete_message(chat_id, message_id)
                    
                    # إنشاء زر شفاف بعد تحميل الفيديو
                    markup = InlineKeyboardMarkup()
                    channel_button = InlineKeyboardButton(text="🔗 اشترك في قناتنا", url=channel_link)
                    markup.add(channel_button)
                    bot.send_message(chat_id, "للاشتراك في قناتنا والحصول على المزيد من الفيديوهات، يرجى النقر على الزر أدناه:", reply_markup=markup)
                else:
                    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="حدث خطأ أثناء تحميل الفيديو.")
    except Exception as e:
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"حدث خطأ: {str(e)}")

async def handle_tiktok_video(chat_id, url, message_id):
    api_url = f"https://www.tikwm.com/api/?url={url}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and 'data' in data and 'play' in data['data']:
                        video_url = data['data']['play']
                        success_message = "تم التحميل بنجاح ✅"
                        await download_and_send_video(chat_id, video_url, message_id, success_message)
                    else:
                        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="لم أتمكن من العثور على رابط الفيديو في الاستجابة.")
                else:
                    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"فشل الاتصال بالـ API. رمز الحالة: {response.status}")
    except Exception as e:
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"حدث خطأ: {str(e)}")

async def handle_instagram_video(chat_id, url, message_id):
    api_url = "https://insta.savetube.me/downloadPostVideo"
    headers = {'Content-Type': 'application/json'}
    json_data = {'url': url}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=json_data, headers=headers) as response:
                if response.status == 200:
                    response_json = await response.json()
                    if 'post_video_url' in response_json:
                        video_url = response_json['post_video_url']
                        success_message = "تم التحميل بنجاح ✅"
                        await download_and_send_video(chat_id, video_url, message_id, success_message)
                    else:
                        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="لم أتمكن من العثور على رابط الفيديو في الاستجابة.")
                else:
                    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"فشل الاتصال بالـ API. رمز الحالة: {response.status}")
    except Exception as e:
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"حدث خطأ: {str(e)}")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    # إنشاء لوحة الأزرار
    markup = InlineKeyboardMarkup()
    # إضافة زر شفاف ينقلك إلى قناتك
    channel_button = InlineKeyboardButton(text="🔗 اشترك في قناتنا", url=channel_link)
    markup.add(channel_button)
    
    # نص الترحيب
    welcome_text = "مرحبًا! أرسل لي رابط TikTok أو Instagram لتحميل الفيديو.\n\n"
    welcome_text += "للاشتراك في قناتنا، يرجى النقر على الزر أدناه:"

    # إرسال الرسالة مع الزر
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = message.text
    loading_message = bot.reply_to(message, '⚡ | جارٍ التحميل انتظر . .')
    
    if "tiktok.com" in url:
        asyncio.run(handle_tiktok_video(message.chat.id, url, loading_message.message_id))
    elif "instagram.com" in url:
        asyncio.run(handle_instagram_video(message.chat.id, url, loading_message.message_id))
    else:
        bot.edit_message_text(chat_id=message.chat.id, message_id=loading_message.message_id, text="الرجاء إرسال رابط TikTok أو Instagram صالح.")

bot.polling(none_stop=True)
