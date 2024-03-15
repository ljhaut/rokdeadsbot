import cv2
from ultralytics import YOLO
import pytesseract
from PIL import Image, ImageOps
from dotenv import dotenv_values
import numpy as np

config = dotenv_values('.env.dev')
debug = True if config['DEBUG'] == 'True' else False

# Converts YOLO format coordinates to bounding box bottom left and top right coordinates
def convert_coordinates(center_x, cetner_y, width, height):
    x_min = center_x - (width / 2)
    y_min = cetner_y - (height / 2)
    x_max = center_x + (width / 2)
    y_max = cetner_y + (height / 2)
    return (int(x_min), int(y_min), int(x_max), int(y_max))

def do_boxes_overlap(box1, box2):
    # Check if two boxes (in [x_min, y_min, x_max, y_max] format) overlap
    return not (box2[0] > box1[2] or box2[2] < box1[0] or box2[1] > box1[3] or box2[3] < box1[1])

# For making the bounding box data more suitable for the program
def update_data_with_converted_coordinates(data):
    converted_data = {}
    for key, value in data.items():
        xywh = value['xywh']
        # Convert tensors to float, if they are tensors
        xywh = [x.item() if hasattr(x, 'item') else x for x in xywh]
        x_min, y_min, x_max, y_max = convert_coordinates(*xywh)
        converted_data[key] = {
            'xywh': [x_min, y_min, x_max, y_max],
            'conf': value['conf']
        }
    
    # Identify overlapping boxes and remove lower confidence ones
    keys_to_remove = set()
    keys = list(converted_data.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            key1, key2 = keys[i], keys[j]
            # checks if 2 troop type bounding boxes overlap
            if ('amount' not in key1 and 'amount' not in key2) and do_boxes_overlap(converted_data[key1]['xywh'], converted_data[key2]['xywh']):
                if converted_data[key1]['conf'] < converted_data[key2]['conf']:
                    keys_to_remove.add(key1)
                elif converted_data[key1]['conf'] > converted_data[key2]['conf']:
                    keys_to_remove.add(key2)

    # Remove identified boxes
    for key in keys_to_remove:
        del converted_data[key]
    
    return converted_data

# make pairs from troop types and their corresponding amounts, based on the spatial distances of the bounding boxes
def make_pairs(data):
    # Identify 'amount' labels and 'other' labels
    amount_labels = [v['xywh'] + [k] for k, v in data.items() if 'amount' in k]
    other_labels = [v['xywh'] + [k] for k, v in data.items() if 'amount' not in k]

    def is_to_the_right_and_aligned(other_label, amount_label, tolerance=20):   # tolerance for possible overlapping of the amount bbox
        # Check if the amount label is to the right of the other label
        other_right_edge = other_label[2]  # x_max of other label
        amount_left_edge = amount_label[0]  # x_min of amount label
        # Check vertical alignment (overlap in y-axis)
        other_vertical_range = set(range(other_label[1], other_label[3]))
        amount_vertical_range = set(range(amount_label[1], amount_label[3]))
        is_aligned_vertically = other_vertical_range.intersection(amount_vertical_range) != set()
        return amount_left_edge >= other_right_edge - tolerance and is_aligned_vertically
    
    pairs = []
    for other in other_labels:
        closest_label = None
        min_distance = float('inf')
        for amount in amount_labels:
            if is_to_the_right_and_aligned(other, amount):
                # Calculate horizontal distance from the right edge of 'other' to the left edge of 'amount'
                distance = amount[0] - other[2]  # x_min of amount - x_max of other
                if distance < min_distance:  # Ensuring the 'amount' label is to the right and vertically aligned
                    min_distance = distance
                    closest_label = amount
        if closest_label:
            pairs.append((other, closest_label))

    return pairs

# for capturing the amount from specified roi
def extract_text_from_amount_roi(image, roi):

    cropped_image = image.crop(roi)  # roi is (x_min, y_min, x_max, y_max)

    gray_image = ImageOps.grayscale(cropped_image)  # grayscaling

    threshold_image = gray_image.point(lambda x: 0 if x < 128 else 255, '1')    # binary threshold

    # Perform OCR
    text = pytesseract.image_to_string(threshold_image, config='--psm 6 digits')
    return text.strip()

# process every pair for troop type and corresponding amount as output
def process_image_pairs_for_roi(pairs, image):

    image = Image.fromarray(image)

    ocr_results = {}

    for pair in pairs:
        class_name, amount_box = pair[0][4], pair[1][:4]    # Extract class name and amount box coordinates
        ocr_result = extract_text_from_amount_roi(image, amount_box)
        ocr_results[class_name] = ocr_result

    return ocr_results

# find the roi for all deads of the original image
def find_roi_for_input_image(image):
    try:
        nparr = np.frombuffer(image, np.uint8)

        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)   # convert image to cv2 readable format

        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)    # image to grayscale

        _, binary = cv2.threshold(gray_image, 210, 255, cv2.THRESH_BINARY)  # binary threshold for grayscale image

        contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)  # find contours for the roi

        contour = max(contours, key=cv2.contourArea)    # largest contour

        copy = image.copy()

        cv2.drawContours(copy, contour, -1, (255, 0, 0), 3)

        x, y, w, h = cv2.boundingRect(contour)  # create coords for roi 

        roi = image[y:y+h, x:x+w] # crop roi from image

        return roi
    except:
        print('no roi, bad picture')

# "main" method
def read_roi_and_create_output_for_amounts(image):

    model = YOLO(r'runs\detect\train4\weights\best.onnx')   # load model

    roi = find_roi_for_input_image(image)

    # make predictions of labels with model
    if debug == False:
        results = model(roi)
    else:
        results = model(roi, save=True, save_txt=True)

    dict = {}
    
    # process the results into more suitable format for the program
    for i, box in enumerate(results[0].boxes.xywh):
        x, y, w, h = box
        class_id = int(results[0].boxes.cls[i])
        class_name = results[0].names[class_id]
        confidence = results[0].boxes.conf[i]
        if class_name == 'amount':
            dict[f'{class_name}_{i}'] = {'xywh':[x, y, w, h], 'conf':confidence}
        else:
            if class_name in dict and dict[class_name]['conf'] > confidence:
                continue
            else:
                dict[class_name] = {'xywh':[x, y, w, h], 'conf':confidence}
    
    pairs = make_pairs(update_data_with_converted_coordinates(dict))

    ocr_results = process_image_pairs_for_roi(pairs, roi)
    
    # process the data for any unwanted characters
    for k, v in ocr_results.items():
        if '.' in v:
            ocr_results[k] = v.replace('.', '')

    return ocr_results
