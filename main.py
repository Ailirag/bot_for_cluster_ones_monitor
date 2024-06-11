#!venv/Scripts/python.exe
# This is a sample Python script.
import asyncio
import os
import time
import traceback
import sys

from vweb.htmltable import HtmlTable

from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.types import ReplyKeyboardRemove
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.contrib.middlewares.logging import LoggingMiddleware
import aiofiles
import configparser
import re
import json
import uuid
from keyboards import generate_keyb
from utils import only_send_message, send_table_errors
from utils import logging
from database import DB
import glob


current_path = os.getcwd()
path_to_settings = f'{current_path}{os.sep}settings.ini'
config_file = configparser.ConfigParser()


class AllStates(StatesGroup):
    START: State = State()
    REG_STATE: State = State()
    QUESTION_REG_STATE: State = State()
    WAIT_PHONE_NUMBER_STATE: State = State()
    WAIT_EMAIL_STATE: State = State()
    WAIT_REGISTRATION_CONFIRMATION_STATE: State = State()
    SUBSCRIBE_CHOICE_BASE_STATE: State = State()
    SUBSCRIBE_STATE: State = State()
    UNSUBSCRIBE_STATE: State = State()
    UNSUBSCRIBE_CHOICE_BASE_STATE: State = State()
    SUBSCRIBE_CHOICE_BASE_STATE_FOR_CHAT: State = State()
    UNSUBSCRIBE_CHOICE_BASE_STATE_FOR_CHAT: State = State()
    SUB_CHOICE_CHAT_STATE: State = State()
    UNSUB_CHOICE_CHAT_STATE: State = State()
    GET_SESSION_START: State = State()


if not os.path.exists(path_to_settings):
    logging('settings.ini not find and will be created.')
    config_file['DEFAULT']['TOKEN'] = ''
    config_file['DEFAULT']['directory_for_exchange'] = ''

    with open(path_to_settings, 'w', encoding='utf8') as configfile:
        config_file.write(configfile)

    logging('settings.ini created. Please fill it and restart program.')
    sys.exit()
else:
    config_file.read(path_to_settings, encoding='utf8')
    TOKEN = config_file['DEFAULT']['TOKEN']
    directory_for_exchange = config_file['DEFAULT']['directory_for_exchange']

    if not TOKEN \
            or not directory_for_exchange:
        logging('All fields on settings.ini must be filled in. Please will it and restart program.')
        sys.exit()


def write_command(dict_of_command):
    json_string = json.dumps(dict_of_command, ensure_ascii=False)
    with open(f'{directory_for_exchange}{os.sep}{str(uuid.uuid4())}.json', 'w', encoding='utf8') as command_file:
        command_file.write(json_string)
    logging(f'Write command: {json_string}')


def run_polling():
    logging('Start polling')
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)


# Initialize bot and dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
dp.middleware.setup(LoggingMiddleware())
db = DB(current_path)


async def run_exchange():
    while True:
        try:
            events_loaded = []
            list_of_files = glob.glob(directory_for_exchange + os.sep + '*.jsonout')
            list_of_files.sort(key=os.path.getmtime)
            for path in list_of_files:
                async with aiofiles.open(path, 'r', encoding='utf8') as file_jsonout:
                    data = await file_jsonout.read()
                data_json = json.loads(data)

                command = data_json['type']

                successful = False

                if command == 'scheduled_jobs_faileds_notification':
                    base_name = data_json['base']

                    if not base_name in events_loaded:
                        await db.register_jobs(base_name, data_json['all_events'])
                        events_loaded.append(base_name)

                    successful = await db.register_events(base_name, data_json['body'])
                elif command == 'update_chat_without_activites':
                    successful = await db.update_chat_without_activites(data_json['body'])
                elif command == 'update_subscriptions_on_bases':
                    successful = await db.update_subscriptions_on_bases(data_json)
                elif command == 'update_users':
                    successful = await db.update_users(data_json)
                elif command == 'update_subscriptions':
                    successful = await db.update_subscriptions_on_user(data_json)
                elif command == 'update_chat_admin':
                    successful = await db.update_chat_admin(data_json)

                if successful:
                    os.remove(path)

            await send_notifications(db)
        except Exception:
            # error_exc = str(type(e)) + str(e)
            logging('Ошибка потока обмена.')
            error_exc = traceback.format_exc()
            logging(error_exc)
        await asyncio.sleep(10)


async def send_notifications(db):
    array_clear_alerts = list()

    notification_on_bases = await db.get_current_notifications()

    bases_without_sub = list()

    if notification_on_bases:
        for base in notification_on_bases:
            chats_for_base = await db.get_chats_for_base(base[0])
            if len(chats_for_base) == False:
                bases_without_sub.append(base[0])
                continue
            for chat_base in await db.get_chats_for_base(base[0]):
                message = [f'☢️Ошибки выполнения РЗ.☢️\n']
                message.append(f'База: {base[0]}\n')
                index = 1
                table = HtmlTable(border=1, cellspacing=2,cellpadding=2,start_indent=2)
                table.addHeader(['Наименование', 'Начало выполнения', 'Окончание выполнения', 'Ошибка'])

                for notification in base[1]:
                    table.addRow([notification[7],notification[5], notification[6], 'Ошибка: '+notification[3]+'\n'+notification[4]])
                    message.append('\n')
                    message.append(f'{index}. {notification[7]} :   {notification[3]}')
                    index += 1
                    array_clear_alerts.append((base[0], notification[2]))

                clear_message = ''.join(message)
                await send_table_errors(table, clear_message, directory_for_exchange, chat_base[0], TOKEN)

    notification_on_users = await db.get_current_notifications_users()
    for user in notification_on_users:
        message = [f'Ошибки выполнения РЗ.\n']
        for base in user[1]:
            message.append(f'База: {base[0]}\n')
            index = 1
            table = HtmlTable(border=1, cellspacing=2, cellpadding=2, start_indent=2,)
            table.addHeader(['Наименование', 'Начало выполнения', 'Окончание выполнения', 'Ошибка'])
            for notification in base[1]:
                table.addRow([notification[2], notification[8], notification[9], 'Ошибка: ' + notification[3] + '\n' + notification[7]])
                message.append('\n')
                message.append(f'{index}. {notification[2]} :   {notification[3]}')
                # sended_ids.append(notification[0])
                index += 1
                if base[0] in bases_without_sub:
                    array_clear_alerts.append((base[0], notification[2]))
            clear_message = ''.join(message)
            await send_table_errors(table, clear_message, directory_for_exchange, user[0], TOKEN)

    if array_clear_alerts:
        await db.clear_sended_data(array_clear_alerts)


@dp.message_handler(state='*', commands=['get_info'])
async def get_info(message: types.Message):
    logging_method('get_info', message)
    info = {
        'message': {
            'message_id': message.message_id,
        },
        'chat': {
            'id': message.chat.id,
            'title': message.chat.title,
            'type': message.chat.type,
            'all_members_are_administrators': message.chat.all_members_are_administrators
        }
    }
    reply_message = json.dumps(info, ensure_ascii=False, indent=4)
    await message.reply(reply_message)


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('btn_registration'), state=AllStates.QUESTION_REG_STATE)
async def process_callback_btn_registration(callback_query: types.CallbackQuery):
    logging_method('process_callback_btn_registration', callback_query.message)
    await AllStates.WAIT_PHONE_NUMBER_STATE.set()
    await callback_query.message.reply(text='Поделитесь своим номером телефона.', reply_markup=await generate_keyb(db, 'keyboard_send_phone'))


@dp.message_handler(content_types=['contact'], state=AllStates.WAIT_PHONE_NUMBER_STATE)
async def message_contact_handler(message: types.Message, state: FSMContext):
    logging_method('message_contact_handler', message)
    file_id = message.contact
    phone_number = file_id.phone_number
    full_name = file_id.full_name
    await state.update_data(phone_number=phone_number)
    await state.update_data(full_name=full_name)
    await AllStates.WAIT_EMAIL_STATE.set()
    await message.reply('Номер получен. Напишите ваш email.', reply_markup=ReplyKeyboardRemove())


@dp.message_handler(state=AllStates.WAIT_EMAIL_STATE)
async def message_email_handler(message: types.Message, state: FSMContext):

    logging_method('message_email_handler', message)

    if not await black_list_check(message):
        return

    all_data = await state.get_data()

    if 'count_input_email' in all_data and all_data['count_input_email'] < 6:
        new_count = all_data['count_input_email'] + 1
        await state.update_data(count_input_email=new_count)
    elif not 'count_input_email' in all_data:
        await state.update_data(count_input_email=1)
    elif all_data['count_input_email'] == 5:
        await db.add_black_list(message.from_user.id)
        await message.reply('Вы внесены в черный список.')
        return

    await AllStates.WAIT_REGISTRATION_CONFIRMATION_STATE.set()

    all_data = await state.get_data()
    all_data['email'] = message.text
    all_data['tg_id'] = message.from_user.id
    all_data['tg_name'] = message.from_user.mention

    await db.register_new_user(all_data)
    await message.reply('Данные регистрации отправлены на валидацию. Ожидайте одобрения.')


@dp.message_handler(state=AllStates.WAIT_REGISTRATION_CONFIRMATION_STATE)
async def message_wait_registration(message: types.Message):
    logging_method('message_wait_registration', message)
    await message.reply('Регистрация еще не подтверждена. Ожидайте.')


async def black_list_check(message_or_id):
    black_list = await db.black_list()
    if type(message_or_id) == types.Message:
        id = str(message_or_id.from_user.id)
    else:
        id = str(message_or_id)

    if id in black_list:
        await message_or_id.reply('Вы в черном списке.')
        return False
    else:
        return True


async def chat_without_activites(message_or_id):
    if type(message_or_id) == types.Message:
        id = str(message_or_id.chat.id)
    else:
        id = str(message_or_id)

    return await db.chat_without_activites(id)


async def user_active_check(message: types.Message):
    active = await db.user_is_active(str(message.from_user.id))
    if active is None:
        return True
    if not active:
        await message.reply('Ваша учетная запись заблокирована или находится в стадии подтверждения.')

    return active


@dp.message_handler(state=AllStates.SUB_CHOICE_CHAT_STATE)
async def process_callback_choice_base_sub_chat(message: types.Message, state: FSMContext):
    logging_method('process_callback_choice_base_sub_chat', message)
    data = await state.get_data()
    base = data['base_name']
    result = await db.subscribe_for_chat(base, message.text)
    await message.reply(result)
    await state.reset_state()


@dp.message_handler(state=AllStates.UNSUB_CHOICE_CHAT_STATE)
async def process_callback_choice_base_unsub_chat(message: types.Message, state: FSMContext):
    logging_method('process_callback_choice_base_unsub_chat', message)
    data = await state.get_data()
    base = data['base_name']
    result = await db.unsubscribe_for_chat(base, message.text)
    await message.reply(result)
    await state.reset_state()


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('choice_base'), state=AllStates.SUBSCRIBE_CHOICE_BASE_STATE_FOR_CHAT)
async def process_callback_choice_base_sub_chat(callback_query: types.CallbackQuery, state: FSMContext):
    logging_method('process_callback_choice_base_sub_chat', callback_query.message)
    await AllStates.SUB_CHOICE_CHAT_STATE.set()
    base_name = callback_query.data.replace('choice_base:', '')
    await state.update_data(base_name=base_name)
    await callback_query.message.edit_text('Введите ID чата для подписки.')


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('choice_base'), state=AllStates.UNSUBSCRIBE_CHOICE_BASE_STATE_FOR_CHAT)
async def process_callback_choice_base_unsub_chat(callback_query: types.CallbackQuery, state: FSMContext):
    logging_method('process_callback_choice_base_unsub_chat', callback_query.message)
    await AllStates.UNSUB_CHOICE_CHAT_STATE.set()
    base_name = callback_query.data.replace('choice_base:', '')
    await state.update_data(base_name=base_name)
    await callback_query.message.edit_text('Введите ID чата для отписки.')


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('choice_base'), state=AllStates.SUBSCRIBE_CHOICE_BASE_STATE)
async def process_callback_choice_base_sub(callback_query: types.CallbackQuery, state: FSMContext):
    logging_method('process_callback_choice_base_sub', callback_query.message)
    await AllStates.SUBSCRIBE_STATE.set()
    base_name = callback_query.data.replace('choice_base:', '')
    pagination = (0,20)
    await state.update_data(base_name=base_name, pagination=pagination)
    keyboard = await generate_keyb(db, 'subscribe', callback_query.from_user.id, base_name, pagination)
    await callback_query.message.edit_text('Выберите интересующие вас задания и нажмите применить.', reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('choice_base'), state=AllStates.UNSUBSCRIBE_CHOICE_BASE_STATE)
async def process_callback_choice_base_unsub(callback_query: types.CallbackQuery, state: FSMContext):
    logging_method('process_callback_choice_base_unsub', callback_query.message)
    await AllStates.UNSUBSCRIBE_STATE.set()
    base_name = callback_query.data.replace('choice_base:', '')
    pagination = (0, 20)
    await state.update_data(base_name=base_name, pagination=pagination)
    keyboard = await generate_keyb(db, 'unsubscribe', callback_query.from_user.id, base_name, pagination)
    await callback_query.message.edit_text('Выберите интересующие вас задания и нажмите применить.', reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('btn_subscribe_for_chat'), state='*')
async def process_callback_btn_subscribe(callback_query: types.CallbackQuery):
    logging_method('process_callback_btn_subscribe_for_chat', callback_query.message)
    await AllStates.SUBSCRIBE_CHOICE_BASE_STATE_FOR_CHAT.set()
    keyboard = await generate_keyb(db, 'choice_base', callback_query.from_user.id)
    await callback_query.message.edit_text('Выберите базу:', reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('btn_unsubscribe_for_chat'), state='*')
async def process_callback_btn_unsubscribe(callback_query: types.CallbackQuery):
    logging_method('process_callback_btn_unsubscribe_for_chat', callback_query.message)
    await AllStates.UNSUBSCRIBE_CHOICE_BASE_STATE_FOR_CHAT.set()
    keyboard = await generate_keyb(db, 'choice_base', callback_query.from_user.id)
    await callback_query.message.edit_text('Выберите базу:', reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('btn_subscribe'), state='*')
async def process_callback_btn_subscribe(callback_query: types.CallbackQuery):
    logging_method('process_callback_btn_subscribe', callback_query.message)
    await AllStates.SUBSCRIBE_CHOICE_BASE_STATE.set()
    keyboard = await generate_keyb(db, 'choice_base', callback_query.from_user.id)
    await callback_query.message.edit_text('Выберите базу:', reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('btn_unsubscribe'), state='*')
async def process_callback_btn_unsubscribe(callback_query: types.CallbackQuery):
    logging_method('process_callback_btn_unsubscribe', callback_query.message)
    await AllStates.UNSUBSCRIBE_CHOICE_BASE_STATE.set()
    keyboard = await generate_keyb(db, 'choice_base', callback_query.from_user.id)
    await callback_query.message.edit_text('Выберите базу:', reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('subscribe'), state=AllStates.SUBSCRIBE_STATE)
async def subscriber(callback_query: types.CallbackQuery, state: FSMContext):
    logging_method('subscriber', callback_query.message)

    all_data = await state.get_data()
    if callback_query.data == 'subscribe:accept':
        if 'jobs' in all_data and all_data['jobs']:
            names_jobs = await db.apply_subscribe(callback_query.from_user.id, all_data)
            message=list()
            message.append('Все ваши подписки:')
            index = 1
            for subs in names_jobs:
                message.append(f'{index}. {subs}')
                index += 1
            await callback_query.message.edit_text('\n'.join(message))
        else:
            await callback_query.message.edit_text('Выбранный список пуст.')
        await state.reset_state()
    elif callback_query.data == 'subscribe:decline':
        await callback_query.message.edit_text('Действие отменено.')
        await state.reset_state()
    elif callback_query.data == 'subscribe:>' or callback_query.data == 'subscribe:<':
        pagination = all_data['pagination']
        new_pagination = list()
        if callback_query.data == 'subscribe:>':
            new_pagination.append(pagination[0] + 20)
            new_pagination.append(pagination[1] + 20)
        else:
            new_pagination.append(pagination[0] - 20)
            new_pagination.append(pagination[1] - 20)
        keyboard = await generate_keyb(db, 'subscribe', callback_query.from_user.id, all_data['base_name'], new_pagination)
        await state.update_data(pagination=new_pagination)
        await callback_query.message.edit_reply_markup(keyboard)
    else:
        if not 'jobs' in all_data:
            all_data['jobs'] = list()
        all_data['jobs'].append(callback_query.data.replace('subscribe:', ''))
        await state.update_data(jobs=all_data['jobs'])


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('unsubscribe'), state=AllStates.UNSUBSCRIBE_STATE)
async def unsubscribe(callback_query: types.CallbackQuery, state: FSMContext):

    logging_method('unsubscribe', callback_query.message)

    all_data = await state.get_data()
    if callback_query.data == 'unsubscribe:accept':
        if 'jobs' in all_data and all_data['jobs']:
            names_jobs = await db.delete_subscribe(callback_query.from_user.id, all_data)
            message=list()
            message.append('Все ваши подписки:')
            index = 1
            for subs in names_jobs:
                message.append(f'{index}. {subs}')
                index += 1
            await callback_query.message.edit_text('\n'.join(message))
        else:
            await callback_query.message.edit_text('Выбранный список пуст.')
        await state.reset_state()
    elif callback_query.data == 'unsubscribe:decline':
        await callback_query.message.edit_text('Действие отменено.')
        await state.reset_state()
    elif callback_query.data == 'unsubscribe:>' or callback_query.data == 'unsubscribe:<':
        pagination = all_data['pagination']
        new_pagination = list()
        if callback_query.data == 'unsubscribe:>':
            new_pagination.append(pagination[0] + 20)
            new_pagination.append(pagination[1] + 20)
        else:
            new_pagination.append(pagination[0] - 20)
            new_pagination.append(pagination[1] - 20)
        keyboard = await generate_keyb(db, 'unsubscribe', callback_query.from_user.id, all_data['base_name'], new_pagination)
        await state.update_data(pagination=new_pagination)
        await callback_query.message.edit_reply_markup(keyboard)
    else:
        if not 'jobs' in all_data:
            all_data['jobs'] = list()
        all_data['jobs'].append(callback_query.data.replace('unsubscribe:', ''))
        await state.update_data(jobs=all_data['jobs'])


@dp.message_handler(state='*', commands=['set'])
async def set_def(message: types.Message):

    logging_method('set_def', message)

    user_info = await db.get_user_info(message.from_user.id)
    if user_info is None or not user_info['is_admin']:
        return

    set_admin_command = re.findall("^\/set user ([-\d]+) is_admin ([\d])$", message.text)

    if set_admin_command:
        tg_id = set_admin_command[0][0]
        is_admin = set_admin_command[0][1]
        result = await db.make_admin(tg_id, is_admin)
        await message.reply(result)
    else:
        instruction = '''Команда наделяющая пользователя правами администратора.
        
    /set user <id пользователя> is_admin <1 или 0>'''
        await message.reply(instruction)


def logging_method(name_method, message):
    logging(f'Method:{name_method}. Message from: {message.from_user.id}|{message.from_user.full_name}|{message.from_user.mention}: {message.text}')


@dp.message_handler(state='*', commands=['stop_bot'])
async def get_info(message: types.Message):
    info = await db.get_user_info(message.from_user.id)
    if info['is_admin']:
        all_base_chats = await db.get_chats_notification_bases()
        for chat in all_base_chats:
            await only_send_message(chat[0], 'Бот будет остановлен для установки обновлений.', TOKEN)


@dp.message_handler(state='*', commands=['start_bot'])
async def get_info(message: types.Message):
    info = await db.get_user_info(message.from_user.id)
    if info['is_admin']:
        all_base_chats = await db.get_chats_notification_bases()
        for chat in all_base_chats:
            await only_send_message(chat[0], 'Работа бота восстановлена.', TOKEN)


@dp.message_handler(state='*', commands=['kill'])
async def do_kill(message: types.Message):
    user_admin_chat = await db.user_is_admin_of_chat_and_base(message.from_user.id, message.chat.id)
    if not user_admin_chat:
        await message.reply('Вы не являетесь администратором чата. Операция невозможна.')
        return

    if 'reply_to_message' in message and 'caption' in message.reply_to_message and message.reply_to_message.caption:
        reply_message = message.reply_to_message.caption
    else:
        reply_message = message.reply_to_message.text

    base = re.findall("База {0,50}:([\а-яА-Яa-zA-Z0-9 \/ -_.]+)", reply_message)[0].strip()
    user = re.findall("Пользователь {0,50}:([\а-яА-Яa-zA-Z0-9_ -.]+)", reply_message)[0].strip()
    number = re.findall("Номер сеанса {0,50}:([  \d]+)", reply_message)[0].strip()

    if base and user and number:
        command = {'command': 'kill',
                   'chat_id': message.chat.id,
                   'base': base,
                   'user': user,
                   'number': number}
        write_command(command)
    else:
        logging(f'One of arguments is empty. Base: [{base}], user: [{user}], number: [{number}]')
    await message.reply('Функционал еще не реализован.')


@dp.message_handler(state='*', commands=['say'])
async def get_info(message: types.Message):
    info = await db.get_user_info(message.from_user.id)
    if info['is_admin']:
        all_base_chats = await db.get_chats_notification_bases()
        text = message.text.replace('/say ', '')
        for chat in all_base_chats:
            await only_send_message(chat[0], text, TOKEN)


@dp.message_handler(state='*', commands=['get_sessions'])
async def get_info(message: types.Message):
    arguments = message.text.replace('/get_sessions ', '').split(' ')
    if len(arguments) < 1:
        await message.reply('Введите команду в формате /get_sessions <base_name> <СтрокаПоискаПользователя-опционально>')

    if len(arguments) == 1:
        pass
    #     Проверить что база с таким именем существует и у пользователя есть на нее права Вернуть файл со всеми сеансами базы
    


    user_admin_chat = await db.user_is_admin_of_chat_and_base(message.from_user.id, message.chat.id)
    if not user_admin_chat:
        await message.reply('Вы не являетесь администратором чата. Операция невозможна.')
        return

    if 'reply_to_message' in message and 'caption' in message.reply_to_message and message.reply_to_message.caption:
        reply_message = message.reply_to_message.caption
    else:
        reply_message = message.reply_to_message.text

    base = re.findall("База {0,50}:([\а-яА-Яa-zA-Z0-9 \/ -_.]+)", reply_message)[0].strip()
    user = re.findall("Пользователь {0,50}:([\а-яА-Яa-zA-Z0-9_ -.]+)", reply_message)[0].strip()
    number = re.findall("Номер сеанса {0,50}:([  \d]+)", reply_message)[0].strip()

    if base and user and number:
        command = {'command': 'kill',
                   'chat_id': message.chat.id,
                   'base': base,
                   'user': user,
                   'number': number}
        write_command(command)
    else:
        logging(f'One of arguments is empty. Base: [{base}], user: [{user}], number: [{number}]')
    await message.reply('Функционал еще не реализован.')


@dp.message_handler(state='*')
async def echo(message: types.Message):

    logging_method('echo', message)

    white_list = await db.get_white_list()
    black_list = await db.black_list()

    if not await user_active_check(message):
        return

    if not await black_list_check(message):
        return

    chat_without_reg_message = await chat_without_activites(message)

    try:
        if not str(message.from_user.id) in white_list and not str(message.from_user.id) in black_list:
            if chat_without_reg_message:
                return
            logging(f'Message from unauthorized user. chat_id: {message.chat.id}, name: {message.from_user.full_name} : @{message.from_user.username}. \nMessage: {message.text}')
            # Прекращение активности регистрации через бота
            return
            state = dp.current_state(user=message.from_user.id)
            # await state.set_state(AllStates.QUESTION_REG_STATE)
            await AllStates.QUESTION_REG_STATE.set()
            await message.reply('Регистрация не найдена. Зарегистрироваться?', reply_markup=await generate_keyb(db, 'reg_keyboard_full'))
        elif str(message.from_user.id) in black_list:
            return

        user_info = await db.get_user_info(message.from_user.id)

        if message.text.lower() == '!kill' or message.text.lower() == 'kill' or message.text.lower() == 'килл':

            if 'reply_to_message' in message and 'caption' in message.reply_to_message and message.reply_to_message.caption:
                reply_message = message.reply_to_message.caption
            else:
                reply_message = message.reply_to_message.text
            base = re.findall("База {0,50}:([\а-яА-Яa-zA-Z0-9 \/ -_.]+)", reply_message)[0].strip()
            user = re.findall("Пользователь {0,50}:([\а-яА-Яa-zA-Z0-9_ -.ёЁ]+)", reply_message)[0].strip()
            number = re.findall("Номер сеанса {0,50}:([  \d]+)", reply_message)[0].strip()

            user_chat_admin = user_info['is_admin'] or await db.user_is_admin_of_chat_and_base(message.from_user.id, message.chat.id, base)

            if user_chat_admin:
                if base and user and number:
                    command = {'command': 'kill',
                               'chat_id': message.chat.id,
                               'base': base,
                               'user': user,
                               'number': number}
                    write_command(command)
                else:
                    logging(f'One of arguments is empty. Base: [{base}], user: [{user}], number: [{number}]')
            else:
                await message.reply('Ошибка доступа.')
        elif message.chat.id == message.from_user.id:
            # Вывести клавиатуру навигатор
            await message.reply('/start для начала взаимодействия.',
                                reply_markup=await generate_keyb(db, 'user0', user_info['tg_id'], is_admin=user_info['is_admin']))

    except Exception as e:
        error_exc = traceback.format_exc()
        logging(error_exc)


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('btn_decline_registration'), state='*')
async def process_callback_keyboard_accept_reg(callback_query: types.CallbackQuery):
    tg_id = re.findall("tg id:[ ]+(.*)", callback_query.message.text)[0]
    if user_active_check(callback_query.message):
        await callback_query.message.edit_text('Пользователь уже зарегистрирован. Отмена не возможна.')
    await db.add_black_list(tg_id)
    await bot.send_message(tg_id, 'Вам отказано в регистрации.')


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('btn_accept_registration'), state='*')
async def process_callback_keyboard_accept_reg(callback_query: types.CallbackQuery):
    tg_id = re.findall("tg id:[ ]+(.*)", callback_query.message.text)[0]
    await db.activate_user(tg_id)
    await bot.send_message(tg_id, 'Ваша учетная запись активирована.')
    state = Dispatcher.get_current().current_state(chat=int(tg_id), user=int(tg_id))
    await state.reset_state()
    await callback_query.message.reply('Регистрация подтверждена.')


async def sheduler():
    while True:
        sended_array = list()
        info = await db.get_info_for_accept_registration()
        admins = info[0]
        new_users = info[1]
        for user in new_users:
            message = list()
            message.append('Новая регистрация:\n')
            message.append(f'tg id:\t\t{user[0]}')
            message.append(f'Ник:\t\t{user[1]}')
            message.append(f'Телефон:\t{user[2]}')
            message.append(f'Имя:\t\t{user[3]}')
            message.append(f'Почта:\t\t{user[4]}')

            for admin in admins:
                await bot.send_message(admin[0], '\n'.join(message), reply_markup=await generate_keyb(db, 'reg_keyboard_accept'))
                sended_array.append(user[0])

        if sended_array:
            await db.clear_sended_reg_data(list(set(sended_array)))

        await asyncio.sleep(10)


async def on_startup(_):
    asyncio.create_task(sheduler())
    asyncio.create_task(run_exchange())


if __name__ == '__main__':
    run_polling()
