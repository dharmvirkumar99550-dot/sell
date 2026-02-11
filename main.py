import asyncio, os, uuid, json
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

QR_IMAGE = "https://i.ibb.co/Lh2ZFL6v/IMG-20260209-223256-566.jpg"
UPI_ID = "kingesports@axl"
SUPPORT_URL = "https://t.me/coreversions"

DATA_FILE = "payments.json"

# ================= DATABASE =================
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE,"w") as f:
        json.dump([],f)

def save_payment(data):
    with open(DATA_FILE,"r") as f:
        db = json.load(f)
    db.append(data)
    with open(DATA_FILE,"w") as f:
        json.dump(db,f,indent=2)

def utr_exists(utr):
    with open(DATA_FILE,"r") as f:
        db = json.load(f)
    return any(x["utr"]==utr for x in db)

# ================= PRODUCTS =================
PRODUCTS = {}

ORDERS = {}
USERS = set()

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ================= START =================
@dp.message(Command("start"))
async def start(message: types.Message):
    USERS.add(message.from_user.id)

    if not PRODUCTS:
        await message.answer("⚠️ No products added by admin.")
        return

    for pid,p in PRODUCTS.items():
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Buy Now", callback_data=f"buy:{pid}")],
            [InlineKeyboardButton(text="Support", url=SUPPORT_URL)]
        ])

        await message.answer_photo(
            photo=p["image"],
            caption=f"<b>{p['name']}</b>\nPrice: {p['price']}\nStock: {p['stock']}",
            reply_markup=kb
        )

# ================= AUTO ADD PRODUCT =================
@dp.message(Command("addproduct"))
async def add_product(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(
        "Send product in this format:\n\n"
        "name|price|image|type(file/link)|fileid/link|stock",
        reply_markup=ForceReply()
    )

@dp.message(lambda m: m.reply_to_message and "name|price" in m.reply_to_message.text.lower())
async def save_product(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    name,price,image,ptype,value,stock = message.text.split("|")

    pid = "p"+str(len(PRODUCTS)+1)

    PRODUCTS[pid] = {
        "name":name,
        "price":price,
        "image":image,
        "delivery_type":"telegram" if ptype=="file" else "link",
        "file_id":value if ptype=="file" else None,
        "link":value if ptype=="link" else None,
        "stock":int(stock)
    }

    await message.answer(f"✅ Product Added ID: {pid}")

# ================= BUY =================
@dp.callback_query(lambda c: c.data.startswith("buy:"))
async def buy(call: types.CallbackQuery):
    pid = call.data.split(":")[1]
    p = PRODUCTS[pid]

    if p["stock"] <= 0:
        await call.answer("❌ Out of stock", show_alert=True)
        return

    order_id = str(uuid.uuid4())[:8]

    ORDERS[order_id] = {
        "user":call.from_user.id,
        "product":pid
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Name",callback_data=f"name:{order_id}")],
        [InlineKeyboardButton(text="📱 Mobile",callback_data=f"mobile:{order_id}")],
        [InlineKeyboardButton(text="📧 Email",callback_data=f"email:{order_id}")],
        [InlineKeyboardButton(text="💳 Payment",callback_data=f"pay:{order_id}")]
    ])

    await call.message.answer(f"🧾 Checkout Panel\nOrderID: <code>{order_id}</code>",reply_markup=kb)
    await call.answer()

# ================= INPUT BUTTONS =================
@dp.callback_query(lambda c: c.data.startswith(("name:","mobile:","email:","utr:")))
async def input_buttons(call: types.CallbackQuery):
    field = call.data.split(":")[0]
    await call.message.answer(f"Enter {field.upper()}:",reply_markup=ForceReply())
    await call.answer()

# ================= SAVE INPUT =================
@dp.message()
async def save_inputs(message: types.Message):
    if not message.reply_to_message:
        return

    txt = message.reply_to_message.text.lower()
    order_id = list(ORDERS.keys())[-1]
    data = ORDERS[order_id]

    if "name" in txt:
        data["name"]=message.text
    elif "mobile" in txt:
        data["mobile"]=message.text
    elif "email" in txt:
        data["email"]=message.text
    elif "utr" in txt:

        if utr_exists(message.text):
            await message.answer("⚠️ Fake or Duplicate UTR detected!")
            return

        data["utr"]=message.text

        p = PRODUCTS[data["product"]]

        admin_text=(
            f"🧾 NEW ORDER\n"
            f"OrderID:{order_id}\n"
            f"Product:{p['name']}\n"
            f"UTR:{data['utr']}\n"
            f"User:{data['user']}"
        )

        kb=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Approve",callback_data=f"approve:{order_id}")],
            [InlineKeyboardButton(text="❌ Reject",callback_data=f"reject:{order_id}")]
        ])

        await bot.send_message(ADMIN_ID,admin_text,reply_markup=kb)
        await message.answer("✅ Submitted for approval.")

# ================= PAYMENT =================
@dp.callback_query(lambda c: c.data.startswith("pay:"))
async def payment(call: types.CallbackQuery):
    order_id = call.data.split(":")[1]

    kb=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧾 Enter UTR",callback_data=f"utr:{order_id}")]
    ])

    await call.message.answer_photo(
        photo=QR_IMAGE,
        caption=f"Scan QR & Pay\nUPI: <code>{UPI_ID}</code>",
        reply_markup=kb
    )
    await call.answer()

# ================= APPROVE =================
@dp.callback_query(lambda c: c.data.startswith("approve:"))
async def approve(call: types.CallbackQuery):
    order_id = call.data.split(":")[1]
    data = ORDERS.get(order_id)
    if not data:
        return

    uid=data["user"]
    p=PRODUCTS[data["product"]]

    if p["delivery_type"]=="telegram":
        await bot.send_document(uid,p["file_id"])
    else:
        await bot.send_message(uid,p["link"])

    await bot.send_message(uid,"✅ Approved & Delivered")

    p["stock"]-=1

    save_payment({
        "order_id":order_id,
        "utr":data["utr"],
        "user":uid,
        "product":p["name"]
    })

    ORDERS.pop(order_id,None)

    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("Approved")

# ================= REJECT =================
@dp.callback_query(lambda c: c.data.startswith("reject:"))
async def reject(call: types.CallbackQuery):
    order_id = call.data.split(":")[1]
    data = ORDERS.get(order_id)
    if not data:
        return

    await bot.send_message(data["user"],"❌ Payment Rejected")
    ORDERS.pop(order_id,None)

    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("Rejected")

# ================= BROADCAST =================
@dp.message(Command("broadcast"))
async def broadcast(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    await message.answer("Send broadcast message:",reply_markup=ForceReply())

@dp.message(lambda m: m.reply_to_message and "broadcast" in m.reply_to_message.text.lower())
async def send_broadcast(message: types.Message):
    for u in USERS:
        try:
            await bot.send_message(u,message.text)
        except:
            pass

    await message.answer("✅ Broadcast sent")

# ================= ADMIN PANEL =================
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    kb=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Product",callback_data="dummy")],
        [InlineKeyboardButton(text="📢 Broadcast",callback_data="dummy")]
    ])

    await message.answer(
        f"🔥 ADMIN PANEL\nProducts:{len(PRODUCTS)}\nActive Orders:{len(ORDERS)}",
        reply_markup=kb
    )

# ================= MAIN =================
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())