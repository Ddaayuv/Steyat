from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from .db import Session, touch_user, get_setting, setting_enabled
from .config import settings

class DbMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        async with Session() as session:
            data["session"] = session
            data["new_user"] = await touch_user(session, event.from_user)
            await session.commit()
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise

class ThrottleMiddleware(BaseMiddleware):
    def __init__(self):
        self.last = {}
    async def __call__(self, handler, event, data):
        uid = getattr(getattr(event, "from_user", None), "id", 0)
        import time
        now = time.monotonic()
        if uid and now - self.last.get(uid, 0) < 0.25:
            if isinstance(event, CallbackQuery):
                await event.answer("تمهّل قليلاً")
            return
        self.last[uid] = now
        return await handler(event, data)

class MembershipMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        uid = getattr(getattr(event, "from_user", None), "id", None)
        if not uid or uid in settings.owner_ids:
            return await handler(event, data)
        session: AsyncSession = data.get("session")
        if session is None or not await setting_enabled(session, "force_sub", False):
            return await handler(event, data)
        channel = await get_setting(session, "channel_id", "")
        link = await get_setting(session, "channel_link", settings.channel_link)
        if not channel:
            return await handler(event, data)
        try:
            member = await data["bot"].get_chat_member(int(channel), uid)
            allowed = member.status in {"member", "administrator", "creator"} or (member.status == "restricted" and getattr(member, "is_member", False))
        except Exception:
            allowed = False
        if allowed:
            return await handler(event, data)
        text = "🔒 <b>الاشتراك مطلوب</b>\n\nاشترك بالقناة أولاً ثم اضغط «تحقق من الاشتراك»."
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📢 الاشتراك بالقناة", url=link or "https://t.me/")],[InlineKeyboardButton(text="✅ تحقق من الاشتراك", callback_data="check_sub")]])
        if isinstance(event, CallbackQuery):
            await event.answer("يجب الاشتراك أولاً", show_alert=True)
            try: await event.message.edit_text(text, reply_markup=kb)
            except Exception: pass
        elif isinstance(event, Message):
            await event.answer(text, reply_markup=kb)
        return
