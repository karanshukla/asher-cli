import asyncio

from pylitterbot import Account

import os 
from dotenv import load_dotenv

load_dotenv()

username = os.getenv("LITTER_ROBOT_USER")
password = os.getenv("LITTER_ROBOT_PASSWORD")

async def main():
    # Create an account.
    account = Account()

    try:
        # Connect to the API and load robots.
        await account.connect(username=username, password=password, load_robots=True)

        # Print robots associated with account.
        print("Robots:")
        for robot in account.robots:
            print(robot)
            await robot.start_cleaning()
    finally:
        # Disconnect from the API.
        await account.disconnect()


if __name__ == "__main__":
    asyncio.run(main())