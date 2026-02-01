import asyncio
import asyncpg
import os

async def test_connection():
    url = os.getenv('DATABASE_URL')
    print('Connecting to:', url)
    try:
        conn = await asyncpg.connect(url)
        print('Connected successfully')
        await conn.close()
    except Exception as e:
        print('Connection failed:', e)

if __name__ == '__main__':
    asyncio.run(test_connection())