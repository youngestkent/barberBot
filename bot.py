import logging
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define conversation states
(START, CHOOSE_SERVICE, CHOOSE_DATE, CHOOSE_TIME, PROVIDE_CONTACT, CONFIRM_BOOKING, 
 ADMIN_MENU, ADMIN_VIEW_BOOKINGS, ADMIN_ADD_DATES, ADMIN_REMOVE_DATES) = range(10)

# Admin phone number for authentication
ADMIN_PHONE = '+79252083325'  # Replace this with your actual admin phone number when needed

# Service types with emojis
SERVICES = {
    '💇‍♂️ Мужская стрижка': 'Men\'s Haircut',
    '💇‍♀️ Женская стрижка': 'Women\'s Haircut',
    '👦 Детская стрижка': 'Children\'s Haircut',
    '🎨 Окрашивание': 'Hair Coloring'
}

# Database initialization
def init_db():
    conn = sqlite3.connect('barber_shop.db')
    cursor = conn.cursor()
    
    # Create clients table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY,
        user_id INTEGER UNIQUE,
        name TEXT,
        phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create appointments table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY,
        client_id INTEGER,
        service TEXT,
        date TEXT,
        time TEXT,
        status TEXT DEFAULT 'scheduled',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (client_id) REFERENCES clients (id)
    )
    ''')
    
    # Create working_days table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS working_days (
        id INTEGER PRIMARY KEY,
        date TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

# Helper functions for database operations
def save_client(user_id, name, phone):
    conn = sqlite3.connect('barber_shop.db')
    cursor = conn.cursor()
    
    cursor.execute('INSERT OR REPLACE INTO clients (user_id, name, phone) VALUES (?, ?, ?)',
                  (user_id, name, phone))
    
    client_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return client_id

def get_client_id(user_id):
    conn = sqlite3.connect('barber_shop.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT id FROM clients WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    conn.close()
    
    return result[0] if result else None

def save_appointment(client_id, service, date, time):
    conn = sqlite3.connect('barber_shop.db')
    cursor = conn.cursor()
    
    cursor.execute('INSERT INTO appointments (client_id, service, date, time) VALUES (?, ?, ?, ?)',
                  (client_id, service, date, time))
    
    appointment_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return appointment_id

def get_working_days():
    conn = sqlite3.connect('barber_shop.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT date FROM working_days ORDER BY date')
    dates = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    
    return dates

def add_working_day(date):
    conn = sqlite3.connect('barber_shop.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('INSERT INTO working_days (date) VALUES (?)', (date,))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    
    conn.close()
    return success

def remove_working_day(date):
    conn = sqlite3.connect('barber_shop.db')
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM working_days WHERE date = ?', (date,))
    deleted = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return deleted

def get_available_times(date):
    # Default time slots
    all_times = ['10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00', '18:00']
    
    # Get booked times for the date
    conn = sqlite3.connect('barber_shop.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT time FROM appointments WHERE date = ? AND status = "scheduled"', (date,))
    booked_times = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    
    # Filter out booked times
    available_times = [time for time in all_times if time not in booked_times]
    
    return available_times

def get_all_appointments():
    conn = sqlite3.connect('barber_shop.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT a.id, c.name, c.phone, a.service, a.date, a.time, a.status 
    FROM appointments a 
    JOIN clients c ON a.client_id = c.id 
    WHERE a.status = "scheduled" 
    ORDER BY a.date, a.time
    ''')
    
    appointments = cursor.fetchall()
    conn.close()
    
    return appointments

def mark_appointment_completed(appointment_id):
    conn = sqlite3.connect('barber_shop.db')
    cursor = conn.cursor()
    
    cursor.execute('UPDATE appointments SET status = "completed" WHERE id = ?', (appointment_id,))
    
    conn.commit()
    conn.close()

# Calendar helper functions
def generate_calendar_markup(year, month):
    """Generate an inline keyboard markup for a calendar"""
    calendar_markup = []
    
    # Add month and year as header
    month_names = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 
                  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
    header = [InlineKeyboardButton(f"📅 {month_names[month-1]} {year}", callback_data="ignore")]
    calendar_markup.append(header)
    
    # Add navigation buttons
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    navigation = [
        InlineKeyboardButton("◀️", callback_data=f"calendar:{prev_year}:{prev_month}"),
        InlineKeyboardButton("▶️", callback_data=f"calendar:{next_year}:{next_month}")
    ]
    calendar_markup.append(navigation)
    
    # Add weekday headers
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    calendar_markup.append([InlineKeyboardButton(day, callback_data="ignore") for day in weekdays])
    
    # Get the first day of the month and the number of days
    first_day = datetime(year, month, 1)
    if month == 12:
        last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1) - timedelta(days=1)
    
    num_days = last_day.day
    
    # Get the weekday of the first day (0 is Monday in our display)
    first_weekday = first_day.weekday()
    
    # Create calendar grid
    current_date = datetime.now().date()
    day = 1
    for week in range(6):  # Maximum 6 weeks in a month
        week_buttons = []
        for weekday in range(7):  # 7 days in a week
            if (week == 0 and weekday < first_weekday) or day > num_days:
                # Empty cell
                week_buttons.append(InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                # Date cell
                date_str = f"{year}-{month:02d}-{day:02d}"
                # Only allow selecting current or future dates
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                
                if date_obj >= current_date:
                    week_buttons.append(InlineKeyboardButton(f"{day}", callback_data=f"date:{date_str}"))
                else:
                    week_buttons.append(InlineKeyboardButton(f"{day}", callback_data="ignore"))
                day += 1
        
        if any(btn.text != " " for btn in week_buttons):  # Only add non-empty weeks
            calendar_markup.append(week_buttons)
    
    # Add back button
    calendar_markup.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")])
    
    return InlineKeyboardMarkup(calendar_markup)

# Command handlers
async def start(update: Update, context: CallbackContext) -> int:
    user = update.effective_user
    context.user_data.clear()
    
    # Check if user is admin by requesting phone number
    keyboard = [
        [KeyboardButton(text="📱 Поделиться номером телефона", request_contact=True)]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    await update.message.reply_text(
        f"Здравствуйте, {user.first_name}! Добро пожаловать в бот записи к парикмахеру. "
        f"Пожалуйста, поделитесь своим номером телефона для продолжения.",
        reply_markup=reply_markup
    )
    
    return PROVIDE_CONTACT

async def handle_contact(update: Update, context: CallbackContext) -> int:
    user = update.effective_user
    contact = update.message.contact
    phone = contact.phone_number
    
    # Save client info
    client_id = save_client(user.id, user.first_name, phone)
    context.user_data['client_id'] = client_id
    context.user_data['phone'] = phone
    
    # Store the last message ID for future edits
    context.user_data['last_message_id'] = update.message.message_id
    
    # Check if user is admin
    if phone == ADMIN_PHONE:
        # Create admin menu with persistent keyboard
        keyboard = [
            ["📋 Просмотр записей"],
            ["➕ Добавить рабочие дни"],
            ["➖ Удалить рабочие дни"],
            ["🚪 Выход из админ-панели"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Send a new message with the admin menu
        message = await update.message.reply_text(
            "Вы вошли как администратор. Выберите действие:",
            reply_markup=reply_markup
        )
        context.user_data['last_message_id'] = message.message_id
        return ADMIN_MENU
    else:
        # Regular client flow with persistent keyboard
        keyboard = []
        for service in SERVICES.keys():
            keyboard.append([service])
        keyboard.append(["❌ Отмена"])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Send a new message with the service selection menu
        message = await update.message.reply_text(
            "Выберите услугу:",
            reply_markup=reply_markup
        )
        context.user_data['last_message_id'] = message.message_id
        return CHOOSE_SERVICE

async def choose_service(update: Update, context: CallbackContext) -> int:
    # Handle text input from ReplyKeyboardMarkup
    if update.message:
        service = update.message.text
        
        # Check if the user wants to cancel
        if service == "❌ Отмена":
            await update.message.reply_text("Запись отменена.", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
            
        # Check if the service is valid
        if service not in SERVICES.keys():
            # If not a valid service, ask again
            keyboard = []
            for service_key in SERVICES.keys():
                keyboard.append([service_key])
            keyboard.append(["❌ Отмена"])
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                "Пожалуйста, выберите услугу из предложенных вариантов:",
                reply_markup=reply_markup
            )
            return CHOOSE_SERVICE
    # For backward compatibility, still handle callback queries
    else:
        query = update.callback_query
        await query.answer()
        service = query.data
        
    context.user_data['service'] = service
    
    # Get available dates
    available_dates = get_working_days()
    
    if not available_dates:
        message_text = "К сожалению, сейчас нет доступных дат для записи. Пожалуйста, попробуйте позже."
        if update.message:
            await update.message.reply_text(message_text, reply_markup=ReplyKeyboardRemove())
        else:
            await query.edit_message_text(message_text)
        return ConversationHandler.END
    
    # Create keyboard with dates
    keyboard = []
    for date in available_dates:
        keyboard.append([date])
    
    keyboard.append(["❌ Отмена"])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    message_text = f"Вы выбрали: {service}\n📅 Теперь выберите дату:"
    
    if update.message:
        await update.message.reply_text(message_text, reply_markup=reply_markup)
    else:
        await query.edit_message_text(message_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Используйте меню ниже", callback_data="ignore")]]))
        await update.effective_chat.send_message(message_text, reply_markup=reply_markup)
    
    return CHOOSE_DATE

async def choose_date(update: Update, context: CallbackContext) -> int:
    # Handle text input from ReplyKeyboardMarkup
    if update.message:
        date_text = update.message.text
        
        # Check if the user wants to cancel
        if date_text == "❌ Отмена":
            await update.message.reply_text("Запись отменена.", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
            
        # Validate the date format
        available_dates = get_working_days()
        if date_text not in available_dates:
            # If not a valid date, ask again
            keyboard = []
            for date in available_dates:
                keyboard.append([date])
            keyboard.append(["❌ Отмена"])
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                "Пожалуйста, выберите дату из предложенных вариантов:",
                reply_markup=reply_markup
            )
            return CHOOSE_DATE
            
        date = date_text
    # For backward compatibility, still handle callback queries
    else:
        query = update.callback_query
        await query.answer()
        
        if query.data == 'cancel':
            await query.edit_message_text("Запись отменена.")
            return ConversationHandler.END
        
        date = query.data
    
    context.user_data['date'] = date
    
    # Get available times for the selected date
    available_times = get_available_times(date)
    
    if not available_times:
        message_text = f"К сожалению, на {date} нет свободных слотов. Пожалуйста, выберите другую дату."
        
        # Return to date selection
        available_dates = get_working_days()
        keyboard = []
        for d in available_dates:
            keyboard.append([d])
        
        keyboard.append(["❌ Отмена"])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        if update.message:
            await update.message.reply_text(message_text)
            await update.message.reply_text(
                f"Вы выбрали: {context.user_data['service']}\n📅 Теперь выберите другую дату:",
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text(message_text)
            await update.effective_chat.send_message(
                f"Вы выбрали: {context.user_data['service']}\n📅 Теперь выберите другую дату:",
                reply_markup=reply_markup
            )
        return CHOOSE_DATE
    
    # Create keyboard with times
    keyboard = []
    row = []
    for i, time in enumerate(available_times):
        row.append(time)
        if (i + 1) % 3 == 0 or i == len(available_times) - 1:
            keyboard.append(row)
            row = []
    
    keyboard.append(["❌ Отмена"])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    message_text = f"Вы выбрали: {context.user_data['service']} на {date}\n⏰ Теперь выберите время:"
    
    if update.message:
        await update.message.reply_text(message_text, reply_markup=reply_markup)
    else:
        await query.edit_message_text(message_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Используйте меню ниже", callback_data="ignore")]]))
        await update.effective_chat.send_message(message_text, reply_markup=reply_markup)
    
    return CHOOSE_TIME

async def choose_time(update: Update, context: CallbackContext) -> int:
    # Handle text input from ReplyKeyboardMarkup
    if update.message:
        time_text = update.message.text
        
        # Check if the user wants to cancel
        if time_text == "❌ Отмена":
            await update.message.reply_text("Запись отменена.", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
            
        # Validate the time format
        available_times = get_available_times(context.user_data['date'])
        if time_text not in available_times:
            # If not a valid time, ask again
            keyboard = []
            row = []
            for i, time in enumerate(available_times):
                row.append(time)
                if (i + 1) % 3 == 0 or i == len(available_times) - 1:
                    keyboard.append(row)
                    row = []
            keyboard.append(["❌ Отмена"])
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                "Пожалуйста, выберите время из предложенных вариантов:",
                reply_markup=reply_markup
            )
            return CHOOSE_TIME
            
        time = time_text
    # For backward compatibility, still handle callback queries
    else:
        query = update.callback_query
        await query.answer()
        
        if query.data == 'cancel':
            await query.edit_message_text("Запись отменена.")
            return ConversationHandler.END
        
        time = query.data
    
    context.user_data['time'] = time
    
    # Confirm booking
    keyboard = [
        ["✅ Подтвердить"],
        ["❌ Отмена"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    message_text = (
        f"Подтвердите вашу запись:\n"
        f"Услуга: {context.user_data['service']}\n"
        f"Дата: {context.user_data['date']}\n"
        f"Время: {context.user_data['time']}"
    )
    
    if update.message:
        await update.message.reply_text(message_text, reply_markup=reply_markup)
    else:
        await query.edit_message_text(message_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Используйте меню ниже", callback_data="ignore")]]))
        await update.effective_chat.send_message(message_text, reply_markup=reply_markup)
    
    return CONFIRM_BOOKING

async def confirm_booking(update: Update, context: CallbackContext) -> int:
    # Handle text input from ReplyKeyboardMarkup
    if update.message:
        confirmation = update.message.text
        
        # Check if the user wants to cancel
        if confirmation == "❌ Отмена":
            await update.message.reply_text("Запись отменена.", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
            
        # Check if the user confirmed
        if confirmation != "✅ Подтвердить":
            # If not a valid confirmation, ask again
            keyboard = [
                ["✅ Подтвердить"],
                ["❌ Отмена"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                "Пожалуйста, подтвердите или отмените запись:",
                reply_markup=reply_markup
            )
            return CONFIRM_BOOKING
    # For backward compatibility, still handle callback queries
    else:
        query = update.callback_query
        await query.answer()
        
        if query.data == 'cancel':
            await query.edit_message_text("Запись отменена.")
            return ConversationHandler.END
    
    # Save appointment to database
    client_id = context.user_data['client_id']
    service = context.user_data['service']
    date = context.user_data['date']
    time = context.user_data['time']
    
    appointment_id = save_appointment(client_id, service, date, time)
    
    confirmation_message = (
        f"✅ Ваша запись успешно подтверждена!\n\n"
        f"🔹 Услуга: {service}\n"
        f"📅 Дата: {date}\n"
        f"⏰ Время: {time}\n\n"
        f"🙏 Мы будем ждать вас! В случае необходимости с вами свяжутся по указанному номеру телефона."
    )
    
    if update.message:
        await update.message.reply_text(confirmation_message, reply_markup=ReplyKeyboardRemove())
    else:
        await query.edit_message_text(confirmation_message)
    
    # Send notification to admin
    try:
        # Get admin user_id from database
        conn = sqlite3.connect('barber_shop.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM clients WHERE phone = ?', (ADMIN_PHONE,))
        admin_user_id = cursor.fetchone()
        conn.close()
        
        if admin_user_id:
            admin_message = (
                f"📣 Новая запись!\n\n"
                f"👤 Клиент: {update.effective_user.first_name}\n"
                f"📱 Телефон: {context.user_data['phone']}\n"
                f"🔹 Услуга: {service}\n"
                f"📅 Дата: {date}\n"
                f"⏰ Время: {time}"
            )
            await context.bot.send_message(chat_id=admin_user_id[0], text=admin_message)
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")
    
    return ConversationHandler.END

# Admin handlers
async def admin_menu(update: Update, context: CallbackContext) -> int:
    # Handle text input from ReplyKeyboardMarkup
    if update.message:
        admin_choice = update.message.text
        
        # Handle admin menu options
        if admin_choice == "📋 Просмотр записей":
            appointments = get_all_appointments()
            
            if not appointments:
                await update.message.reply_text(
                    "Нет активных записей.\n\n"
                    "Вернуться в /start"
                )
                return ConversationHandler.END
            
            message = "Активные записи:\n\n"
            for appt in appointments:
                appt_id, name, phone, service, date, time, status = appt
                message += f"ID: {appt_id} - {name} ({phone})\n"
                message += f"Услуга: {service}\n"
                message += f"Дата и время: {date} {time}\n"
                message += "-------------------\n"
            
            keyboard = [
                ["✅ Отметить как выполненную"],
                ["🔙 Назад в меню админа"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(message, reply_markup=reply_markup)
            return ADMIN_VIEW_BOOKINGS
        
        elif admin_choice == "➕ Добавить рабочие дни":
            # Generate calendar for date selection
            current_date = datetime.now()
            calendar_markup = generate_calendar_markup(current_date.year, current_date.month)
            
            # For adding dates, we still use inline keyboard for the calendar
            await update.message.reply_text(
                "📅 Выберите дату для добавления в рабочие дни:",
                reply_markup=calendar_markup
            )
            return ADMIN_ADD_DATES
        
        elif admin_choice == "➖ Удалить рабочие дни":
            available_dates = get_working_days()
            
            if not available_dates:
                await update.message.reply_text(
                    "Нет доступных рабочих дней для удаления.\n\n"
                    "Вернуться в /start"
                )
                return ConversationHandler.END
            
            keyboard = []
            for date in available_dates:
                keyboard.append([date])
            
            keyboard.append(["🔙 Назад в меню админа"])
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                "📅 Выберите дату для удаления:",
                reply_markup=reply_markup
            )
            return ADMIN_REMOVE_DATES
        
        elif admin_choice == "🚪 Выход из админ-панели":
            await update.message.reply_text(
                "Вы вышли из админ-панели.\n\n"
                "Для возврата используйте /start",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        elif admin_choice == "🔙 Назад в меню админа":
            keyboard = [
                ["📋 Просмотр записей"],
                ["➕ Добавить рабочие дни"],
                ["➖ Удалить рабочие дни"],
                ["🚪 Выход из админ-панели"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                "Вы вошли как администратор. Выберите действие:",
                reply_markup=reply_markup
            )
            return ADMIN_MENU
    # For backward compatibility, still handle callback queries
    else:
        query = update.callback_query
        await query.answer()
        
        if query.data == 'view_bookings':
            appointments = get_all_appointments()
            
            if not appointments:
                await query.edit_message_text(
                    "Нет активных записей.\n\n"
                    "Вернуться в /start"
                )
                return ConversationHandler.END
            
            message = "Активные записи:\n\n"
            for appt in appointments:
                appt_id, name, phone, service, date, time, status = appt
                message += f"ID: {appt_id} - {name} ({phone})\n"
                message += f"Услуга: {service}\n"
                message += f"Дата и время: {date} {time}\n"
                message += "-------------------\n"
            
            # Create persistent keyboard
            keyboard = [
                ["✅ Отметить как выполненную"],
                ["🔙 Назад в меню админа"]
            ]
            reply_markup_persistent = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            # First edit the inline message
            await query.edit_message_text(message)
            # Then send a new message with the persistent keyboard
            await update.effective_chat.send_message(
                "Используйте меню ниже для дальнейших действий:",
                reply_markup=reply_markup_persistent
            )
            return ADMIN_VIEW_BOOKINGS
        
        elif query.data == 'add_dates':
            # Generate calendar for date selection
            current_date = datetime.now()
            calendar_markup = generate_calendar_markup(current_date.year, current_date.month)
            
            await query.edit_message_text(
                "📅 Выберите дату для добавления в рабочие дни:",
                reply_markup=calendar_markup
            )
            return ADMIN_ADD_DATES
        
        elif query.data == 'remove_dates':
            available_dates = get_working_days()
            
            if not available_dates:
                await query.edit_message_text(
                    "Нет доступных рабочих дней для удаления.\n\n"
                    "Вернуться в /start"
                )
                return ConversationHandler.END
            
            # Create persistent keyboard
            keyboard = []
            for date in available_dates:
                keyboard.append([date])
            
            keyboard.append(["🔙 Назад в меню админа"])
            reply_markup_persistent = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            # First edit the inline message
            await query.edit_message_text("📅 Выберите дату для удаления:")
            # Then send a new message with the persistent keyboard
            await update.effective_chat.send_message(
                "Используйте меню ниже для выбора даты:",
                reply_markup=reply_markup_persistent
            )
            return ADMIN_REMOVE_DATES
        
        elif query.data == 'exit_admin':
            await query.edit_message_text(
                "Вы вышли из админ-панели.\n\n"
                "Для возврата используйте /start"
            )
            return ConversationHandler.END
        
        elif query.data == 'back_to_admin':
            # Create persistent keyboard
            keyboard = [
                ["📋 Просмотр записей"],
                ["➕ Добавить рабочие дни"],
                ["➖ Удалить рабочие дни"],
                ["🚪 Выход из админ-панели"]
            ]
            reply_markup_persistent = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            # First edit the inline message
            await query.edit_message_text("Вы вошли как администратор. Выберите действие:")
            # Then send a new message with the persistent keyboard
            await update.effective_chat.send_message(
                "Используйте меню ниже для выбора действия:",
                reply_markup=reply_markup_persistent
            )
            return ADMIN_MENU
    
    return ADMIN_MENU

async def admin_view_bookings(update: Update, context: CallbackContext) -> int:
    # Handle text input from ReplyKeyboardMarkup
    if update.message:
        admin_choice = update.message.text
        
        if admin_choice == "🔙 Назад в меню админа":
            return await admin_menu(update, context)
        
        elif admin_choice == "✅ Отметить как выполненную":
            await update.message.reply_text(
                "Введите ID записи, которую нужно отметить как выполненную:"
            )
            context.user_data['awaiting_appointment_id'] = True
            return ADMIN_VIEW_BOOKINGS
    # For backward compatibility, still handle callback queries
    else:
        query = update.callback_query
        await query.answer()
        
        if query.data == 'back_to_admin':
            return await admin_menu(update, context)
        
        elif query.data == 'mark_completed':
            await query.edit_message_text(
                "Введите ID записи, которую нужно отметить как выполненную:"
            )
            context.user_data['awaiting_appointment_id'] = True
            return ADMIN_VIEW_BOOKINGS

async def admin_mark_completed(update: Update, context: CallbackContext) -> int:
    if 'awaiting_appointment_id' in context.user_data and context.user_data['awaiting_appointment_id']:
        try:
            appointment_id = int(update.message.text.strip())
            mark_appointment_completed(appointment_id)
            
            await update.message.reply_text(
                f"Запись #{appointment_id} отмечена как выполненная.\n\n"
                "Вернуться в /start"
            )
        except ValueError:
            await update.message.reply_text(
                "Неверный формат ID. Пожалуйста, введите число.\n\n"
                "Вернуться в /start"
            )
        
        context.user_data['awaiting_appointment_id'] = False
        return ConversationHandler.END

async def admin_add_dates(update: Update, context: CallbackContext) -> int:
    # For text input, we still need to use the calendar for date selection
    # So we'll only handle the back button via text
    if update.message:
        admin_choice = update.message.text
        
        if admin_choice == "🔙 Назад в меню админа":
            return await admin_menu(update, context)
        
        # Try to parse the date if it's in YYYY-MM-DD format
        try:
            # Validate date format
            date_text = admin_choice
            datetime.strptime(date_text, '%Y-%m-%d')
            
            success = add_working_day(date_text)
            
            if success:
                await update.message.reply_text(
                    f"✅ Дата {date_text} успешно добавлена как рабочий день.\n\n"
                    "Вернуться в /start",
                    reply_markup=ReplyKeyboardRemove()
                )
            else:
                await update.message.reply_text(
                    f"⚠️ Дата {date_text} уже существует в списке рабочих дней.\n\n"
                    "Вернуться в /start",
                    reply_markup=ReplyKeyboardRemove()
                )
            return ConversationHandler.END
        except ValueError:
            # If not a valid date format, just continue with the calendar
            pass
    
    # Handle callback queries for the calendar
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        callback_data = query.data
        
        if callback_data == 'back_to_admin':
            return await admin_menu(update, context)
        
        if callback_data == 'ignore':
            return ADMIN_ADD_DATES
        
        if callback_data.startswith('calendar:'):
            # Handle calendar navigation
            _, year, month = callback_data.split(':')
            year, month = int(year), int(month)
            
            calendar_markup = generate_calendar_markup(year, month)
            await query.edit_message_text(
                "📅 Выберите дату для добавления в рабочие дни:",
                reply_markup=calendar_markup
            )
            return ADMIN_ADD_DATES
        
        if callback_data.startswith('date:'):
            # Handle date selection
            date_text = callback_data.split(':', 1)[1]
            
            try:
                # Validate date format
                datetime.strptime(date_text, '%Y-%m-%d')
                
                success = add_working_day(date_text)
                
                # Create a keyboard with back to admin option
                keyboard = [["🔙 Назад в меню админа"]]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                
                if success:
                    await query.edit_message_text(
                        f"✅ Дата {date_text} успешно добавлена как рабочий день."
                    )
                    await update.effective_chat.send_message(
                        "Вы можете вернуться в меню администратора:",
                        reply_markup=reply_markup
                    )
                    return ADMIN_MENU
                else:
                    await query.edit_message_text(
                        f"⚠️ Дата {date_text} уже существует в списке рабочих дней."
                    )
                    await update.effective_chat.send_message(
                        "Вы можете вернуться в меню администратора:",
                        reply_markup=reply_markup
                    )
                    return ADMIN_MENU
            except ValueError:
                await query.edit_message_text(
                    "❌ Ошибка при добавлении даты.\n\n"
                    "Вернуться в /start"
                )
                return ConversationHandler.END
    
    return ADMIN_ADD_DATES

async def admin_remove_dates(update: Update, context: CallbackContext) -> int:
    # Handle text input from ReplyKeyboardMarkup
    if update.message:
        admin_choice = update.message.text
        
        if admin_choice == "🔙 Назад в меню админа":
            return await admin_menu(update, context)
        
        date = admin_choice
        success = remove_working_day(date)
        
        if success:
            await update.message.reply_text(
                f"Дата {date} успешно удалена из списка рабочих дней.\n\n"
                "Вернуться в /start",
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            await update.message.reply_text(
                f"Ошибка при удалении даты {date}.\n\n"
                "Вернуться в /start",
                reply_markup=ReplyKeyboardRemove()
            )
        
        return ConversationHandler.END
    # For backward compatibility, still handle callback queries
    else:
        query = update.callback_query
        await query.answer()
        
        if query.data == 'back_to_admin':
            return await admin_menu(update, context)
        
        date = query.data
        success = remove_working_day(date)
        
        if success:
            await query.edit_message_text(
                f"Дата {date} успешно удалена из списка рабочих дней.\n\n"
                "Вернуться в /start"
            )
        else:
            await query.edit_message_text(
                f"Ошибка при удалении даты {date}.\n\n"
                "Вернуться в /start"
            )
        
        return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text(
        "Операция отменена.", 
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

def main() -> None:
    # Initialize database
    init_db()
    
    # Create the Application
    application = Application.builder().token("7776578154:AAFzZDiIi2yhPVjqNv-7od85ve-UJ1S4ZRU").build()
    
    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PROVIDE_CONTACT: [
                MessageHandler(filters.CONTACT, handle_contact)
            ],
            CHOOSE_SERVICE: [
                CallbackQueryHandler(choose_service),
                MessageHandler(filters.TEXT & ~filters.COMMAND, choose_service)
            ],
            CHOOSE_DATE: [
                CallbackQueryHandler(choose_date),
                MessageHandler(filters.TEXT & ~filters.COMMAND, choose_date)
            ],
            CHOOSE_TIME: [
                CallbackQueryHandler(choose_time),
                MessageHandler(filters.TEXT & ~filters.COMMAND, choose_time)
            ],
            CONFIRM_BOOKING: [
                CallbackQueryHandler(confirm_booking),
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_booking)
            ],
            ADMIN_MENU: [
                CallbackQueryHandler(admin_menu),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_menu)
            ],
            ADMIN_VIEW_BOOKINGS: [
                CallbackQueryHandler(admin_view_bookings),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_view_bookings)
            ],
            ADMIN_ADD_DATES: [
                CallbackQueryHandler(admin_add_dates),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_dates)
            ],
            ADMIN_REMOVE_DATES: [
                CallbackQueryHandler(admin_remove_dates),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_remove_dates)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    application.add_handler(conv_handler)
    
    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()