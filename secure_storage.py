import sqlite3
import threading
import base64
import json
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class SecureStorage:
    def __init__(self, db_path: str = "passwords.db"):
        self.db_path = db_path
        self.lock = threading.Lock()  # Для потокобезопасности
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS passwords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    account TEXT NOT NULL,
                    encrypted_password TEXT NOT NULL,
                    date_added TEXT NOT NULL
                )
            ''')
            conn.commit()
    
    def generate_key_from_password(self, password: str) -> bytes:
        """Создание ключа шифрования из пароля"""
        password_bytes = password.encode()
        salt = b'salt_12345678'  # В реальном приложении используйте случайную соль
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
        return key
    
    def encrypt_data(self, data: str, key: bytes) -> str:
        """Шифрование данных"""
        f = Fernet(key)
        encrypted_bytes = f.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted_bytes).decode()

    def decrypt_data(self, encrypted_data: str, key: bytes) -> str:
        """Расшифровка данных"""
        f = Fernet(key)
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
        decrypted_bytes = f.decrypt(encrypted_bytes)
        return decrypted_bytes.decode()
    
    def save_password(self, user_id: int, account: str, password: str):
        """Сохранение зашифрованного пароля"""
        with self.lock:
            # Создаем ключ на основе user_id
            key = self.generate_key_from_password(str(user_id))
            
            # Шифруем пароль
            encrypted_password = self.encrypt_data(password, key)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO passwords (user_id, account, encrypted_password, date_added) VALUES (?, ?, ?, ?)",
                    (user_id, account, encrypted_password, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                )
                conn.commit()
    
    def get_passwords(self, user_id: int):
        """Получение расшифрованных паролей пользователя"""
        with self.lock:
            key = self.generate_key_from_password(str(user_id))
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT account, encrypted_password, date_added FROM passwords WHERE user_id = ?",
                    (user_id,)
                )
                rows = cursor.fetchall()
                
                # Расшифровываем пароли
                result = []
                for row in rows:
                    try:
                        decrypted_password = self.decrypt_data(row[1], key)
                        result.append({
                            "account": row[0],
                            "password": decrypted_password,
                            "date_added": row[2]
                        })
                    except Exception as e:
                        print(f"Error decrypting password for user {user_id}: {e}")
                        # Возвращаем зашифрованный пароль как есть, если расшифровка не удалась
                        result.append({
                            "account": row[0],
                            "password": "[Ошибка при расшифровке]",
                            "date_added": row[2]
                        })
                return result
    
    def delete_all_passwords(self, user_id: int):
        """Удаление всех паролей пользователя"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM passwords WHERE user_id = ?", (user_id,))
                conn.commit()
    
    def account_exists(self, user_id: int, account: str) -> bool:
        """Проверка, существует ли уже учетная запись"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM passwords WHERE user_id = ? AND account = ?",
                    (user_id, account)
                )
                return cursor.fetchone() is not None