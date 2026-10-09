from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..db import Subject, Section, Item, Attachment, get_setting
from ..utils import esc, normalize

router=Router()

def subjects_kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{s.emoji} {s.name_ar}",callback_data=f"sub:{s.id}")] for s in rows]+[[InlineKeyboardButton(text="🔎 بحث",callback_data="search")]])

@router.message(CommandStart())
@router.message(Command("menu"))
async def start(m: Message, session: AsyncSession):
    rows=(await session.scalars(select(Subject).where(Subject.is_active==True).order_by(Subject.sort_order,Subject.id))).all()
    await m.answer("🎓 <b>أكاديمية الأمن السيبراني</b>\n\nاختر المادة التي تريدها:",reply_markup=subjects_kb(rows))

@router.callback_query(F.data=="check_sub")
async def check_sub(cb: CallbackQuery, session: AsyncSession):
    channel=await get_setting(session,"channel_id","")
    try:
        member=await cb.bot.get_chat_member(int(channel),cb.from_user.id)
        if member.status in {"member","administrator","creator"} or (member.status=="restricted" and getattr(member,"is_member",False)):
            await cb.answer("تم التحقق ✅")
            await start(cb.message,session)
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
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{x.emoji} {x.name_ar}",callback_data=f"sec:{sid}:{mode}:{x.id}")] for x in rows]+[[InlineKeyboardButton(text="⬅️ المواد",callback_data="home")]])
    text="اختر القسم:" if rows else "لا توجد أقسام بعد."
    if isinstance(event,CallbackQuery): await event.message.edit_text(text,reply_markup=kb); await event.answer()

@router.callback_query(F.data.startswith("sec:"))
async def section(cb: CallbackQuery, session: AsyncSession):
    _,sid,mode,secid=cb.data.split(":")
    q=select(Item).where(Item.subject_id==int(sid),Item.section_id==int(secid),Item.is_published==True)
    if mode!="general": q=q.where(Item.study_mode==mode)
    rows=(await session.scalars(q.order_by(Item.sort_order,Item.id))).all()
    if not rows:return await cb.answer("لا توجد محاضرات هنا بعد",show_alert=True)
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=("⭐ " if x.is_important else "📄 ")+x.title[:55],callback_data=f"item:{x.id}")] for x in rows]+[[InlineKeyboardButton(text="⬅️ رجوع",callback_data=f"sub:{sid}")]])
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
async def home(cb: CallbackQuery,session:AsyncSession): await start(cb.message,session)

@router.message(Command("search"))
async def search(m:Message,session:AsyncSession):
    term=normalize((m.text or "").partition(" ")[2])
    if not term:return await m.answer("استخدم: <code>/search لينكس</code>")
    rows=(await session.scalars(select(Item).where(Item.is_published==True,Item.search_text.contains(term)).limit(15))).all()
    if not rows:return await m.answer("لم أجد نتائج.")
    await m.answer("🔎 النتائج:\n\n"+"\n".join(f"• {esc(x.title)} — #{x.id}" for x in rows))
