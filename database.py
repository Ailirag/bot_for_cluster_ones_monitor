import sqlite3
import os
import json
from datetime import datetime
from utils import logging

class DB(object):
    def __init__(self, current_path):
        self.conn = sqlite3.connect(current_path + os.sep + 'database.db')
        self.cur = self.conn.cursor()
        self.__init_base__()

    def __init_base__(self):
        sql = list()
        sql.append('''
            CREATE TABLE IF NOT EXISTS jobs(
           base_name TEXT,
           uuid TEXT,
           name TEXT);''')
        sql.append('''
            CREATE TABLE IF NOT EXISTS users(
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           tg_name TEXT,
           tg_id TEXT,
           phone TEXT,
           post TEXT,
           user_name TEXT,
           is_admin INT,
           active INT,
           email TEXT);''')
        sql.append('''
                CREATE TABLE IF NOT EXISTS subscriptions(
                base_name TEXT,
                user_id TEXT,
                uuid_job TEXT);''')
        sql.append('''
                CREATE TABLE IF NOT EXISTS settings(
                name TEXT,
                value TEXT);''')
        sql.append('''
                CREATE TABLE IF NOT EXISTS event_queue(
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                base_name TEXT,
                uuid_job TEXT,
                datetime TEXT,
                details TEXT,
                start TEXT,
                end TEXT,
                description TEXT);''')
        sql.append('''
                CREATE TABLE IF NOT EXISTS history(
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                base_name TEXT,
                uuid_job TEXT,
                datetime TEXT,
                description TEXT);''')
        sql.append('''CREATE TABLE IF NOT EXISTS black_list(
                tg_id TEXT,
                tg_name TEXT,
                full_name TEXT
                );''')
        sql.append('''CREATE TABLE IF NOT EXISTS registration_list(
                user_id TEXT,
                sended_notification_to_admins INT
                );''')
        sql.append('''CREATE TABLE IF NOT EXISTS subscriptions_on_bases(
                base_name TEXT,
                chat_id TEXT,
                description TEXT
                );''')
        sql.append('''CREATE TABLE IF NOT EXISTS chat_without_activites(
                chat_id TEXT);''')
        sql.append('''CREATE TABLE IF NOT EXISTS chat_admins(
                chat_id TEXT,
                user_id TEXT,
                base_name TEXT);''')
        for sql_text in sql:
            self.cur.execute(sql_text)
        self.conn.commit()

    def get_setting(self, setting_name):
        sql = '''select value from settings where name = ? '''
        self.cur.execute(sql, (setting_name))
        data = self.cur.fetchone()
        result = json.loads(data)
        return result

    def write_setting(self, setting_name, value, replace=False):
        sql = '''select name from settings where name = ?'''
        self.cur.execute(sql, (setting_name))
        data = self.cur.fetchone()

    async def register_jobs(self, base_name, data):
        sql = '''delete from jobs where base_name = ?'''
        self.cur.execute(sql, (base_name,))

        list_arguments = list()
        for event_name in data:
            list_arguments.append((base_name, event_name[0], event_name[1]))
        sql = '''insert into jobs values(?,?,?);'''
        self.cur.executemany(sql, list_arguments)
        self.conn.commit()

    async def register_events(self, base_name, events):
        try:
            sql = '''insert into event_queue(base_name, uuid_job, description, datetime, details, start, end) values (?,?,?,?,?,?,?)'''
            sql_history = '''insert into history(base_name, uuid_job, description, datetime) values (?,?,?,?)'''
            list_arguments_history = list()
            list_arguments = list()
            for data_event in events:
                list_arguments_history.append((base_name, data_event['uuid'], data_event['comment'], datetime.now()))
                list_arguments.append((base_name, data_event['uuid'], data_event['comment'], datetime.now(), data_event['details'], data_event['start'], data_event['end']))

            self.cur.executemany(sql, list_arguments)
            self.cur.executemany(sql_history, list_arguments_history)
            self.conn.commit()
            return True
        except Exception as e:
            error_exc = str(type(e)) + str(e)
            logging(error_exc)
            return False

    async def get_current_notifications(self):
        sql = 'select distinct base_name from event_queue'
        self.cur.execute(sql)
        all_bases = self.cur.fetchall()
        notification_on_bases = list()
        sql = '''SELECT e.id,
                       e.base_name,
                       e.uuid_job,
                       e.description,
                       e.details,
                       e.start,
                       e.end,
                       j.name
                  FROM event_queue e
                       INNER JOIN
                       jobs j ON e.uuid_job = j.uuid
                 WHERE e.base_name = ?;'''
        for base in all_bases:
            self.cur.execute(sql, (base[0],))
            notification_on_bases.append((base[0], self.cur.fetchall()))
        return notification_on_bases

    async def get_current_notifications_users(self):
        sql = '''select distinct
                u.tg_id,
                u.tg_name
                from event_queue as e
                inner join jobs as j
                on e.uuid_job = j.uuid
                inner join subscriptions as s
                on e.uuid_job = s.uuid_job
                inner join users as u
                on s.user_id = u.tg_id'''
        self.cur.execute(sql)
        all_users = self.cur.fetchall()

        sql = 'select distinct base_name from event_queue'
        self.cur.execute(sql)
        all_bases = self.cur.fetchall()

        sql = '''select 
                e.id,
                e.base_name,
                j.name,
                e.description,
                u.tg_id,
                u.tg_name,
                j.uuid,
                e.details,
                e.start,
                e.end

                from event_queue as e
                inner join jobs as j
                on e.uuid_job = j.uuid
                inner join subscriptions as s
                on e.uuid_job = s.uuid_job
                inner join users as u
                on s.user_id = u.tg_id
                where
                e.base_name = ? and u.tg_id = ?'''

        notification_on_users = list()
        for user in all_users:
            notification_on_base = list()
            for base in all_bases:
                self.cur.execute(sql, (base[0], user[0]))
                event_for_base = self.cur.fetchall()
                if event_for_base:
                    notification_on_base.append((base[0], event_for_base))
            notification_on_users.append((user[0], notification_on_base))

        return notification_on_users

    async def clear_sended_data(self, data):
        sql = 'delete from event_queue where base_name=? and uuid_job=?'
        array_arguments = list()
        self.cur.executemany(sql, list(set(data)))
        self.conn.commit()

    async def clear_sended_reg_data(self, tg_id):
        sql = 'delete from registration_list where user_id=?'
        self.cur.executemany(sql, (tg_id,))
        self.conn.commit()

    async def user_is_active(self, tg_id):
        sql = 'select active from users where tg_id = ?'
        self.cur.execute(sql, (tg_id,))
        info = self.cur.fetchone()
        if info is None:
            return None
        else:
            return bool(info[0])

    async def get_white_list(self) -> list:
        sql = '''select tg_id, active from users'''
        self.cur.execute(sql)
        result = list()
        for res in self.cur.fetchall():
            result.append(res[0])
        return result

    async def black_list(self) -> list:
        sql = 'select tg_id from black_list'
        self.cur.execute(sql)
        result = list()
        for res in self.cur.fetchall():
            result.append(res[0])
        return result

    async def add_black_list(self, id):
        sql = 'insert into black_list(tg_id) values (?)'
        self.cur.execute(sql, (id,))
        self.conn.commit()

    async def register_new_user(self, user_data):
        sql = 'insert into users (tg_name, tg_id, phone, post, user_name, is_admin, active, email) values (?,?,?,?,?,?,?,?)'
        array_arguments = list()
        array_arguments.append(user_data['tg_name'])
        array_arguments.append(user_data['tg_id'])
        array_arguments.append(user_data['phone_number'])
        array_arguments.append('human')
        array_arguments.append(user_data['full_name'])
        array_arguments.append(0)
        array_arguments.append(0)
        array_arguments.append(user_data['email'])
        self.cur.execute(sql, array_arguments)

        sql = 'insert into registration_list(user_id,sended_notification_to_admins) values (?,?)'
        self.cur.execute(sql, (user_data['tg_id'], 0))

        self.conn.commit()

    async def get_info_for_accept_registration(self):
        sql = 'select tg_id from users where is_admin = 1 and active = 1'
        self.cur.execute(sql)
        all_admins = self.cur.fetchall()
        sql = '''select distinct 
                rl.user_id,
                u.tg_name,
                u.phone,
                u.user_name,
                u.email

                from registration_list as rl
                inner join users as u
                on rl.user_id = u.tg_id'''
        self.cur.execute(sql)
        all_users = self.cur.fetchall()
        return (all_admins, all_users)

    async def get_user_info(self, tg_id):
        if type(tg_id) == int:
            tg_id = str(tg_id)
        sql = 'select * from users where tg_id = ?'
        self.cur.execute(sql, (str(tg_id),))
        sql_info = self.cur.fetchone()
        if sql_info is None:
            return None
        user_info = dict()
        user_info['tg_name'] = sql_info[1]
        user_info['tg_id'] = sql_info[2]
        user_info['phone'] = sql_info[3]
        user_info['full_name'] = sql_info[5]
        user_info['is_admin'] = sql_info[6]
        user_info['active'] = sql_info[7]
        user_info['email'] = sql_info[8]
        return user_info

    async def activate_user(self, tg_id):
        sql = 'update users set active=1 where tg_id = ?'
        self.cur.execute(sql, (tg_id,))
        self.conn.commit()

    async def get_user_sybscr_jobs(self, str_type, tg_id, base_name):
        if str_type == 'subscribe':
            sql = '''
            SELECT j.name,
                   j.uuid
              FROM jobs AS j
                   LEFT JOIN
                   subscriptions AS s ON j.uuid = s.uuid_job AND 
                                         s.user_id = ?
             WHERE j.base_name = ? AND 
                   s.uuid_job IS NULL
             ORDER BY j.name;'''
        else:
            sql = '''select
                    j.name,
                    j.uuid
                    from subscriptions as s
                    inner join 
                    jobs as j
                    on j.uuid = s.uuid_job
                    and s.user_id = ?
                    and s.base_name = ?
                    order by j.name'''

        self.cur.execute(sql, (tg_id, base_name))
        result = self.cur.fetchall()
        return result

    async def get_all_events_base(self):
        sql = 'select distinct base_name from jobs'
        self.cur.execute(sql)
        all_bases = self.cur.fetchall()
        return all_bases

    async def apply_subscribe(self, tg_id, all_data):
        sql = 'insert into subscriptions(base_name, user_id, uuid_job) values (?,?,?)'

        array_arguments = list()
        all_jobs = list()
        for job in list(set(all_data['jobs'])):
            array_arguments.append((all_data['base_name'], tg_id, job))
            all_jobs.append(job)

        self.cur.executemany(sql, array_arguments)
        self.conn.commit()

        return await self.get_all_subs(tg_id, all_data['base_name'])

    async def get_all_subs(self, tg_id, base_name):
        all_subs = await self.get_user_sybscr_jobs('unsubscribe', tg_id, base_name)
        result = list()
        for subs in all_subs:
            result.append(subs[0])
        return result

    async def delete_subscribe(self, tg_id, all_data):
        sql = 'delete from subscriptions where base_name = ? and user_id = ? and uuid_job = ?'
        array_argument = list()
        all_jobs = list()
        for job in list(set(all_data['jobs'])):
            array_argument.append((all_data['base_name'], tg_id, job))

        self.cur.executemany(sql, array_argument)
        self.conn.commit()

        return await self.get_all_subs(tg_id, all_data['base_name'])

    async def make_admin(self, tg_id, is_admin):
        sql = 'select tg_name from users where tg_id = ?'
        self.cur.execute(sql, (tg_id,))
        result = self.cur.fetchone()
        if result is None:
            return f'Пользователь с id:{tg_id} не обнаружен'
        else:
            sql = 'update users set is_admin = ? where tg_id = ?'
            self.cur.execute(sql, (is_admin, tg_id))
            self.conn.commit()
            return 'Успешно'

    async def subscribe_for_chat(self, base_name, chat_id):
        sql = 'select tg_id from users where tg_id = ?'
        self.cur.execute(sql, (chat_id,))
        result = self.cur.fetchone()
        if result is None:
            return 'Пользователь не найден.'

        sql_to_play = list()
        sql_to_play.append('Delete from subscriptions where user_id=? and base_name=?')
        sql_to_play.append('''
                    INSERT INTO subscriptions SELECT j.base_name,
                                 ?,
                                 j.uuid
                            FROM jobs AS j
                           WHERE base_name = ?;''')
        for sql in sql_to_play:
            self.cur.execute(sql, (chat_id, base_name))

        self.conn.commit()

        return 'Успешно'

    async def unsubscribe_for_chat(self, base_name, chat_id):
        sql = 'select tg_id from users where tg_id = ?'
        self.cur.execute(sql, (chat_id,))
        result = self.cur.fetchone()
        if result is None:
            return 'Пользователь не найден.'

        self.cur.execute('Delete from subscriptions where user_id=? and base_name=?', (chat_id, base_name))
        self.conn.commit()
        return 'Успешно'

    async def get_chats_for_base(self, base_name):
        sql = 'select chat_id from subscriptions_on_bases where base_name = ?'
        self.cur.execute(sql, (base_name,))
        result = self.cur.fetchall()
        return result

    async def get_chats_notification_bases(self):
        sql = 'select distinct chat_id from subscriptions_on_bases'
        self.cur.execute(sql)
        result = self.cur.fetchall()
        return result

    async def chat_without_activites(self, id):
        sql = 'select chat_id from chat_without_activites where chat_id = ?'
        self.cur.execute(sql, (id,))
        result = self.cur.fetchone()
        if result is None:
            return False
        else:
            return True

    async def update_chat_without_activites(self, new_data):
        try:
            sql = 'delete from chat_without_activites'
            self.cur.execute(sql)
            self.cur.executemany('insert into chat_without_activites values(?)', [(i,) for i in new_data])
            self.conn.commit()
            return True
        except Exception as e:
            error_exc = str(type(e)) + str(e)
            logging(error_exc)
            return False

    async def update_subscriptions_on_bases(self, data_json):
        try:
            if data_json['action'] == 'delete':
                sql = 'delete from subscriptions_on_bases where chat_id = ? and base_name = ?'
                self.cur.execute(sql,(data_json['chat_id'], data_json['base_name']))
            else:
                sql = 'delete from subscriptions_on_bases where chat_id = ? and base_name = ?'
                self.cur.execute(sql, (data_json['chat_id'], data_json['base_name']))
                sql = 'insert into subscriptions_on_bases(base_name,chat_id) values(?, ?)'
                self.cur.execute(sql, (data_json['base_name'], data_json['chat_id']))
            self.conn.commit()
            return True
        except Exception as e:
            error_exc = str(type(e)) + str(e)
            logging(error_exc)
            return False

    async def update_users(self, data_json):
        try:
            if data_json['action'] == 'delete':
                sql = 'delete from users' \
                      ' where' \
                      ' tg_name=:tg_name and tg_id=:tg_id and phone=:phone ' \
                      ' and user_name=:name and is_admin=:is_admin and active=:active and email=:email'
                self.cur.execute(sql, data_json)
            else:
                sql = 'delete from users' \
                      ' where' \
                      ' tg_name=:tg_name and tg_id=:tg_id and phone=:phone ' \
                      ' and user_name=:name and is_admin=:is_admin and active=:active and email=:email'
                self.cur.execute(sql, data_json)
                sql = 'insert into users (tg_name, tg_id, phone, post, user_name, is_admin, active, email) values (?,?,?,?,?,?,?,?)'
                arguments = list()
                arguments.append(data_json['tg_name'])
                arguments.append(data_json['tg_id'])
                arguments.append(data_json['phone'])
                arguments.append('human')
                arguments.append(data_json['name'])
                arguments.append(data_json['is_admin'])
                arguments.append(data_json['active'])
                arguments.append(data_json['email'])
                self.cur.execute(sql, arguments)

            self.conn.commit()
            return True
        except Exception as e:
            error_exc = str(type(e)) + str(e)
            logging(error_exc)
            return False

    async def update_subscriptions_on_user(self, data_json):
        try:
            if data_json['action'] == 'delete':
                sql = 'delete from subscriptions where base_name=:base_name and user_id=:user_id and uuid_job=:uuid_job'
                self.cur.execute(sql, data_json)
            else:
                sql = 'delete from subscriptions where base_name=:base_name and user_id=:user_id and uuid_job=:uuid_job'
                self.cur.execute(sql, data_json)

                sql = 'insert into subscriptions (base_name, user_id, uuid_job) values (:base_name, :user_id, :uuid_job)'
                self.cur.execute(sql, data_json)

            self.conn.commit()
            return True
        except Exception as e:
            error_exc = str(type(e)) + str(e)
            logging(error_exc)
            return False

    async def update_chat_admin(self, data_json):
        try:
            if data_json['action'] == 'delete':
                sql = 'delete from chat_admins where chat_id = :chat_id and base_name = :base_name'
                self.cur.execute(sql, data_json)
            else:
                sql = 'delete from chat_admins where chat_id = :chat and base_name = :base_name'
                self.cur.execute(sql, data_json)

                all_params = list()
                for chat in data_json['chats']:
                    all_params.append([chat, data_json['chat'], data_json['base_name']])
                self.cur.executemany(f'insert into chat_admins (user_id, chat_id, base_name) values (?,?,?)', all_params)

            self.conn.commit()
            return True
        except Exception as e:
            error_exc = str(type(e)) + str(e)
            logging(error_exc)
            return False

    async def user_is_admin_of_chat_and_base(self, user_id, chat_id, base):
        sql = '''
                SELECT 
                user_id,
                chat_id,
                base_name
                from chat_admins
                where user_id=:user_id and chat_id = :chat_id and base_name = :base_name'''
        self.cur.execute(sql, {'user_id': user_id, 'chat_id': chat_id, 'base_name': base})
        res = self.cur.fetchall()
        return bool(len(res))

