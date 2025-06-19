import sqlite3
import re
from difflib import SequenceMatcher

class LicensePlateValidator:
    def __init__(self, db_path='plates.db'):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.camera_plate = None
    
    def set_camera_plate(self, plate):
        self.camera_plate = plate
    
    def clean_plate(self, raw_plate):
        """
        Очистка номера с сохранением оригинальных символов
        и минимальными заменами только критичных ошибок
        """
        # Удаляем все не-буквенно-цифровые символы
        cleaned = re.sub(r'[^АВЕКМНОРСТУХ0-9]', '', raw_plate.upper())
        
        # Только самые необходимые замены:
        char_map = {
            '0': 'О', 
            'О': '0', 
            'З': '3',  
            'Ч': '4',  
        }
        
        return ''.join(char_map.get(c, c) for c in cleaned)
    
    def calculate_similarity(self, plate1, plate2):
        return SequenceMatcher(None, plate1, plate2).ratio() * 100
    
    def check_against_database(self, threshold=80):
        if not self.camera_plate:
            return []
        
        cleaned_plate = self.clean_plate(self.camera_plate)
        
        try:
            self.cursor.execute("SELECT plate_number, first_name, last_name, patronymic FROM car_owners")
            all_plates = self.cursor.fetchall()
            
            matches = []
            for db_plate, first_name, last_name, patronymic in all_plates:
                similarity = self.calculate_similarity(cleaned_plate, db_plate)
                if similarity >= threshold:
                    matches.append({
                        'plate': db_plate,
                        'similarity': round(similarity, 1),
                        'owner': f"{last_name} {first_name} {patronymic or ''}".strip()
                    })
            
            matches.sort(key=lambda x: x['similarity'], reverse=True)
            return matches
            
        except sqlite3.Error:
            return []
    
    def get_verdict(self, threshold=80):
        matches = self.check_against_database(threshold)
        
        return {
            'input': self.camera_plate,
            'cleaned': self.clean_plate(self.camera_plate) if self.camera_plate else None,
            'matches': matches,
            'access_granted': len(matches) > 0
        }
    
    def close(self):
        self.conn.close()