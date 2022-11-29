from telegram.ext import CallbackContext, Updater, JobQueue, CommandHandler, Filters, MessageHandler
from telegram import ParseMode, InputMediaPhoto, Update
from redis import Redis
from os import environ
import requests
from bs4 import BeautifulSoup
import logging

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


CHECK_INTERVAL: int = 15 * 60  # 15 min
CHAT_ID = None
SS_GE_URL = (
    "https://ss.ge/en/real-estate/l/Flat/For-Rent"
    "?Sort.SortExpression=%22OrderDate%22%20DESC"
    "&RealEstateTypeId=5"
    "&RealEstateDealTypeId=1"
    "&MunicipalityId=95"
    "&CityIdList=95"
    "&subdistr=47,31,20,21,22,23,51,52"
    "&PrcSource=2"
    "&CommercialRealEstateType="
    "&QuantityFrom=50"
    "&PriceType=false"
    "&CurrencyId=2"
    "&PriceTo=1200"
    "&Context.Request.Query[Query]="
    "&WithImageOnly=true"
    "&BedroomsFrom=2"
    "&AdditionalInformation=Heating,Internet,Furniture,Hot%20water,Washing%20machine"
)
REDIS_PREFIX = "ssgebot:"

def escape(s: str) -> str:
    special = "\\_*[]()~`>#+-=|{}.!"
    result = s
    for c in special:
        result = result.replace(c, "\\" + c)
    return result


def run_search(job_queue: JobQueue):
    job_queue.run_once(fetch_and_send, 0, name="fetch")


def fetch_and_send(ctx: CallbackContext):
    ctx.job_queue.run_once(fetch_and_send, CHECK_INTERVAL, name="fetch")
    if CHAT_ID is None:
        return

    with requests.Session() as s:
        resp = s.get(SS_GE_URL)

    soup = BeautifulSoup(resp.text, "html.parser")
    r = Redis()

    for listing in list(soup.find_all(class_="latest_article_each_in"))[:1]:
        listing = listing.find_all(class_="DesktopArticleLayout")[0]

        link = listing.div.a["href"]
        id = link.split("-")[-1]
        if r.exists(REDIS_PREFIX + id):
            continue

        images = []
        for img in listing.find_all("img"):
            try:
                images.append(InputMediaPhoto(img["data-src"].replace("_Thumb", "")))
            except:
                pass

        title = listing.find_all(class_="TiTleSpanList")[0].contents[0].strip()
        street = listing.find_all(class_="StreeTaddressList")[0].a.contents[0].strip()
        area = listing.find_all(class_="latest_flat_km")[0].contents[0].strip().replace(" ", "").replace("\r", "").replace("\n", "")
        type = listing.find_all(class_="latest_flat_type")[0].contents[0].strip()
        floor = listing.find_all(class_="latest_stair_count")[0].contents[0].strip().replace(" ", "").replace("\r", "").replace("\n", "")
        time = listing.find_all(class_="add_time")[0].contents[0].strip()
        price = listing.find_all(class_="latest_price")[1].contents[0].strip().replace(' ', '')
        maps_link = f"https://yandex.com.ge/maps/10277/tbilisi/search/{street}/?ll=44.812381%2C41.710399&z=13"
        ssge_link = f"https://ss.ge{link}"

        message = f"""{escape(title)}\n`{escape(time)}`\n${escape(price)} {escape(area)} {escape(type)} {escape(floor)}\n{escape(street)}\n"""
        links = f"""[maps]({escape(maps_link)}) / [ssge]({escape(ssge_link)})"""

        images[0].caption = message + links
        images[0].parse_mode = ParseMode.MARKDOWN_V2
        print(images)

        ctx.bot.send_media_group(
            CHAT_ID,  # CHAD_IT
            media=images,
        )

        r.set(REDIS_PREFIX + id, 1)


def add_link(update: Update, ctx: CallbackContext):
    global CHAT_ID
    if CHAT_ID is not None:
        return
    CHAT_ID = update.effective_chat.id
    print(f"setting chat id = {CHAT_ID}")
    ctx.job_queue.run_once(fetch_and_send, 0, name="fetch")


def start_bot():
    updater = Updater(environ.get("TOKEN"))
    dispatcher = updater.dispatcher

    dispatcher.add_handler(MessageHandler(Filters.command, add_link))

    run_search(dispatcher.job_queue)

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    start_bot()
