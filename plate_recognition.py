from PIL import Image
from PIL import ImageDraw #импорт необходимого инструментария из библиотеки PIL
from PIL import ImageOps
import cv2 # импорт Open CV
import numpy as np
import os
import matplotlib.pyplot as plt
from matplotlib.pyplot import hist
from skimage.io import imread, imsave, imshow
import easyocr

def recognize_plate(plate_image):
    """Распознавание текста на картинке"""
    # конвертация в оттенки серого
    gray_plate = cv2.cvtColor(plate_image, cv2.COLOR_BGR2GRAY)

    # дополнительная обработка для EasyOCR
    _, binary_plate = cv2.threshold(gray_plate, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # увеличение изображения для лучшего распознавания
    scale_percent = 200  # увеличение на 200%
    width = int(binary_plate.shape[1] * scale_percent / 100)
    height = int(binary_plate.shape[0] * scale_percent / 100)
    resized = cv2.resize(binary_plate, (width, height), interpolation=cv2.INTER_CUBIC)

    # распознавание текста
    reader = easyocr.Reader(['ru'])
    string = reader.readtext(resized)
    result = ""
    for (bbox, text, prob) in string:
      result = text

    return result

def detect_place(image_path):
  result = ""
  # 1. Загрузка изображения
  car_img = cv2.imread(image_path)
  if car_img is None:
      print("Ошибка: изображение не загружено!")
      return

  # переводим в gray
  gray = cv2.cvtColor(car_img, cv2.COLOR_BGR2GRAY)

  # бинаризация + игра с шумом
  binary = cv2.inRange(gray, 100, 255)
  kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
  transform_img = cv2.dilate(binary, kernel, iterations=1)

  # перебираем все найденные контуры в цикле
  contours, _ = cv2.findContours(transform_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
  for icontour in contours:
    x, y, w, h = cv2.boundingRect(icontour)
    aspect_ratio = w / h
    # номер обычно шире, чем высота (2:1 - 5:1)
    if 2 < aspect_ratio < 5 and w > 50 and h > 10:
      number = car_img[y +1: y + h-1, x+1: x + w-1]
      text = recognize_plate(number)
      result += text

  if result == "":
    result = "Номер не найден или не прочитан"
  return result