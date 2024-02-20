import telebot
import sqlite3
from telebot import types
import datetime
from threading import Lock

bot = telebot.TeleBot("TOKEN")

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

credit_taken = False  # Флаг, показывающий, взят ли кредит

# Функция выполнения запроса к базе данных внутри блокировки
def execute_query(query):
    with db_lock:
        cursor.execute(query)
        conn.commit()

# Обработчик для команды /start и кнопок действий
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "Банк ААААА - Меню")
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('/take_loan'))
    markup.add(types.KeyboardButton('/view_payments'))
    markup.add(types.KeyboardButton('/make_payment'))
    markup.add(types.KeyboardButton('/info'))
    bot.send_message(message.chat.id, "Выберите действие:", reply_markup=markup)



# Обработчик для кнопки /info
@bot.message_handler(commands=['info'])
def send_info(message):
    bot.send_message(message.chat.id, "Добро пожаловать в Telegram версию банка ААААА. Пользуясь им, вы поймете к чему такое название. По всем вопросам пинайте @Kronen10, он виноват если что-то не работает.")


# Обработчик для взятия кредита
@bot.message_handler(func=lambda message: message.text == '/take_loan' and not credit_taken)
def take_loan(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    amounts = [1000, 5000, 10000]  # Ваши варианты сумм кредита
    buttons = [types.KeyboardButton(str(amount)) for amount in amounts]
    markup.add(*buttons)
    
    bot.send_message(message.chat.id, "Выберите сумму кредита:", reply_markup=markup)
    bot.register_next_step_handler(message, handle_credit_choice)
#обработчик выбора суммы
@bot.message_handler(func=lambda message: message.text.isdigit() and not credit_taken)
def handle_credit_choice(message):
    global credit_taken
    user_id = message.from_user.id
    try:
        connection = None
        with db_lock:
            connection = sqlite3.connect('bank.db')
            cursor = connection.cursor()
            
        credit_amount = int(message.text)
        
        query = f"INSERT INTO credits (user_id, amount, duration, interest_rate) VALUES ({user_id}, {credit_amount}, 12, 0.1)"
        connection.execute(query)
        connection.commit()
        bot.send_message(message.chat.id, f'Вы успешно взяли кредит на сумму {credit_amount} на 12 месяцев.')
        credit_taken = True
        send_welcome(message)  # Возврат в стартовое меню после выбора суммы кредита
    finally:
        if connection:
            connection.close()

# Обработчик для обработки команды /take_loan после взятия кредита
@bot.message_handler(func=lambda message: message.text == '/take_loan' and credit_taken)
def handle_loan_after_taken(message):
    bot.send_message(message.chat.id, 'Погасите этот кредит')

# Обработчик для просмотра текущих платежей
@bot.message_handler(commands=['view_payments'])
def view_payments(message):
    user_id = message.from_user.id
    query = f"SELECT id, amount, duration, interest_rate FROM credits WHERE user_id={user_id}"
    with db_lock:
        cursor.execute(query)
        row = cursor.fetchone()

    if row:
        credit_id, amount, duration, interest_rate = row  
        total_payment = amount * (1 + interest_rate)
        monthly_payment = total_payment / duration
        payments_info = f"Сумма кредита: {amount}\nПроцентная ставка: {interest_rate}\nПлатеж в месяц: {monthly_payment}\n\n"
        query = f"SELECT payment_date, payment_amount FROM payments WHERE credit_id={credit_id} ORDER BY payment_date ASC"
        cursor.execute(query)
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                payment_date, payment_amount = row
                if isinstance(payment_date, str):
                    payment_date = datetime.datetime.strptime(payment_date, '%Y-%m-%d')
                payments_info += f"{payment_date.strftime('%Y-%m-%d')}: {payment_amount}\n"
        else:
            payments_info += "Нет платежей."
        bot.send_message(message.chat.id, payments_info)
    else:
        bot.send_message(message.chat.id, 'Нет активных кредитов.')

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
        if updated_amount <= 0:
            bot.send_message(message.chat.id, 'Вы закрыли кредит')
            query = f"DELETE FROM credits WHERE id={credit_id}"
            execute_query(query)
        else:
            query = f"UPDATE credits SET amount={updated_amount} WHERE id={credit_id}"
            execute_query(query)
        bot.send_message(message.chat.id, f'Платеж на сумму {monthly_payment} успешно проведен.')
    except ValueError:
        bot.send_message(message.chat.id, 'Пожалуйста, введите корректную сумму платежа.')



# Обработчик для остальных сообщений
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, "Выберите действие через меню кнопок.")

# Запуск бота
try:
    bot.polling()
except Exception as e:
    print(f"An error occurred: {e}")
