import asyncio, os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

QR_IMAGE = "https://i.ibb.co/Lh2ZFL6v/IMG-20260209-223256-566.jpg"
UPI_ID = "kingesports@axl"
SUPPORT_URL = "https://t.me/coreversions"

PRODUCTS = {
    "p1": {
        "name": "Premium PDF Guide",
        "price": "₹299",
        "image": "https://i.ibb.co/M5p8wYDk/images-1.jpg",
        "delivery_type": "telegram",
        "file_id": "BQACAgUAAxkBAAIBQ2exampleFILEID",
    },
    "p2": {
        "name": "Trading Video Course",
        "price": "₹499",
        "image": "https://i.ibb.co/1JTcfGzh/artworks-y-FAn3-OCup-DU92dl-F-t-Sxmdw-t500x500.jpg",
        "delivery_type": "link",
        "link": "https://example.com/download.zip",
    }
}

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

USER_STATE = {}

@dp.message(Command("start"))
async def start(message: types.Message):
    for pid, p in PRODUCTS.items():
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Buy Now", callback_data=f"buy:{pid}")],
            [InlineKeyboardButton(text="Support", url=SUPPORT_URL)]
        ])
        await message.answer_photo(
            photo=p["image"],
            caption=f"<b>{p['name']}</b>\nPrice: {p['price']}",
            reply_markup=kb
        )

@dp.callback_query(lambda c: c.data.startswith("buy:"))
async def buy(call: types.CallbackQuery):
    pid = call.data.split(":")[1]
    USER_STATE[call.from_user.id] = {"product": pid}
    await call.message.answer("Enter your <b>Name</b>:")
    await call.answer()

@dp.message(lambda m: m.from_user.id in USER_STATE and "name" not in USER_STATE[m.from_user.id])
async def get_name(message: types.Message):
    USER_STATE[message.from_user.id]["name"] = message.text
    await message.answer("Enter your <b>Mobile Number</b>:")

@dp.message(lambda m: m.from_user.id in USER_STATE and "mobile" not in USER_STATE[m.from_user.id])
async def get_mobile(message: types.Message):
    USER_STATE[message.from_user.id]["mobile"] = message.text
    await message.answer("Enter your <b>Email</b>:")

@dp.message(lambda m: m.from_user.id in USER_STATE and "email" not in USER_STATE[m.from_user.id])
async def get_email(message: types.Message):
    USER_STATE[message.from_user.id]["email"] = message.text
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Proceed to Payment", callback_data="pay")]
    ])
    await message.answer("Checkout complete. Click below to pay.", reply_markup=kb)

@dp.callback_query(lambda c: c.data == "pay")
async def payment(call: types.CallbackQuery):
    await call.message.answer_photo(
        photo=QR_IMAGE,
        caption=f"Pay via UPI\nUPI ID: <code>{UPI_ID}</code>\n\nEnter <b>UTR Number</b>:"
    )
    await call.answer()

@dp.message(lambda m: m.from_user.id in USER_STATE and "utr" not in USER_STATE[m.from_user.id])
async def get_utr(message: types.Message):
    USER_STATE[message.from_user.id]["utr"] = message.text
    data = USER_STATE[message.from_user.id]
    pid = data["product"]
    p = PRODUCTS[pid]

    admin_text = (
        f"🧾 <b>New Payment Request</b>\n\n"
        f"Product: {p['name']}\n"
        f"Name: {data['name']}\n"
        f"Mobile: {data['mobile']}\n"
        f"Email: {data['email']}\n"
        f"UTR: {data['utr']}\n"
        f"UserID: {message.from_user.id}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Approve", callback_data=f"approve:{message.from_user.id}")],
        [InlineKeyboardButton(text="❌ Reject", callback_data=f"reject:{message.from_user.id}")]
    ])

    await bot.send_message(ADMIN_ID, admin_text, reply_markup=kb)
    await message.answer("✅ Payment submitted. Waiting for admin approval.")

@dp.callback_query(lambda c: c.data.startswith("approve:"))
async def approve(call: types.CallbackQuery):
    uid = int(call.data.split(":")[1])
    data = USER_STATE.get(uid)
    if not data:
        return
    p = PRODUCTS[data["product"]]

    if p["delivery_type"] == "telegram":
        await bot.send_document(uid, p["file_id"])
    else:
        await bot.send_message(uid, f"📦 Download link:\n{p['link']}")

    await bot.send_message(uid, "✅ Payment approved. Product delivered.")
    USER_STATE.pop(uid, None)
    await call.answer("Approved")

@dp.callback_query(lambda c: c.data.startswith("reject:"))
async def reject(call: types.CallbackQuery):
    uid = int(call.data.split(":")[1])
    await bot.send_message(uid, "❌ Payment rejected. Please contact support.")
    USER_STATE.pop(uid, None)
    await call.answer("Rejected")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())