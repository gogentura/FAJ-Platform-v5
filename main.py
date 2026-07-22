"""
FAJ Platform v5.1
Main Launcher

Автоматический запуск:
- создание базы РПЛ
- запуск Telegram Bot
"""

import logging

from app.rpl_database import create_rpl_database
from app.bot import run_bot


logging.basicConfig(
    level=logging.INFO
)


def main():

    logging.info(
        "FAJ Platform starting..."
    )


    # Создание базы паспортов РПЛ
    try:

        create_rpl_database()

        logging.info(
            "FAJ RPL Database created"
        )

    except Exception as e:

        logging.error(
            f"RPL database error: {e}"
        )


    # Запуск Telegram Bot

    run_bot()



if __name__ == "__main__":

    main()
