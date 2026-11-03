import io
import os
import re
import html
import json
import math
import asyncio
from typing import Callable, Dict, Any, Awaitable
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.types import (
    Message,
    TelegramObject,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    BufferedInputFile,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandStart

BOT_TOKEN = "8706677874:AAFslqcEmnyry5u6ZHmMBLYHe_kfAAOInp4"
TARGET_TELEGRAM_GROUP_ID = -1003826229666

# Список ID администраторов и целевой группы
ADMIN_IDS = [
    294001568,
    210925919,
    860289743,
    -1003826229666,
]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Middleware: блокирует работу в группах и не пускает не-администраторов
class AdminPrivateOnlyMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = data.get("event_from_user")
        chat = data.get("event_chat")

        # В группах/супергруппах бот полностью игнорирует входящие сообщения участников
        if chat and chat.type in ["group", "supergroup"]:
            return

        # В личке проверяем права администратора
        if not user or user.id not in ADMIN_IDS:
            if isinstance(event, Message):
                await event.answer("⛔ У вас нет доступа к этому боту.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ У вас нет доступа к этому боту.", show_alert=True)
            return

        return await handler(event, data)

dp.message.outer_middleware(AdminPrivateOnlyMiddleware())
dp.callback_query.outer_middleware(AdminPrivateOnlyMiddleware())

TEMPLATES_FILE = "templates.json"

DEFAULT_TEMPLATES = {
    "1": (
        "Начинаем день активно, в темпе и с хорошим настроем! Сегодня наша задача - максимально поднять показатели и показать, на что мы способны. 😊\n\n"
        "Особое внимание уделяем конверсии и рабочему времени - держим показатели на высоте и не теряем ни одной возможности! 💻\n\n"
        "Утро - самая лучшая возможность задать хороший старт на всю смену. Помним, что до обеденного времени не берем перерывы и обеды 🏋️\n\n"
        "Вы можете, вы лучшие 🤩\n\n"
        "Реакции 🌹"
    ),
    "2": (
        "Ребята, нужно поднажать, как мы умеем! Каждый дозвоненный клиент - наше золото, и наша задача забрать из него максимум: сохранить качество разговора и довести до успешного результата 📞\n\n"
        "Зеленой зоны много - вы лучшие. Уже показываете, как нужно работать и держать результат ❤️\n\n"
        "А те, кто пока ниже - я знаю, что ваше место тоже там. Отбрасываем сомнения, поднажимаем и подтягиваемся к своим коллегам 🏋️\n\n"
        "Следим за категориями, стремимся не падать ниже 1-2, чтобы не сталкиваться с долгим поиском 🙈\n\n"
        "Особое внимание сейчас на конверсию, пока проседаем, но еще есть время все исправить. Так что показываем результат лучших и забираем всё золото, которое есть 🤩\n\n"
        "Не переживаем из-за поиска и таймера, мы видим технические проблемы и фиксики стараются максимально оперативно их подсвечивать и решать 😊\n\n"
        "Дайте реакцию 🏳️"
    ),
    "3": (
        "Звонков в обеденное время не так много, так что сейчас наша ключевая задача работать на качество каждого звонка и повышать конверсию, а так же следить за рабочим временем 👍\n\n"
        "Поэтому сохраняем и удерживаем каждого клиента - дабы забрать все, что можем - золото и его душу 📞\n\n"
        "Зеленой зоны много - Лучшие ❤️\n\n"
        "Ребята которые ниже - знаю, что ваше место там же - пора поднажать и подходить к коллегам ❤️‍🩹\n\n"
        "Дайте реакцию 😆"
    ),
    "4": (
        "Ребята, собираемся и усиливаем показатели! 🏋️\n\n"
        "Особенно делаем упор на продуктивное рабочее время и продолжаем держать конверсию. Наращиваем темп и забираем максимум из каждого звонка! 🚗\n\n"
        "Вечером особенно важно не просесть - держим темп до самого конца. Старайтесь максимально дольше оставаться в линии и использовать рабочее время эффективно 💻\n\n"
        "Показываем, на что способны! 🤩\n\n"
        "Реакции 🌹"
    ),
    "5": (
        "Последний рывок вверх, дорабатываем часы и поднимаем конверсию"
    ),
    "6": (
        "Результаты за сегодня"
    ),
}

def load_templates():
    if os.path.exists(TEMPLATES_FILE):
        try:
            with open(TEMPLATES_FILE, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
                return {**DEFAULT_TEMPLATES, **data}
        except Exception:
            pass
    return DEFAULT_TEMPLATES.copy()

def save_templates(templates):
    with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Срез для группы"), KeyboardButton(text="Срез для админки")],
        [KeyboardButton(text="Срез для наставников"), KeyboardButton(text="Анализ группы")],
        [KeyboardButton(text="Сравнительный по ГП"), KeyboardButton(text="Сравнительный по ГП неделя")],
        [KeyboardButton(text="Отчет в группу неделя"), KeyboardButton(text="Загрузить базу тегов")],
        [KeyboardButton(text="⚙️ Редактировать шаблоны")]
    ],
    resize_keyboard=True,
)

class ReportFSM(StatesGroup):
    waiting_for_file = State()
    waiting_for_group_number = State()
    waiting_for_staff_numbers = State()
    waiting_for_gp_average = State()
    waiting_for_tags_file = State()
    waiting_for_template_text = State()
    waiting_for_mentor_mappings = State()
    waiting_for_mentor_file_before = State()
    waiting_for_mentor_file_after = State()

user_sessions = {}
cached_group_posts = {}

# ==================== УМНЫЙ МАТЧИНГ ТЕГОВ ====================
def clean_fio_string(text: str) -> str:
    if not text or pd.isnull(text):
        return ""
    s = str(text)
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"\b(У|ОБ|НС|СВ)\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"[^а-яА-ЯёЁa-zA-Z\s]", " ", s)
    return " ".join(s.split()).strip()

def get_tags_map() -> dict:
    if os.path.exists("tags.json"):
        try:
            with open("tags.json", "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def get_tag_for_fio(fio_raw: str, tags_dict: dict) -> str:
    cleaned = clean_fio_string(fio_raw)
    if not cleaned:
        return ""

    tokens = cleaned.lower().split()
    cleaned_lower = cleaned.lower()

    for db_fio, tag in tags_dict.items():
        if clean_fio_string(db_fio).lower() == cleaned_lower:
            return tag.strip() if tag and str(tag).lower() != "nan" else cleaned

    if len(tokens) >= 2:
        fi = f"{tokens[0]} {tokens[1]}"
        for db_fio, tag in tags_dict.items():
            db_tokens = clean_fio_string(db_fio).lower().split()
            if len(db_tokens) >= 2 and f"{db_tokens[0]} {db_tokens[1]}" == fi:
                return tag.strip() if tag and str(tag).lower() != "nan" else cleaned

    if tokens:
        last_name = tokens[0]
        matches = [
            tag.strip() for db_fio, tag in tags_dict.items()
            if clean_fio_string(db_fio).lower().startswith(last_name) and tag and str(tag).lower() != "nan"
        ]
        if len(matches) == 1:
            return matches[0]

    return " ".join(cleaned.split()[:2])

def split_text(text: str, limit: int = 4000):
    parts = []
    while len(text) > limit:
        split_idx = text.rfind("\n\n", 0, limit)
        if split_idx == -1:
            split_idx = text.rfind("\n", 0, limit)
        if split_idx == -1:
            split_idx = limit
        parts.append(text[:split_idx])
        text = text[split_idx:].strip()
    if text:
        parts.append(text)
    return parts

def get_templates_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сообщение 1", callback_data="tmpl_select:1"), InlineKeyboardButton(text="Сообщение 2", callback_data="tmpl_select:2")],
            [InlineKeyboardButton(text="Сообщение 3", callback_data="tmpl_select:3"), InlineKeyboardButton(text="Сообщение 4", callback_data="tmpl_select:4")],
            [InlineKeyboardButton(text="Сообщение 5", callback_data="tmpl_select:5"), InlineKeyboardButton(text="Сообщение 6 (⭐ Звезды)", callback_data="tmpl_select:6")],
        ]
    )

def get_edit_templates_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Сообщение 1", callback_data="tmpl_edit:1"), InlineKeyboardButton(text="✏️ Сообщение 2", callback_data="tmpl_edit:2")],
            [InlineKeyboardButton(text="✏️ Сообщение 3", callback_data="tmpl_edit:3"), InlineKeyboardButton(text="✏️ Сообщение 4", callback_data="tmpl_edit:4")],
            [InlineKeyboardButton(text="✏️ Сообщение 5", callback_data="tmpl_edit:5"), InlineKeyboardButton(text="✏️ Сообщение 6", callback_data="tmpl_edit:6")],
        ]
    )

@dp.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выберите действие или тип отчета:", reply_markup=main_kb)

@dp.message(F.text == "⚙️ Редактировать шаблоны")
async def cmd_edit_templates(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выберите номер сообщения для редактирования:", reply_markup=get_edit_templates_keyboard())

@dp.callback_query(F.data.startswith("tmpl_edit:"))
async def callback_edit_template(call: CallbackQuery, state: FSMContext):
    msg_num = call.data.split(":")[1]
    templates = load_templates()
    current_text = templates.get(msg_num, "")

    await state.update_data(editing_msg_num=msg_num)
    await state.set_state(ReportFSM.waiting_for_template_text)

    await call.message.answer(
        f"Текущий текст для <b>Сообщения {msg_num}</b>:\n\n"
        f"{current_text}\n\n"
        "Отправьте в ответ новый текст сообщения:",
        parse_mode="HTML"
    )
    await call.answer()

@dp.message(ReportFSM.waiting_for_template_text)
async def process_new_template_text(message: Message, state: FSMContext):
    data = await state.get_data()
    msg_num = data.get("editing_msg_num")

    if msg_num:
        templates = load_templates()
        new_text = message.html_text.strip() if hasattr(message, "html_text") and message.html_text else message.text.strip()
        templates[msg_num] = new_text
        save_templates(templates)

        await message.answer(
            f"✅ Текст для <b>Сообщения {msg_num}</b> успешно сохранен!\n\n{new_text}",
            parse_mode="HTML",
            reply_markup=main_kb
        )

    await state.clear()

@dp.message(F.text == "Загрузить базу тегов")
async def cmd_load_tags(message: Message, state: FSMContext):
    await message.answer("Отправьте Excel-файл с тегами.\n1-й столбец: ФИО, 2-й столбец: @username.")
    await state.set_state(ReportFSM.waiting_for_tags_file)

@dp.message(ReportFSM.waiting_for_tags_file, F.document)
async def process_tags_file(message: Message, state: FSMContext):
    try:
        file = await bot.get_file(message.document.file_id)
        downloaded = await bot.download_file(file.file_path)
        df_tags = pd.read_excel(io.BytesIO(downloaded.read()))

        tags_dict = {}
        for _, row in df_tags.iterrows():
            fio = str(row.iloc[0]).strip()
            tag = str(row.iloc[1]).strip()
            if fio and fio.lower() != "nan":
                tags_dict[fio] = tag if tag.lower() != "nan" else ""

        with open("tags.json", "w", encoding="utf-8") as f:
            json.dump(tags_dict, f, ensure_ascii=False, indent=2)

        await message.answer(f"✅ База тегов обновлена! Загружено контактов: {len(tags_dict)}", reply_markup=main_kb)
    except Exception as e:
        await message.answer(f"❌ Ошибка при чтении файла: {e}")
    finally:
        await state.clear()

# ==================== ВЕТКА НАСТАВНИКОВ ====================
@dp.message(F.text == "Срез для наставников")
async def start_mentor_flow(message: Message, state: FSMContext):
    await state.clear()
    help_text = (
        "Введите привязку Наставников и Операторов (можно в одну строку через точку или с новой строки).\n\n"
        "<b>Пример:</b>\n"
        "<code>Шалунова Мишель: Кафиан Алина. Лазарева Вероника: Денисюк, Гаджикеримова</code>"
    )
    await message.answer(help_text, parse_mode="HTML")
    await state.set_state(ReportFSM.waiting_for_mentor_mappings)

@dp.message(ReportFSM.waiting_for_mentor_mappings)
async def process_mentor_mappings(message: Message, state: FSMContext):
    raw_text = message.text.replace("\n", ".").replace(";", ".")
    blocks = [b.strip() for b in raw_text.split(".") if ":" in b]

    if not blocks:
        await message.answer(
            "Не найден формат `Наставник: Операторы`. Пример:\n"
            "<code>Шалунова Мишель: Кафиан Алина. Лазарева Вероника: Денисюк, Гаджикеримова</code>",
            parse_mode="HTML"
        )
        return

    mentor_map = []
    for block in blocks:
        mentor, ops_str = block.split(":", 1)
        mentor_clean = mentor.strip()
        ops = [op.strip() for op in ops_str.split(",") if op.strip()]
        for op in ops:
            mentor_map.append({"mentor": mentor_clean, "op_query": op})

    user_sessions[message.from_user.id] = {"mentor_map": mentor_map}
    await message.answer(f"Принято связок: {len(mentor_map)}.\nТеперь отправьте Excel-файл <b>«ДО»</b>:", parse_mode="HTML")
    await state.set_state(ReportFSM.waiting_for_mentor_file_before)

@dp.message(ReportFSM.waiting_for_mentor_file_before, F.document)
async def handle_mentor_file_before(message: Message, state: FSMContext):
    file = await bot.get_file(message.document.file_id)
    downloaded = await bot.download_file(file.file_path)
    df_before = pd.read_excel(io.BytesIO(downloaded.read()))

    session = user_sessions.setdefault(message.from_user.id, {})
    session["df_before"] = df_before
    await message.answer("Файл «ДО» сохранён. Теперь отправьте Excel-файл <b>«ПОСЛЕ»</b>:", parse_mode="HTML")
    await state.set_state(ReportFSM.waiting_for_mentor_file_after)

@dp.message(ReportFSM.waiting_for_mentor_file_after, F.document)
async def handle_mentor_file_after(message: Message, state: FSMContext):
    file = await bot.get_file(message.document.file_id)
    downloaded = await bot.download_file(file.file_path)
    df_after = pd.read_excel(io.BytesIO(downloaded.read()))

    session = user_sessions.setdefault(message.from_user.id, {})
    df_before = session.get("df_before")
    mentor_map = session.get("mentor_map", [])

    await message.answer("Генерирую срез для наставников...")
    try:
        image_bytes, df_result = generate_mentor_report(mentor_map, df_before, df_after)
        await message.answer_photo(
            photo=BufferedInputFile(image_bytes.read(), filename="mentors_report.jpg"),
            caption="🏆 Срез для наставников готов",
            reply_markup=main_kb
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка генерации таблицы: {e}", reply_markup=main_kb)
    finally:
        await state.clear()

def clean_num_val(val, default=0.0):
    if pd.isnull(val):
        return default
    v = str(val).replace("%", "").replace(",", ".").replace(" ", "").strip()
    try:
        return float(v)
    except Exception:
        return default

def find_column(df, patterns):
    for col in df.columns:
        col_str = str(col).lower()
        if any(p.lower() in col_str for p in patterns):
            return col
    return None

def generate_mentor_report(mentor_map, df_before, df_after):
    for df in [df_before, df_after]:
        df.columns = [str(c).strip() for c in df.columns]

    col_fio_b = find_column(df_before, ["фио", "сотрудник", "оператор"])
    col_fio_a = find_column(df_after, ["фио", "сотрудник", "оператор"])
    col_cat_b = find_column(df_before, ["категор"])
    col_cat_a = find_column(df_after, ["категор"])
    col_cr_b = find_column(df_before, ["% успешных", "конверс", "cr"])
    col_cr_a = find_column(df_after, ["% успешных", "конверс", "cr"])
    col_vsego_b = find_column(df_before, ["всего", "звонков"])
    col_vsego_a = find_column(df_after, ["всего", "звонков"])
    col_smen_b = find_column(df_before, ["смен"])
    col_smen_a = find_column(df_after, ["смен"])
    col_dozvon_b = find_column(df_before, ["дозвон"])
    col_dozvon_a = find_column(df_after, ["дозвон"])
    col_id = find_column(df_after, ["id", "айди"]) or find_column(df_before, ["id", "айди"])
    col_zp_a = find_column(df_after, ["зп", "за период", "оплата"])

    rows = []
    for item in mentor_map:
        mentor = item["mentor"]
        op_query = item["op_query"].lower()

        sub_a = df_after[df_after[col_fio_a].astype(str).str.lower().str.contains(op_query, na=False)] if col_fio_a else pd.DataFrame()
        sub_b = df_before[df_before[col_fio_b].astype(str).str.lower().str.contains(op_query, na=False)] if col_fio_b else pd.DataFrame()

        row_a = sub_a.iloc[0] if not sub_a.empty else None
        row_b = sub_b.iloc[0] if not sub_b.empty else None

        fio_op = ""
        if row_a is not None:
            fio_op = str(row_a[col_fio_a])
        elif row_b is not None:
            fio_op = str(row_b[col_fio_b])
        else:
            fio_op = item["op_query"]

        id_val = ""
        if col_id:
            if row_a is not None and pd.notnull(row_a.get(col_id)):
                id_val = str(row_a[col_id]).replace(".0", "")
            elif row_b is not None and pd.notnull(row_b.get(col_id)):
                id_val = str(row_b[col_id]).replace(".0", "")

        cat_b = clean_num_val(row_b[col_cat_b], 4.0) if row_b is not None and col_cat_b else 4.0
        cr_b = clean_num_val(row_b[col_cr_b], 0.0) if row_b is not None and col_cr_b else 0.0
        if 0 < cr_b < 1.0:
            cr_b *= 100
        vsego_b = clean_num_val(row_b[col_vsego_b], 0) if row_b is not None and col_vsego_b else 0
        smen_b = clean_num_val(row_b[col_smen_b], 1) if row_b is not None and col_smen_b else 1
        smen_b = 1 if smen_b <= 0 else smen_b
        zv_smena_b = vsego_b / smen_b
        dozvon_b = clean_num_val(row_b[col_dozvon_b], 0.0) if row_b is not None and col_dozvon_b else 0.0
        if 0 < dozvon_b < 1.0:
            dozvon_b *= 100

        cat_a = clean_num_val(row_a[col_cat_a], 4.0) if row_a is not None and col_cat_a else 4.0
        cr_a = clean_num_val(row_a[col_cr_a], 0.0) if row_a is not None and col_cr_a else 0.0
        if 0 < cr_a < 1.0:
            cr_a *= 100
        vsego_a = clean_num_val(row_a[col_vsego_a], 0) if row_a is not None and col_vsego_a else 0
        smen_a = clean_num_val(row_a[col_smen_a], 1) if row_a is not None and col_smen_a else 1
        smen_a = 1 if smen_a <= 0 else smen_a
        zv_smena_a = vsego_a / smen_a
        dozvon_a = clean_num_val(row_a[col_dozvon_a], 0.0) if row_a is not None and col_dozvon_a else 0.0
        if 0 < dozvon_a < 1.0:
            dozvon_a *= 100

        zp_a = clean_num_val(row_a[col_zp_a], 0.0) if row_a is not None and col_zp_a else 0.0

        prirost = cat_b - cat_a
        steps_05 = math.floor(prirost / 0.5) if prirost > 0 else 0
        payout_pct = steps_05 * 0.10

        zp_ns_str = "-"
        if payout_pct >= 0.10 and zp_a > 0:
            zp_ns_str = f"{int(round(zp_a * payout_pct))}"

        rows.append({
            "ФИО НС": mentor,
            "ID": id_val,
            "ФИО Оператора": fio_op,
            "Категория\nДО": f"{cat_b:.2f}".replace(".", ","),
            "Конверсия\nДО": f"{cr_b:.2f}%".replace(".", ","),
            "Звонков в\nсмену ДО": f"{int(round(zv_smena_b))}",
            "% дозвона\nДО": f"{dozvon_b:.2f}%".replace(".", ","),
            "Категория": f"{cat_a:.2f}".replace(".", ","),
            "Конверсия": f"{cr_a:.2f}%".replace(".", ","),
            "Звонков в\nсмену": f"{int(round(zv_smena_a))}",
            "Прирост": f"{prirost:+.2f}".replace(".", ","),
            "ЗП НС": zp_ns_str,
            "Смен": f"{int(round(smen_a))}",
            "% дозвона": f"{dozvon_a:.2f}%".replace(".", ","),
        })

    res_df = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(24, len(res_df) * 0.52 + 1.8))
    ax.axis("off")

    col_widths = [0.12, 0.05, 0.22, 0.06, 0.06, 0.06, 0.06, 0.06, 0.06, 0.06, 0.06, 0.05, 0.04, 0.06]
    table = ax.table(
        cellText=res_df.values,
        colLabels=res_df.columns,
        loc="center",
        cellLoc="center",
        colWidths=col_widths,
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10.5)
    table.scale(1.15, 2.3)

    blue_cols = [0, 1, 2]
    teal_cols = [3, 4, 5, 6]
    purple_cols = [7, 8, 9, 10, 11, 12, 13]

    for c_idx in range(len(res_df.columns)):
        cell = table[(0, c_idx)]
        cell.get_text().set_weight("bold")
        if c_idx in blue_cols:
            cell.set_facecolor("#2b6cb0")
            cell.get_text().set_color("white")
        elif c_idx in teal_cols:
            cell.set_facecolor("#1f6f78")
            cell.get_text().set_color("white")
        elif c_idx in purple_cols:
            cell.set_facecolor("#dcd6e8")
            cell.get_text().set_color("black")

    for r_idx in range(len(res_df)):
        table[(r_idx + 1, 0)].get_text().set_horizontalalignment("left")
        table[(r_idx + 1, 2)].get_text().set_horizontalalignment("left")
        for c_idx in range(len(res_df.columns)):
            table[(r_idx + 1, c_idx)].set_edgecolor("#cccccc")

    buf = io.BytesIO()
    plt.savefig(buf, format="jpeg", bbox_inches="tight", dpi=250)
    buf.seek(0)
    plt.close()
    return buf, res_df

# ==================== СТАНДАРТНЫЕ ОТЧЕТЫ ====================
@dp.message(F.text.in_([
    "Срез для группы",
    "Срез для админки",
    "Сравнительный по ГП",
    "Отчет в группу неделя",
    "Сравнительный по ГП неделя",
    "Анализ группы"
]))
async def choose_report_type(message: Message, state: FSMContext):
    user_sessions[message.from_user.id] = {"type": message.text}
    await message.answer(f"Отправьте Excel-файл для отчета «{message.text}»:")
    await state.set_state(ReportFSM.waiting_for_file)

@dp.message(ReportFSM.waiting_for_file, F.document)
async def handle_file(message: Message, state: FSMContext):
    file = await bot.get_file(message.document.file_id)
    downloaded_file = await bot.download_file(file.file_path)
    df = pd.read_excel(io.BytesIO(downloaded_file.read()))

    session = user_sessions.setdefault(message.from_user.id, {})
    session["df"] = df
    report_type = session.get("type", "")

    if "Сравнительный" in report_type:
        await process_comparative_report(message, df, "неделя" in report_type)
        await state.clear()
    else:
        await message.answer("Введите номер(а) группы через запятую (например: 47 или 47, 31):")
        await state.set_state(ReportFSM.waiting_for_group_number)

@dp.message(ReportFSM.waiting_for_group_number)
async def handle_group_number(message: Message, state: FSMContext):
    session = user_sessions.setdefault(message.from_user.id, {})
    session["target_groups"] = [g.strip() for g in message.text.split(",") if g.strip()]
    report_type = session.get("type", "")

    if report_type in ["Анализ группы", "Срез для группы"]:
        await message.answer("Введите среднее (Конва) по ГП через пробел (например: 2.51):")
        await state.set_state(ReportFSM.waiting_for_gp_average)
    else:
        await message.answer("Введите Штат и Выход через пробел (например: 26 14):")
        await state.set_state(ReportFSM.waiting_for_staff_numbers)

@dp.message(ReportFSM.waiting_for_staff_numbers)
async def handle_staff_numbers(message: Message, state: FSMContext):
    try:
        parts = message.text.replace(",", " ").split()
        staff_data = []
        for i in range(0, len(parts), 2):
            if i + 1 < len(parts):
                staff_data.append((int(parts[i]), int(parts[i + 1])))

        if not staff_data:
            raise ValueError

        session = user_sessions.setdefault(message.from_user.id, {})
        session["staff_data"] = staff_data
        await message.answer("Введите среднее (Конва) по ГП через пробел (например: 2.51):")
        await state.set_state(ReportFSM.waiting_for_gp_average)
    except ValueError:
        await message.answer("Ошибка формата. Введите пары чисел (Штат Выход) через пробел:")

@dp.message(ReportFSM.waiting_for_gp_average)
async def handle_gp_average(message: Message, state: FSMContext):
    session = user_sessions.setdefault(message.from_user.id, {})
    gp_text_cleaned = message.text.replace(",", ".").split()

    gp_averages = []
    for val in gp_text_cleaned:
        try:
            gp_averages.append(float(val))
        except ValueError:
            pass

    if not gp_averages:
        gp_averages = [0.0]
    session["gp_averages"] = gp_averages
    report_type = session.get("type", "")

    if report_type == "Срез для группы":
        await message.answer("Выберите шаблон сообщения для отправки в группу:", reply_markup=get_templates_keyboard())
    else:
        await process_report(message, state, session, selected_template="1")

@dp.callback_query(F.data.startswith("tmpl_select:"))
async def callback_select_template(call: CallbackQuery, state: FSMContext):
    tmpl_num = call.data.split(":")[1]
    session = user_sessions.get(call.from_user.id, {})
    await call.answer()
    try:
        await call.message.delete()
    except Exception:
        pass
    await process_report(call.message, state, session, selected_template=tmpl_num)

async def process_report(message: Message, state: FSMContext, session: dict, selected_template: str = "1"):
    df_all = session.get("df")
    target_groups = session.get("target_groups", ["47"])
    gp_averages = session.get("gp_averages", [0.0])
    staff_data = session.get("staff_data", [(1, 1)])
    report_type = session.get("type", "")

    df_all.columns = [str(c).strip() for c in df_all.columns]
    rename_dict = {}
    for col in df_all.columns:
        c_low = col.lower()
        if "период" in c_low or "зп" in c_low or "за период" in c_low:
            rename_dict[col] = "ЗП"
        elif "категор" in c_low:
            rename_dict[col] = "Категория"
        elif "последнее" in c_low:
            rename_dict[col] = "Последнее действие"
    df_all.rename(columns=rename_dict, inplace=True)

    templates = load_templates()
    template_body = templates.get(selected_template, DEFAULT_TEMPLATES.get(selected_template, ""))

    for idx, target_group in enumerate(target_groups):
        gp_avg_val = gp_averages[idx] if idx < len(gp_averages) else gp_averages[-1]
        gp_avg_text = f"{gp_avg_val:.2f}"
        shtat, smena = staff_data[idx] if idx < len(staff_data) else staff_data[-1]

        df_target_full = df_all[df_all["Ответственный"].astype(str).str.contains(target_group, na=False)].copy()

        if df_target_full.empty:
            await message.answer(f"Нет данных по группе {target_group}.")
            continue

        if report_type == "Анализ группы":
            analysis_text = generate_analysis_text(df_target_full, gp_avg_val, target_group)
            for chunk in split_text(analysis_text):
                await message.answer(chunk, parse_mode="HTML")
            continue

        def safe_sum_name(df, substr):
            col = next((c for c in df.columns if substr.lower() in str(c).lower()), None)
            if not col:
                return 0
            s = df[col].astype(str).str.replace(r"\s+", "", regex=True).str.replace(",", ".").str.replace("%", "")
            return pd.to_numeric(s, errors="coerce").sum()

        try:
            sum_usp = safe_sum_name(df_target_full, "успешные")
            sum_vsego = safe_sum_name(df_target_full, "всего")
            sum_nedozvon = safe_sum_name(df_target_full, "недозвон")
            sum_nekor = safe_sum_name(df_target_full, "некор")
            sum_prinyatye = sum_vsego - sum_nedozvon - sum_nekor
            real_avg_usp = (sum_usp / sum_prinyatye * 100) if sum_prinyatye > 0 else None
        except Exception:
            real_avg_usp = None

        try:
            sum_vsego = safe_sum_name(df_target_full, "всего")
            sum_nedozvon = safe_sum_name(df_target_full, "недозвон")
            real_avg_dozvon = ((sum_vsego - sum_nedozvon) / sum_vsego * 100) if sum_vsego > 0 else None
        except Exception:
            real_avg_dozvon = None

        admin_report_text = generate_admin_text(df_all, shtat, smena, gp_avg_text, real_avg_usp, real_avg_dozvon, target_group)

        columns_to_keep = [
            "ФИО",
            "Рабочее время",
            "Время перерывов",
            "% у рабочего места",
            "% дозвона до человека",
            "% успешных по дозвону",
            "Успешные",
            "Всего",
            "Категория",
            "ЗП",
        ]

        if report_type != "Срез для группы":
            if "Последнее действие" in df_all.columns:
                columns_to_keep.append("Последнее действие")

        existing_cols = [c for c in columns_to_keep if c in df_target_full.columns]
        df_target = df_target_full[existing_cols]

        image_bytes = render_dataframe_to_image(df_target, gp_avg_val, real_avg_usp, real_avg_dozvon)
        image_data = image_bytes.getvalue()

        # Строим компактный текст, строго умещающийся в caption под фото (до 1024 символов)
        group_post_text = build_group_message_text(template_body, df_target_full, selected_template, gp_avg_text)

        post_key = f"{message.chat.id}_{target_group}"
        cached_group_posts[post_key] = {"img": image_data, "text": group_post_text}

        send_markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="📤 Отправить в группу", callback_data=f"send_group:{post_key}")]]
        )

        if report_type == "Срез для группы":
            # Всегда отправляем единым сообщением: картинка + подпись под ней
            await message.answer_photo(
                photo=BufferedInputFile(image_data, filename="group_slice.jpg"),
                caption=group_post_text,
                parse_mode="HTML",
                reply_markup=send_markup,
            )
        else:
            for chunk in split_text(admin_report_text):
                await message.answer(chunk, parse_mode="HTML")

            await message.answer_photo(
                photo=BufferedInputFile(image_data, filename="admin_slice.jpg"),
                caption=f"Срез для админки (Группа {target_group})",
                reply_markup=send_markup,
            )

    await state.clear()

def build_group_message_text(template_body: str, df: pd.DataFrame, tmpl_num: str, gp_avg_text: str) -> str:
    tags_dict = get_tags_map()

    # Базовая часть сообщения (шаблон + конва по ГП)
    base_text = f"{template_body}\n\nКонва по ГП: <b>{gp_avg_text}%</b>"

    if tmpl_num == "5":
        return base_text

    if tmpl_num == "6":
        df_valid = df.copy()
        df_valid = df_valid[~df_valid["ФИО"].astype(str).str.upper().str.contains("СРЕДНЕЕ|ИТОГО")]
        df_valid["Усп_число"] = pd.to_numeric(df_valid["Успешные"], errors="coerce").fillna(0)
        df_valid = df_valid.sort_values(by="Усп_число", ascending=False)

        top_lines = []
        medals = ["⭐", "🌟", "✨"]
        for i, (_, row) in enumerate(df_valid.head(5).iterrows()):
            usp_val = int(row["Усп_число"])
            if usp_val <= 0:
                continue
            icon = medals[i] if i < len(medals) else "🔸"
            tag = get_tag_for_fio(row.get("ФИО", ""), tags_dict)
            top_lines.append(f"{icon} {tag} — <b>{usp_val}</b>")

        stars_block = "\n".join(top_lines) if top_lines else "Пока нет успешных"
        return f"🏆 <b>{template_body}</b>\n\nКонва по ГП: <b>{gp_avg_text}%</b>\n\n<b>Лидеры смены:</b>\n{stars_block}"

    # Для шаблонов 1, 2, 3, 4: собираем теги операторов
    all_tags = []
    for _, row in df.iterrows():
        fio_raw = str(row.get("ФИО", "")).strip()
        if not fio_raw or fio_raw.upper() in ["СРЕДНЕЕ", "ИТОГО", "NAN"]:
            continue
        tag = get_tag_for_fio(fio_raw, tags_dict)
        if tag and tag not in all_tags:
            all_tags.append(tag)

    # Гарантируем, что подпись не превысит лимит Telegram в 1024 символа
    header_prefix = "\n\n👥 "
    max_caption_len = 1010
    allowed_for_tags = max_caption_len - len(base_text) - len(header_prefix)

    fitted_tags = []
    curr_len = 0
    for t in all_tags:
        # длина тега + 1 символ пробела
        if curr_len + len(t) + 1 <= allowed_for_tags:
            fitted_tags.append(t)
            curr_len += len(t) + 1
        else:
            break

    if fitted_tags:
        tags_str = " ".join(fitted_tags)
        return f"{base_text}{header_prefix}{tags_str}"
    
    return base_text

@dp.callback_query(F.data.startswith("send_group:"))
async def callback_send_to_group(call: CallbackQuery):
    await call.answer("Отправка в группу...")
    post_key = call.data.split("send_group:")[1]
    post_data = cached_group_posts.get(post_key)

    if not post_data:
        await call.message.answer("⚠️ Данные среза устарели в памяти. Сгенерируйте срез заново.")
        return

    text = post_data["text"]
    img = post_data["img"]

    try:
        # Всегда отправляем строго одним сообщением (подпись под фото)
        await bot.send_photo(
            chat_id=TARGET_TELEGRAM_GROUP_ID,
            photo=BufferedInputFile(img, filename="report.jpg"),
            caption=text,
            parse_mode="HTML",
        )
        await call.message.answer("✅ Успешно опубликовано в группе единым сообщением под фото!")
    except Exception as e:
        error_msg = f"❌ Ошибка отправки в группу:\n<code>{html.escape(str(e))}</code>\n\nПроверьте права бота в группе {TARGET_TELEGRAM_GROUP_ID}."
        await call.message.answer(error_msg, parse_mode="HTML")

def generate_analysis_text(df, gp_avg, target_group):
    if df.empty:
        return f"Нет данных по {target_group} группе."

    def clean_pct(val):
        if pd.isnull(val):
            return 0.0
        v = str(val).replace("%", "").replace(",", ".").replace(" ", "")
        try:
            res = float(v)
            return res * 100 if res < 1.5 else res
        except Exception:
            return 0.0

    def clean_num(val):
        if pd.isnull(val):
            return 0
        v = str(val).replace(",", ".").replace(" ", "")
        try:
            return float(v)
        except Exception:
            return 0

    col_smen = next((c for c in df.columns if "смен" in str(c).lower()), None)
    col_vsego = next((c for c in df.columns if "всего" in str(c).lower()), None)
    col_rab = next((c for c in df.columns if "рабочего" in str(c).lower()), None)
    col_dozvon = next((c for c in df.columns if "дозвона" in str(c).lower()), None)
    col_cr = next((c for c in df.columns if "успешных по" in str(c).lower()), None)

    report_lines = [f"📊 <b>Анализ операторов группы {target_group}</b>\n"]

    for _, row in df.iterrows():
        fio = str(row.get("ФИО", "Неизвестно")).split("(")[0].strip()
        if fio.upper() in ["СРЕДНЕЕ", "ИТОГО"] or fio == "nan":
            continue

        smen = clean_num(row[col_smen]) if col_smen else 1
        if smen <= 0:
            smen = 1
        vsego = clean_num(row[col_vsego]) if col_vsego else 0
        intens = vsego / smen

        rab_mesto = clean_pct(row[col_rab]) if col_rab else 0
        dozvon = clean_pct(row[col_dozvon]) if col_dozvon else 0
        cr = clean_pct(row[col_cr]) if col_cr else 0

        issues = []
        if 0 < intens < 150:
            issues.append(f"• Интенсивность: <b>{intens:.0f}</b> зв/смена (норма 150+). <i>Низкий темп прозвона.</i>")
        if 0 < rab_mesto < 70:
            issues.append(f"• На рабочем месте: <b>{rab_mesto:.1f}%</b> (норма 70%+). <i>Потери времени и перерывы.</i>")
        if dozvon > 0:
            if dozvon > 90:
                issues.append(f"• Дозвон: <b>{dozvon:.1f}%</b> (норма до 90%). <i>Подозрение на ручной сброс.</i>")
            elif dozvon < 86:
                issues.append(f"• Дозвон: <b>{dozvon:.1f}%</b> (норма от 86%). <i>Долгое бездействие на линии.</i>")
        if 0 < cr < gp_avg:
            issues.append(f"• Конверсия: <b>{cr:.2f}%</b> (цель {gp_avg:.2f}%). <i>Подтянуть дожим и отработку возражений.</i>")

        if issues:
            report_lines.append(f"👤 <b>{fio}</b>")
            report_lines.extend(issues)
            report_lines.append("")

    if len(report_lines) == 1:
        return report_lines[0] + "\n✅ У всех операторов группы показатели в норме!"

    return "\n".join(report_lines).strip()

def generate_admin_text(df_all, shtat, smena, gp_avg, real_avg_usp=None, real_avg_dozvon=None, target_group="47"):
    df = df_all[df_all["Ответственный"].astype(str).str.contains(target_group, na=False)].copy()
    if df.empty:
        return f"Нет данных по {target_group} группе."

    def clean_pct(col):
        res = pd.to_numeric(df[col].astype(str).str.replace("%", "").str.replace(",", "."), errors="coerce")
        return res * 100 if res.mean() < 1.5 else res

    avg_usp_dozvon = real_avg_usp if real_avg_usp is not None else clean_pct("% успешных по дозвону").mean()
    avg_dozvon = real_avg_dozvon if real_avg_dozvon is not None else clean_pct("% дозвона до человека").mean()
    avg_rab_mesto_series = clean_pct("% у рабочего места")
    avg_rab_mesto = avg_rab_mesto_series.mean()

    avg_usp = pd.to_numeric(df["Успешные"], errors="coerce").mean()
    vsego_series = pd.to_numeric(df["Всего"], errors="coerce")
    avg_vsego = vsego_series.mean()

    fact_vyhod_count = pd.to_numeric(df["Смен"], errors="coerce").sum() if "Смен" in df.columns else len(df)
    plan_vyhod = (smena / shtat) * 100 if shtat > 0 else 0
    fact_vyhod = (fact_vyhod_count / shtat) * 100 if shtat > 0 else 0

    over_100_calls = len(df[vsego_series >= 100])
    kpp_count = len(df[(avg_rab_mesto_series > 0) & (avg_rab_mesto_series <= 80)])

    def time_to_seconds(t_str):
        if pd.isnull(t_str):
            return 0
        v = str(t_str).strip()
        try:
            if v.startswith("1900-01-"):
                d_str, time_part = v.split(" ")
                days = int(d_str.split("-")[2])
                h, m, s = map(float, time_part.split(":"))
                return days * 24 * 3600 + h * 3600 + m * 60 + s
            elif "day" in v:
                parts = v.split(" ")
                days = int(parts[0])
                h, m, s = map(float, parts[-1].split(":"))
                return days * 24 * 3600 + h * 3600 + m * 60 + s
            parts = v.split(":")
            if len(parts) >= 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        except Exception:
            pass
        return 0

    def format_seconds_to_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = round(seconds % 60)
        if s == 60:
            s, m = 0, m + 1
        if m == 60:
            m, h = 0, h + 1
        return f"{h}:{m:02d}:{s:02d}"

    total_seconds = df["Рабочее время"].apply(time_to_seconds).sum() if "Рабочее время" in df.columns else 0
    avg_seconds = total_seconds / fact_vyhod_count if fact_vyhod_count > 0 else 0
    prod_hours_str = format_seconds_to_time(avg_seconds)

    admin_report = f"""<b>КЦ УД {target_group} Солянка прочее</b>
% усп. по дозвону - <b>{avg_usp_dozvon:.2f}%</b>
% дозвон до человека - <b>{avg_dozvon:.0f}%</b>
% у рабочего места - <b>{avg_rab_mesto:.1f}</b>
Среднее количество усп: <b>{avg_usp:.2f}</b>
Заявок на оператора: <b>{avg_vsego:.2f}</b>
% выход план : <b>{plan_vyhod:.0f}%</b>
% выход факт: <b>{fact_vyhod:.0f}%</b>
КПП - <b>{kpp_count}/{int(fact_vyhod_count)}</b>
От 100 ЗВ - <b>{over_100_calls}/{int(fact_vyhod_count)}</b>
Продуктивные часы: <b>{prod_hours_str}</b>

Конва по ГП: <b>{gp_avg}</b>"""

    return admin_report

def render_dataframe_to_image(df_original, gp_avg=0.0, real_avg_usp=None, real_avg_dozvon=None):
    df = df_original.copy()
    pct_cols = [c for c in ["% у рабочего места", "% дозвона до человека", "% успешных по дозвону"] if c in df.columns]
    numeric_cols = [c for c in ["Успешные", "Всего", "ЗП", "Категория"] if c in df.columns]

    for col in pct_cols:
        val = pd.to_numeric(df[col].astype(str).str.replace("%", "").str.replace(",", "."), errors="coerce")
        df[col] = val * 100 if val.mean() < 1.5 else val
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "."), errors="coerce")

    avg_row = {col: "" for col in df.columns}
    avg_row["ФИО"] = "СРЕДНЕЕ"
    for col in pct_cols + numeric_cols:
        avg_row[col] = df[col].mean()

    if real_avg_usp is not None and "% успешных по дозвону" in avg_row:
        avg_row["% успешных по дозвону"] = real_avg_usp
    if real_avg_dozvon is not None and "% дозвона до человека" in avg_row:
        avg_row["% дозвона до человека"] = real_avg_dozvon

    if "% успешных по дозвону" in df.columns:
        df = df.sort_values(by="% успешных по дозвону", ascending=False).reset_index(drop=True)

    usp_avg_val = avg_row.get("% успешных по дозвону", 0.0)
    insert_idx = 0
    if "% успешных по дозвону" in df.columns:
        for idx_row, val in enumerate(df["% успешных по дозвону"]):
            if val < usp_avg_val:
                insert_idx = idx_row
                break
        else:
            insert_idx = len(df)

    df_above = df.iloc[:insert_idx]
    df_below = df.iloc[insert_idx:]
    df = pd.concat([df_above, pd.DataFrame([avg_row]), df_below], ignore_index=True)

    display_df = df.copy()

    def fix_time_format(val):
        if pd.isnull(val):
            return ""
        v = str(val).strip()
        try:
            if v.startswith("1900-01-"):
                d_str, t_str = v.split(" ")
                days = int(d_str.split("-")[2])
                h, m, s = map(float, t_str.split(":"))
                return f"{days * 24 + int(h):02d}:{int(m):02d}:{int(s):02d}"
            elif "day" in v:
                parts = v.split(" ")
                days = int(parts[0])
                h, m, s = map(float, parts[-1].split(":"))
                return f"{days * 24 + int(h):02d}:{int(m):02d}:{int(s):02d}"
        except Exception:
            pass
        return v

    def safe_str(val):
        if pd.isnull(val):
            return ""
        v = str(val).strip()
        if v in ["NaT", "nan", "None", ""]:
            return ""
        if "1900-01-01" in v:
            v = v.replace("1900-01-01", "").strip()
        return v

    for col in pct_cols:
        display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) and x != "" else "")
    for col in ["Успешные", "Всего", "ЗП"]:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: f"{x:.0f}" if pd.notnull(x) and x != "" else "")
    if "Категория" in display_df.columns:
        display_df["Категория"] = display_df["Категория"].apply(lambda x: f"{x:.2f}" if pd.notnull(x) and x != "" else "")

    for col in df.columns:
        if col not in pct_cols and col not in numeric_cols and col != "ФИО":
            if col in ["Рабочее время", "Время перерывов"]:
                display_df[col] = display_df[col].apply(fix_time_format)
            else:
                display_df[col] = display_df[col].apply(safe_str)

    fig, ax = plt.subplots(figsize=(26, len(df) * 0.48 + 1.6))
    ax.axis("off")
    cols_count = len(display_df.columns)
    col_widths = [0.22] + [0.78 / (cols_count - 1)] * (cols_count - 1)

    table = ax.table(
        cellText=display_df.values,
        colLabels=display_df.columns,
        loc="center",
        cellLoc="center",
        colWidths=col_widths,
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.15, 2.1)

    rwg_cmap = mcolors.LinearSegmentedColormap.from_list("rwg", ["#f4cccc", "#ffffff", "#77c38d"])
    norm_dict = {}
    for col in pct_cols + [c for c in numeric_cols if c != "Категория"]:
        vals = pd.to_numeric(df[df["ФИО"] != "СРЕДНЕЕ"][col], errors="coerce").dropna()
        if not vals.empty:
            norm_dict[col] = mcolors.Normalize(vmin=vals.min(), vmax=vals.max())

    usp_col = "% успешных по дозвону"

    def get_usp_color(v):
        if gp_avg <= 0 or pd.isnull(v):
            return "#ffffff"
        t1, t2, t3, t4 = gp_avg * 0.70, gp_avg * 0.85, gp_avg * 1.15, gp_avg * 1.30
        if v < t1:
            return "#f4cccc"
        elif v < t2:
            return "#fce5cd"
        elif v < t3:
            return "#fff2cc"
        elif v < t4:
            return "#b7e1cd"
        else:
            return "#77c38d"

    for i, col in enumerate(df.columns):
        table[(0, i)].get_text().set_fontsize(10)
        table[(0, i)].set_facecolor("#d9d2e9")
        table[(0, i)].get_text().set_color("black")
        table[(0, i)].get_text().set_weight("bold")

        for j in range(len(df)):
            is_avg_row = (df.iloc[j]["ФИО"] == "СРЕДНЕЕ")
            val = df.iloc[j][col]
            bg_color = "#ffffff"

            if is_avg_row:
                bg_color = "#d9d2e9"
                if col == usp_col:
                    bg_color = "#fff2cc"
            else:
                row_usp_val = pd.to_numeric(df.iloc[j].get(usp_col), errors="coerce")

                if col == "ФИО" or col == usp_col:
                    bg_color = get_usp_color(row_usp_val)
                elif col in ["Рабочее время", "Время перерывов", "Категория"]:
                    bg_color = "#ffffff"
                elif col in pct_cols + numeric_cols and col in norm_dict:
                    v_num = pd.to_numeric(val, errors="coerce")
                    if pd.notnull(v_num):
                        bg_color = mcolors.to_hex(rwg_cmap(norm_dict[col](v_num)))

            table[(j + 1, i)].set_facecolor(bg_color)

        if col == "ФИО":
            for j in range(len(df) + 1):
                cell_text = table[(j, i)].get_text()
                cell_text.set_horizontalalignment("left")

    buf = io.BytesIO()
    plt.savefig(buf, format="jpeg", bbox_inches="tight", dpi=250)
    buf.seek(0)
    plt.close()
    return buf

async def process_comparative_report(message: Message, df: pd.DataFrame, is_weekly: bool):
    df.columns = [str(c).strip() for c in df.columns]
    rename_dict = {}
    for col in df.columns:
        if "период" in col.lower() or "зп" in col.lower():
            rename_dict[col] = "ЗП"
    df.rename(columns=rename_dict, inplace=True)

    df["Группа"] = df["Ответственный"].astype(str).str.extract(r"(\d{2})")
    df = df.dropna(subset=["Группа"])

    def time_to_seconds(t_str):
        if pd.isnull(t_str):
            return 0
        v = str(t_str).strip()
        try:
            if v.startswith("1900-01-"):
                d_str, time_part = v.split(" ")
                days = int(d_str.split("-")[2])
                h, m, s = map(float, time_part.split(":"))
                return days * 24 * 3600 + h * 3600 + m * 60 + s
            elif "day" in v:
                parts = v.split(" ")
                days = int(parts[0])
                h, m, s = map(float, parts[-1].split(":"))
                return days * 24 * 3600 + h * 3600 + m * 60 + s
            parts = v.split(":")
            if len(parts) >= 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        except Exception:
            pass
        return 0

    def format_seconds_to_time(seconds):
        if pd.isnull(seconds):
            return "0:00:00"
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = round(seconds % 60)
        if s == 60:
            s, m = 0, m + 1
        if m == 60:
            m, h = 0, h + 1
        return f"{h}:{m:02d}:{s:02d}"

    df["Рабочее_сек"] = df.get("Рабочее время", pd.Series([0] * len(df))).apply(time_to_seconds)
    df["Перерыв_сек"] = df.get("Время перерывов", pd.Series([0] * len(df))).apply(time_to_seconds)

    def clean_num(col_name):
        if col_name in df.columns:
            return pd.to_numeric(
                df[col_name].astype(str).str.replace(r"\s+", "", regex=True).str.replace(",", ".").str.replace("%", ""),
                errors="coerce",
            ).fillna(0)
        return pd.Series([0] * len(df))

    df["Успешные_num"] = clean_num("Успешные")
    df["Всего_num"] = clean_num("Всего")
    df["Недозвон_num"] = clean_num("Недозвон")
    df["Некор_num"] = clean_num("Некорректные") if "Некорректные" in df.columns else clean_num("Некор")
    df["Смен_num"] = clean_num("Смен")
    df["ЗП_num"] = clean_num("ЗП")
    df["У_раб_места_num"] = clean_num("% у рабочего места")
    if df["У_раб_места_num"].mean() < 1.5:
        df["У_раб_места_num"] *= 100

    grouped = df.groupby("Группа").agg(
        Смен=("Смен_num", "sum"),
        ОБРАБОТАНО=("Всего_num", "sum"),
        УСПЕШНЫЕ=("Успешные_num", "sum"),
        Недозвон=("Недозвон_num", "sum"),
        Некор=("Некор_num", "sum"),
        Рабочее_сек=("Рабочее_сек", "sum"),
        Перерыв_сек=("Перерыв_сек", "sum"),
        ЗП=("ЗП_num", "sum"),
        У_раб_места=("У_раб_места_num", "mean"),
    ).reset_index()

    if grouped["Смен"].sum() == 0:
        grouped["Смен"] = grouped["Группа"].map(df.groupby("Группа").size())

    grouped["CR%"] = (grouped["УСПЕШНЫЕ"] / (grouped["ОБРАБОТАНО"] - grouped["Недозвон"] - grouped["Некор"]).replace(0, 1)) * 100
    grouped["ЗАЯВОК НА ОП"] = grouped["ОБРАБОТАНО"] / grouped["Смен"].replace(0, 1)
    grouped["УСПЕШЕК НА ОП"] = grouped["УСПЕШНЫЕ"] / grouped["Смен"].replace(0, 1)
    grouped["Продуктивное_сек_оп"] = grouped["Рабочее_сек"] / grouped["Смен"].replace(0, 1)
    grouped["Перерыв_сек_оп"] = grouped["Перерыв_сек"] / grouped["Смен"].replace(0, 1)
    grouped["% ДОЗВОНА"] = ((grouped["ОБРАБОТАНО"] - grouped["Недозвон"]) / grouped["ОБРАБОТАНО"].replace(0, 1)) * 100
    grouped["ОПЛАТА"] = grouped["ЗП"]
    grouped["ОПЛАТА НА ОП"] = grouped["ОПЛАТА"] / grouped["Смен"].replace(0, 1)

    final_df = pd.DataFrame()
    final_df["Группа"] = grouped["Группа"]
    final_df["CR%"] = grouped["CR%"].apply(lambda x: f"{x:.2f}%")
    final_df["Смен"] = grouped["Смен"].astype(int)
    final_df["Обрабо\n-тано"] = grouped["ОБРАБОТАНО"].astype(int)
    final_df["Заявок\nна ОП"] = grouped["ЗАЯВОК НА ОП"].apply(lambda x: f"{x:.2f}")
    final_df["Успеш\n-ные"] = grouped["УСПЕШНЫЕ"].astype(int)
    final_df["Успешек\nна ОП"] = grouped["УСПЕШЕК НА ОП"].apply(lambda x: f"{x:.2f}")
    final_df["Прод. время\nна ОП"] = grouped["Продуктивное_сек_оп"].apply(format_seconds_to_time)
    final_df["Перерывы\nна ОП"] = grouped["Перерыв_сек_оп"].apply(format_seconds_to_time)
    final_df["% у раб.\nместа"] = grouped["У_раб_места"].apply(lambda x: f"{x:.2f}%")
    final_df["% дозвона"] = grouped["% ДОЗВОНА"].apply(lambda x: f"{x:.2f}%")
    final_df["Оплата"] = grouped["ОПЛАТА"].apply(lambda x: f"{x:.2f}")
    final_df["Оплата\nна ОП"] = grouped["ОПЛАТА НА ОП"].apply(lambda x: f"{x:.2f}")

    total_smen = grouped["Смен"].sum()
    total_obrabotano = grouped["ОБРАБОТАНО"].sum()
    total_uspeshnye = grouped["УСПЕШНЫЕ"].sum()
    total_nedozvon = grouped["Недозвон"].sum()
    total_nekor = grouped["Некор"].sum()
    total_rabochee_sek = grouped["Рабочее_сек"].sum()
    total_pereryv_sek = grouped["Перерыв_сек"].sum()
    total_zp = grouped["ЗП"].sum()

    total_cr = (total_uspeshnye / (total_obrabotano - total_nedozvon - total_nekor) * 100) if (total_obrabotano - total_nedozvon - total_nekor) > 0 else 0
    total_zayavok_op = total_obrabotano / total_smen if total_smen > 0 else 0
    total_uspeshek_op = total_uspeshnye / total_smen if total_smen > 0 else 0
    total_prod_op = total_rabochee_sek / total_smen if total_smen > 0 else 0
    total_pereryv_op = total_pereryv_sek / total_smen if total_smen > 0 else 0
    total_rab_mesto = grouped["У_раб_места"].mean()
    total_dozvon = ((total_obrabotano - total_nedozvon) / total_obrabotano * 100) if total_obrabotano > 0 else 0
    total_oplata_op = total_zp / total_smen if total_smen > 0 else 0

    itogo_row = {
        "Группа": "ИТОГО",
        "CR%": f"{total_cr:.2f}%",
        "Смен": int(total_smen),
        "Обрабо\n-тано": int(total_obrabotano),
        "Заявок\nна ОП": f"{total_zayavok_op:.2f}",
        "Успеш\n-ные": int(total_uspeshnye),
        "Успешек\nна ОП": f"{total_uspeshek_op:.2f}",
        "Прод. время\nна ОП": format_seconds_to_time(total_prod_op),
        "Перерывы\nна ОП": format_seconds_to_time(total_pereryv_op),
        "% у раб.\nместа": f"{total_rab_mesto:.2f}%",
        "% дозвона": f"{total_dozvon:.2f}%",
        "Оплата": f"{total_zp:.2f}",
        "Оплата\nна ОП": f"{total_oplata_op:.2f}",
    }
    final_df = pd.concat([pd.DataFrame([itogo_row]), final_df], ignore_index=True)

    fig, ax = plt.subplots(figsize=(24, len(final_df) * 0.5 + 1.5))
    ax.axis("off")
    cols_count = len(final_df.columns)
    col_widths = [0.06] + [0.94 / (cols_count - 1)] * (cols_count - 1)

    table = ax.table(cellText=final_df.values, colLabels=final_df.columns, loc="center", cellLoc="center", colWidths=col_widths)
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1.2, 2.4)

    rwg_cmap = mcolors.LinearSegmentedColormap.from_list("rwg", ["#f4cccc", "#ffffff", "#77c38d"])
    target_cols = {"CR%": "CR%", "Прод. время\nна ОП": "Продуктивное_сек_оп", "Оплата\nна ОП": "ОПЛАТА НА ОП"}
    norms = {}
    for final_col, raw_col in target_cols.items():
        vals = grouped[raw_col].dropna()
        if not vals.empty and vals.max() > vals.min():
            norms[final_col] = mcolors.Normalize(vmin=vals.min(), vmax=vals.max())
        else:
            norms[final_col] = None

    for i, col_name in enumerate(final_df.columns):
        table[(0, i)].set_facecolor("#6aa84f")
        table[(0, i)].get_text().set_color("white")
        table[(0, i)].get_text().set_weight("bold")
        table[(0, i)].get_text().set_fontsize(10)
        table[(1, i)].set_facecolor("#b6d7a8")
        table[(1, i)].get_text().set_weight("bold")
        for j in range(2, len(final_df) + 1):
            bg_color = "#ffffff"
            idx = j - 2
            if col_name in target_cols:
                raw_col = target_cols[col_name]
                val = grouped.iloc[idx][raw_col]
                if pd.notnull(val) and norms[col_name] is not None:
                    bg_color = mcolors.to_hex(rwg_cmap(norms[col_name](val)))
            table[(j, i)].set_facecolor(bg_color)

    buf = io.BytesIO()
    plt.savefig(buf, format="jpeg", bbox_inches="tight", dpi=250)
    buf.seek(0)
    plt.close()
    await message.answer_photo(
        photo=BufferedInputFile(buf.read(), filename="comp.jpg"),
        caption=f"Сравнительный {'(Неделя)' if is_weekly else '(День)'}",
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
