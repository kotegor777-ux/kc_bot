import io
import asyncio
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandStart

BOT_TOKEN = "8706677874:AAHCELGsaHKGU52inrRYx9YOX9MdLG_660A"
bot = Bot(token=BOT_Token)
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
    waiting_for_gp_average = State()

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
        session = user_sessions.get(message.from_user.id, {})
        session["shtat"] = shtat
        session["smena"] = smena
        await message.answer("Введите среднее (Конва) по ГП (например: 4.92):")
        await state.set_state(ReportFSM.waiting_for_gp_average)
    except ValueError:
        await message.answer("Ошибка формата. Введите два числа через пробел:")

@dp.message(ReportFSM.waiting_for_gp_average)
async def handle_gp_average(message: Message, state: FSMContext):
    session = user_sessions.get(message.from_user.id, {})
    gp_avg = message.text.strip()
    df_all = session.get("df")
    shtat = session.get("shtat")
    smena = session.get("smena")
    
    # Текстовый отчет
    text_report = generate_group_text(df_all, shtat, smena, gp_avg)
    await message.answer(text_report, parse_mode="HTML")
    
    # Скриншот таблицы
    df_47 = df_all[df_all['Ответственный'].astype(str).str.contains('47', na=False)].copy()
    columns_to_keep = ['ФИО', 'Рабочее время', 'Время перерывов', '% у рабочего места', 
                       '% дозвона до человека', '% успешных по дозвону', 'Успешные', 'Всего']
    if set(columns_to_keep).issubset(df_47.columns):
        df_47 = df_47[columns_to_keep]
        
    image_bytes = render_dataframe_to_image(df_47)
    await message.answer_photo(photo=BufferedInputFile(image_bytes.read(), filename="report.jpg"), caption="Срез по группе")
    await state.set_state(ReportFSM.waiting_for_report_type)

def time_to_seconds(t_str):
    try:
        parts = str(t_str).split(':')
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except:
        pass
    return 0

def format_seconds_to_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}:{m:02d}:{s:02d}"

def generate_group_text(df_all, shtat, smena, gp_avg):
    df = df_all[df_all['Ответственный'].astype(str).str.contains('47', na=False)].copy()
    if df.empty:
        return "Нет данных по 47 группе."

    def clean_pct(col):
        # Перевод долей из Excel в проценты (*100)
        res = pd.to_numeric(df[col].astype(str).str.replace('%', '').str.replace(',', '.'), errors='coerce')
        return res * 100 if res.mean() < 1.5 else res

    avg_usp_dozvon = clean_pct('% успешных по дозвону').mean()
    avg_dozvon = clean_pct('% дозвона до человека').mean()
    avg_rab_mesto = clean_pct('% у рабочего места').mean()
    avg_usp = pd.to_numeric(df['Успешные'], errors='coerce').mean()
    avg_vsego = pd.to_numeric(df['Всего'], errors='coerce').mean()
    
    fact_vyhod_count = pd.to_numeric(df['Смен'], errors='coerce').sum()
    plan_vyhod = (smena / shtat) * 100 if shtat > 0 else 0
    fact_vyhod = (fact_vyhod_count / shtat) * 100 if shtat > 0 else 0
    over_100_calls = len(df[pd.to_numeric(df['Всего'], errors='coerce') >= 100])

    total_seconds = df['Рабочее время'].apply(time_to_seconds).sum()
    avg_seconds = total_seconds / fact_vyhod_count if fact_vyhod_count > 0 else 0
    prod_hours_str = format_seconds_to_time(avg_seconds)

    return f"""
<b>КЦ УД 47 Солянка прочее</b>
% усп. по дозвону - <b>{avg_usp_dozvon:.2f}%</b>
% дозвон до человека - <b>{avg_dozvon:.0f}%</b>
% у рабочего места - <b>{avg_rab_mesto:.1f}</b>
Среднее количество усп: <b>{avg_usp:.2f}</b>
Заявок на оператора: <b>{avg_vsego:.2f}</b>
% выход план : <b>{plan_vyhod:.0f}%</b>
% выход факт: <b>{fact_vyhod:.0f}%</b>
КПП-{over_100_calls}/{int(fact_vyhod_count)}
От 100 ЗВ - <b>{over_100_calls}/{int(fact_vyhod_count)}</b>
Продуктивные часы: <b>{prod_hours_str}</b>

Конва по ГП: <b>{gp_avg}</b>
"""

def render_dataframe_to_image(df_original):
    df = df_original.copy()
    pct_cols = ['% у рабочего места', '% дозвона до человека', '% успешных по дозвону']
    numeric_cols = ['Успешные', 'Всего']

    for col in pct_cols:
        val = pd.to_numeric(df[col].astype(str).str.replace('%', '').str.replace(',', '.'), errors='coerce')
        df[col] = val * 100 if val.mean() < 1.5 else val
        
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Расчет строки СРЕДНЕЕ
    avg_row = {col: '' for col in df.columns}
    avg_row['ФИО'] = 'СРЕДНЕЕ'
    for col in pct_cols + numeric_cols:
        avg_row[col] = df[col].mean()
    
    df = pd.concat([df, pd.DataFrame([avg_row])], ignore_index=True)
    
    # Форматирование отображения
    display_df = df.copy()
    for col in pct_cols:
        display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) and x != '' else "")
    for col in numeric_cols:
        display_df[col] = display_df[col].apply(lambda x: f"{x:.0f}" if pd.notnull(x) and x != '' else "")

    fig, ax = plt.subplots(figsize=(15, len(df) * 0.4 + 1))
    ax.axis('off')

    table = ax.table(cellText=display_df.values, colLabels=display_df.columns, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.2, 1.6)

    # Тепловая карта и стилизация
    cmap = plt.get_cmap('RdYlGn')
    for i, col in enumerate(df.columns):
        if col in pct_cols + numeric_cols:
            vals = pd.to_numeric(df[col].iloc[:-1], errors='coerce').dropna()
            if not vals.empty:
                norm = mcolors.Normalize(vmin=vals.min(), vmax=vals.max())
                for j in range(len(df) - 1):
                    val = df.iloc[j][col]
                    if pd.notnull(val) and val != '':
                        table[(j+1, i)].set_facecolor(cmap(norm(float(val))))
        
        # Шапка
        table[(0, i)].set_facecolor("#4C566A")
        table[(0, i)].get_text().set_color("white")
        # Строка СРЕДНЕЕ (Фиолетовая)
        table[(len(df), i)].set_facecolor("#D8BFD8")

    buf = io.BytesIO()
    plt.savefig(buf, format='jpeg', bbox_inches='tight', dpi=150)
    buf.seek(0)
    plt.close()
    return buf

async def process_comparative_report(message: Message, df: pd.DataFrame, is_weekly: bool):
    # Логика сравнительного отчета остается без изменений
    df['Номер_Группы'] = df['Ответственный'].astype(str).str.extract(r'(\d{2})')
    grouped = df.groupby('Номер_Группы').agg(
        БАЗА=('Смен' if is_weekly else 'ФИО', 'sum' if is_weekly else 'count'), 
        ОБРАБОТАНО=('Всего', 'sum'), УСПЕШНЫЕ=('Успешные', 'sum'),
        НЕКОРРЕКТНЫЕ=('Некоректные', 'sum'), НЕДОЗВОН=('Недозвон', 'sum')
    ).reset_index()

    valid_calls = (grouped['ОБРАБОТАНО'] - grouped['НЕКОРРЕКТНЫЕ'] - grouped['НЕДОЗВОН'])
    grouped['CR%'] = (grouped['УСПЕШНЫЕ'] / valid_calls.replace(0, 1)) * 100
    grouped['ЗАЯВОК НА ЕД'] = grouped['ОБРАБОТАНО'] / grouped['БАЗА']
    
    grouped = grouped.round(2)
    fig, ax = plt.subplots(figsize=(10, len(grouped) * 0.4 + 1))
    ax.axis('off')
    table = ax.table(cellText=grouped.values, colLabels=grouped.columns, loc='center', cellLoc='center')
    table.scale(1.2, 1.5)
    
    for i in range(len(grouped.columns)):
        table[(0, i)].set_facecolor("#4C566A")
        table[(0, i)].get_text().set_color("white")
        
    buf = io.BytesIO()
    plt.savefig(buf, format='jpeg', bbox_inches='tight')
    buf.seek(0)
    plt.close()
    
    await message.answer_photo(photo=BufferedInputFile(buf.read(), filename="comp.jpg"), caption=f"Сравнительный {'(Неделя)' if is_weekly else '(День)'}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
