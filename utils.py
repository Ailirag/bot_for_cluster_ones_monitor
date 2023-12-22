import requests
from datetime import datetime
import os
import uuid


async def only_send_message(id: str, text: str, TOKEN: str):
    url = "https://api.telegram.org/bot"
    url += TOKEN
    method = url + "/sendMessage"

    r = requests.post(method, data={
         "chat_id": id,
         "text": text
          })
    if r.status_code != 200:
        logging(f'chat_id={id}, status: {r.text}')


def logging(text):
    with open(f'{os.getcwd() + os.sep}log.txt', 'a', encoding='utf8') as log_file:
        for log_text in text.split('\n'):
            error = f'{datetime.now()} :   {log_text}'
            log_file.write(f'{error}\n')
            print(error)

async def send_document(text, path_to_doc, chat_id, TOKEN, remove_after=False):
    url = "https://api.telegram.org/bot"
    url += TOKEN
    method = url + "/sendDocument"

    with open(path_to_doc, "rb") as file_doc:
        files = {"document": file_doc}

        r = requests.post(method, data={
            "chat_id": chat_id,
            "caption": text
        }, files=files)

    if remove_after:
        os.remove(path_to_doc)

async def send_table_errors(table, clear_message, directory_for_exchange, chat_id, TOKEN):
    html_file_name = str(uuid.uuid4()) + '.html'
    # html_file_name = 'details.html'
    path_to_html_file = f'{directory_for_exchange}{os.sep}{html_file_name}'
    with open(path_to_html_file, 'w', encoding='utf8') as html_file:
        all_text = table.getTable()
        all_text = '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; CHARSET=utf-8">\n' +all_text.replace('<td>', '<td style="white-space: pre;">')
        html_file.write(all_text)

    await send_document(clear_message, path_to_html_file, chat_id, TOKEN, True)


async def get_sessions_from_base(base_name):
    pass