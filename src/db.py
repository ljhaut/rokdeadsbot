import os
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import dotenv_values
from constants import columns
from botConfigHandler import read_bot_config

config = dotenv_values('.env.dev')

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = config['3090_SPREADSHEET_ID']

def save_credentials(credentials):
    with open('token.json', 'w') as token:
        token.write(credentials.to_json())

def load_credentials():
    if os.path.exists('token.json'):
        return Credentials.from_authorized_user_file('token.json', SCOPES)
    return None

def refresh_credentials(credentials):
    credentials.refresh(Request())
    save_credentials(credentials)

def authenticate():
    credentials = load_credentials()

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            refresh_credentials(credentials)
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            credentials = flow.run_local_server(port=0)
            save_credentials(credentials)

    return credentials

async def store_deads_info(user_id, data):

    bot_config = read_bot_config()
    SHEET_NAME = bot_config['SHEET_NAME']

    print(f'{data} stored for {user_id}')

    try:
        credentials = authenticate()
        service = build('sheets', 'v4', credentials=credentials)
        sheets = service.spreadsheets()

        #get all discord ids
        result = sheets.values().get(spreadsheetId=SPREADSHEET_ID, range="ID correspondance!C:C").execute()
        discord_ids = result.get('values', [])

        #get all governor ids
        result = sheets.values().get(spreadsheetId=SPREADSHEET_ID, range="ID correspondance!A:A").execute()
        corresponding_gvrnr_ids = result.get('values', [])

        correct_gvrnr_id = None

        #find the correct governor id based on it's position in array (i)
        for i, id in enumerate(discord_ids):
            if str(user_id) in id:
                correct_gvrnr_id = corresponding_gvrnr_ids[i][0]
        
        if correct_gvrnr_id == None:
            print('No user found')
            return False
        
        result = sheets.values().get(spreadsheetId=SPREADSHEET_ID, range=f"{SHEET_NAME}!B:B").execute()
        gvrnr_ids_for_deads = result.get('values', [])

        for k, v in data.items():   # k: troop type, v: value of dead troops for troop type
            for i, id in enumerate(gvrnr_ids_for_deads):
                if correct_gvrnr_id in id:
                    row = i + 1 
                    sheets.values().update(spreadsheetId=SPREADSHEET_ID, range=f"{SHEET_NAME}!{columns[k]}{row}",    # find correspondance for correct column from "columns"
                                        valueInputOption="USER_ENTERED", body={"values": [[str(v)]]}).execute()

    except HttpError as err:
        print(err)
