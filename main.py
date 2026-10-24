import io
import asyncio
import pandas as pd
import matplotlib.pyplot as plt
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandStart

BOT_TOKEN = "8706677874:AAHCELGsaHKGU52inrRYx9YOX9MdLG_660A"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Отчет в группу 2ч"), KeyboardButton(text="Сравнительный по ГП")],
        [KeyboardButton(text="Отчет в группу неделя"), KeyboardButton(text="Сравнительный по ГП неделя")]
    ],
    resize_keyboard=True
)

class ReportFSM(StatesGroup):
    waiting_for_report_type = State()
    waiting_for_file = State()
    waiting_for_staff_numbers = State()

user_sessions = {}

@dp.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    await message.answer("Выберите тип отчета:", reply_markup=main_kb)
    await state.set_state(ReportFSM.waiting_for_report_type)

@dp.message(ReportFSM.waiting_for_report_type, F.text.in_(["Отчет в группу 2ч", "Сравнительный по ГП", "Отчет в группу неделя", "Сравнительный по ГП неделя"]))
async def choose_report_type(message: Message, state: FSMContext):
    user_sessions[message.from_user.id] = {"type": message.text}
    await message.answer(f"Жду файл Excel для: {message.text}")
    await state.set_state(ReportFSM.waiting_for_file)

@dp.message(ReportFSM.waiting_for_file, F.document)
async def handle_file(message: Message, state: FSMContext):
    file = await bot.get_file(message.document.file_id)
    downloaded_file = await bot.download_file(file.file_path)
    df = pd.read_excel(io.BytesIO(downloaded_file.read()))
    
    session = user_sessions.get(message.from_user.id, {})
    session["df"] = df
    report_type = session.get("type")
    
    if "Сравнительный" in report_type:
        await process_comparative_report(message, df, "неделя" in report_type)
        await state.set_state(ReportFSM.waiting_for_report_type)
    else:
        await message.answer("Введите Штат и Кол-во человек (или смен) через пробел (например: 24 16):")
        await state.set_state(ReportFSM.waiting_for_staff_numbers)

@dp.message(ReportFSM.waiting_for_staff_numbers)
async def handle_staff_numbers(message: Message, state: FSMContext):
    try:
        shtat, smena = map(int, message.text.split())
    except ValueError:
        await message.answer("Ошибка формата. Введите два числа через пробел:")
        return

    session = user_sessions.get(message.from_user.id, {})
    df_all = session.get("df")
    report_type = session.get("type")
    is_weekly = "неделя" in report_type
    
    text_report = generate_group_text(df_all, shtat, smena, is_weekly)
    await message.answer(text_report, parse_mode="HTML")
    
    df_47 = df_all[df_all['Ответственный'].astype(str).str.contains('47', na=False)].copy()
    columns_to_keep = ['ФИО', 'Рабочее время', 'Время перерывов', '% у рабочего места', 
                       '% дозвона до человека', '% успешных по дозвону', 'Успешные', 'Всего']
    df_47 = df_47[columns_to_keep] if set(columns_to_keep).issubset(df_47.columns) else df_47
    
    image_bytes = render_dataframe_to_image(df_47)
    await message.answer_photo(photo=BufferedInputFile(image_bytes.read(), filename="report.jpg"), caption="Срез по группе")
    await state.set_state(ReportFSM.waiting_for_report_type)

def generate_group_text(df_all, shtat, smena, is_weekly):
    df = df_all[df_all['Ответственный'].astype(str).str.contains('47', na=False)]
    if df.empty:
        return "Нет данных по 47 группе."

    total_usp_all = pd.to_numeric(df_all['Успешные'], errors='coerce').sum()
    total_calls_all = pd.to_numeric(df_all['Всего'], errors='coerce').sum()
    konva_gp = (total_usp_all / total_calls_all) * 100 if total_calls_all > 0 else 0

    def clean_pct(col):
        return pd.to_numeric(df[col].astype(str).str.replace('%', '').str.replace(',', '.'), errors='coerce')

    avg_usp_dozvon = clean_pct('% успешных по дозвону').mean()
    avg_dozvon = clean_pct('% дозвона до человека').mean()
    avg_rab_mesto = clean_pct('% у рабочего места').mean()
    avg_usp = pd.to_numeric(df['Успешные'], errors='coerce').mean()
    avg_vsego = pd.to_numeric(df['Всего'], errors='coerce').mean()
    
    fact_vyhod_count = pd.to_numeric(df['Смен'], errors='coerce').sum()
    plan_vyhod = (smena / shtat) * 100 if shtat > 0 else 0
    fact_vyhod = (fact_vyhod_count / shtat) * 100 if shtat > 0 else 0
    over_100_calls = len(df[pd.to_numeric(df['Всего'], errors='coerce') >= 100])

    return f"""
<b>КЦ УД 47 ({"Неделя" if is_weekly else "Смена"})</b>
Штат: <b>{shtat}</b> | Кол-во: <b>{smena}</b>

▫️ % усп. по дозвону: <b>{avg_usp_dozvon:.2f}%</b>
▫️ % дозвон до человека: <b>{avg_dozvon:.0f}%</b>
▫️ % у рабочего места: <b>{avg_rab_mesto:.1f}%</b>
▫️ Среднее количество усп: <b>{avg_usp:.2f}</b>
▫️ Заявок на оператора: <b>{avg_vsego:.2f}</b>
▫️ % выход план : <b>{plan_vyhod:.0f}%</b>
▫️ % выход факт: <b>{fact_vyhod:.0f}%</b>
▫️ КПП-{over_100_calls}/{int(fact_vyhod_count)}
▫️ От 100 ЗВ: <b>{over_100_calls}/{int(fact_vyhod_count)}</b>

🔵 Конва по ГП: <b>{konva_gp:.2f}%</b>
"""

async def process_comparative_report(message: Message, df: pd.DataFrame, is_weekly: bool):
    df['Номер_Группы'] = df['Ответственный'].astype(str).str.extract(r'(\d{2})')
    
    if is_weekly:
        grouped = df.groupby('Номер_Группы').agg(
            БАЗА=('Смен', 'sum'), ОБРАБОТАНО=('Всего', 'sum'), 
            УСПЕШНЫЕ=('Успешные', 'sum'), ОПЛАТА=('За период', 'sum'),
            НЕКОРРЕКТНЫЕ=('Некоректные', 'sum'), НЕДОЗВОН=('Недозвон', 'sum')
        ).reset_index()
    else:
        grouped = df.groupby('Номер_Группы').agg(
            БАЗА=('ФИО', 'count'), ОБРАБОТАНО=('Всего', 'sum'), 
            УСПЕШНЫЕ=('Успешные', 'sum'), ОПЛАТА=('За период', 'sum'),
            НЕКОРРЕКТНЫЕ=('Некоректные', 'sum'), НЕДОЗВОН=('Недозвон', 'sum')
        ).reset_index()

    valid_calls = (grouped['ОБРАБОТАНО'] - grouped['НЕКОРРЕКТНЫЕ'] - grouped['НЕДОЗВОН'])
    grouped['CR%'] = (grouped['УСПЕШНЫЕ'] / valid_calls.replace(0, 1)) * 100
    grouped['ЗАЯВОК НА ЕД'] = grouped['ОБРАБОТАНО'] / grouped['БАЗА']
    
    grouped = grouped.round(2)
    image_bytes = render_dataframe_to_image(grouped)
    await message.answer_photo(photo=BufferedInputFile(image_bytes.read(), filename="comp.jpg"), caption=f"Сравнительный {'(Неделя)' if is_weekly else '(День)'}")

def render_dataframe_to_image(df):
    fig, ax = plt.subplots(figsize=(12, len(df) * 0.4 + 1))
    ax.axis('off')
    ax.axis('tight')

    table = ax.table(cellText=df.values, colLabels=df.columns, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.2, 1.5)

    for i in range(len(df.columns)):
        table[(0, i)].set_facecolor("#4C566A")
        table[(0, i)].get_text().set_color("white")

    buf = io.BytesIO()
    plt.savefig(buf, format='jpeg', bbox_inches='tight', dpi=150)
    buf.seek(0)
    plt.close()
    return buf

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
