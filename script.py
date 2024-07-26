# This is the lambda function that contains most of the logic for the FlightTracker for Savanti Travel.

# There is another script that operates when the flight is a day out, this one is specific to when the flight is 3 days out,
# thus the logic is mostly the same.



import requests
import json
from datetime import datetime, timedelta
import os

# FlightAware configurations
FA_BASE_URL = "https://aeroapi.flightaware.com/aeroapi"
FA_ENDPOINT = "/flights/{ident}"
FA_HEADERS = {
    "Authorization": "Bearer |||||||||||||||||||||||||||||||"
}

# Monday.com configurations
MONDAY_API_KEY = "|||||||||||||||||||||||||||||||"
MONDAY_HEADERS = {
    "Authorization": f"Bearer {MONDAY_API_KEY}",
    "Content-Type": "application/json",
    "API-Version": "2023-10"
}
MONDAY_BOARD_ID = 5370191526

def main():
    update_flight_statuses()

def get_flight_status_from_flightaware(ident, frequency):
    print("get_flight_status_from_flightaware; "+ident)
    # Getting today's date
    today = datetime.now()
    to_date = ''
    from_date = ''
    url = ''
    if frequency == 360:
        # Adding 2 days to today's date
        one_days_later = today + timedelta(days=2)

        # Formatting the date in yyyy-mm-dd format
        from_date = one_days_later.strftime("%Y-%m-%d")
        url = FA_BASE_URL + FA_ENDPOINT.format(ident=ident) +"?start="+from_date
    
    elif frequency == 15: 
         # Adding 1 days to today's date
        one_day_later = today + timedelta(days=1)

        to_date = one_day_later.strftime("%Y-%m-%d")
        from_date = today.strftime("%Y-%m-%d")
        url = FA_BASE_URL + FA_ENDPOINT.format(ident=ident) +"?start="+from_date+"&end="+to_date

    headers = {
        "x-apikey": FA_HEADERS["Authorization"].split()[-1],
        "Accept": "application/json; charset=UTF-8"
    }
    response = requests.get(url, headers=headers)
    response_data = response.json()
    flights = response_data.get("flights", [])
    if flights:
        return flights[0].get("status", "Unknown")
    else:
        return "Unknown"


def get_flights_from_monday(frequency):
    query = '''
     query ($boardId: [ID!], $columnId1: ID!, $columnValue1: CompareValue!){
        boards (ids: $boardId){
            items_page (limit: 500, query_params: {rules: [{column_id: $columnId1, compare_value: $columnValue1, operator: between}], operator: and}) {
                cursor
                items {
                    id 
                    name 

                    column_values {
                        id
                        type
                        value
                        text
                    }
                }
            }
        }
    }
    '''
    today = datetime.now()
    to_date = ''
    from_date = ''

    if frequency == 360:
        # Adding 2 days to today's date
        two_days_later = today + timedelta(days=2)

        to_date = two_days_later.strftime("%Y-%m-%d")
        from_date = to_date
    elif frequency == 15: 
        
         # Adding 1 day to today's date
        one_day_later = today + timedelta(days=1)

        to_date = one_day_later.strftime("%Y-%m-%d")
        from_date = today.strftime("%Y-%m-%d")

    # Variables for the query
    variables = {
        'boardId': [MONDAY_BOARD_ID],
        'columnId1': 'date_1',
        'columnValue1': [from_date, to_date]
    }

    # The payload for the request
    payload = {
        'query': query,
        'variables': variables
    }

    response = requests.post("https://api.monday.com/v2/", headers=MONDAY_HEADERS, json=payload)
    data = response.json()
    flights = parseData(data)
    return flights

def parseData(data):
    # Extracting required fields
    extracted_data = {}
    for board in data['data']['boards']:
        for item in board['items_page']['items']:
            item_id = item['id']
            item_name = item['name']
            text_1_value = next((cv['text'] for cv in item['column_values'] if cv['id'] == 'text_1'), None)

            extracted_data[item_id] = {'ItemName':item_name, 'status':text_1_value}

    return extracted_data


def update_status_on_monday(flight_id, status, formatted_datetime):
    # Ensure flight_id is an integer
    try:
        flight_id_int = int(flight_id)
    except ValueError:
        # Handle the case where flight_id cannot be converted to an integer
        return {"error": "Invalid flight_id. Must be an integer."}
    date_part, time_part = formatted_datetime.split(" ")
    
    mutation = '''
        mutation changeStatus($boardId: ID!, $itemId: ID!, $columnValues: JSON!) {
            change_multiple_column_values(
                board_id: $boardId,
                item_id: $itemId,
                column_values: $columnValues
            ) {
                id
            }
        }
    '''

    currenttime = {
        "date": date_part,
        "time": time_part
    }

    column_values = {
        "text_1": status,
        "date_17": currenttime
    }

    # variables for the mutation
    variables = {
        "boardId": MONDAY_BOARD_ID,
        "itemId": flight_id_int,
        "columnValues": json.dumps(column_values)
    }
    
    # JSOn payload
    payload = {
        'query': mutation,
        'variables': json.dumps(variables)
    }
   
    response = requests.post("https://api.monday.com/v2/", headers=MONDAY_HEADERS, json=payload)
    return response.json()

def update_flight_statuses(event, context):
    print("Updating flight status ")
    frequency = int(os.environ["RUN_FREQUENCY"])
    monday_flights = get_flights_from_monday(frequency)
    for item_id in monday_flights:
        flight_ident = monday_flights[item_id]['ItemName']
        flight_status = monday_flights[item_id]['status']    
        flightaware_status = get_flight_status_from_flightaware(flight_ident, frequency)
        # Current datetime in UTC
        current_datetime_utc = datetime.utcnow()

        formatted_datetime = current_datetime_utc.strftime("%Y-%m-%d %H:%M:%S")


        # Only update if the status on Monday.com doesn't match the desired status based on FlightAware's status
        if flightaware_status != flight_status:
            print(f"Updating status for Flight ID: {flight_ident} from {flight_status} to {flightaware_status}")
            update_status_on_monday(item_id, flightaware_status, formatted_datetime)
           
            

#update_flight_statuses()
if __name__ == "__main__":
   update_flight_statuses()