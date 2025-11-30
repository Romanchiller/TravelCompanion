import sys
import asyncio
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent))

from search_place_app.views.views import search_hotels

# Для асинхронного вызова
async def main():
    result = await search_hotels(search_info='New York', country_code='FR', max_results=20)
    print(result)

if __name__ == "__main__":
    asyncio.run(main())

# async def test_client():
#     client = httpx.AsyncClient()
#
#     response = await client.get(url='https://test.api.amadeus.com/v1/reference-data/locations/hotel',
#                                 headers={'accept': 'application/vnd.amadeus+json',
#                                          'Authorization': 'Bearer IPtTWrIbw5uffSLAz48q0jjiqOzh'},
#                                 params={'keyword': 'New York',
#                                         'subType': 'HOTEL_GDS',
#                                         'countryCode': 'FR',
#                                         'max': 20}
#                                  )
#
#     pprint(response.json())
#
# asyncio.run(test_client())
#
# async def get_token():
#
#     timeout = httpx.Timeout(connect=15.0, read=40.0, write=15.0, pool=40.0)
#     client = httpx.AsyncClient(timeout=timeout)
#     response = await client.post(url='https://test.api.amadeus.com/v1/security/oauth2/token',
#                                 headers={'Content-Type': 'application/x-www-form-urlencoded'},
#                                 data={'grant_type': 'client_credentials',
#                                       'client_id': 'TEAv0zHp7s4KVAVNQ4NQOf67gnvAGvM9',
#                                       'client_secret': 'FiE8fA1StahGF1nP'}
#                                  )
#     print(response.json())
#
# asyncio.run(get_token())