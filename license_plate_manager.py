import sqlite3
import re
import sys
import io
from datetime import datetime

# кодировка
if sys.stdout.encoding != 'UTF-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

class LicensePlateManager:
    def __init__(self, db_name='plates.db'):
        """Инициализация соединения с базой данных"""
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_table()
        
    def create_table(self):
        """Создание таблицы, если она не существует"""
        try:
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS car_owners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate_number TEXT NOT NULL UNIQUE,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                patronymic TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Ошибка при создании таблицы: {e}")
    
    @staticmethod
    def is_valid_plate(plate):
        """Проверка формата номера по российскому стандарту"""
        pattern = r'^[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}$'
        return re.match(pattern, plate.upper()) is not None
    
    def add_plate(self, plate, first_name, last_name, patronymic):
        """Добавление нового номера в базу данных"""
        if not self.is_valid_plate(plate):
            return False, "Неверный формат номера! Используйте формат: А123АA123 "
        
        try:
            self.cursor.execute("""
            INSERT INTO car_owners (plate_number, first_name, last_name, patronymic)
            VALUES (?, ?, ?, ?)
            """, (plate.upper(), first_name, last_name, patronymic))
            self.conn.commit()
            return True, f"Номер {plate} успешно добавлен!"
        except sqlite3.IntegrityError:
            return False, f"Ошибка: номер {plate} уже существует в базе!"
        except sqlite3.Error as e:
            return False, f"Ошибка базы данных: {e}"


    def delete_plate(self, plate):
        """Удаление номера из базы данных"""
        try:
            #  существует ли номер
            self.cursor.execute("""
            SELECT id FROM car_owners WHERE plate_number = ?
            """, (plate.upper(),))
            if not self.cursor.fetchone():
                return False, f"Номер {plate} не найден в базе данных"
            
            # Удаляем запись
            self.cursor.execute("""
            DELETE FROM car_owners WHERE plate_number = ?
            """, (plate.upper(),))
            self.conn.commit()
            
            # Проверяем успешность удаления
            if self.cursor.rowcount > 0:
                return True, f"Номер {plate} успешно удален!"
            return False, f"Ошибка при удалении номера {plate}"
        except sqlite3.Error as e:
            return False, f"Ошибка базы данных: {e}"
    
    def list_all_plates(self):
        """Получение всех записей из базы"""
        try:
            self.cursor.execute("SELECT * FROM car_owners")
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Ошибка при получении данных: {e}")
            return []
    
    def close(self):
        """Закрытие соединения с базой данных"""
        try:
            self.cursor.close()
            self.conn.close()
        except:
            pass