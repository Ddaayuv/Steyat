from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from ..config import settings
from ..db import User,Subject,Section,Item,Attachment,Admin,BotSetting,audit,set_setting,setting_enabled,create_item
from ..utils import esc,is_url

router=Router()

def owner(uid): return uid in settings.owner_ids

def panel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 الإحصائيات",callback_data="adm:stats"),InlineKeyboardButton(text="➕ إضافة محتوى",callback_data="adm:add")],
        [InlineKeyboardButton(text="📚 المواد",callback_data="adm:subjects"),InlineKeyboardButton(text="⚙️ الإعدادات",callback_data="adm:settings")],
        [InlineKeyboardButton(text="📢 إذاعة",callback_data="adm:broadcast")]])

class AddContent(StatesGroup):
    meta=State(); content=State()
class Broadcast(StatesGroup): content=State()

@router.message(Command("adminpanel"))
async def adminpanel(m:Message,session:AsyncSession):
    if not owner(m.from_user.id): return await m.answer("⛔ هذا الأمر للمطوّر فقط.")
    await m.answer("🛠 <b>لوحة المطوّر</b>\n\nاختر العملية:",reply_markup=panel_kb())

@router.callback_query(F.data=="adm:stats")
async def stats(cb:CallbackQuery,session:AsyncSession):
    if not owner(cb.from_user.id): return await cb.answer("ممنوع",show_alert=True)
    users=await session.scalar(select(func.count(User.id))) or 0; subjects=await session.scalar(select(func.count(Subject.id))) or 0; items=await session.scalar(select(func.count(Item.id))) or 0
    await cb.message.edit_text(f"📊 <b>الإحصائيات</b>\n👥 المستخدمون: {users}\n📚 المواد: {subjects}\n📦 المحتوى: {items}",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ اللوحة",callback_data="adm:panel")]])); await cb.answer()

@router.callback_query(F.data=="adm:subjects")
async def subjects(cb:CallbackQuery,session:AsyncSession):
    if not owner(cb.from_user.id): return await cb.answer("ممنوع",show_alert=True)
    rows=(await session.scalars(select(Subject).order_by(Subject.sort_order,Subject.id))).all()
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{x.emoji} {x.name_ar} · {'عملي+نظري' if x.has_practical else 'قسم واحد'}",callback_data=f"adm:toggle:{x.id}")] for x in rows]+[[InlineKeyboardButton(text="➕ إضافة مادة",callback_data="adm:addsubject")],[InlineKeyboardButton(text="⬅️ اللوحة",callback_data="adm:panel")]])
    await cb.message.edit_text("📚 <b>إدارة المواد</b>\nاضغط على المادة لتبديل العملي/النظري:",reply_markup=kb); await cb.answer()

@router.callback_query(F.data.startswith("adm:toggle:"))
async def toggle(cb:CallbackQuery,session:AsyncSession):
    if not owner(cb.from_user.id): return await cb.answer("ممنوع",show_alert=True)
    s=await session.get(Subject,int(cb.data.split(":")[2])); s.has_practical=not s.has_practical; await cb.answer("تم التحديث"); await subjects(cb,session)

@router.message(Command("addsubject"))
async def addsubject(m:Message,command:CommandObject,session:AsyncSession):
    if not owner(m.from_user.id): return
    p=[x.strip() for x in (command.args or "").split("|")]
    if not p or not p[0]: return await m.answer("الاستخدام: <code>/addsubject اسم المادة | الاسم الإنكليزي | 🧪</code>")
    name=p[0]; practical=len(p)>1 and p[-1].lower() in {"عملي","نعم","true","1"};
    if practical:p.pop()
    emoji=p[2] if len(p)>2 else "📘"; en=p[1] if len(p)>1 else ""
    slug="".join(c.lower() if c.isalnum() else "-" for c in (en or name)).strip("-") or "subject"
    s=Subject(slug=slug,name_ar=name,name_en=en,emoji=emoji,aliases=name,sort_order=(await session.scalar(select(func.max(Subject.sort_order))) or 0)+1,has_practical=practical); session.add(s); await audit(session,m.from_user.id,"add_subject",name); await m.answer(f"✅ تمت إضافة {esc(name)}")

@router.callback_query(F.data=="adm:addsubject")
async def addsubject_help(cb:CallbackQuery,session:AsyncSession):
    await cb.answer(); await cb.message.answer("أرسل الأمر:\n<code>/addsubject اسم المادة | English | 🧪 | عملي</code>")

@router.message(Command("practical"))
async def practical(m:Message,command:CommandObject,session:AsyncSession):
    if not owner(m.from_user.id):return
    try:s=await session.get(Subject,int((command.args or "").strip()))
    except Exception:s=None
    if not s:return await m.answer("الاستخدام: /practical رقم_المادة")
    s.has_practical=not s.has_practical; await m.answer("🧪 عملي + نظري" if s.has_practical else "📚 قسم واحد")

@router.message(Command("setchannel"))
async def setchannel(m:Message,command:CommandObject,session:AsyncSession):
    if not owner(m.from_user.id):return
    p=[x.strip() for x in (command.args or "").split("|")]
    if not p or not p[0]:return await m.answer("الاستخدام: /setchannel @channel | https://t.me/channel")
    await set_setting(session,"channel_id",p[0].replace("@","")); await set_setting(session,"channel_link",p[1] if len(p)>1 else ""); await m.answer("✅ تم حفظ القناة.")

@router.message(Command("forcesub"))
async def forcesub(m:Message,command:CommandObject,session:AsyncSession):
    if not owner(m.from_user.id):return
    value=(command.args or "").strip().lower() in {"1","on","yes","true","تشغيل"}; await set_setting(session,"force_sub",str(value).lower()); await m.answer("🔒 الاشتراك الإجباري: " + ("مفعّل" if value else "متوقف"))

@router.message(Command("alerts"))
async def alerts(m:Message,command:CommandObject,session:AsyncSession):
    if not owner(m.from_user.id):return
    value=(command.args or "").strip().lower() in {"1","on","yes","true","تشغيل"}; await set_setting(session,"new_user_alerts",str(value).lower()); await m.answer("🔔 إشعارات الأعضاء الجدد: " + ("مفعّلة" if value else "متوقفة"))

@router.callback_query(F.data=="adm:settings")
async def settings_view(cb:CallbackQuery,session:AsyncSession):
    if not owner(cb.from_user.id):return await cb.answer("ممنوع",show_alert=True)
    force=await setting_enabled(session,"force_sub"); alerts=await setting_enabled(session,"new_user_alerts",True); announce=await setting_enabled(session,"announce",True)
    await cb.message.edit_text(f"⚙️ <b>الإعدادات</b>\n🔒 اشتراك إجباري: {'ON' if force else 'OFF'}\n🔔 عضو جديد: {'ON' if alerts else 'OFF'}\n📢 الإذاعة: {'ON' if announce else 'OFF'}\n\nالأوامر:\n<code>/setchannel @channel | link</code>\n<code>/forcesub on/off</code>\n<code>/alerts on/off</code>",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ اللوحة",callback_data="adm:panel")]])); await cb.answer()

@router.callback_query(F.data=="adm:add")
async def add_start(cb:CallbackQuery,state:FSMContext,session:AsyncSession):
    if not owner(cb.from_user.id):return await cb.answer("ممنوع",show_alert=True)
    await state.set_state(AddContent.meta)
    await cb.message.answer("➕ <b>إضافة محتوى</b>\n\nأرسل في رسالة واحدة:\n<code>رقم_المادة | عملي/نظري/عام | رقم_القسم | عنوان</code>\n\nمثال:\n<code>2 | نظري | 4 | مقدمة في الأمن السيبراني</code>\n\nالأقسام: 1 محاضرات، 2 ملاحظات، 4 ملفات، 5 أسئلة، 6 أهم النقاط، 7 مصادر")
    await cb.answer()

@router.message(AddContent.meta)
async def add_meta(m:Message,state:FSMContext,session:AsyncSession):
    if not owner(m.from_user.id):return await state.clear()
    p=[x.strip() for x in (m.text or "").split("|",3)]
    if len(p)<4:return await m.answer("الصيغة غير صحيحة. مثال: <code>2 | نظري | 4 | مقدمة</code>")
    try:sid=int(p[0]); secid=int(p[2])
    except ValueError:return await m.answer("رقم المادة والقسم يجب أن يكونا أرقاماً.")
    s=await session.get(Subject,sid); sec=await session.get(Section,secid)
    if not s or not sec:return await m.answer("المادة أو القسم غير موجود. استخدم /subjects")
    mode={'عملي':'practical','نظري':'theory','عام':'general'}.get(p[1].lower(),p[1].lower())
    if mode not in {'practical','theory','general'}:return await m.answer("النوع يجب أن يكون عملي أو نظري أو عام.")
    await state.update_data(subject_id=sid,section_id=secid,title=p[3],study_mode=mode,attachments=[])
    await state.set_state(AddContent.content)
    await m.answer("📎 الآن أرسل الملف أو الفيديو أو الصوت أو الصورة أو رابطاً.\n\nيمكنك إرسال مرفق واحد، وسيُحفظ داخل المادة والقسم المحددين.")

@router.message(AddContent.content)
async def add_content(m:Message,state:FSMContext,session:AsyncSession):
    if not owner(m.from_user.id):return await state.clear()
    data=await state.get_data(); a=None
    if m.document:a={'kind':'file','tg_file_id':m.document.file_id,'file_name':m.document.file_name,'size':m.document.file_size}
    elif m.video:a={'kind':'video','tg_file_id':m.video.file_id,'file_name':m.video.file_name,'size':m.video.file_size}
    elif m.audio:a={'kind':'audio','tg_file_id':m.audio.file_id,'file_name':m.audio.file_name,'size':m.audio.file_size}
    elif m.photo:a={'kind':'photo','tg_file_id':m.photo[-1].file_id,'file_name':None,'size':m.photo[-1].file_size}
    elif m.text and is_url(m.text.strip()):a={'kind':'link','url':m.text.strip()}
    else:return await m.answer("أرسل PDF/ملف/فيديو/صوت/صورة أو رابطاً صحيحاً.")
    data['attachments']=[a]; item=await create_item(session,data,m.from_user.id); await audit(session,m.from_user.id,'add_item',f'#{item.id} {item.title}'); await state.clear(); await m.answer(f"✅ تم حفظ المحتوى داخل المادة.\n🆔 رقم المحتوى: {item.id}\n📘 {esc(item.title)}")

@router.message(Command("subjects"))
async def list_subjects(m:Message,session:AsyncSession):
    if not owner(m.from_user.id):return
    rows=(await session.scalars(select(Subject).order_by(Subject.sort_order,Subject.id))).all(); await m.answer("📚 المواد:\n"+"\n".join(f"{x.id}. {x.emoji} {x.name_ar} — {'عملي/نظري' if x.has_practical else 'قسم واحد'}" for x in rows))

@router.callback_query(F.data=="adm:broadcast")
async def broadcast_start(cb:CallbackQuery,state:FSMContext):
    if not owner(cb.from_user.id):return await cb.answer("ممنوع",show_alert=True)
    await state.set_state(Broadcast.content); await cb.message.answer("📢 أرسل الآن الرسالة أو الصورة أو الملف الذي تريد إذاعته للمستخدمين."); await cb.answer()

@router.message(Command("broadcast"))
async def broadcast_cmd(m:Message,state:FSMContext):
    if owner(m.from_user.id): await state.set_state(Broadcast.content); await m.answer("📢 أرسل محتوى الإذاعة الآن.")

@router.message(Broadcast.content)
async def broadcast_send(m:Message,state:FSMContext,session:AsyncSession):
    if not owner(m.from_user.id):return await state.clear()
    if not await setting_enabled(session,"announce",True):return await state.clear()
    users=(await session.scalars(select(User.telegram_id))).all(); ok=bad=0
    for uid in users:
        try: await m.bot.copy_message(uid,m.chat.id,m.message_id); ok+=1
        except Exception: bad+=1
    await state.clear(); await m.answer(f"📢 انتهت الإذاعة.\n✅ وصلت: {ok}\n❌ فشلت: {bad}")

@router.callback_query(F.data=="adm:panel")
async def panel_cb(cb:CallbackQuery,session:AsyncSession):
    if owner(cb.from_user.id): await cb.message.edit_text("🛠 <b>لوحة المطوّر</b>",reply_markup=panel_kb())
    await cb.answer()
