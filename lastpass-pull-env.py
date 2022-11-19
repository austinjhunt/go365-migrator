import lastpass
import getpass
import os
print(
    '\nYou can run this script to automatically populate the .env environment '
    'file for the project by pulling it from LastPass if you have it stored '
    'there as a secure note.\n\n')
SAVE_ENV_TO_LOCAL_FOLDER = os.path.join(os.path.dirname(__file__), 'src')
SAVE_ENV_PATH = os.path.join(SAVE_ENV_TO_LOCAL_FOLDER, '.env')
username = input(
    'Please enter your LastPass username (user@cofc.edu): ').strip()
password = getpass.getpass(prompt='Please enter your LastPass password: ')
print('If the script is pausing here you may need to handle MFA on your mobile device.')
try:
    found = False
    vault = lastpass.Vault.open_remote(username, password)
    lastpass_folder = input(
        'Please enter the path to the parent folder of the .env secure note in LastPass (use a single backslash \\ to separate directories if nested): ')
    print('\nNow pulling the environment for this project from LastPass\n')
    env_file_contents = None
    for a in vault.accounts:
        folder = a.group.decode()
        name = a.name.decode()
        if folder == lastpass_folder and name == '.env':
            found = True
            env_file_contents = a.notes.decode()
            break
    if found:
        print('Found .env file in lastpass, extracting contents')
        print(f'Saving .env contents to {SAVE_ENV_PATH}')
        with open(SAVE_ENV_PATH, 'w') as f:
            f.write(env_file_contents)
    else:
        print(
            f'LastPass environment file {lastpass_folder}\\.env was not found')
except lastpass.exceptions.LastPassUnknownError as e:
    print(e)
    raise Exception(e)
