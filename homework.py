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

logger = logging.getLogger(__name__)

formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

console_handler = logging.StreamHandler(stream=sys.stdout)
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.setLevel(logging.DEBUG)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    ENV_VARS = {'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
                'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
                'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID}
    for key, value in ENV_VARS.items():
        if value is None:
            logger.critical(
                f'Отсутствует обязательная переменная окружения: "{key}". '
                'Программа принудительно остановлена.')
            sys.exit()


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение успешно отправлено.')
    except Exception:
        logger.error('Сбой при отправке сообщения.')


def get_api_answer(timestamp):
    """Возвращает ответ API, приведенный к типам даных Python."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=payload)
    except requests.RequestException:
        logger.error(f'Эндпоинт {ENDPOINT} недоступен.')
    if response.status_code == HTTPStatus.BAD_REQUEST:
        logger.error('Неверный формат from_date.')
        raise APIAnswerException('Неверный формат from_date.')
    if response.status_code == HTTPStatus.UNAUTHORIZED:
        logger.error(
            'Недействительный или некорректный токен PRACTICUM_TOKEN.'
        )
        raise APIAnswerException(
            'Недействительный или некорректный токен PRACTICUM_TOKEN.'
        )
    if response.status_code != HTTPStatus.OK:
        logger.error(
            f'Сбой в работе программы: Эндпоинт {ENDPOINT} '
            f'недоступен. Код ответа API: {response.status_code}.'
        )
        raise APIAnswerException(
            f'Сбой в работе программы: Эндпоинт {ENDPOINT} '
            f'недоступен. Код ответа API: {response.status_code}.'
        )
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        logger.error('В ответе API ожидается словарь.')
        raise TypeError('В ответе API ожидается словарь.')
    if response.get('homeworks') is None:
        logger.error('В ответе API отсутствует ключ "homeworks".')
        raise KeyError('В ответе API отсутствует ключ "homeworks".')
    if not isinstance(response.get('homeworks'), list):
        logger.error(
            'В ответе API под ключом "homeworks" '
            'ожидаются данные в виде списка.'
        )
        raise TypeError(
            'В ответе API под ключом "homeworks" '
            'ожидаются данные в виде списка.'
        )
    if response.get('current_date') is None:
        logger.error('В ответе API отсутствует ключ "current_date".')
        raise KeyError('В ответе API отсутствует ключ "current_date".')
    if len(response.get('homeworks')) == 0:
        logger.debug('В ответе отсутствуют новые статусы.')
    else:
        return response.get('homeworks')[0]


def parse_status(homework):
    """Получает статус домашней работы."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        logger.error('Отсутствует ключ "homework_name".')
        raise KeyError('Отсутствует ключ "homework_name".')
    verdict = HOMEWORK_VERDICTS.get(homework.get('status'))
    if verdict is None:
        logger.error(
            'API возвращает недокументированный статус домашней работы, '
            'либо домашку без статуса.'
        )
        raise Exception(
            'API возвращает недокументированный статус домашней работы, '
            'либо домашку без статуса.'
        )
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    current_error = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework:
                message = parse_status(homework)
                send_message(bot, message)
            timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if current_error != str(error):
                current_error = str(error)
                send_message(bot, message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
