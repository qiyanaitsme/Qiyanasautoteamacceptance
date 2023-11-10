import sqlite3
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# Установите свой tguserid и token здесь
admin_id = ТУТ АЙДИ
token_api = "ТОКЕН"

bot = Bot(token=token_api)
dp = Dispatcher(bot)

conn = sqlite3.connect("applications.db")
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        forum_link TEXT NOT NULL,
        experienced INTEGER NOT NULL,
        daily_time INTEGER NOT NULL,
        has_experience TEXT NOT NULL,
        skills TEXT NOT NULL,
        status TEXT DEFAULT 'Pending'
    )
""")
conn.commit()

blacklist_conn = sqlite3.connect("blocked.db")
blacklist_cursor = blacklist_conn.cursor()

blacklist_cursor.execute("""
    CREATE TABLE IF NOT EXISTS blacklist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE
    )
""")
blacklist_conn.commit()

questions = [
    "1. Ссылка на форум.",
    "2. Занимались ли Вы этим ранее?",
    "3. Сколько времени в день Вы будете заниматься этим?",
    "4. Имеете ли Вы опыт?",
    "5. Что Вы вообще умеете?"
]

user_data = {}

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    user_id = message.from_user.id
    if user_id == admin_id:
        await message.answer("Приветствую, админ. Не хотите ознакомиться с потенциальными работниками?")
        await send_admin_applications(admin_id)
    else:
        if is_user_blocked(user_id):
            await message.answer("Вам уже отказали. Не пытайтесь отправить заявку еще раз.")
        elif is_application_submitted(user_id):
            await message.answer("Вы уже отправили заявку.")
        else:
            await message.answer("Приветствую. Заполните форму ниже, чтобы подать заявку на вступление.")
            await ask_question(user_id)

def is_user_blocked(user_id: int) -> bool:
    blacklist_cursor.execute("SELECT COUNT(*) FROM blacklist WHERE user_id=?", (user_id,))
    count = blacklist_cursor.fetchone()[0]
    return count > 0

def is_application_submitted(user_id: int) -> bool:
    cursor.execute("SELECT COUNT(*) FROM applications WHERE user_id=?", (user_id,))
    count = cursor.fetchone()[0]
    return count > 0

async def ask_question(user_id: int):
    current_step = user_data.get(user_id, 0)
    if current_step < len(questions):
        await bot.send_message(user_id, questions[current_step])
    else:
        await process_application(user_id)

async def process_answer(message: types.Message):
    user_id = message.from_user.id
    current_step = user_data.get(user_id, 0)

    if current_step < len(questions):
        question = questions[current_step]
        answer = message.text

        user_data[user_id] = current_step + 1
        user_data[question] = answer

        await ask_question(user_id)
    else:
        await process_application(user_id)

async def process_application(user_id: int):
    if len(user_data) == len(questions) + 1:
        forum_link = user_data.get(questions[0])
        experienced = user_data.get(questions[1])
        daily_time = user_data.get(questions[2])
        has_experience = user_data.get(questions[3])
        skills = user_data.get(questions[4])

        cursor.execute(
            "INSERT INTO applications (user_id, forum_link, experienced, daily_time, has_experience, skills) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, forum_link, experienced, daily_time, has_experience, skills))
        conn.commit()

        await send_admin_applications(user_id)
    else:
        await ask_question(user_id)

async def send_admin_applications(chat_id: int, applicant_id: int = None):
    applications = get_all_applications()
    if applications:
        for application in applications:
            application_id, applicant_id, forum_link, experienced, daily_time, has_experience, skills, status = application
            text = f"Заявка #{application_id}\n" \
                   f"Пользователь {applicant_id}:\n" \
                   f"Форум: {forum_link}\n" \
                   f"Занимались ранее: {experienced}\n" \
                   f"Время в день: {daily_time}\n" \
                   f"Опыт: {has_experience}\n" \
                   f"Навыки: {skills}\n" \
                   f"Статус: {status}\n\n"

            if chat_id == admin_id:
                keyboard = InlineKeyboardMarkup(row_width=2)
                approve_button = InlineKeyboardButton("Принять", callback_data=f"approve_{applicant_id}")
                reject_button = InlineKeyboardButton("Отклонить", callback_data=f"reject_{applicant_id}")
                keyboard.add(approve_button, reject_button)
                await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)
            else:
                await bot.send_message(chat_id=chat_id, text=text)

    if chat_id == admin_id:
        keyboard = InlineKeyboardMarkup(row_width=2)
        all_applications_button = InlineKeyboardButton("Все заявки", callback_data="view_all")
        accepted_applications_button = InlineKeyboardButton("Принятые заявки", callback_data="view_accepted")
        rejected_applications_button = InlineKeyboardButton("Отклоненные заявки", callback_data="view_rejected")
        user_count_button = InlineKeyboardButton("Количество пользователей", callback_data="view_user_count")
        keyboard.add(all_applications_button, accepted_applications_button, rejected_applications_button, user_count_button)

        await bot.send_message(chat_id=chat_id, text="Пожалуйста, примите решение:", reply_markup=keyboard)

@dp.message_handler(content_types=types.ContentTypes.TEXT)
async def handle_message(message: types.Message):
    await process_answer(message)

@dp.message_handler(commands=['admin'])
async def admin_command(message: types.Message):
    if message.from_user.id != admin_id:
        await message.answer("У вас нет доступа к админ-панели.")
        return

    await message.answer("Выберите действие:", reply_markup=get_admin_keyboard())

def get_admin_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    all_applications_button = InlineKeyboardButton("Все заявки", callback_data="view_all")
    accepted_applications_button = InlineKeyboardButton("Принятые заявки", callback_data="view_accepted")
    rejected_applications_button = InlineKeyboardButton("Отклоненные заявки", callback_data="view_rejected")
    user_count_button = InlineKeyboardButton("Количество пользователей", callback_data="view_user_count")
    keyboard.add(all_applications_button, accepted_applications_button, rejected_applications_button, user_count_button)
    return keyboard

def is_user_admin(user_id: int) -> bool:
    return user_id == admin_id

@dp.callback_query_handler(lambda c: True)
async def handle_admin_callback_query(query: types.CallbackQuery):
    if query.from_user.id != admin_id:
        await bot.answer_callback_query(query.id, "У вас нет доступа к админ-панели.")
        return

    action = query.data

    if action == "view_all":
        applications = get_all_applications()
        await bot.send_message(admin_id, "Список всех заявок:")
        if applications:
            for application in applications:
                application_id, applicant_id, forum_link, experienced, daily_time, has_experience, skills, status = application
                text = f"Заявка #{application_id}\n" \
                       f"Пользователь {applicant_id}:\n" \
                       f"Форум: {forum_link}\n" \
                       f"Занимались ранее: {experienced}\n" \
                       f"Время в день: {daily_time}\n" \
                       f"Опыт: {has_experience}\n" \
                       f"Навыки: {skills}\n" \
                       f"Статус: {status}\n\n"
                keyboard = InlineKeyboardMarkup(row_width=2)
                approve_button = InlineKeyboardButton("Принять", callback_data=f"approve_{applicant_id}")
                reject_button = InlineKeyboardButton("Отклонить", callback_data=f"reject_{applicant_id}")
                keyboard.add(approve_button, reject_button)
                await bot.send_message(admin_id, text, reply_markup=keyboard)
        else:
            await bot.send_message(admin_id, "Заявок пока нет.")

    elif action == "view_accepted":
        applications = get_accepted_applications()
        await bot.send_message(admin_id, "Список принятых заявок:")
        if applications:
            for application in applications:
                application_id, applicant_id, forum_link, experienced, daily_time, has_experience, skills, status = application
                text = f"Заявка #{application_id}\n" \
                       f"Пользователь {applicant_id}:\n" \
                       f"Форум: {forum_link}\n" \
                       f"Занимались ранее: {experienced}\n" \
                       f"Время в день: {daily_time}\n" \
                       f"Опыт: {has_experience}\n" \
                       f"Навыки: {skills}\n" \
                       f"Статус: {status}\n\n"
                await bot.send_message(admin_id, text)
        else:
            await bot.send_message(admin_id, "Принятых заявок пока нет.")

    elif action == "view_rejected":
        applications = get_rejected_applications()
        await bot.send_message(admin_id, "Список отклоненных заявок:")
        if applications:
            for application in applications:
                application_id, applicant_id, forum_link, experienced, daily_time, has_experience, skills, status = application
                text = f"Заявка #{application_id}\n" \
                       f"Пользователь {applicant_id}:\n" \
                       f"Форум: {forum_link}\n" \
                       f"Занимались ранее: {experienced}\n" \
                       f"Время в день: {daily_time}\n" \
                       f"Опыт: {has_experience}\n" \
                       f"Навыки: {skills}\n" \
                       f"Статус: {status}\n\n"
                await bot.send_message(admin_id, text)
        else:
            await bot.send_message(admin_id, "Отклоненных заявок пока нет.")

    elif action.startswith("approve"):
        user_id = int(action.split("_")[1])
        if is_user_admin(admin_id):
            cursor.execute("UPDATE applications SET status='Accepted' WHERE user_id=?", (user_id,))
            conn.commit()
            await bot.send_message(user_id, "Ваша заявка на вступление в команду одобрена.")
        else:
            await bot.answer_callback_query(query.id, "У вас нет доступа к этой функции.")

    elif action.startswith("reject"):
        user_id = int(action.split("_")[1])
        if is_user_admin(admin_id):
            cursor.execute("UPDATE applications SET status='Rejected' WHERE user_id=?", (user_id,))
            conn.commit()
            await bot.send_message(user_id, "Ваша заявка на вступление в команду отклонена.")
            blacklist_cursor.execute("INSERT INTO blacklist (user_id) VALUES (?)", (user_id,))
            blacklist_conn.commit()
        else:
            await bot.answer_callback_query(query.id, "У вас нет доступа к этой функции.")

    elif action == "view_user_count":
        user_count = get_user_count()
        await bot.send_message(admin_id, f"Количество пользователей в боте: {user_count}")

    await bot.answer_callback_query(query.id)

def get_all_applications():
    cursor.execute("SELECT * FROM applications")
    applications = cursor.fetchall()
    return applications

def get_accepted_applications():
    cursor.execute("SELECT * FROM applications WHERE status='Accepted'")
    applications = cursor.fetchall()
    return applications

def get_rejected_applications():
    cursor.execute("SELECT * FROM applications WHERE status='Rejected'")
    applications = cursor.fetchall()
    return applications

def get_user_count():
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM applications")
    user_count = cursor.fetchone()[0]
    return user_count

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)