import asyncio, os, json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=BOT_TOKEN,
          default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

FILES = ["config.json","users.json","admins.json"]
for f in FILES:
    if not os.path.exists(f):
        open(f,"w").write("{}")

def load(x): return json.load(open(x))
def save(x,d): json.dump(d,open(x,"w"),indent=2)

ADMIN_STATE={}
USER_STATE={}

# ================= ADMIN CHECK =================
def is_admin(uid):
    admins=load("admins.json")
    return str(uid)==str(ADMIN_ID) or str(uid) in admins

# ================= START =================
@dp.message(Command("start"))
async def start(m:types.Message):

    users=load("users.json")
    users[str(m.from_user.id)]={"id":m.from_user.id}
    save("users.json",users)

    cfg=load("config.json")

    buttons=[]

    if cfg.get("review_url"):
        buttons.append([InlineKeyboardButton(text="⭐ Go To Review",url=cfg["review_url"])])

    buttons.append([InlineKeyboardButton(text="📤 Submit Review Slip",callback_data="slip")])
    buttons.append([InlineKeyboardButton(text="💰 Withdraw",callback_data="withdraw")])

    if cfg.get("support_url"):
        buttons.append([InlineKeyboardButton(text="💬 Support",url=cfg["support_url"])])

    if cfg.get("guide_video"):
        buttons.append([InlineKeyboardButton(text="🎥 Guide",url=cfg["guide_video"])])

    kb=InlineKeyboardMarkup(inline_keyboard=buttons)

    if cfg.get("main_image"):
        await m.answer_photo(
            photo=cfg["main_image"],
            caption=cfg.get("instructions","Welcome"),
            reply_markup=kb)
    else:
        await m.answer(cfg.get("instructions","Welcome"),
        reply_markup=kb)

# ================= SUBMIT SLIP =================
@dp.callback_query(F.data=="slip")
async def slip(c:types.CallbackQuery):
    USER_STATE[c.from_user.id]="slip"
    await c.message.answer("📤 Send your Review Slip Image")
    await c.answer()

# ================= WITHDRAW =================
@dp.callback_query(F.data=="withdraw")
async def withdraw(c:types.CallbackQuery):
    USER_STATE[c.from_user.id]="withdraw"
    await c.message.answer("💰 Send UPI ID or QR Image")
    await c.answer()

# ================= USER MEDIA HANDLER =================
@dp.message(lambda m:m.from_user.id in USER_STATE)
async def user_upload(m:types.Message):

    state=USER_STATE.get(m.from_user.id)

    text=f"""
👤 {m.from_user.full_name}
🆔 ID: {m.from_user.id}
"""

    if state=="slip":

        if m.photo:
            await bot.send_photo(ADMIN_ID,
            m.photo[-1].file_id,
            caption="📤 Review Slip\n"+text)

        USER_STATE.pop(m.from_user.id)
        await m.answer("✅ Slip Sent To Admin")

    elif state=="withdraw":

        if m.photo:
            await bot.send_photo(ADMIN_ID,
            m.photo[-1].file_id,
            caption="💰 Withdraw Request\n"+text)
        else:
            await bot.send_message(ADMIN_ID,
            "💰 Withdraw Request\n"+text+f"\nUPI:\n{m.text}")

        USER_STATE.pop(m.from_user.id)
        await m.answer("✅ Withdraw Request Sent")

# ================= LIVE CHAT SYSTEM =================
@dp.message(lambda m:m.from_user.id!=ADMIN_ID)
async def user_chat(m:types.Message):

    # ignore commands
    if m.text and m.text.startswith("/"):
        return

    text=f"""
📩 User Message

👤 {m.from_user.full_name}
🆔 ID: {m.from_user.id}

{m.text}
"""
    await bot.send_message(ADMIN_ID,text)

# ADMIN REPLY
@dp.message(lambda m:m.from_user.id==ADMIN_ID and m.reply_to_message)
async def admin_reply(m:types.Message):
    try:
        lines=m.reply_to_message.text.splitlines()
        uid=int([l for l in lines if "ID:" in l][0].split(":")[1].strip())

        await bot.send_message(uid,
        f"👨‍💼 <b>Admin Reply:</b>\n\n{m.text}")
    except:
        pass

# ================= ADMIN PANEL =================
@dp.message(Command("admin"))
async def admin_panel(m:types.Message):

    if not is_admin(m.from_user.id): return

    kb=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼 Set Main Image",callback_data="set_img")],
        [InlineKeyboardButton(text="📜 Set Instructions",callback_data="set_text")],
        [InlineKeyboardButton(text="⭐ Review URL",callback_data="set_review")],
        [InlineKeyboardButton(text="💬 Support Link",callback_data="set_support")],
        [InlineKeyboardButton(text="🎥 Guide Video",callback_data="set_guide")],
        [InlineKeyboardButton(text="📢 Broadcast",callback_data="bc")]
    ])

    await m.answer("👑 REVIEW BOT ADMIN PANEL",reply_markup=kb)

# ================= ADMIN SETTINGS =================
@dp.callback_query(F.data=="set_img")
async def set_img(c:types.CallbackQuery):
    ADMIN_STATE[c.from_user.id]="img"
    await c.message.answer("Send Image URL")

@dp.callback_query(F.data=="set_text")
async def set_text(c:types.CallbackQuery):
    ADMIN_STATE[c.from_user.id]="text"
    await c.message.answer("Send Instructions Text")

@dp.callback_query(F.data=="set_review")
async def set_review(c:types.CallbackQuery):
    ADMIN_STATE[c.from_user.id]="review"
    await c.message.answer("Send Review URL or type DELETE")

@dp.callback_query(F.data=="set_support")
async def set_support(c:types.CallbackQuery):
    ADMIN_STATE[c.from_user.id]="support"
    await c.message.answer("Send Support URL")

@dp.callback_query(F.data=="set_guide")
async def set_guide(c:types.CallbackQuery):
    ADMIN_STATE[c.from_user.id]="guide"
    await c.message.answer("Send Guide Video Link")

# ================= ADMIN INPUT HANDLER =================
@dp.message(lambda m:m.from_user.id in ADMIN_STATE)
async def admin_input(m:types.Message):

    state=ADMIN_STATE[m.from_user.id]
    cfg=load("config.json")

    if state=="img":
        cfg["main_image"]=m.text
    elif state=="text":
        cfg["instructions"]=m.text
    elif state=="review":
        if m.text.lower()=="delete":
            cfg["review_url"]=""
        else:
            cfg["review_url"]=m.text
    elif state=="support":
        cfg["support_url"]=m.text
    elif state=="guide":
        cfg["guide_video"]=m.text

    save("config.json",cfg)
    ADMIN_STATE.pop(m.from_user.id)

    await m.answer("✅ Updated")

# ================= BROADCAST =================
@dp.callback_query(F.data=="bc")
async def bc(c:types.CallbackQuery):
    ADMIN_STATE[c.from_user.id]="bc"
    await c.message.answer("Send broadcast text")

@dp.message(lambda m:ADMIN_STATE.get(m.from_user.id)=="bc")
async def send_bc(m:types.Message):

    users=load("users.json")

    for uid in users.keys():
        try:
            await bot.send_message(uid,m.text)
        except:
            pass

    ADMIN_STATE.pop(m.from_user.id)
    await m.answer("📢 Broadcast Sent")

# ================= RUN =================
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())
