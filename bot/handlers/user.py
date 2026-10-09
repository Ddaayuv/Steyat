from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..config import settings
from ..db import Subject, Section, Item, Attachment, get_setting
from ..utils import esc, normalize

router=Router()

def _two_columns(buttons):
    rows=[]
    for i in range(0,len(buttons),2):
        rows.append(buttons[i:i+2])
    return rows

def subjects_kb(rows, developer=False):
    buttons=[InlineKeyboardButton(text=f"{s.emoji} {s.name_ar}",callback_data=f"sub:{s.id}") for s in rows]
    keyboard=_two_columns(buttons)
    keyboard.append([InlineKeyboardButton(text="🔎 بحث",callback_data="search")])
    if developer:
        keyboard.append([InlineKeyboardButton(text="🛠 لوحة المطوّر",callback_data="adm:panel")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.message(CommandStart())
async def start(m: Message, session: AsyncSession):
    # OWNER_IDS is the source of truth for developer recognition.
    is_developer = m.from_user.id in settings.owner_ids
    if is_developer:
        # Show the full developer panel immediately on /start.
        from .admin import panel_kb
        await m.answer(
            "🛠 <b>مرحباً بك أيها المطوّر</b>\n\n"
            "تم التعرف عليك تلقائياً. هذه لوحة التحكم الكاملة:",
            reply_markup=panel_kb(),
        )
        return
    await show_home(m, session)

@router.message(Command("menu"))
async def menu(m: Message, session: AsyncSession):
    await show_home(m, session)

async def show_home(m: Message, session: AsyncSession):
    rows=(await session.scalars(select(Subject).where(Subject.is_active==True).order_by(Subject.sort_order,Subject.id))).all()
    await m.answer("🎓 <b>المواد الدراسية 📚</b>\n\nاختر المادة:",reply_markup=subjects_kb(rows, m.from_user.id in settings.owner_ids))

@router.callback_query(F.data=="check_sub")
async def check_sub(cb: CallbackQuery, session: AsyncSession):
    channel=await get_setting(session,"channel_id","")
    try:
        member=await cb.bot.get_chat_member(int(channel),cb.from_user.id)
        if member.status in {"member","administrator","creator"} or (member.status=="restricted" and getattr(member,"is_member",False)):
            await cb.answer("تم التحقق ✅")
            await show_home(cb.message,session)
        else: await cb.answer("لم يتم العثور على اشتراكك بعد",show_alert=True)
    except Exception: await cb.answer("تعذر التحقق. تأكد أن البوت مشرف بالقناة.",show_alert=True)

@router.callback_query(F.data.startswith("sub:"))
async def subject(cb: CallbackQuery, session: AsyncSession):
    s=await session.get(Subject,int(cb.data.split(":")[1]))
    if not s:return await cb.answer("المادة غير موجودة",show_alert=True)
    if s.has_practical:
        kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📚 النظري",callback_data=f"mode:{s.id}:theory"),InlineKeyboardButton(text="🧪 العملي",callback_data=f"mode:{s.id}:practical")],[InlineKeyboardButton(text="⬅️ رجوع",callback_data="home")]])
        return await cb.message.edit_text(f"{s.emoji} <b>{esc(s.name_ar)}</b>\n\nاختر نوع المحتوى:",reply_markup=kb)
    await show_sections(cb,s.id,"general",session)

@router.callback_query(F.data.startswith("mode:"))
async def mode(cb: CallbackQuery, session: AsyncSession):
    _,sid,mode=cb.data.split(":"); await show_sections(cb,int(sid),mode,session)

async def show_sections(event,sid,mode,session):
    rows=(await session.scalars(select(Section).where(Section.slug!="practical").order_by(Section.sort_order,Section.id))).all()
    buttons=[InlineKeyboardButton(text=f"{x.emoji} {x.name_ar}",callback_data=f"sec:{sid}:{mode}:{x.id}") for x in rows]
    kb=InlineKeyboardMarkup(inline_keyboard=_two_columns(buttons)+[[InlineKeyboardButton(text="⬅️ المواد",callback_data="home")]])
    text="اختر القسم:" if rows else "لا توجد أقسام بعد."
    if isinstance(event,CallbackQuery): await event.message.edit_text(text,reply_markup=kb); await event.answer()

@router.callback_query(F.data.startswith("sec:"))
async def section(cb: CallbackQuery, session: AsyncSession):
    _,sid,mode,secid=cb.data.split(":")
    q=select(Item).where(Item.subject_id==int(sid),Item.section_id==int(secid),Item.is_published==True)
    if mode!="general": q=q.where(Item.study_mode==mode)
    rows=(await session.scalars(q.order_by(Item.sort_order,Item.id))).all()
    if not rows:return await cb.answer("لا توجد محاضرات هنا بعد",show_alert=True)
    buttons=[InlineKeyboardButton(text=("⭐ " if x.is_important else "📄 ")+x.title[:55],callback_data=f"item:{x.id}") for x in rows]
    kb=InlineKeyboardMarkup(inline_keyboard=_two_columns(buttons)+[[InlineKeyboardButton(text="⬅️ رجوع",callback_data=f"sub:{sid}")]])
    await cb.message.edit_text("📚 <b>المحتوى</b>",reply_markup=kb); await cb.answer()

@router.callback_query(F.data.startswith("item:"))
async def item(cb: CallbackQuery,session:AsyncSession):
    x=await session.get(Item,int(cb.data.split(":")[1]))
    if not x or not x.is_published:return await cb.answer("المحتوى غير متاح",show_alert=True)
    text=f"📘 <b>{esc(x.title)}</b>\n\n{esc(x.description)}"
    if x.week_no:text+=f"\n\n🗓 الأسبوع: {x.week_no}"
    await cb.message.answer(text)
    for a in x.attachments:
        try:
            if a.kind=="file" and a.tg_file_id: await cb.message.answer_document(a.tg_file_id,caption=esc(a.file_name or x.title))
            elif a.kind=="video" and a.tg_file_id: await cb.message.answer_video(a.tg_file_id,caption=esc(a.file_name or x.title))
            elif a.kind=="audio" and a.tg_file_id: await cb.message.answer_audio(a.tg_file_id,caption=esc(a.file_name or x.title))
            elif a.kind=="photo" and a.tg_file_id: await cb.message.answer_photo(a.tg_file_id,caption=esc(a.file_name or x.title))
            elif a.url: await cb.message.answer(a.url)
        except Exception: await cb.message.answer("⚠️ تعذر إرسال هذا المرفق.")
    await cb.answer()

@router.callback_query(F.data=="home")
async def home(cb: CallbackQuery,session:AsyncSession): await show_home(cb.message,session)

@router.message(Command("search"))
async def search(m:Message,session:AsyncSession):
    term=normalize((m.text or "").partition(" ")[2])
    if not term:return await m.answer("استخدم: <code>/search لينكس</code>")
    rows=(await session.scalars(select(Item).where(Item.is_published==True,Item.search_text.contains(term)).limit(15))).all()
    if not rows:return await m.answer("لم أجد نتائج.")
    await m.answer("🔎 النتائج:\n\n"+"\n".join(f"• {esc(x.title)} — #{x.id}" for x in rows))
