import json

def read_bot_config(file_path='bot_config.json'):
    with open(file_path, 'r') as file:
        return json.load(file)

# params: config dict, name for sheet name
def update_bot_config_sheet_name(config, name):
    config['SHEET_NAME'] = name
    write_bot_config(config)

# params: config dict, admins as many discord ids as wanted separated with a comma
def add_admins_to_bot_config(config, *admins):
    for i in admins:
        config['ADMINS'].append(i)
    write_bot_config(config)

# params: config dict, admins as many discord ids as wanted separated with a comma
def remove_admins_from_bot_config(config, *admins):
    for i in admins:
        if i in config['ADMINS'] and i not in config['SUPERUSERS']:
            config['ADMINS'].remove(i)
    write_bot_config(config)

def write_bot_config(config, file_path='bot_config.json'):
    with open(file_path, 'w') as file:
        json.dump(config, file, indent=4)