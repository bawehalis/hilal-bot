import os
import logging
import asyncio
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from hijri import (
    check_hilal, miladi_to_hicri, hicri_to_miladi,
    ramazan_basi, sevval_basi, ay_adi, get_sf,
    prev_conjunction, DEFAULT_CRITERION
)
from criteria import CRITERIA, get_criterion
from locations import add_location, remove_location, list_locations
from country_data import (
    get_countries, get_country_name, get_ramazan, get_bayram, get_all_years
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise EnvironmentError("TOKEN env var missing")

_criterion = DEFAULT_CRITERION
_ready     = False


def fark(bot, ref):
    if ref is None:
        return "?"
    d = (bot - ref).days
    return ("+" if d >= 0 else "") + str(d)


def uzlasma(bot, refs):
    ayni = sum(1 for r in refs if r == bot)
    return ayni, len(refs)


def gun_flag(n):
    if n == 29: return "29"
    if n == 30: return "30"
    return str(n) + "(!)"


HELP_TEXT = (
    "HICRI TAKVIM BOTU\n\n"
    "/bugun                           Bugunun Hicri tarihi\n"
    "/hilal                           Bugun hilal durumu\n"
    "/karsilastir 2025                Yil bazli karsilastirma\n"
    "/analiz                          1995-2025 analizi\n"
    "/kriter [odeh|yallop|iranian]    Kriter sec\n"
    "/konum ekle <isim> <lat> <lon>   Konum ekle\n"
    "/konum sil <isim>                Konum sil\n"
    "/konum listele                   Konumlari goster\n"
    "/yardim                          Bu menu\n"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)


async def yardim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)


async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _ready:
        return await update.message.reply_text("Sistem hazirlanıyor, bekleyin...")
    today = datetime.now(timezone.utc).date()
    loop  = asyncio.get_event_loop()
    gun, hay, hyil = await loop.run_in_executor(
        None, miladi_to_hicri, today, _criterion
    )
    await update.message.reply_text(
        "Bugun  : " + str(today) + "\n"
        "Hicri  : " + str(gun) + " " + ay_adi(hay) + " " + str(hyil) + "\n"
        "Kriter : " + _criterion
    )


async def hilal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc).date()
    nm    = prev_conjunction(today)
    if nm is None:
        return await update.message.reply_text("Konjunksiyon bulunamadi.")
    await update.message.reply_text("Hilal hesaplaniyor...")
    loop  = asyncio.get_event_loop()
    gorunur, best_q, best_loc, detaylar = await loop.run_in_executor(
        None, check_hilal, today, nm, _criterion
    )
    crit = get_criterion(_criterion)
    durum = crit.description(best_q) if hasattr(crit, "description") else ("Gorunur" if gorunur else "Gorunmez")
    lines = [
        "Hilal Durumu - " + str(today) + "\n",
        "Kriter  : " + _criterion,
        "En iyi  : " + best_loc,
        "Skor    : " + str(round(best_q, 3)),
        "Durum   : " + durum,
        "\nKonum Detaylari:",
    ]
    for loc_name, p in detaylar.items():
        if p["alt"] > 0:
            lines.append(
                loc_name + ": alt=" + str(round(p["alt"], 1)) +
                " elong=" + str(round(p["elong"], 1)) +
                " q=" + str(round(p["q"], 3))
            )
    await update.message.reply_text("\n".join(lines))


async def kriter_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _criterion
    if not context.args:
        secenekler = ", ".join(CRITERIA.keys())
        return await update.message.reply_text(
            "Mevcut kriter: " + _criterion + "\n"
            "Secenekler: " + secenekler + "\n"
            "Kullanim: /kriter odeh"
        )
    yeni = context.args[0].lower()
    if yeni not in CRITERIA:
        return await update.message.reply_text("Gecersiz kriter. Secenekler: " + ", ".join(CRITERIA.keys()))
    _criterion = yeni
    await update.message.reply_text("Kriter degistirildi: " + _criterion)


async def konum_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text(
            "Kullanim:\n"
            "/konum ekle <isim> <lat> <lon>\n"
            "/konum sil <isim>\n"
            "/konum listele"
        )
    alt = context.args[0].lower()
    if alt == "listele":
        await update.message.reply_text(list_locations())
    elif alt == "ekle":
        if len(context.args) < 4:
            return await update.message.reply_text("Kullanim: /konum ekle <isim> <lat> <lon>")
        try:
            isim = context.args[1]
            lat  = float(context.args[2])
            lon  = float(context.args[3])
            add_location(isim, lat, lon)
            await update.message.reply_text(isim + " eklendi.")
        except Exception as e:
            await update.message.reply_text("Hata: " + str(e))
    elif alt == "sil":
        if len(context.args) < 2:
            return await update.message.reply_text("Kullanim: /konum sil <isim>")
        try:
            remove_location(context.args[1])
            await update.message.reply_text(context.args[1] + " silindi.")
        except Exception as e:
            await update.message.reply_text("Hata: " + str(e))
    else:
        await update.message.reply_text("Bilinmeyen alt komut.")


async def karsilastir_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _ready:
        return await update.message.reply_text("Sistem hazirlanıyor, bekleyin...")
    try:
        yil = int(context.args[0]) if context.args else datetime.now().year
    except ValueError:
        return await update.message.reply_text("Ornek: /karsilastir 2025")

    loop  = asyncio.get_event_loop()
    bot_r = await loop.run_in_executor(None, ramazan_basi, yil, _criterion)
    bot_b = await loop.run_in_executor(None, sevval_basi,  yil, _criterion)

    if not bot_r or not bot_b:
        return await update.message.reply_text("Hesaplanamadi.")

    bot_gun = (bot_b - bot_r).days
    countries = get_countries()

    lines = [str(yil) + " Karsilastirma\n", "--- RAMAZAN BASLANGICI ---", "Bot : " + str(bot_r)]
    r_refs = []
    for c in countries:
        ref = get_ramazan(c, yil)
        r_refs.append(ref)
        lines.append(get_country_name(c) + " : " + str(ref) + "  " + fark(bot_r, ref))
    r_ayni, r_top = uzlasma(bot_r, r_refs)
    lines.append("Uzlasma: " + str(r_ayni) + "/" + str(r_top))

    lines.append("\n--- RAMAZAN BITISI (1 Sevval) ---")
    lines.append("Bot : " + str(bot_b))
    b_refs = []
    for c in countries:
        ref = get_bayram(c, yil)
        b_refs.append(ref)
        lines.append(get_country_name(c) + " : " + str(ref) + "  " + fark(bot_b, ref))
    b_ayni, b_top = uzlasma(bot_b, b_refs)
    lines.append("Uzlasma: " + str(b_ayni) + "/" + str(b_top))

    lines.append("\n--- GUN SAYISI ---")
    lines.append("Bot : " + gun_flag(bot_gun))
    for c in countries:
        tr = get_ramazan(c, yil)
        tb = get_bayram(c, yil)
        if tr and tb:
            lines.append(get_country_name(c) + " : " + gun_flag((tb - tr).days))

    if r_ayni >= 2 and b_ayni >= 2:
        lines.append("\nSonuc: Bot dogru.")
    elif r_ayni >= 2 or b_ayni >= 2:
        lines.append("\nSonuc: Kismen eslesiyor, kontrol et.")
    else:
        lines.append("\nSonuc: Bot kontrol edilmeli.")

    await update.message.reply_text("\n".join(lines))


async def analiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _ready:
        return await update.message.reply_text("Sistem hazirlanıyor, bekleyin...")
    await update.message.reply_text("Analiz yapiliyor...")

    years     = get_all_years()
    countries = get_countries()
    loop      = asyncio.get_event_loop()

    lines = [
        "RAMAZAN ANALIZI — " + str(years[0]) + "-" + str(years[-1]) + "\n",
        "Kriter: " + _criterion + "\n",
        "-" * 55,
    ]

    bot_ok = bot_sapma = 0
    country_sapma = {c: 0 for c in countries}
    total = 0

    for yil in years:
        bot_r = await loop.run_in_executor(None, ramazan_basi, yil, _criterion)
        bot_b = await loop.run_in_executor(None, sevval_basi,  yil, _criterion)
        if not bot_r or not bot_b:
            continue

        bot_gun = (bot_b - bot_r).days
        r_refs  = [get_ramazan(c, yil) for c in countries]
        b_refs  = [get_bayram(c,  yil) for c in countries]

        r_ayni, r_top = uzlasma(bot_r, r_refs)
        b_ayni, b_top = uzlasma(bot_b, b_refs)

        r_str = "|".join(fark(bot_r, r) for r in r_refs)
        b_str = "|".join(fark(bot_b, b) for b in b_refs)

        if r_ayni >= 2 and b_ayni >= 2:
            durum = "OK"
            bot_ok += 1
            for i, c in enumerate(countries):
                if r_refs[i] and r_refs[i] != bot_r:
                    country_sapma[c] += 1
        elif r_ayni == r_top and b_ayni == b_top:
            durum = "OK"
            bot_ok += 1
        else:
            durum = "KONTROL"
            bot_sapma += 1

        total += 1
        lines.append(
            str(yil) + " RAM[" + r_str + "] BAY[" + b_str + "] " +
            "GUN:" + gun_flag(bot_gun) + " " + durum
        )

    lines.append("\nOzet:")
    lines.append("Bot dogru   : " + str(bot_ok) + "/" + str(total) +
                 " (%" + str(round(bot_ok / total * 100, 1)) + ")")
    lines.append("Bot kontrol : " + str(bot_sapma) + "/" + str(total))
    for c in countries:
        lines.append(get_country_name(c) + " sapma : " + str(country_sapma[c]))

    msg = "\n".join(lines)
    for chunk in [msg[i:i+4000] for i in range(0, len(msg), 4000)]:
        await update.message.reply_text(chunk)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Hata: %s", context.error, exc_info=True)
    if isinstance(update, Update) and update.message:
        await update.message.reply_text("Beklenmeyen hata. /yardim yazin.")


async def bilinmeyen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bilinmeyen komut. /yardim yazin.")


async def warm_up(app):
    global _ready
    logger.info("Sistem baslatiliyor...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, get_sf)
    _ready = True
    logger.info("Sistem hazir.")


def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",       start))
    app.add_handler(CommandHandler("yardim",      yardim))
    app.add_handler(CommandHandler("bugun",       bugun))
    app.add_handler(CommandHandler("hilal",       hilal_cmd))
    app.add_handler(CommandHandler("kriter",      kriter_cmd))
    app.add_handler(CommandHandler("konum",       konum_cmd))
    app.add_handler(CommandHandler("karsilastir", karsilastir_cmd))
    app.add_handler(CommandHandler("analiz",      analiz_cmd))
    app.add_handler(MessageHandler(filters.COMMAND, bilinmeyen))
    app.add_error_handler(error_handler)
    app.post_init = warm_up
    logger.info("Bot baslatildi.")
    app.run_polling()


if __name__ == "__main__":
    main()
