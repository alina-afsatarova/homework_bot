import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import APIAnswerException

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    ENV_VARS = {'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
                'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
                'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID}
    none_count = 0
    for key, value in ENV_VARS.items():
        if value is None:
            none_count += 1
            logging.critical(
                f'Отсутствует обязательная переменная окружения: "{key}". '
                'Программа принудительно остановлена.')
    if none_count != 0:
        sys.exit()


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Сообщение успешно отправлено.')
    except Exception:
        logging.error('Сбой при отправке сообщения.')


def get_api_answer(timestamp):
    """Возвращает ответ API, приведенный к типам даных Python."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=payload)
    except Exception:
        raise Exception(f'Эндпоинт {ENDPOINT} недоступен.')
    if response.status_code == HTTPStatus.BAD_REQUEST:
        raise APIAnswerException('Неверный формат from_date.')
    if response.status_code == HTTPStatus.UNAUTHORIZED:
        raise APIAnswerException(
            'Недействительный или некорректный токен PRACTICUM_TOKEN.'
        )
    if response.status_code != HTTPStatus.OK:
        raise APIAnswerException(
            f'Сбой в работе программы: Эндпоинт {ENDPOINT} '
            f'недоступен. Код ответа API: {response.status_code}.'
        )
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(
            'Ожидаемый тип данных в ответе API - dict, '
            f'пришедший тип данных - {type(response)}.'
        )
    if 'homeworks' not in response:
        raise KeyError('В ответе API отсутствует ключ "homeworks".')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            'В ответе API под ключом "homeworks" ожидаются данные типа list, '
            f'пришедший тип данных - {type(homeworks)}'
        )
    if 'current_date' not in response:
        raise KeyError('В ответе API отсутствует ключ "current_date".')
    if len(homeworks) == 0:
        logging.debug('В ответе отсутствуют новые статусы.')
    else:
        return homeworks[0]


def parse_status(homework):
    """Получает статус домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name".')
    homework_name = homework['homework_name']
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status".')
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise Exception(
            'API возвращает недокументированный статус домашней работы.'
        )
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 0
    current_error = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework:
                message = parse_status(homework)
                send_message(bot, message)
            timestamp = response['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if current_error != str(error):
                current_error = str(error)
                send_message(bot, message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format=(
            '%(asctime)s, [%(levelname)s], %(funcName)s, '
            '%(lineno)d, %(message)s'
        ),
        handlers=[
            logging.FileHandler('main.log', mode='w', encoding='UTF-8'),
            logging.StreamHandler(stream=sys.stdout)
        ]
    )
    main()
