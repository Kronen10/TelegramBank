import telebot
import sqlite3
from telebot import types
import datetime
from threading import Lock

bot = telebot.TeleBot("6437286640:AAFmkoOCXx6KVakLR0PJdAhnQBVmNJCMm-g")

conn = sqlite3.connect('bank.db', check_same_thread=False)
cursor = conn.cursor()
db_lock = Lock()

# Создание таблиц для хранения данных о кредитах и платежах
cursor.execute('''
    CREATE TABLE IF NOT EXISTS credits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        duration INTEGER,
        interest_rate REAL
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        credit_id INTEGER,
        payment_date DATE,
        payment_amount INTEGER
    )
''')
conn.commit()

# Функция выполнения запроса к базе данных внутри блокировки
def execute_query(query):
    with db_lock:
        cursor.execute(query)
        conn.commit()


# Обработчик для команды /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('/take_credit'))
    markup.add(types.KeyboardButton('/view_payments'))
    markup.add(types.KeyboardButton('/make_payment'))
    bot.send_message(message.chat.id, "Выберите действие:", reply_markup=markup)

# Обработчик для взятия кредита
@bot.message_handler(func=lambda message: message.text == '/take_credit')
def take_credit(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    amounts = [1000, 5000, 10000]  # Ваши варианты сумм кредита
    buttons = [types.KeyboardButton(str(amount)) for amount in amounts]
    markup.add(*buttons)
    
    bot.send_message(message.chat.id, "Выберите сумму кредита:", reply_markup=markup)
    bot.register_next_step_handler(message, handle_credit_choice)

# Обработчик для выбора суммы кредита и выполнения действий
@bot.message_handler(func=lambda message: message.text.isdigit())
def handle_credit_choice(message):
    user_id = message.from_user.id
    try:
        credit_amount = int(message.text)
        
        query = f"INSERT INTO credits (user_id, amount, duration, interest_rate) VALUES ({user_id}, {credit_amount}, 12, 0.1)"
        execute_query(query)
        
        bot.send_message(message.chat.id, f'Вы успешно взяли кредит на сумму {credit_amount} на 12 месяцев.')
    except ValueError:
        bot.send_message(message.chat.id, 'Пожалуйста, выберите сумму кредита из предложенных вариантов.')





# Обновленный обработчик для внесения платежа с возможностью ввода суммы платежа
@bot.message_handler(commands=['make_payment'])
def make_payment(message):
    user_id = message.from_user.id
    query = f"SELECT id, amount, duration, interest_rate FROM credits WHERE user_id={user_id}"

    with db_lock:
        cursor.execute(query)
        row = cursor.fetchone()

    if row:
        credit_id, amount, duration, interest_rate = row
        bot.send_message(message.chat.id, "Введите сумму платежа:")
        bot.register_next_step_handler(message, lambda msg: process_payment_input(msg, credit_id, amount, duration, interest_rate))
    else:
        bot.send_message(message.chat.id, 'Нет активных кредитов.')

# Обработчик для обработки введенной пользователем суммы платежа
def process_payment_input(message, credit_id, amount, duration, interest_rate):
    try:
        monthly_payment = float(message.text)
        payment_date = datetime.datetime.now().date()
        query = f"INSERT INTO payments (credit_id, payment_date, payment_amount) VALUES ({credit_id}, '{payment_date}', {monthly_payment})"
        execute_query(query)
        updated_amount = amount - monthly_payment  # Уменьшаем сумму кредита на введенный платеж
        query = f"UPDATE credits SET amount={updated_amount} WHERE id={credit_id}"
        execute_query(query)
        bot.send_message(message.chat.id, f'Платеж на сумму {monthly_payment} успешно проведен.')
    except ValueError:
        bot.send_message(message.chat.id, 'Пожалуйста, введите корректную сумму платежа.')

# Обработчик для просмотра графика платежей
@bot.message_handler(commands=['view_payments'])
def view_payments(message):
    user_id = message.from_user.id
    query = f"SELECT amount, duration, interest_rate FROM credits WHERE user_id={user_id}"
    with db_lock:
        cursor.execute(query)
        row = cursor.fetchone()

    if row:
        amount, duration, interest_rate = row  
        total_payment = amount * (1 + interest_rate)
        monthly_payment = total_payment / duration
        payments_info = f"Сумма кредита: {amount}\nПроцентная ставка: {interest_rate}\nПлатеж в месяц: {monthly_payment}"
        bot.send_message(message.chat.id, payments_info)
    else:
        bot.send_message(message.chat.id, 'Нет активных кредитов.')

# Обработчик для всех остальных сообщений
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, "Выберите действие через меню кнопок.")

try:
    bot.polling()
except Exception as e:
    print(f"An error occurred: {e}")