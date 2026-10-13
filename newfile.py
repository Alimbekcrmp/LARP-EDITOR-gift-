import os; os.environ['aiohttp_trust_env'] = '1'
import asyncio, logging, random, json, time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp import ClientSession, ClientTimeout
import aiosqlite

TOKEN = "8694291907:AAES8fJtodpxav9wK_FL8PlpcrQtvLLVLNw"
ADMIN_ID = 8694291907
DB_PATH = "simulator_gift.db"

bot = Bot(token=TOKEN)



dp = Dispatcher(storage=MemoryStorage())
RARITIES = {"💚 Зелёный": 50, "💙 Синий": 25, "💜 Фиолетовый": 15, "💛 Золотой": 7, "🖤 Чёрный": 3}


def roll_gift_color():
    return random.choices(list(RARITIES.keys()), weights=list(RARITIES.values()), k=1)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 500)")
        await db.execute("CREATE TABLE IF NOT EXISTS gift_templates (gift_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, description TEXT, photo_id TEXT, price INTEGER, max_limit INTEGER, issued_count INTEGER DEFAULT 0)")
        await db.execute("CREATE TABLE IF NOT EXISTS inventory (item_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, gift_id INTEGER, serial_number INTEGER, color TEXT DEFAULT '💚 Зелёный')")
        await db.execute("CREATE TABLE IF NOT EXISTS p2p_market (market_id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER, seller_id INTEGER, price INTEGER)")
        await db.execute("CREATE TABLE IF NOT EXISTS promo_codes (code TEXT PRIMARY KEY, reward_type TEXT, reward_value TEXT, max_uses INTEGER, used_count INTEGER DEFAULT 0)")
        await db.execute("CREATE TABLE IF NOT EXISTS promo_uses (code TEXT, user_id INTEGER, PRIMARY KEY (code, user_id))")
        await db.execute("CREATE TABLE IF NOT EXISTS cases (case_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price INTEGER, items TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('x5_event', 'off')")
        await db.execute("CREATE TABLE IF NOT EXISTS giveaways (giveaway_id INTEGER PRIMARY KEY AUTOINCREMENT, prize_type TEXT, prize_value TEXT, status TEXT DEFAULT 'active')")
        await db.execute("CREATE TABLE IF NOT EXISTS giveaway_participants (giveaway_id INTEGER, user_id INTEGER, PRIMARY KEY(giveaway_id, user_id))")
        await db.execute("CREATE TABLE IF NOT EXISTS battles (battle_id INTEGER PRIMARY KEY AUTOINCREMENT, creator_id INTEGER, creator_item_id INTEGER, opponent_id INTEGER DEFAULT NULL, opponent_item_id INTEGER DEFAULT NULL, status TEXT DEFAULT 'waiting')")
        await db.execute("CREATE TABLE IF NOT EXISTS battle_bets (battle_id INTEGER, user_id INTEGER, side INTEGER, amount INTEGER)")
        await db.commit()

async def get_balance(uid):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT balance FROM users WHERE user_id=?", (uid,)) as c:
            r = await c.fetchone()
            return r if r else 0

async def update_balance(uid, amt):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amt, uid))
        await db.commit()

async def check_x5_event():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key='x5_event'") as c:
            r = await c.fetchone()
            return r[0] == 'on' if r else False

async def give_gift(uid, gid, cc=None):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT max_limit, issued_count FROM gift_templates WHERE gift_id=?", (gid,)) as c:
            g = await c.fetchone()
            if not g: return None
            ml, iss = g
            if ml > 0 and iss >= ml: return False
            ns = iss + 1
            fc = cc if cc else roll_gift_color()
            await db.execute("UPDATE gift_templates SET issued_count=? WHERE gift_id=?", (ns, gid))
            await db.execute("INSERT INTO inventory (user_id,gift_id,serial_number,color) VALUES (?,?,?,?)", (uid, gid, ns, fc))
            await db.commit()
            return {"serial": ns, "color": fc}

class AdminGiftState(StatesGroup):
    photo = State()
    text = State()
    price = State()
    limit = State()

class P2PSellState(StatesGroup):
    item_id = State()
    price = State()

class TransferState(StatesGroup):
    target = State()
    amount = State()

    amount = State()

class BetState(StatesGroup):
    battle_id = State()
    side = State()
    amount = State()
class PromoState(StatesGroup):
    code = State()

def main_kb(uid):
    b = ReplyKeyboardBuilder()
    for t in ["👤 Профиль", "🏪 Магазин", "🏛️ P2P Рынок", "🎰 Mini-Игры", "🧳 Кейсы", "⚡ Апгрейдер", "⚔️ Батлы (1x1)", "🎁 Розыгрыши/Промо"]:
        b.button(text=t)
    if uid == ADMIN_ID:
        b.button(text="👑 Админка")
    b.adjust(2)
    return b.as_markup(resize_keyboard=True)


@dp.message(CommandStart())
async def cmd_start(m: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id,username,balance) VALUES (?,?,500)", (m.from_user.id, m.from_user.username or m.from_user.first_name))
        await db.commit()
        await m.answer("Добро пожаловать в **SIMULATOR GIFT EDITORS LARP**!\nВы получили **500 стартовых монет**", reply_markup=main_kb(m.from_user.id), parse_mode="Markdown")


@dp.message(F.text == "🎒 Профиль")
async def view_profile(m: types.Message):
    bal = await get_balance(m.from_user.id)
    text = f"👤 **Ваш профиль:**\n💰 Баланс: `{bal}` монет\n\n🎁 Ваши Подарки:**"
    async with ConcreteConnect(DB_PATH) as db:
        async with db.execute("SELECT i.item_id, t.name, i.serial_number, i.color FROM inventory i JOIN gift_templates t ON i.gift_id = t.gift_id WHERE i.user_id = ?", (m.from_user.id,)) as c:
            inv = await c.fetchall()
    if inv:
        for it in inv: text += f" 🆔 `{it[0]}` | {it[5]} *{it[1]}* #{it[2]}**"
    else:
        text += " _Инвентарь пуст_"
    b = InlineKeyboardBuilder()
    b.button(text="💸 Перевести монеты", callback_data="tr_coins")
    b.button(text="🏪 Продать на P2P", callback_data="p2p_sell")
    b.adjust(1)
    await m.answer(text, reply_markup=b.as_markup(), parse_mode="Markdown")

@dp.message(F.text == "👑 Админка", F.from_user.id == ADMIN_ID)
async def admin_menu(m: types.Message):
    b = InlineKeyboardBuilder()
    b.button(text="➕ Создать Подарок", callback_data="adm_add_gift")
    b.button(text="⚙️ Переключить X5", callback_data="adm_toggle_x5")
    b.adjust(1)
    await m.answer("👑 **Панель создателя игры:**\n\n💡 **Выдать подарок вручную:**\n`/give_custom [User_ID] [Gift_ID] [Номер цвета]`\nЦвета: 1=💚, 2=💙, 3=💜, 4=💛, 5=🖤", reply_markup=b.as_markup(), parse_mode="Markdown")

@dp.message(Command("give_custom"), F.from_user.id == ADMIN_ID)
async def cmd_give_custom(m: types.Message):
    a = m.text.split()
    if len(a) < 4: return await m.answer("⚠️ Шаблон: `/give_custom [User_ID] [Gift_ID] [1-5]`")
    try: tu, gi, cn = int(a[1]), int(a[2]), int(a[3])
    except ValueError: return await m.answer("❌ Все аргументы должны быть числами!")
    cm = {1: "💚 Зелёный", 2: "💙 Синий", 3: "💜 Фиолетовый", 4: "💛 Золотой", 5: "🖤 Чёрный"}
    sc = cm.get(cn, "💚 Зелёный")
    res = await give_gift(tu, gi, cc=sc)
    if res:
        await m.answer(f"✅ Выдан подарок ID {gi} в цвете {sc} #{res['serial']}!")
        try: await bot.send_message(tu, f"👑 Admin выдал подарок! {sc} #{res['serial']}!")
        except: pass
    else: await m.answer("Ошибка выдачи.")

@dp.callback_query(F.data == "adm_add_gift", F.from_user.id == ADMIN_ID)
async def start_gift_fsm(c: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminGiftState.photo)
    await c.message.answer("Шаг 1: Отправьте ФОТО подарка.")
    await c.answer()

@dp.message(AdminGiftState.photo, F.photo)
async def process_gift_photo(m: types.Message, state: FSMContext):
    await state.update_data(photo=m.photo[-1].file_id)
    await state.set_state(AdminGiftState.text)
    await m.answer("Шаг 2: Введите НАЗВАНИЕ и ОПИСАНИЕ.")

@dp.message(AdminGiftState.text)
async def process_gift_text(m: types.Message, state: FSMContext):
    await state.update_data(text=m.text)
    await state.set_state(AdminGiftState.price)
    await m.answer("Шаг 3: СТОИМОСТЬ (число).")

@dp.message(AdminGiftState.price)
async def process_gift_price(m: types.Message, state: FSMContext):
    try:
        await state.update_data(price=int(m.text))
        await state.set_state(AdminGiftState.limit)
        await m.answer("Шаг 4: ТИРАЖ (0 — безлимит).")
    except ValueError: await m.answer("❌ Введите число!")

@dp.message(AdminGiftState.limit)
async def process_gift_limit(m: types.Message, state: FSMContext):
    try:
        lim = int(m.text)
        d = await state.get_data()
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("INSERT INTO gift_templates (name,description,photo_id,price,max_limit) VALUES (?,?,?,?,?)", (d['text'].split('\n'), d['text'], d['photo'], d['price'], lim))
            await db.commit()
            gid = cur.lastrowid
        await state.clear()
        await m.answer(f"✅ Подарок создан (ID: {gid})!")
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id FROM users") as c:
                us = await c.fetchall()
        lt = "Безлимитный" if lim == 0 else f"{lim} шт."
        for u in us:
            try: await bot.send_photo(u[0], d['photo'], caption=f"🚨 НОВЫЙ ПОДАРОК!\n\n📌 {d['text']}\n💰 Цена: {d['price']}\n📊 Тираж: {lt}", parse_mode="Markdown")
            except: pass
    except ValueError: await m.answer("❌ Введите число!")

@dp.callback_query(F.data == "adm_toggle_x5", F.from_user.id == ADMIN_ID)
async def toggle_x5(c: types.CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key='x5_event'") as cur:
            cr = await cur.fetchone()
        nv = "off" if cr and cr[0] == "on" else "on"
        await db.execute("UPDATE settings SET value=? WHERE key='x5_event'", (nv,))
        await db.commit()
    await c.message.answer(f"⚙️ X5: {nv.upper()}")
    await c.answer()

@dp.message(F.text == "🏪 Магазин")
async def view_shop(m: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT gift_id,name,price,max_limit,issued_count FROM gift_templates") as c:
            gs = await c.fetchall()
    if not gs: return await m.answer("🏪 Магазин пуст.")
    for g in gs:
        gid, nm, pr, lm, iss = g
        lt = "♾️ Безлимит" if lm == 0 else f"📉 Осталось: {lm-iss}/{lm}"
        b = InlineKeyboardBuilder()
        b.button(text=f"🛒 Купить за {pr} монет", callback_data=f"buy_sys_{gid}")
        await m.answer(f"🎁 {nm}\n💰 Цена: {pr} монет\n📊 {lt}", reply_markup=b.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("buy_sys_"))
async def process_buy_sys(c: types.CallbackQuery):
    gid = int(c.data.split("_")[2])
    uid = c.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT price,max_limit,issued_count FROM gift_templates WHERE gift_id=?", (gid,)) as cur:
            g = await cur.fetchone()
    if not g: return await c.answer("Товар не найден!", show_alert=True)
    pr, lm, iss = g
    if lm > 0 and iss >= lm: return await c.answer("❌ Тираж раскуплен!", show_alert=True)
    bal = await get_balance(uid)
    if bal < pr: return await c.answer("❌ Недостаточно монет!", show_alert=True)
    await update_balance(uid, -pr)
    res = await give_gift(uid, gid)
    if res: await c.message.answer(f"🎉 Покупка!\nВариация: {res['color']}\nНомер #{res['serial']}!", parse_mode="Markdown")
    else: await c.message.answer("Ошибка.")
    await c.answer()

@dp.callback_query(F.data == "p2p_sell")
async def p2p_sell_start(c: types.CallbackQuery, state: FSMContext):
    await state.set_state(P2PSellState.item_id)
    await c.message.answer("Введите ID предмета из профиля.")
    await c.answer()

@dp.message(P2PSellState.item_id)
async def p2p_sell_id(m: types.Message, state: FSMContext):
    try:
        await state.update_data(item_id=int(m.text))
        await state.set_state(P2PSellState.price)
        await m.answer("Укажите цену.")
    except ValueError: await m.answer("❌ Число!")

@dp.message(P2PSellState.price)
async def p2p_sell_price(m: types.Message, state: FSMContext):
    try:
        d = await state.get_data()
        pr = int(m.text)
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT item_id FROM inventory WHERE item_id=? AND user_id=?", (d['item_id'], m.from_user.id)) as c:
                own = await c.fetchone()
            if own:
                await db.execute("INSERT INTO p2p_market (item_id,seller_id,price) VALUES (?,?,?)", (d['item_id'], m.from_user.id, pr))
                await db.commit()
                await m.answer("🏪 Товар выставлен!")
            else: await m.answer("❌ Не ваш предмет.")
        await state.clear()
    except ValueError: await m.answer("❌ Цифрами!")

@dp.message(F.text == "🏛️ P2P Рынок")
async def view_p2p(m: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT m.market_id,t.name,i.serial_number,u.username,m.price,i.color FROM p2p_market m JOIN inventory i ON m.item_id=i.item_id JOIN gift_templates t ON i.gift_id=t.gift_id JOIN users u ON m.seller_id=u.user_id") as c:
            its = await c.fetchall()
    if not its: return await m.answer("🏛️ Рынок пуст.")
    for it in its:
        mid, nm, sn, sl, pr, cl = it
        b = InlineKeyboardBuilder()
        b.button(text=f"💰 Выкупить за {pr}", callback_data=f"buyp2p_{mid}")
        await m.answer(f"🎁 {cl} {nm} #{sn}\n👤 @{sl}\n💰 {pr}", reply_markup=b.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("buyp2p_"))
async def process_buy_p2p(c: types.CallbackQuery):
    mid = int(c.data.split("_")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT item_id,seller_id,price FROM p2p_market WHERE market_id=?", (mid,)) as cur:
            deal = await cur.fetchone()
    if not deal: return await c.answer("Продан!", show_alert=True)
    iid, sid, pr = deal
    bal = await get_balance(c.from_user.id)
    if bal < pr: return await c.answer("❌ Мало монет!", show_alert=True)
    await update_balance(c.from_user.id, -pr)
    await update_balance(sid, pr)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE inventory SET user_id=? WHERE item_id=?", (c.from_user.id, iid))
        await db.execute("DELETE FROM p2p_market WHERE market_id=?", (mid,))
        await db.commit()
    try: await bot.send_message(sid, f"💰 Выкуплен! +{pr}")
    except: pass
    await c.message.answer("🎉 Предмет у вас!")
    await c.answer()

@dp.callback_query(F.data == "tr_coins")
async def tr_start(c: types.CallbackQuery, state: FSMContext):
    await state.set_state(TransferState.target)
    await c.message.answer("Введите user_id получателя.")
    await c.answer()

@dp.message(TransferState.target)
async def tr_target(m: types.Message, state: FSMContext):
    try:
        await state.update_data(target=int(m.text))
        await state.set_state(TransferState.amount)
        await m.answer("Введите сумму.")
    except ValueError: await m.answer("❌ Число!")

@dp.message(TransferState.amount)
async def tr_amount(m: types.Message, state: FSMContext):
    try:
        amt = int(m.text)
        if amt <= 0: return await m.answer("❌ >0!")
        d = await state.get_data()
        tg = d['target']
        if tg == m.from_user.id: return await m.answer("❌ Себе нельзя.")
        bal = await get_balance(m.from_user.id)
        if bal < amt: return await m.answer("❌ Мало!")
        await update_balance(m.from_user.id, -amt)
        await update_balance(tg, amt)
        await m.answer(f"✅ Отправлено {amt}")
        try: await bot.send_message(tg, f"💸 +{amt} монет!")
        except: pass
        await state.clear()
    except ValueError: await m.answer("❌ Число!")

@dp.message(F.text == "🎲 Mini-Игры")
async def games_menu(m: types.Message):
    b = InlineKeyboardBuilder()
    b.button(text="🎰 Слоты 777", callback_data="play_slots")
    b.button(text="🏀 Баскетбол", callback_data="play_basket")
    b.button(text="🎲 Кости", callback_data="play_dice")
    b.adjust(2)
    await m.answer("🎰 Ставка 100:", reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("play_"))
async def run_game(c: types.CallbackQuery):
    gm = c.data.split("_")[1]
    uid = c.from_user.id
    bal = await get_balance(uid)
    if bal < 100: return await c.answer("❌ Нужно 100!", show_alert=True)
    await update_balance(uid, -100)
    x5 = await get_x5()
    m = 5 if x5 else 1
    win = 0
    if gm == "slots":
        msg = await c.message.answer_dice(emoji="🎰")
        await asyncio.sleep(3)
        win = 1000 * m if msg.dice.value == 64 else (200 * m if msg.dice.value in [1, 22, 43] else 0)
    elif gm == "basket":
        msg = await c.message.answer_dice(emoji="🏀")
        await asyncio.sleep(3)
        win = 300 * m if msg.dice.value >= 4 else 0
    elif gm == "dice":
        msg = await c.message.answer_dice(emoji="🎲")
        await asyncio.sleep(3)
        win = 200 * m if msg.dice.value >= 4 else 0
    if win > 0:
        await update_balance(uid, win)
        await c.message.answer(f"🎉 +{win} монет.{' 🔥X5' if x5 else ''}")
    else: await c.message.answer("😢 Проигрыш!")
    await c.answer()

@dp.message(F.text == "🧳 Кейсы")
async def view_cases(m: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT case_id,name,price FROM cases") as c:
            cs = await c.fetchall()
    if not cs: return await m.answer("🧳 Нет кейсов.")
    for cs_ in cs:
        cid, nm, pr = cs_
        b = InlineKeyboardBuilder()
        b.button(text=f"🔓 Открыть за {pr}", callback_data=f"open_case_{cid}")
        await m.answer(f"🧳 {nm}\n💰 {pr}", reply_markup=b.as_markup())



@dp.callback_query(F.data.startswith("open_case_"))
async def open_case(c: types.CallbackQuery):
    cid = int(c.data.split("_")[2])
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name,price,items FROM cases WHERE case_id=?", (cid,)) as cur:
            cs = await cur.fetchone()
    if not cs: return await c.answer("Нет кейса!", show_alert=True)
    nm, pr, ij = cs
    bal = await get_balance(c.from_user.id)
    if bal < pr: return await c.answer("❌ Мало!", show_alert=True)   
    await update_balance(c.from_user.id, -pr)
    try: its = json.loads(ij) if ij else []
    except: its = []
    if not its: return await c.answer("Пусто.", show_alert=True)
    gid = random.choice(its)
    res = await give_gift(c.from_user.id, gid)
    if res:
        await c.message.answer(f"🎉 Кейс «{nm}» открыт!\nВыпал подарок ID {gid}, {res['color']} #{res['serial']}")
    else:
        await c.message.answer("Ошибка.")
    await c.answer()


@dp.message(F.text == "⚡ Апгрейдер")
async def upgrader_menu(m: types.Message):
    await m.answer("⚡ Недоступно.")

@dp.message(F.text == "⚔️ Батлы (1x1)")
async def battles_menu(m: types.Message):
    b = InlineKeyboardBuilder()
    b.button(text="➕ Создать", callback_data="battle_create")
    b.button(text="📋 Список", callback_data="battle_list")
    b.adjust(1)
    await m.answer("⚔️ **Батлы 1x1**", reply_markup=b.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "battle_create")
async def battle_create(c: types.CallbackQuery, state: FSMContext):
    await state.set_state(BetState.battle_id)
    await c.message.answer("Введите ID предмета.")
    await c.answer()

@dp.message(BetState.battle_id)
async def battle_set_item(m: types.Message, state: FSMContext):
    try: iid = int(m.text)
    except ValueError: return await m.answer("❌ Число!")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT item_id FROM inventory WHERE item_id=? AND user_id=?", (iid, m.from_user.id)) as cur:
            own = await cur.fetchone()
        if not own: return await m.answer("❌ Нет предмета.")
        await db.execute("INSERT INTO battles (creator_id,creator_item_id,status) VALUES (?,?,'waiting')", (m.from_user.id, iid))
        await db.commit()
    await state.clear()
    await m.answer("✅ Батл создан!")

@dp.callback_query(F.data == "battle_list")
async def battle_list(c: types.CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT battle_id,creator_id,creator_item_id FROM battles WHERE status='waiting'") as cur:
            rs = await cur.fetchall()
    if not rs: return await c.answer("Нет батлов.", show_alert=True)   
    txt = "⚔️ **Батлы:**"
    for r in rs: txt += f"\n#{r[0]} | Создатель ID: `{r[1]}` | Предмет ID: `{r[2]}`"

    await c.message.answer(txt, parse_mode="Markdown")
    await c.answer()

@dp.message(F.text == "🎁 Розыгрыши/Промо")
async def promo_menu(m: types.Message):
    b = InlineKeyboardBuilder()
    b.button(text="🎟 Ввести промокод", callback_data="promo_enter")
    b.button(text="🎉 Розыгрыши", callback_data="giveaway_list")
    b.adjust(1)
    await m.answer("🎁 **Промо:**", reply_markup=b.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "promo_enter")
async def promo_enter(c: types.CallbackQuery, state: FSMContext):
    await state.set_state(PromoState.code)
    await c.message.answer("Введите промокод:")
    await c.answer()

@dp.message(PromoState.code)
async def promo_check(m: types.Message, state: FSMContext):
    code = m.text.strip()
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT reward_type,reward_value,max_uses,used_count FROM promo_codes WHERE code=?", (code,)) as cur:
                p = await cur.fetchone()
            if not p:
                await m.answer("❌ Не найден.")
                return await state.clear()
            rt, rv, mu, uc = p
            if mu > 0 and uc >= mu:
                await m.answer("❌ Исчерпан.")
                return await state.clear()
            async with db.execute("SELECT 1 FROM promo_uses WHERE code=? AND user_id=?", (code, m.from_user.id)) as cur:
                al = await cur.fetchone()
            if al:
                await m.answer("❌ Использован.")
                return await state.clear()
            await db.execute("INSERT INTO promo_uses (code,user_id) VALUES (?,?)", (code, m.from_user.id))
            await db.execute("UPDATE promo_codes SET used_count=used_count+1 WHERE code=?", (code,))
            await db.commit()
        if rt == "coins":
            try: amt = int(rv)
            except: amt = 0
            await update_balance(m.from_user.id, amt)
            await m.answer(f"🎉 +{amt} монет!")
        elif rt == "gift":
            try: gid = int(rv)
            except: gid = 0
            res = await give_gift(m.from_user.id, gid)
            if res: await m.answer(f"🎉 {res['color']} #{res['serial']}")
            else: await m.answer("❌ Не выдано.")
        else: await m.answer("🎉 Активирован!")
        await state.clear()
    except Exception as e:
        logging.error(e)

@dp.callback_query(F.data == "giveaway_list")
async def giveaway_list(c: types.CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT giveaway_id,prize_type,prize_value FROM giveaways WHERE status='active'") as cur:
            rs = await cur.fetchall()
    if not rs: return await c.answer("Нет розыгрышей.", show_alert=True)
    for r in rs:
        gid, pt, pv = r
        b = InlineKeyboardBuilder()
        b.button(text="🎟 Участвовать", callback_data=f"giveaway_join_{gid}")        
        await c.message.answer(f"🎉 Розыгрыш #{gid}\nПриз: {pt} — {pv}", reply_markup=b.as_markup())

    await c.answer()

@dp.callback_query(F.data.startswith("giveaway_join_"))
async def giveaway_join(c: types.CallbackQuery):
    await c.answer("Вы успешно записались!")

async def start_bot():
    print("3. Входим в функцию start_bot...")
    # await init_db()
    print("4. Пробуем очистить вебхуки...")
    await bot.delete_webhook(drop_pending_updates=True)
    print("🔥 5. БОТ ПОДКЛЮЧИЛСЯ И СЛУШАЕТ КОМАНДЫ!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    print("0. Скрипт запущен, вызываем start_bot...")
    asyncio.run(start_bot())

