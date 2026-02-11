import asyncio, os, json, uuid
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN=os.getenv("BOT_TOKEN")
OWNER_ID=int(os.getenv("ADMIN_ID"))

bot=Bot(token=BOT_TOKEN,
default=DefaultBotProperties(parse_mode="HTML"))
dp=Dispatcher()

FILES=["products.json","users.json","orders.json",
"payments.json","admins.json","slider.json"]

for f in FILES:
    if not os.path.exists(f):
        open(f,"w").write("{}")

def load(x): return json.load(open(x))
def save(x,d): json.dump(d,open(x,"w"),indent=2)

USER_STATE={}
ADMIN_STATE={}
ORDERS={}

# ========= ADMIN CHECK =========
def is_admin(uid):
    admins=load("admins.json")
    return str(uid)==str(OWNER_ID) or str(uid) in admins

# ========= START =========
@dp.message(Command("start"))
async def start(m:types.Message):

    users=load("users.json")
    users[str(m.from_user.id)]={"id":m.from_user.id}
    save("users.json",users)

    sliders=load("slider.json")
    for sid,s in sliders.items():
        kb=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=s["text"],url=s["link"])]
        ])
        await m.answer_photo(photo=s["image"],reply_markup=kb)

    products=load("products.json")
    cats=set(p.get("category","General") for p in products.values())

    rows=[[InlineKeyboardButton(text=c,callback_data=f"cat:{c}")]
    for c in cats]

    if rows:
        await m.answer("🛍 Choose Category:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

# ========= CATEGORY =========
@dp.callback_query(lambda c:c.data.startswith("cat:"))
async def cat(c:types.CallbackQuery):

    cat=c.data.split(":")[1]
    products=load("products.json")

    for pid,p in products.items():
        if p.get("category")!=cat: continue

        kb=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Buy Now",callback_data=f"buy:{pid}")]
        ])

        await c.message.answer_photo(
        photo=p["image"],
        caption=f"<b>{p['name']}</b>\n💰 ₹{p['price']}\n📦 Stock:{p.get('stock',0)}",
        reply_markup=kb)
    await c.answer()

# ========= BUY =========
@dp.callback_query(lambda c:c.data.startswith("buy:"))
async def buy(c:types.CallbackQuery):

    pid=c.data.split(":")[1]
    products=load("products.json")

    if products[pid].get("stock",0)<=0:
        return await c.answer("❌ Out Of Stock")

    oid=str(uuid.uuid4())[:8]
    ORDERS[oid]={"user":c.from_user.id,"product":pid}
    USER_STATE[c.from_user.id]={"order":oid}

    kb=InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👤 Name",callback_data="name")],
    [InlineKeyboardButton(text="📧 Email",callback_data="email")],
    [InlineKeyboardButton(text="💳 Pay",callback_data="pay")]
    ])

    await c.message.answer(f"🧾 OrderID: <code>{oid}</code>",reply_markup=kb)
    await c.answer()

# ========= FORM =========
@dp.callback_query(F.data=="name")
async def name_btn(c:types.CallbackQuery):
    USER_STATE[c.from_user.id]["await"]="name"
    await c.message.answer("Enter Name:")
    await c.answer()

@dp.callback_query(F.data=="email")
async def email_btn(c:types.CallbackQuery):
    USER_STATE[c.from_user.id]["await"]="email"
    await c.message.answer("Enter Email:")
    await c.answer()

@dp.message(lambda m:m.from_user.id in USER_STATE)
async def form(m:types.Message):

    st=USER_STATE[m.from_user.id]

    if st.get("await")=="name": st["name"]=m.text
    elif st.get("await")=="email": st["email"]=m.text
    elif st.get("await")=="utr": st["utr"]=m.text

    st.pop("await",None)

# ========= PAYMENT =========
@dp.callback_query(F.data=="pay")
async def pay(c:types.CallbackQuery):

    payments=load("payments.json")

    if not payments:
        return await c.message.answer("❌ No Payment Method")

    first=list(payments.values())[0]

    USER_STATE[c.from_user.id]["await"]="utr"

    await c.message.answer_photo(
    photo=first["qr"],
    caption=f"UPI: <code>{first['upi']}</code>\nSend UTR:")
    await c.answer()

# ========= ADMIN REQUEST =========
@dp.message(lambda m:m.from_user.id in USER_STATE and "utr" in USER_STATE[m.from_user.id])
async def admin_req(m:types.Message):

    st=USER_STATE[m.from_user.id]
    oid=st["order"]

    kb=InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Approve",callback_data=f"ap:{oid}")],
    [InlineKeyboardButton(text="❌ Reject",callback_data=f"rej:{oid}")]
    ])

    await bot.send_message(OWNER_ID,
    f"🧾 OrderID:{oid}\nUTR:{st['utr']}",
    reply_markup=kb)

    await m.answer("⏳ Waiting Approval")

# ========= APPROVE =========
@dp.callback_query(lambda c:c.data.startswith("ap:"))
async def approve(c:types.CallbackQuery):

    oid=c.data.split(":")[1]
    order=ORDERS.get(oid)
    if not order: return

    products=load("products.json")
    p=products[order["product"]]

    uid=order["user"]

    if p["delivery_type"]=="file":
        await bot.send_document(uid,p["data"])
    else:
        await bot.send_message(uid,p["data"])

    p["stock"]=p.get("stock",0)-1
    save("products.json",products)

    orders=load("orders.json")
    orders[oid]=order
    save("orders.json",orders)

    ORDERS.pop(oid,None)
    USER_STATE.pop(uid,None)

    await c.message.edit_reply_markup(None)
    await c.answer("Approved")

# ========= ADMIN PANEL =========
@dp.message(Command("admin"))
async def admin_panel(m:types.Message):

    if not is_admin(m.from_user.id): return

    kb=InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ Add Product",callback_data="add_p")],
    [InlineKeyboardButton(text="📦 Manage Products",callback_data="manage_p")],
    [InlineKeyboardButton(text="🎞 Manage Slider",callback_data="manage_s")],
    [InlineKeyboardButton(text="💰 Payment Panel",callback_data="pay_panel")],
    [InlineKeyboardButton(text="🧾 Orders",callback_data="orders")],
    [InlineKeyboardButton(text="📢 Broadcast",callback_data="bc")]
    ])

    await m.answer("👑 ULTRA ADMIN V8.6",reply_markup=kb)

# ========= ADD PRODUCT =========
@dp.callback_query(F.data=="add_p")
async def addp(c:types.CallbackQuery):
    ADMIN_STATE[c.from_user.id]="add"
    await c.message.answer("name|price|image|category|type(file/link)|data|stock")

@dp.message(lambda m:ADMIN_STATE.get(m.from_user.id)=="add")
async def savep(m:types.Message):

    name,price,img,cat,ptype,data,stock=m.text.split("|")
    products=load("products.json")
    pid=f"p{len(products)+1}"

    products[pid]={
    "name":name,"price":price,"image":img,
    "category":cat,"delivery_type":ptype,
    "data":data,"stock":int(stock)
    }

    save("products.json",products)
    ADMIN_STATE.pop(m.from_user.id)
    await m.answer("✅ Product Added")

# ========= MANAGE PRODUCTS =========
@dp.callback_query(F.data=="manage_p")
async def managep(c:types.CallbackQuery):

    products=load("products.json")
    rows=[]

    for pid,p in products.items():
        rows.append([
        InlineKeyboardButton(text=f"✏️ {p['name']}",callback_data=f"edit:{pid}"),
        InlineKeyboardButton(text="🗑",callback_data=f"del:{pid}")
        ])

    await c.message.answer("Manage Products:",
    reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(lambda c:c.data.startswith("edit:"))
async def editp(c:types.CallbackQuery):
    pid=c.data.split(":")[1]
    ADMIN_STATE[c.from_user.id]=f"edit:{pid}"
    await c.message.answer("Send NEW name|price|image|category|type|data|stock")

@dp.message(lambda m:ADMIN_STATE.get(m.from_user.id,"").startswith("edit:"))
async def save_editp(m:types.Message):

    pid=ADMIN_STATE[m.from_user.id].split(":")[1]
    name,price,img,cat,ptype,data,stock=m.text.split("|")

    products=load("products.json")
    products[pid]={
    "name":name,"price":price,"image":img,
    "category":cat,"delivery_type":ptype,
    "data":data,"stock":int(stock)
    }

    save("products.json",products)
    ADMIN_STATE.pop(m.from_user.id)
    await m.answer("✏️ Product Updated")

@dp.callback_query(lambda c:c.data.startswith("del:"))
async def delp(c:types.CallbackQuery):
    pid=c.data.split(":")[1]
    products=load("products.json")
    products.pop(pid,None)
    save("products.json",products)
    await c.message.edit_text("🗑 Deleted")

# ========= SLIDER PANEL =========
@dp.callback_query(F.data=="manage_s")
async def slider(c:types.CallbackQuery):

    sliders=load("slider.json")
    rows=[]

    for sid,s in sliders.items():
        rows.append([
        InlineKeyboardButton(text=f"✏️ {sid}",callback_data=f"sed:{sid}"),
        InlineKeyboardButton(text="🗑",callback_data=f"sdel:{sid}")
        ])

    rows.append([InlineKeyboardButton(text="➕ Add Slider",callback_data="sadd")])

    await c.message.answer("Slider Panel:",
    reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data=="sadd")
async def sadd(c:types.CallbackQuery):
    ADMIN_STATE[c.from_user.id]="slider"
    await c.message.answer("image|text|link")

@dp.message(lambda m:ADMIN_STATE.get(m.from_user.id)=="slider")
async def saves(m:types.Message):

    img,txt,link=m.text.split("|")
    sliders=load("slider.json")
    sid=f"s{len(sliders)+1}"
    sliders[sid]={"image":img,"text":txt,"link":link}
    save("slider.json",sliders)

    ADMIN_STATE.pop(m.from_user.id)
    await m.answer("🎞 Slider Added")

@dp.callback_query(lambda c:c.data.startswith("sed:"))
async def sedit(c:types.CallbackQuery):
    sid=c.data.split(":")[1]
    ADMIN_STATE[c.from_user.id]=f"sedit:{sid}"
    await c.message.answer("Send NEW image|text|link")

@dp.message(lambda m:ADMIN_STATE.get(m.from_user.id,"").startswith("sedit:"))
async def save_sedit(m:types.Message):

    sid=ADMIN_STATE[m.from_user.id].split(":")[1]
    img,txt,link=m.text.split("|")

    sliders=load("slider.json")
    sliders[sid]={"image":img,"text":txt,"link":link}
    save("slider.json",sliders)

    ADMIN_STATE.pop(m.from_user.id)
    await m.answer("✏️ Slider Updated")

@dp.callback_query(lambda c:c.data.startswith("sdel:"))
async def sdel(c:types.CallbackQuery):

    sid=c.data.split(":")[1]
    sliders=load("slider.json")
    sliders.pop(sid,None)
    save("slider.json",sliders)

    await c.message.edit_text("🗑 Slider Deleted")

# ========= PAYMENT PANEL =========
@dp.callback_query(F.data=="pay_panel")
async def pay_panel(c:types.CallbackQuery):

    payments=load("payments.json")
    rows=[]

    for pid,p in payments.items():
        rows.append([
        InlineKeyboardButton(text=f"✏️ {p['upi']}",callback_data=f"pedit:{pid}"),
        InlineKeyboardButton(text="🗑",callback_data=f"pdel:{pid}")
        ])

    rows.append([InlineKeyboardButton(text="➕ Add Payment",callback_data="padd")])

    await c.message.answer("💰 Payment Panel:",
    reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data=="padd")
async def padd(c:types.CallbackQuery):
    ADMIN_STATE[c.from_user.id]="padd"
    await c.message.answer("Send UPI|QR_LINK")

@dp.message(lambda m:ADMIN_STATE.get(m.from_user.id)=="padd")
async def save_payment(m:types.Message):

    upi,qr=m.text.split("|")
    payments=load("payments.json")
    pid=f"pay{len(payments)+1}"

    payments[pid]={"upi":upi,"qr":qr}
    save("payments.json",payments)

    ADMIN_STATE.pop(m.from_user.id)
    await m.answer("✅ Payment Added")

@dp.callback_query(lambda c:c.data.startswith("pedit:"))
async def pedit(c:types.CallbackQuery):
    pid=c.data.split(":")[1]
    ADMIN_STATE[c.from_user.id]=f"pedit:{pid}"
    await c.message.answer("Send NEW UPI|NEW_QR")

@dp.message(lambda m:ADMIN_STATE.get(m.from_user.id,"").startswith("pedit:"))
async def save_pedit(m:types.Message):

    pid=ADMIN_STATE[m.from_user.id].split(":")[1]
    upi,qr=m.text.split("|")

    payments=load("payments.json")
    payments[pid]={"upi":upi,"qr":qr}
    save("payments.json",payments)

    ADMIN_STATE.pop(m.from_user.id)
    await m.answer("✏️ Payment Updated")

@dp.callback_query(lambda c:c.data.startswith("pdel:"))
async def pdel(c:types.CallbackQuery):

    pid=c.data.split(":")[1]
    payments=load("payments.json")
    payments.pop(pid,None)
    save("payments.json",payments)

    await c.message.edit_text("🗑 Payment Deleted")

# ========= ORDERS =========
@dp.callback_query(F.data=="orders")
async def orders(c:types.CallbackQuery):

    orders=load("orders.json")
    txt="🧾 Orders:\n"

    for oid,o in orders.items():
        txt+=f"\n{oid} - User:{o['user']}"

    await c.message.answer(txt)

# ========= BROADCAST =========
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
        except: pass

    ADMIN_STATE.pop(m.from_user.id)
    await m.answer("📢 Broadcast Sent")

# ========= RUN =========
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())