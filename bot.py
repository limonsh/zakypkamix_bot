#!/usr/bin/env python3
import json, os, logging
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters, ContextTypes
)

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
DATA_FILE = "data.json"
ST_EDIT_COMMENT, ST_ADD_ITEM_NAME, ST_ADD_ITEM_COMMENT, ST_ADD_ZAYAVKA_NAME, ST_ADD_ZAYAVKA_COMMENT, ST_ADD_SECTION_NAME, ST_ADD_SECTION_EMOJI = range(7)

def default_data():
    return {
        "sections": [
            {"id": "sherif", "name": "Sherif", "emoji": "🏪"},
            {"id": "japan", "name": "Yaponiya", "emoji": "🍜"},
            {"id": "bazar", "name": "Bazar", "emoji": "🛖"},
            {"id": "endis", "name": "Endis", "emoji": "📦"},
        ],
        "template": {
            "sherif": ["Maslo", "Syr", "Moloko"],
            "japan": ["Soevyy sous", "Ris", "Vasabi"],
            "bazar": ["Pomidory", "Zelen", "Ogurcy"],
            "endis": ["Muka", "Sahar", "Maslo rastitelnoe"],
        },
        "zayavka": {},
        "zakupka_status": {},
        "zakazano": [],
        "carry": {},
        "comments": {},
        "last_date": str(date.today()),
        "pinned_msg_id": None,
    }

def load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    d = default_data()
    save(d)
    return d

def save(d):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def get_data():
    d = load()
    today = str(date.today())
    if d["last_date"] != today:
        carry = {}
        statuses = d.get("zakupka_status", {})
        for sec_id, items in d.get("zayavka", {}).items():
            for item in items:
                if not item.get("checked"):
                    continue
                key = sec_id + ":" + item["name"]
                if statuses.get(key) != "bought":
                    carry.setdefault(sec_id, []).append(item["name"])
        d["carry"] = carry
        d["zayavka"] = {}
        d["zakupka_status"] = {}
        d["comments"] = {}
        d["last_date"] = today
        save(d)
    return d

def sec_label(d, sec_id):
    for s in d["sections"]:
        if s["id"] == sec_id:
            return s["emoji"] + " " + s["name"]
    return sec_iddef kb_main():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📋 Zayavka", callback_data="screen:zayavka"),
        InlineKeyboardButton("🛒 Zakupka", callback_data="screen:zakupka"),
    ],[
        InlineKeyboardButton("📞 Zakazano", callback_data="screen:zakazano"),
        InlineKeyboardButton("⚙️ Nastroyki", callback_data="screen:settings"),
    ]])

def kb_zayavka(d):
    rows = []
    zayavka = d.get("zayavka", {})
    comments = d.get("comments", {})
    carry = d.get("carry", {})
    for sec in d["sections"]:
        sid = sec["id"]
        template_items = d["template"].get(sid, [])
        carried = carry.get(sid, [])
        all_names = list(dict.fromkeys(template_items + carried))
        if not all_names:
            continue
        rows.append([InlineKeyboardButton("-- " + sec["emoji"] + " " + sec["name"] + " --", callback_data="noop")])
        sec_items = {item["name"]: item for item in zayavka.get(sid, [])}
        for name in all_names:
            checked = sec_items.get(name, {}).get("checked", False)
            icon = "✅" if checked else "⬜"
            carry_tag = " 🔁" if name in carried and name not in template_items else ""
            comment = comments.get(sid + ":" + name, "")
            comment_tag = " | " + comment if comment else ""
            rows.append([
                InlineKeyboardButton(icon + " " + name + carry_tag + comment_tag, callback_data="z:toggle:" + sid + ":" + name),
                InlineKeyboardButton("✏️", callback_data="z:edit:" + sid + ":" + name),
            ])
    rows.append([InlineKeyboardButton("➕ Dobavit tovar", callback_data="z:additem")])
    rows.append([InlineKeyboardButton("📤 Otpravit zayavku", callback_data="z:send")])
    rows.append([InlineKeyboardButton("« Nazad", callback_data="screen:main")])
    return InlineKeyboardMarkup(rows)

def kb_zakupka(d):
    rows = []
    zayavka = d.get("zayavka", {})
    statuses = d.get("zakupka_status", {})
    comments = d.get("comments", {})
    has_items = False
    for sec in d["sections"]:
        sid = sec["id"]
        checked_items = [i for i in zayavka.get(sid, []) if i.get("checked")]
        if not checked_items:
            continue
        has_items = True
        rows.append([InlineKeyboardButton("-- " + sec["emoji"] + " " + sec["name"] + " --", callback_data="noop")])
        for item in checked_items:
            name = item["name"]
            key = sid + ":" + name
            st = statuses.get(key)
            comment = comments.get(key, "")
            comment_tag = " | " + comment if comment else ""
            icon = "✅" if st == "bought" else ("📞" if st == "ordered" else "⬜")
            rows.append([InlineKeyboardButton(icon + " " + name + comment_tag, callback_data="noop")])
            rows.append([
                InlineKeyboardButton("✅ Kupleno", callback_data="k:buy:" + sid + ":" + name),
                InlineKeyboardButton("📞 Zakazano", callback_data="k:ord:" + sid + ":" + name),
            ])
    if not has_items:
        rows.append([InlineKeyboardButton("⚠️ Snachala sozdaj zayavku", callback_data="noop")])
    rows.append([InlineKeyboardButton("« Nazad", callback_data="screen:main")])
    return InlineKeyboardMarkup(rows)

def kb_zakazano(d):
    rows = []
    zakazano = d.get("zakazano", [])
    if not zakazano:
        rows.append([InlineKeyboardButton("✅ Vse prinyato!", callback_data="noop")])
    else:
        by_sec = {}
        for item in zakazano:
            by_sec.setdefault(item["section_id"], []).append(item)
        for sec in d["sections"]:
            sid = sec["id"]
            if sid not in by_sec:
                continue
            rows.append([InlineKeyboardButton("-- " + sec["emoji"] + " " + sec["name"] + " --", callback_data="noop")])
            for item in by_sec[sid]:
                name = item["name"]
                comment = item.get("comment", "")
                label = "📦 " + name + (" | " + comment if comment else "")
                rows.append([
                    InlineKeyboardButton(label, callback_data="noop"),
                    InlineKeyboardButton("✅ Prinyato", callback_data="d:accept:" + sid + ":" + name),
                ])
    rows.append([InlineKeyboardButton("« Nazad", callback_data="screen:main")])
    return InlineKeyboardMarkup(rows)

def kb_settings(d):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Novyj razdel", callback_data="cfg:addsec")],
        [InlineKeyboardButton("🗑 Udalit razdel", callback_data="cfg:delsec")],
        [InlineKeyboardButton("➕ Dobavit tovar v shablon", callback_data="cfg:additem")],
        [InlineKeyboardButton("🗑 Udalit tovar iz shablona", callback_data="cfg:delitem")],
        [InlineKeyboardButton("« Nazad", callback_data="screen:main")],
    ])

def text_main():
    return "📦 Bot zakupok\n" + date.today().strftime("%d.%m.%Y") + "\n\nVyberi ekran:"

def text_zayavka(d):
    total = sum(1 for items in d.get("zayavka", {}).values() for i in items if i.get("checked"))
    return "📋 Zayavka\nOtmecheno: " + str(total) + "\n\nVyberi tovary i nazhmi Otpravit"

def text_zakupka(d):
    statuses = d.get("zakupka_status", {})
    total = sum(1 for items in d.get("zayavka", {}).values() for i in items if i.get("checked"))
    bought = sum(1 for v in statuses.values() if v == "bought")
    ordered = sum(1 for v in statuses.values() if v == "ordered")
    return "🛒 Zakupka\nVsego: " + str(total) + " Kupleno: " + str(bought) + " Zakazano: " + str(ordered)

def text_zakazano(d):
    count = len(d.get("zakazano", []))
    return "📞 Zakazano\nPozicij: " + str(count)

def text_settings(d):
    sec_count = len(d["sections"])
    item_count = sum(len(v) for v in d["template"].values())
    return "⚙️ Nastrojki\nRazdelov: " + str(sec_count) + " Tovarov: " + str(async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    d = get_data()
    msg = await update.message.reply_text(text_main(), reply_markup=kb_main())
    try:
        await ctx.bot.pin_chat_message(update.effective_chat.id, msg.message_id, disable_notification=True)
        d["pinned_msg_id"] = msg.message_id
        save(d)
    except Exception:
        pass

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    d = get_data()
    if data == "noop":
        return
    if data == "screen:main":
        await q.edit_message_text(text_main(), reply_markup=kb_main())
        return
    if data == "screen:zayavka":
        await q.edit_message_text(text_zayavka(d), reply_markup=kb_zayavka(d))
        return
    if data == "screen:zakupka":
        await q.edit_message_text(text_zakupka(d), reply_markup=kb_zakupka(d))
        return
    if data == "screen:zakazano":
        await q.edit_message_text(text_zakazano(d), reply_markup=kb_zakazano(d))
        return
    if data == "screen:settings":
        await q.edit_message_text(text_settings(d), reply_markup=kb_settings(d))
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
        await q.edit_message_text(text_zayavka(d), reply_markup=kb_zayavka(d))
        return
    if data.startswith("z:edit:"):
        _, _, sid, name = data.split(":", 3)
        ctx.user_data["edit"] = {"sid": sid, "name": name}
        await q.message.reply_text("✏️ Kommentarij k " + name + ":\n\nNapishi tekst ili /skip")
        return ST_EDIT_COMMENT
    if data == "z:additem":
        rows = [[InlineKeyboardButton(s["emoji"] + " " + s["name"], callback_data="z:additem:sec:" + s["id"])] for s in d["sections"]]
        rows.append([InlineKeyboardButton("❌ Otmena", callback_data="screen:zayavka")])
        await q.edit_message_text("➕ V kakoj razdel?", reply_markup=InlineKeyboardMarkup(rows))
        return
    if data.startswith("z:additem:sec:"):
        sid = data.split(":", 3)[3]
        ctx.user_data["zadd"] = {"sid": sid}
        await q.message.reply_text("➕ Nazvanie tovara:\n\n/cancel - otmena")
        return ST_ADD_ZAYAVKA_NAME
    if data == "z:send":
        total = sum(1 for items in d.get("zayavka", {}).values() for i in items if i.get("checked"))
        if total == 0:
            await q.answer("Nichego ne otmecheno!", show_alert=True)
            return
        await q.message.reply_text("✅ Zayavka otpravlena! " + str(total) + " pozicij")
        return
    if data.startswith("k:buy:"):
        _, _, sid, name = data.split(":", 3)
        key = sid + ":" + name
        statuses = d.setdefault("zakupka_status", {})
        if statuses.get(key) == "bought":
            statuses.pop(key)
        else:
            statuses[key] = "bought"
            d["zakazano"] = [z for z in d.get("zakazano", []) if not (z["section_id"] == sid and z["name"] == name)]
        save(d)
        await q.edit_message_text(text_zakupka(d), reply_markup=kb_zakupka(d))
        return
    if data.startswith("k:ord:"):
        _, _, sid, name = data.split(":", 3)
        key = sid + ":" + name
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
        await q.edit_message_text(text_zakupka(d), reply_markup=kb_zakupka(d))
        return
    if data.startswith("d:accept:"):
        _, _, sid, name = data.split(":", 3)
        d["zakazano"] = [z for z in d.get("zakazano", []) if not (z["section_id"] == sid and z["name"] == name)]
        d.get("zakupka_status", {}).pop(sid + ":" + name, None)
        save(d)
        await q.message.reply_text("✅ " + name + " prinyato!")
        await q.edit_message_text(text_zakazano(d), reply_markup=kb_zakazano(d))
        return
    if data == "cfg:addsec":
        ctx.user_data["newsec"] = {}
        await q.message.reply_text("📁 Nazvanie novogo razdela:\n\n/cancel - otmena")
        return ST_ADD_SECTION_NAME
    if data == "cfg:delsec":
        rows = [[InlineKeyboardButton("🗑 " + s["emoji"] + " " + s["name"], callback_data="cfg:delsec:" + s["id"])] for s in d["sections"]]
        rows.append([InlineKeyboardButton("❌ Otmena", callback_data="screen:settings")])
        await q.edit_message_text("Kakoj razdel udalit?", reply_markup=InlineKeyboardMarkup(rows))
        return
    if data.startswith("cfg:delsec:"):
        sid = data.split(":", 2)[2]
        d["sections"] = [s for s in d["sections"] if s["id"] != sid]
        d["template"].pop(sid, None)
        save(d)
        await q.edit_message_text(text_settings(d), reply_markup=kb_settings(d))
        return
    if data == "cfg:additem":
        rows = [[InlineKeyboardButton(s["emoji"] + " " + s["name"], callback_data="cfg:additem:sec:" + s["id"])] for s in d["sections"]]
        rows.append([InlineKeyboardButton("❌ Otmena", callback_data="screen:settings")])
        await q.edit_message_text("➕ V kakoj razdel?", reply_markup=InlineKeyboardMarkup(rows))
        return
    if data.startswith("cfg:additem:sec:"):
        sid = data.split(":", 3)[3]
        ctx.user_data["additem"] = {"sid": sid}
        await q.message.reply_text("➕ Nazvanie tovara:\n\n/cancel - otmena")
        return ST_ADD_ITEM_NAME
    if data == "cfg:delitem":
        rows = [[InlineKeyboardButton(s["emoji"] + " " + s["name"], callback_data="cfg:delitem:sec:" + s["id"])] for s in d["sections"] if d["template"].get(s["id"])]
        rows.append([InlineKeyboardButton("❌ Otmena", callback_data="screen:settings")])
        await q.edit_message_text("Iz kakogo razdela udalit?", reply_markup=InlineKeyboardMarkup(rows))
        return
    if data.startswith("cfg:delitem:sec:"):
        sid = data.split(":", 3)[3]
        items = d["template"].get(sid, [])
        rows = [[InlineKeyboardButton("🗑 " + name, callback_data="cfg:delitem:item:" + sid + ":" + name)] for name in items]
        rows.append([InlineKeyboardButton("❌ Otmena", callback_data="screen:settings")])
        await q.edit_message_text("Kakoj tovar udalit?", reply_markup=InlineKeyboardMarkup(rows))
        return
    if data.startswith("cfg:delitem:item:"):
        parts = data.split(":", 4)
        sid, name = parts[3], parts[4]
        if name in d["template"].get(sid, []):
            d["template"][sid].remove(name)
        save(d)
        await q.edit_message_text(name + " udalen.", reply_markup=kb_settings(d))
        return
      async def edit_comment_receive(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    ed = ctx.user_data.get("edit", {})
    sid, name = ed.get("sid"), ed.get("name")
    if sid and name:
        d = get_data()
        key = sid + ":" + name
        if text == "/skip":
            d["comments"].pop(key, None)
            await update.message.reply_text("Kommentarij ubran.")
        else:
            d["comments"][key] = text
            await update.message.reply_text("✅ Sohraneno: " + text)
        save(d)
    ctx.user_data.pop("edit", None)
    return ConversationHandler.END

async def cfg_additem_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Pustoe nazvanie, poprobuj eshche raz:")
        return ST_ADD_ITEM_NAME
    ctx.user_data["additem"]["name"] = name
    await update.message.reply_text("Kommentarij (neobyazatelno):\n\n/skip - propustit")
    return ST_ADD_ITEM_COMMENT

async def cfg_additem_comment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    ai = ctx.user_data.get("additem", {})
    sid, name = ai.get("sid"), ai.get("name")
    d = get_data()
    d["template"].setdefault(sid, [])
    if name not in d["template"][sid]:
        d["template"][sid].append(name)
    if text and text != "/skip":
        d["comments"][sid + ":" + name] = text
    save(d)
    await update.message.reply_text("✅ " + name + " dobavlen!")
    ctx.user_data.pop("additem", None)
    return ConversationHandler.END

async def z_additem_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Pustoe nazvanie, poprobuj eshche raz:")
        return ST_ADD_ZAYAVKA_NAME
    ctx.user_data["zadd"]["name"] = name
    await update.message.reply_text("Kommentarij (neobyazatelno):\n\n/skip - propustit")
    return ST_ADD_ZAYAVKA_COMMENT

async def z_additem_comment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    za = ctx.user_data.get("zadd", {})
    sid, name = za.get("sid"), za.get("name")
    d = get_data()
    d["template"].setdefault(sid, [])
    if name not in d["template"][sid]:
        d["template"][sid].append(name)
    zayavka = d.setdefault("zayavka", {})
    items = zayavka.setdefault(sid, [])
    if not any(i["name"] == name for i in items):
        items.append({"name": name, "checked": True})
    if text and text != "/skip":
        d["comments"][sid + ":" + name] = text
    save(d)
    await update.message.reply_text("✅ " + name + " dobavlen i otmechen!")
    ctx.user_data.pop("zadd", None)
    return ConversationHandler.END

async def cfg_addsec_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Pustoe nazvanie, poprobuj eshche raz:")
        return ST_ADD_SECTION_NAME
    ctx.user_data["newsec"]["name"] = name
    await update.message.reply_text("Emoji dlya razdela " + name + ":\n\nNaprimer: 🥩 🐟\n\n/skip - bez emoji")
    return ST_ADD_SECTION_EMOJI

async def cfg_addsec_emoji(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    emoji = update.message.text.strip()
    ns = ctx.user_data.get("newsec", {})
    name = ns.get("name", "Novyj razdel")
    if emoji == "/skip":
        emoji = "📂"
    d = get_data()
    sec_id = name.lower().replace(" ", "_")[:20]
    existing = {s["id"] for s in d["sections"]}
    if sec_id in existing:
        sec_id += "_2"
    d["sections"].append({"id": sec_id, "name": name, "emoji": emoji})
    d["template"][sec_id] = []
    save(d)
    await update.message.reply_text("✅ Razdel " + emoji + " " + name + " sozdan!")
    ctx.user_data.pop("newsec", None)
    return ConversationHandler.END

async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("Otmeneno.")
    return ConversationHandler.END

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("Nuzhen BOT_TOKEN!")
    app = Application.builder().token(token).build()
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", cmd_start),
            CallbackQueryHandler(button_handler),
        ],
        states={
            ST_EDIT_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_comment_receive), CommandHandler("skip", edit_comment_receive)],
            ST_ADD_ITEM_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, cfg_additem_name)],
            ST_ADD_ITEM_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, cfg_additem_comment), CommandHandler("skip", cfg_additem_comment)],
            ST_ADD_ZAYAVKA_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, z_additem_name)],
            ST_ADD_ZAYAVKA_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, z_additem_comment), CommandHandler("skip", z_additem_comment)],
            ST_ADD_SECTION_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, cfg_addsec_name)],
            ST_ADD_SECTION_EMOJI: [MessageHandler(filters.TEXT & ~filters.COMMAND, cfg_addsec_emoji), CommandHandler("skip", cfg_addsec_emoji)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel), CommandHandler("start", cmd_start)],
        per_chat=True,
        per_user=False,
        allow_reentry=True,
    )
    app.add_handler(conv)
    logger.info("Bot zapushhen!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()


  

