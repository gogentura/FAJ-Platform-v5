import asyncio
import logging

from app.bot import run_bot
from app.core.faj_core import FAJCore
from app.journal import Journal


logging.basicConfig(
    level=logging.INFO
)


async def main():

    core = FAJCore()

    journal = Journal()


    await run_bot(
        core,
        journal
    )



if __name__ == "__main__":

    asyncio.run(main())
