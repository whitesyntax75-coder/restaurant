import asyncio
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

BOT_TOKEN = "8855624248:AAFBK746GnZ_ei7wD7GGvTbu6cMvejxENv4"

async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.delete_webhook(drop_pending_updates=True)
    info = await bot.get_me()
    print(f"Webhook o'chirildi! Bot: @{info.username}")
    await bot.session.close()

asyncio.run(main())
