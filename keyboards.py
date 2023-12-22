from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton

async def generate_keyb(db, str_type, tg_id=None, base_name=None, pagination=None, is_admin=False):
    if type(tg_id) == int:
        tg_id = str(tg_id)

    keyboard = InlineKeyboardMarkup(row_width=3)
    if str_type == 'user0':
        keyboard.add(
            InlineKeyboardButton('Подписаться на события', callback_data='btn_subscribe'))
        keyboard.add(
            InlineKeyboardButton('Отписаться от событий', callback_data='btn_unsubscribe'))
        if is_admin:
            keyboard.add(
                InlineKeyboardButton('Подписать на события', callback_data='btn_subscribe_for_chat'))
            keyboard.add(
                InlineKeyboardButton('Отписать от событий', callback_data='btn_unsubscribe_for_chat'))
    elif str_type == 'subscribe' or str_type == 'unsubscribe':
        if str_type == 'subscribe':
            all_jobs = await db.get_user_sybscr_jobs('subscribe', tg_id, base_name)
        else:
            all_jobs = await db.get_user_sybscr_jobs('unsubscribe', tg_id, base_name)

        for job in all_jobs[pagination[0]:pagination[1]]:
            keyboard.add(InlineKeyboardButton(job[0], callback_data=f'{str_type}:'+job[1]))

        next = InlineKeyboardButton('>>', callback_data=f'{str_type}:>')
        middle = InlineKeyboardButton(f'{pagination[0]} : {pagination[1]}', callback_data='middle')
        prew = InlineKeyboardButton('<<', callback_data=f'{str_type}:<')
        keyboard.add(prew, middle, next)

        accept = InlineKeyboardButton('Применить', callback_data=f'{str_type}:accept')
        decline = InlineKeyboardButton('Отмена', callback_data=f'{str_type}:decline')
        keyboard.add(accept, decline)

    elif str_type == 'choice_base':
        all_base = await db.get_all_events_base()
        for base in all_base:
            keyboard.add(InlineKeyboardButton(base[0], callback_data=f'choice_base:{base[0]}'))
            
    elif str_type == 'reg_keyboard_accept':
        keyboard.add(InlineKeyboardButton('Подтвердить регистрацию', request_contact=True, callback_data='btn_accept_registration'))
        keyboard.add(InlineKeyboardButton('Отклонить', request_contact=True, callback_data='btn_decline_registration'))
        
    elif str_type == 'reg_keyboard_full':
        keyboard.add(InlineKeyboardButton('Отправить номер телефона', request_contact=True, callback_data='btn_registration'))
        
    elif str_type == 'keyboard_send_phone':
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton('Отправить номер телефона', request_contact=True))

    return keyboard