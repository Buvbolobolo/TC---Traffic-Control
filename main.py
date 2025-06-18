import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor
from PyQt5.QtCore import QThread, pyqtSignal, QElapsedTimer, Qt
from PyQt5 import QtCore, QtGui


# Импортируем UI классы
from main_window_designe import Ui_MainWindow
from data_modification_designe import Ui_MainWindow as DataModificationWindowUI

# Импортируем менеджер БД и функции распознавания
from license_plate_manager import LicensePlateManager
from plate_recognition import detect_place


class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)
    plate_detected_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url
        self.running = True
        self.plate_check_enabled = False
        self.cap = None

    def run(self):
        try:
            self.cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
            if not self.cap.isOpened():
                self.error_signal.emit("Ошибка: Не удалось открыть камеру")
                return

            timer = QElapsedTimer()
            while self.running:
                ret, frame = self.cap.read()
                if not ret:
                    self.error_signal.emit("Ошибка чтения кадра, попытка переподключения...")
                    self.msleep(1000)
                    continue

                self.change_pixmap_signal.emit(frame)

                if self.plate_check_enabled:
                    try:
                        temp_file = "temp_plate.jpg"
                        if cv2.imwrite(temp_file, frame):
                            plate_text = detect_place(temp_file)
                            if plate_text and plate_text != "Номер не найден или не прочитан":
                                self.plate_detected_signal.emit(plate_text)
                                self.plate_check_enabled = False
                    except Exception as e:
                        self.error_signal.emit(f"Ошибка распознавания: {str(e)}")

                # Ограничение FPS (~25 кадров/сек)
                ms_per_frame = 40
                elapsed = timer.elapsed()
                if elapsed < ms_per_frame:
                    self.msleep(ms_per_frame - elapsed)
                timer.start()

        except Exception as e:
            self.error_signal.emit(f"Критическая ошибка в потоке видео: {str(e)}")
        finally:
            if self.cap:
                self.cap.release()

    def stop(self):
        self.running = False
        self.wait()


class DataModificationWindow(QMainWindow, DataModificationWindowUI):
    def __init__(self, manager=None):
        super().__init__()
        self.setupUi(self)
        self.manager = manager

        # Связываем кнопки
        self.add_button.clicked.connect(self.add_record)
        self.delete_button.clicked.connect(self.delete_record)
        self.check_list_button.clicked.connect(self.show_all_records)

    def show_message(self, title, message):
        msg = QMessageBox()
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.exec_()

    def add_record(self):
        plate = self.lineEdit.text().strip()
        if not plate:
            self.show_message("Ошибка", "Поле ввода пустое!")
            return

        parts = plate.split()
        if len(parts) < 3:
            self.show_message("Ошибка",
                              "Неверный формат ввода!\nИспользуйте: номер фамилия имя [отчество]")
            return

        plate_number = parts[0]
        last_name = parts[1]
        first_name = parts[2]
        patronymic = " ".join(parts[3:]) if len(parts) > 3 else ""

        success, message = self.manager.add_plate(plate_number, first_name, last_name, patronymic)
        self.show_message("Результат", message)
        self.lineEdit.clear()

    def delete_record(self):
        plate = self.lineEdit.text().strip()
        if not plate:
            self.show_message("Ошибка", "Поле ввода пустое!")
            return

        plate_number = plate.split()[0]
        success, message = self.manager.delete_plate(plate_number)
        self.show_message("Результат", message)
        self.lineEdit.clear()

    def show_all_records(self):
        records = self.manager.list_all_plates()
        if not records:
            self.show_message("Информация", "Нет записей в базе.")
            return

        message = "Все записи в базе:\n\n"
        for record in records:
            full_name = f"{record[3]} {record[2]} {record[4]}" if record[
                4] else f"{record[3]} {record[2]}"
            message += f"{record[0]} | {record[1]} | {full_name} | {record[5]}\n"

        self.show_message("Список записей", message)


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        # Переменные
        self.current_frame = None
        self.is_processing = False
        self.url = "http://192.168.0.109:8080/video"
        self.recognized_plate = None

        # Менеджер БД
        self.manager = LicensePlateManager()

        # Второе окно
        self.data_modification_window = None

        # Настройка видеопотока
        self.setup_video_thread()

        # Связываем кнопки
        self.check_button.clicked.connect(self.start_plate_recognition)
        self.database_button.clicked.connect(self.open_data_modification_window)

    def setup_video_thread(self):
        self.thread = VideoThread(self.url)
        self.thread.change_pixmap_signal.connect(self.update_image)
        self.thread.plate_detected_signal.connect(self.on_plate_detected)
        self.thread.error_signal.connect(self.log)
        self.thread.start()

    def update_image(self, frame):
        """Обновление изображения в QLabel"""
        if self.is_processing or frame is None or frame.size == 0:
            return

        self.is_processing = True
        self.current_frame = frame.copy()

        try:
            label_size = self.video_label.size()
            resized = cv2.resize(frame, (label_size.width(), label_size.height()))
            rgb_image = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self.video_label.setPixmap(QPixmap.fromImage(qt_image))
        except Exception as e:
            self.log(f"Ошибка обновления изображения: {str(e)}")
        finally:
            self.is_processing = False

    def start_plate_recognition(self):
        """Запуск распознавания номерного знака"""
        if self.current_frame is None:
            self.log("Ошибка: Нет доступного кадра для проверки")
            return

        self.thread.plate_check_enabled = True
        self.log("Начато распознавание номерного знака...")

    def on_plate_detected(self, plate_text):
        """Обработка обнаруженного номерного знака"""
        self.recognized_plate = plate_text
        self.log(f"Распознан номер: {plate_text}")

        # Проверка номера в базе данных
        first_name, last_name, patronymic = self.manager.find_owner(plate_text)

        if first_name:
            result = "Проезжает"
            owner_info = f"{last_name} {first_name} {patronymic or ''}"
            self.log(f"Владелец найден: {owner_info}")
        else:
            result = "Не проезжает"
            self.log("Номер не найден в базе данных")

        self.show_result(result)

    def show_result(self, result):
        msg = QMessageBox()
        msg.setWindowTitle("Результат проверки")

        if result == "Проезжает":
            msg.setText(
                "<span style='color: #00AA00; font-weight: bold; font-size: 16pt;'>ПРОЕЗД РАЗРЕШЁН!</span>")
            msg.setInformativeText("Можете продолжать движение по территории объекта.")

            pixmap = QPixmap(100, 100)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setPen(QPen(QColor(0, 200, 0), 10))
            painter.drawLine(20, 50, 45, 75)
            painter.drawLine(45, 75, 85, 25)
            painter.end()
        else:
            msg.setText(
                "<span style='color: #AA0000; font-weight: bold; font-size: 16pt;'>ПРОЕЗД ЗАПРЕЩЁН!</span>")
            msg.setInformativeText("Машину необходимо остановить.")

            pixmap = QPixmap(100, 100)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setPen(QPen(QColor(200, 0, 0), 10))
            painter.drawLine(20, 20, 80, 80)
            painter.drawLine(20, 80, 80, 20)
            painter.end()

        msg.setIconPixmap(pixmap)
        msg.setStyleSheet("""
            QMessageBox {
                min-width: 400px;
            }
            QLabel#qt_msgbox_label {
                margin-left: 15px;
                font-size: 14pt;
            }
            QLabel#qt_msgbox_informativelabel {
                font-size: 12pt;
            }
            QPushButton {
                min-width: 100px;
                font-size: 12pt;
            }
        """)
        msg.exec_()

    def log(self, message):
        """Логирование сообщений в главном окне"""
        current_time = QtCore.QDateTime.currentDateTime().toString("hh:mm:ss")
        self.log_text.append(f"[{current_time}] {message}")
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def open_data_modification_window(self):
        """Открытие окна модификации данных"""
        try:
            if self.data_modification_window is None:
                self.data_modification_window = DataModificationWindow(manager=self.manager)
                self.data_modification_window.setAttribute(Qt.WA_DeleteOnClose)
                self.data_modification_window.destroyed.connect(
                    lambda: setattr(self, 'data_modification_window', None))

            if self.data_modification_window.isHidden():
                self.data_modification_window.show()
            self.data_modification_window.activateWindow()
            self.data_modification_window.raise_()
        except Exception as e:
            self.log(f"Ошибка при открытии окна: {str(e)}")

    def closeEvent(self, event):
        """Обработка закрытия главного окна"""
        self.thread.stop()
        self.manager.close()
        if self.data_modification_window is not None:
            self.data_modification_window.close()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())