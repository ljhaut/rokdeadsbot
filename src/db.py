import os
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import dotenv_values

config = dotenv_values('.env.dev')

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = config['SPREADSHEET_ID']

credentials = None
if os.path.exists('token.json'):
    credentials = Credentials.from_authorized_user_file('token.json', SCOPES)
if not credentials or not credentials.valid:
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        credentials = flow.run_local_server(port=0)
    with open('token.json', 'w') as token:
        token.write(credentials.to_json())

def store_deads_info(user_id, data, column):
    try:
        service = build('sheets', 'v4', credentials=credentials)
        sheets = service.spreadsheets()

        result = sheets.values().get(spreadsheetId=SPREADSHEET_ID, range="ID correspondance!C:C").execute()
        discord_ids = result.get('values', [])
        result = sheets.values().get(spreadsheetId=SPREADSHEET_ID, range="ID correspondance!A:A").execute()
        corresponding_gvrnr_ids = result.get('values', [])

        correct_gvrnr_id = None

        for i, id in enumerate(discord_ids):
            if str(user_id) in id:
                correct_gvrnr_id = corresponding_gvrnr_ids[i][0]
        
        result = sheets.values().get(spreadsheetId=SPREADSHEET_ID, range="Dead mitigation!B:B").execute()
        gvrnr_ids_for_deads = result.get('values', [])

        for i, id in enumerate(gvrnr_ids_for_deads):
            if correct_gvrnr_id in id:
                row = i + 1 
                sheets.values().update(spreadsheetId=SPREADSHEET_ID, range=f"Dead mitigation!{column}{row}",
                                       valueInputOption="USER_ENTERED", body={"values": [[str(data)]]}).execute()

    except HttpError as err:
        print(err)
