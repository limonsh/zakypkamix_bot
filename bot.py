#!/usr/bin/env python3
import json, os, logging
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
Application, CommandHandler, CallbackQueryHandler,
MessageHandler, ConversationHandler, filters, ContextTypes
)

logging.basicConfig(format=”%(asctime)s [%(levelname)s] %(message)s”, level=logging.INFO)
logger = logging.getLogger(**name**)

DATA_FILE = “data.json”

(
ST_EDIT_COMMENT,
ST_ADD_ITEM_NAME,
ST_ADD_ITEM_COMMENT,
ST_ADD_ZAYAVKA_NAME,
ST_ADD_ZAYAVKA_COMMENT,
ST_ADD_SECTION_NAME,
ST_ADD_SECTION_EMOJI,
) = range(7)

def default_data():
return {
“sections”: [
{“id”: “sherif”, “name”: “Шериф”,  “emoji”: “🏪”},
{“id”: “japan”,  “name”: “Япония”,  “emoji”: “🍜”},
{“id”: “bazar”,  “name”: “Базар”,   “emoji”: “🛖”},
{“id”: “endis”,  “name”: “Эндис”,   “emoji”: “📦”},
],
“template”: {
“sherif”: [“Масло сливочное”, “Сыр пармезан”, “Молоко”],
“japan”:  [“Соевый соус”, “Рис для суши”, “Васаби”],
“bazar”:  [“Помидоры”, “Зелень”, “Огурцы”],
“endis”:  [“Мука пшеничная”, “Сахар”, “Масло растительное”],
},
“zayavka”: {},
“zakupka_status”: {},
“zakazano”: [],
“carry”: {},
“comments”: {},
“last_date”: str(date.today()),
“pinned_msg_id”: None,
}

def load():
if os.path.exists(DATA_FILE):
with open(DATA_FILE, “r”, encoding=“utf-8”) as f:
return json.load(f)
d = default_data()
save(d)
return d

def save(d):
with open(DATA_FILE, “w”, encoding=“utf-8”) as f:
json.dump(d, f, ensure_ascii=False, indent=2)

def get_data():
d = load()
today = str(date.today())
if d[“last_date”] != today:
_rollover(d)
d[“last_date”] = today
save(d)
return d

def _rollover(d):
carry = {}
statuses = d.get(“zakupka_status”, {})
for sec_id, items in d.get(“zayavka”, {}).items():
for item in items:
if not item.get(“checked”):
continue
key = f”{sec_id}:{item[‘name’]}”
if statuses.get(key) != “bought”:
carry.setdefault(sec_id, []).append(item[“name”])
d[“carry”] = carry
d[“zayavka”] = {}
d[“zakupka_status”] = {}
d[“comments”] = {}

def sec_label(d, sec_id):
for s in d[“sections”]:
if s[“id”] == sec_id:
return f”{s[‘emoji’]} {s[‘name’]}”
return sec_id

def kb_main():
return InlineKeyboardMarkup([[
InlineKeyboardButton(“📋 Заявка”,    callback_data=“screen:zayavka”),
InlineKeyboardButton(“🛒 Закупка”,   callback_data=“screen:zakupka”),
],[
InlineKeyboardButton(“📞 Заказано”,  callback_data=“screen:zakazano”),
InlineKeyboardButton(“⚙️ Настройки”, callback_data=“screen:settings”),
]])

def kb_zayavka(d):
rows = []
zayavka = d.get(“zayavka”, {})
comments = d.get(“comments”, {})
carry = d.get(“carry”, {})
for sec in d[“sections”]:
sid = sec[“id”]
template_items = d[“template”].get(sid, [])
carried = carry.get(sid, [])
all_names = list(dict.fromkeys(template_items + carried))
if not all_names:
continue
rows.append([InlineKeyboardButton(f”── {sec[‘emoji’]} {sec[‘name’]} ──”, callback_data=“noop”)])
sec_items = {item[“name”]: item for item in zayavka.get(sid, [])}
for name in all_names:
checked = sec_items.get(name, {}).get(“checked”, False)
icon = “✅” if checked else “⬜”
carry_tag = “ 🔁” if name in carried and name not in template_items else “”
comment = comments.get(f”{sid}:{name}”, “”)
comment_tag = f” · {comment}” if comment else “”
rows.append([
InlineKeyboardButton(f”{icon} {name}{carry_tag}{comment_tag}”, callback_data=f”z:toggle:{sid}:{name}”),
InlineKeyboardButton(“✏️”, callback_data=f”z:edit:{sid}:{name}”),
])
rows.append([InlineKeyboardButton(“➕ Добавить товар”, callback_data=“z:additem”)])
rows.append([InlineKeyboardButton(“📤 Отправить заявку”, callback_data=“z:send”)])
rows.append([InlineKeyboardButton(”« Назад”, callback_data=“screen:main”)])
return InlineKeyboardMarkup(rows)

def kb_zakupka(d):
rows = []
zayavka = d.get(“zayavka”, {})
statuses = d.get(“zakupka_status”, {})
comments = d.get(“comments”, {})
has_items = False
for sec in d[“sections”]:
sid = sec[“id”]
checked_items = [i for i in zayavka.get(sid, []) if i.get(“checked”)]
if not checked_items:
continue
has_items = True
rows.append([InlineKeyboardButton(f”── {sec[‘emoji’]} {sec[‘name’]} ──”, callback_data=“noop”)])
for item in checked_items:
name = item[“name”]
key = f”{sid}:{name}”
st = statuses.get(key)
comment = comments.get(key, “”)
comment_tag = f” · {comment}” if comment else “”
if st == “bought”:
icon = “✅”
elif st == “ordered”:
icon = “📞”
else:
icon = “⬜”
rows.append([InlineKeyboardButton(f”{icon} {name}{comment_tag}”, callback_data=“noop”)])
rows.append([
InlineKeyboardButton(“✅ Куплено”,  callback_data=f”k:buy:{sid}:{name}”),
InlineKeyboardButton(“📞 Заказано”, callback_data=f”k:ord:{sid}:{name}”),
])
if not has_items:
rows.append([InlineKeyboardButton(“⚠️ Сначала создай заявку”, callback_data=“noop”)])
rows.append([InlineKeyboardButton(”« Назад”, callback_data=“screen:main”)])
return InlineKeyboardMarkup(rows)

def kb_zakazano(d):
rows = []
zakazano = d.get(“zakazano”, [])
if not zakazano:
rows.append([InlineKeyboardButton(“✅ Всё принято!”, callback_data=“noop”)])
else:
by_sec = {}
for item in zakazano:
by_sec.setdefault(item[“section_id”], []).append(item)
for sec in d[“sections”]:
sid = sec[“id”]
if sid not in by_sec:
continue
rows.append([InlineKeyboardButton(f”── {sec[‘emoji’]} {sec[‘name’]} ──”, callback_data=“noop”)])
for item in by_sec[sid]:
name = item[“name”]
comment = item.get(“comment”, “”)
label = f”📦 {name}” + (f” · {comment}” if comment else “”)
rows.append([
InlineKeyboardButton(label, callback_data=“noop”),
InlineKeyboardButton(“✅ Принято”, callback_data=f”d:accept:{sid}:{name}”),
])
rows.append([InlineKeyboardButton(”« Назад”, callback_data=“screen:main”)])
return InlineKeyboardMarkup(rows)

def kb_settings(d):
return InlineKeyboardMarkup([
[InlineKeyboardButton(“➕ Новый раздел”,             callback_data=“cfg:addsec”)],
[InlineKeyboardButton(“🗑 Удалить раздел”,           callback_data=“cfg:delsec”)],
[InlineKeyboardButton(“➕ Добавить товар в шаблон”,  callback_data=“cfg:additem”)],
[InlineKeyboardButton(“🗑 Удалить товар из шаблона”, callback_data=“cfg:delitem”)],
[InlineKeyboardButton(”« Назад”,                     callback_data=“screen:main”)],
])

def text_main():
return f”📦 *Бот закупок*\n_{date.today().strftime(’%d.%m.%Y’)}_\n\nВыбери экран:”

def text_zayavka(d):
total = sum(1 for items in d.get(“zayavka”, {}).values() for i in items if i.get(“checked”))
return f”📋 *Заявка*\n_Отмечено: {total} позиций_\n\nВыбери товары ✅ и нажми 📤 Отправить”

def text_zakupka(d):
statuses = d.get(“zakupka_status”, {})
total = sum(1 for items in d.get(“zayavka”, {}).values() for i in items if i.get(“checked”))
bought = sum(1 for v in statuses.values() if v == “bought”)
ordered = sum(1 for v in statuses.values() if v == “ordered”)
return f”🛒 *Закупка*\n_Всего: {total} · Куплено: {bought} · Заказано: {ordered}_”

def text_zakazano(d):
count = len(d.get(“zakazano”, []))
return f”📞 *Заказано — ждём поставку*\n_Позиций: {count}_”

def text_settings(d):
sec_count = len(d[“sections”])
item_count = sum(len(v) for v in d[“template”].values())
return f”⚙️ *Настройки*\n_Разделов: {sec_count} · Товаров: {item_count}_”

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
d = get_data()
msg = await update.message.reply_text(
text_main(), reply_markup=kb_main(), parse_mode=“Markdown”
)
try:
await ctx.bot.pin_chat_message(update.effective_chat.id, msg.message_id, disable_notification=True)
d[“pinned_msg_id”] = msg.message_id
save(d)
except Exception:
pass

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
q = update.callback_query
await q.answer()
data = q.data
d = get_data()

```
if data == "noop":
    return
if data == "screen:main":
    await q.edit_message_text(text_main(), reply_markup=kb_main(), parse_mode="Markdown")
    return
if data == "screen:zayavka":
    await q.edit_message_text(text_zayavka(d), reply_markup=kb_zayavka(d), parse_mode="Markdown")
    return
if data == "screen:zakupka":
    await q.edit_message_text(text_zakupka(d), reply_markup=kb_zakupka(d), parse_mode="Markdown")
    return
if data == "screen:zakazano":
    await q.edit_message_text(text_zakazano(d), reply_markup=kb_zakazano(d), parse_mode="Markdown")
    return
if data == "screen:settings":
    await q.edit_message_text(text_settings(d), reply_markup=kb_settings(d), parse_mode="Markdown")
    return

if data.startswith("z:toggle:"):
    _, _, sid, name = data.split(":", 3)
    zayavka = d.setdefault("zayavka", {})
    items = zayavka.setdefault(sid, [])
    found = next((i for i in items if i["name"] == name), None)
    if found:
        found["checked"] = not found.get("checked", False)
    else:
        items.append({"name": name, "checked": True})
    save(d)
    await q.edit_message_text(text_zayavka(d), reply_markup=kb_zayavka(d), parse_mode="Markdown")
    return

if data.startswith("z:edit:"):
    _, _, sid, name = data.split(":", 3)
    ctx.user_data["edit"] = {"sid": sid, "name": name}
    await q.message.reply_text(
        f"✏️ Комментарий к *{name}*:\n\nНапиши текст или /skip чтобы убрать · /cancel отмена",
        parse_mode="Markdown"
    )
    return ST_EDIT_COMMENT

if data == "z:additem":
    rows = [[InlineKeyboardButton(f"{s['emoji']} {s['name']}", callback_data=f"z:additem:sec:{s['id']}")] for s in d["sections"]]
    rows.append([InlineKeyboardButton("❌ Отмена", callback_data="screen:zayavka")])
    await q.edit_message_text("➕ В какой раздел добавить?", reply_markup=InlineKeyboardMarkup(rows))
    return

if data.startswith("z:additem:sec:"):
    sid = data.split(":", 3)[3]
    ctx.user_data["zadd"] = {"sid": sid}
    await q.message.reply_text(
        f"➕ Название товара для *{sec_label(d, sid)}*:\n\n/cancel — отмена",
        parse_mode="Markdown"
    )
    return ST_ADD_ZAYAVKA_NAME

if data == "z:send":
    total = sum(1 for items in d.get("zayavka", {}).values() for i in items if i.get("checked"))
    if total == 0:
        await q.answer("⚠️ Ничего не отмечено!", show_alert=True)
        return
    await q.message.reply_text(
        f"✅ *Заявка отправлена!*\n_{total} позиций_\n\nЗакупщик — нажми 🛒 Закупка",
        parse_mode="Markdown"
    )
    return

if data.startswith("k:buy:"):
    _, _, sid, name = data.split(":", 3)
    key = f"{sid}:{name}"
    statuses = d.setdefault("zakupka_status", {})
    if statuses.get(key) == "bought":
        statuses.pop(key)
    else:
        statuses[key] = "bought"
        d["zakazano"] = [z for z in d.get("zakazano", []) if not (z["section_id"] == sid and z["name"] == name)]
    save(d)
    await q.edit_message_text(text_zakupka(d), reply_markup=kb_zakupka(d), parse_mode="Markdown")
    return

if data.startswith("k:ord:"):
    _, _, sid, name = data.split(":", 3)
    key = f"{sid}:{name}"
    statuses = d.setdefault("zakupka_status", {})
    zakazano = d.setdefault("zakazano", [])
    if statuses.get(key) == "ordered":
        statuses.pop(key)
        d["zakazano"] = [z for z in zakazano if not (z["section_id"] == sid and z["name"] == name)]
    else:
        statuses[key] = "ordered"
        if not any(z["section_id"] == sid and z["name"] == name for z in zakazano):
            comment = d.get("comments", {}).get(key, "")
            zakazano.append({"section_id": sid, "name": name, "comment": comment})
    save(d)
    await q.edit_message_text(text_zakupka(d), reply_markup=kb_zakupka(d), parse_mode="Markdown")
    return

if data.startswith("d:accept:"):
    _, _, sid, name = data.split(":", 3)
    d["zakazano"] = [z for z in d.get("zakazano", []) if not (z["section_id"] == sid and z["name"] == name)]
    d.get("zakupka_status", {}).pop(f"{sid}:{name}", None)
    save(d)
    await q.message.reply_text(f"✅ *{name}* принято!", parse_mode="Markdown")
    await q.edit_message_text(text_zakazano(d), reply_markup=kb_zakazano(d), parse_mode="Markdown")
    return

if data == "cfg:addsec":
    ctx.user_data["newsec"] = {}
    await q.message.reply_text("📁 Название нового раздела:\n\n/cancel — отмена")
    return ST_ADD_SECTION_NAME

if data == "cfg:delsec":
    rows = [[InlineKeyboardButton(f"🗑 {s['emoji']} {s['name']}", callback_data=f"cfg:delsec:{s['id']}")] for s in d["sections"]]
    rows.append([InlineKeyboardButton("❌ Отмена", callback_data="screen:settings")])
    await q.edit_message_text("Какой раздел удалить?", reply_markup=InlineKeyboardMarkup(rows))
    return

if data.startswith("cfg:delsec:"):
    sid = data.split(":", 2)[2]
    d["sections"] = [s for s in d["sections"] if s["id"] != sid]
    d["template"].pop(sid, None)
    save(d)
    await q.edit_message_text(text_settings(d), reply_markup=kb_settings(d), parse_mode="Markdown")
    return

if data == "cfg:additem":
    rows = [[InlineKeyboardButton(f"{s['emoji']} {s['name']}", callback_data=f"cfg:additem:sec:{s['id']}")] for s in d["sections"]]
    rows.append([InlineKeyboardButton("❌ Отмена", callback_data="screen:settings")])
    await q.edit_message_text("➕ В какой раздел?", reply_markup=InlineKeyboardMarkup(rows))
    return

if data.startswith("cfg:additem:sec:"):
    sid = data.split(":", 3)[3]
    ctx.user_data["additem"] = {"sid": sid}
    await q.message.reply_text(
        f"➕ Название товара для *{sec_label(d, sid)}*:\n\n/cancel — отмена",
        parse_mode="Markdown"
    )
    return ST_ADD_ITEM_NAME

if data == "cfg:delitem":
    rows = [[InlineKeyboardButton(f"{s['emoji']} {s['name']}", callback_data=f"cfg:delitem:sec:{s['id']}")] for s in d["sections"] if d["template"].get(s["id"])]
    rows.append([InlineKeyboardButton("❌ Отмена", callback_data="screen:settings")])
    await q.edit_message_text("Из какого раздела удалить?", reply_markup=InlineKeyboardMarkup(rows))
    return

if data.startswith("cfg:delitem:sec:"):
    sid = data.split(":", 3)[3]
    items = d["template"].get(sid, [])
    rows = [[InlineKeyboardButton(f"🗑 {name}", callback_data=f"cfg:delitem:item:{sid}:{name}")] for name in items]
    rows.append([InlineKeyboardButton("❌ Отмена", callback_data="screen:settings")])
    await q.edit_message_text("Какой товар удалить?", reply_markup=InlineKeyboardMarkup(rows))
    return

if data.startswith("cfg:delitem:item:"):
    parts = data.split(":", 4)
    sid, name = parts[3], parts[4]
    if name in d["template"].get(sid, []):
        d["template"][sid].remove(name)
    save(d)
    await q.edit_message_text(f"🗑 *{name}* удалён.", reply_markup=kb_settings(d), parse_mode="Markdown")
    return
```

async def edit_comment_receive(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
text = update.message.text.strip()
ed = ctx.user_data.get(“edit”, {})
sid, name = ed.get(“sid”), ed.get(“name”)
if sid and name:
d = get_data()
key = f”{sid}:{name}”
if text == “/skip”:
d[“comments”].pop(key, None)
await update.message.reply_text(“🗑 Комментарий убран.”)
else:
d[“comments”][key] = text
await update.message.reply_text(f”✅ Комментарий сохранён: *{text}*”, parse_mode=“Markdown”)
save(d)
ctx.user_data.pop(“edit”, None)
return ConversationHandler.END

async def cfg_additem_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
name = update.message.text.strip()
if not name:
await update.message.reply_text(“Пустое название, попробуй ещё раз:”)
return ST_ADD_ITEM_NAME
ctx.user_data[“additem”][“name”] = name
await update.message.reply_text(
f”Комментарий / количество для *{name}* (необязательно):\n\n/skip — пропустить”,
parse_mode=“Markdown”
)
return ST_ADD_ITEM_COMMENT

async def cfg_additem_comment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
text = update.message.text.strip()
ai = ctx.user_data.get(“additem”, {})
sid, name = ai.get(“sid”), ai.get(“name”)
d = get_data()
d[“template”].setdefault(sid, [])
if name not in d[“template”][sid]:
d[“template”][sid].append(name)
if text and text != “/skip”:
d[“comments”][f”{sid}:{name}”] = text
save(d)
await update.message.reply_text(
f”✅ *{name}* добавлен в *{sec_label(d, sid)}*!”,
parse_mode=“Markdown”
)
ctx.user_data.pop(“additem”, None)
return ConversationHandler.END

async def z_additem_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
name = update.message.text.strip()
if not name:
await update.message.reply_text(“Пустое название, попробуй ещё раз:”)
return ST_ADD_ZAYAVKA_NAME
ctx.user_data[“zadd”][“name”] = name
await update.message.reply_text(
f”Комментарий к *{name}* (необязательно):\n\n/skip — пропустить”,
parse_mode=“Markdown”
)
return ST_ADD_ZAYAVKA_COMMENT

async def z_additem_comment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
text = update.message.text.strip()
za = ctx.user_data.get(“zadd”, {})
sid, name = za.get(“sid”), za.get(“name”)
d = get_data()
d[“template”].setdefault(sid, [])
if name not in d[“template”][sid]:
d[“template”][sid].append(name)
zayavka = d.setdefault(“zayavka”, {})
items = zayavka.setdefault(sid, [])
if not any(i[“name”] == name for i in items):
items.append({“name”: name, “checked”: True})
if text and text != “/skip”:
d[“comments”][f”{sid}:{name}”] = text
save(d)
await update.message.reply_text(
f”✅ *{name}* добавлен и отмечен в заявке!”,
parse_mode=“Markdown”
)
ctx.user_data.pop(“zadd”, None)
return ConversationHandler.END

async def cfg_addsec_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
name = update.message.text.strip()
if not name:
await update.message.reply_text(“Пустое название, попробуй ещё раз:”)
return ST_ADD_SECTION_NAME
ctx.user_data[“newsec”][“name”] = name
await update.message.reply_text(
f”Эмодзи для раздела *{name}*:\n\nНапример: 🥩 🐟 🧀 🥦\n\n/skip — без эмодзи”,
parse_mode=“Markdown”
)
return ST_ADD_SECTION_EMOJI

async def cfg_addsec_emoji(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
emoji = update.message.text.strip()
ns = ctx.user_data.get(“newsec”, {})
name = ns.get(“name”, “Новый раздел”)
if emoji == “/skip”:
emoji = “📂”
d = get_data()
sec_id = name.lower().replace(” “, “_”)[:20]
existing = {s[“id”] for s in d[“sections”]}
if sec_id in existing:
sec_id += “_2”
d[“sections”].append({“id”: sec_id, “name”: name, “emoji”: emoji})
d[“template”][sec_id] = []
save(d)
await update.message.reply_text(
f”✅ Раздел *{emoji} {name}* создан!\n\nДобавь товары через ⚙️ Настройки → ➕ Добавить товар в шаблон”,
parse_mode=“Markdown”
)
ctx.user_data.pop(“newsec”, None)
return ConversationHandler.END

async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
ctx.user_data.clear()
await update.message.reply_text(“Отменено.”)
return ConversationHandler.END

async def cmd_skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
return ConversationHandler.END

def main():
token = os.environ.get(“BOT_TOKEN”)
if not token:
raise ValueError(“Нужен BOT_TOKEN!”)

```
app = Application.builder().token(token).build()

conv = ConversationHandler(
    entry_points=[
        CommandHandler("start", cmd_start),
        CallbackQueryHandler(button_handler),
    ],
    states={
        ST_EDIT_COMMENT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, edit_comment_receive),
            CommandHandler("skip", edit_comment_receive),
        ],
        ST_ADD_ITEM_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, cfg_additem_name),
        ],
        ST_ADD_ITEM_COMMENT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, cfg_additem_comment),
            CommandHandler("skip", cfg_additem_comment),
        ],
        ST_ADD_ZAYAVKA_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, z_additem_name),
        ],
        ST_ADD_ZAYAVKA_COMMENT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, z_additem_comment),
            CommandHandler("skip", z_additem_comment),
        ],
        ST_ADD_SECTION_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, cfg_addsec_name),
        ],
        ST_ADD_SECTION_EMOJI: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, cfg_addsec_emoji),
            CommandHandler("skip", cfg_addsec_emoji),
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cmd_cancel),
        CommandHandler("start",  cmd_start),
    ],
    per_chat=True,
    per_user=False,
    allow_reentry=True,
)

app.add_handler(conv)
logger.info("Бот запущен!")
app.run_polling(allowed_updates=Update.ALL_TYPES)
```

if **name** == “**main**”:
main()
