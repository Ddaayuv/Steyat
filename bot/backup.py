import asyncio
import json
from datetime import datetime
from aiogram import Bot
from .config import settings
from .db import Session, User, Subject, Item
from sqlalchemy import select

async def make_backup() -> str:
    async with Session() as s:
        users=(await s.scalars(select(User))).all()
        subjects=(await s.scalars(select(Subject))).all()
        items=(await s.scalars(select(Item))).all()
        data={"created_at":datetime.utcnow().isoformat(),"users":[{"telegram_id":u.telegram_id,"name":u.name,"username":u.username} for u in users],"subjects":[{"id":x.id,"slug":x.slug,"name":x.name_ar,"practical":x.has_practical} for x in subjects],"items":[{"id":x.id,"subject_id":x.subject_id,"section_id":x.section_id,"title":x.title,"description":x.description,"mode":x.study_mode,"published":x.is_published} for x in items]}
    path="/tmp/ste_yat_backup.json"
    with open(path,"w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False,indent=2)
    return path

async def backup_loop(bot: Bot):
    if not settings.backup_chat_id: return
    while True:
        try:
            await asyncio.sleep(3600)
            if datetime.now().hour == settings.backup_hour:
                path=await make_backup()
                await bot.send_document(settings.backup_chat_id, __import__('aiogram').types.FSInputFile(path), caption="💾 نسخة احتياطية تلقائية")
        except asyncio.CancelledError: raise
        except Exception: await asyncio.sleep(60)
