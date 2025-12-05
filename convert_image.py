import base64
import sys

# Convert image to base64 for HTML embedding
def image_to_base64(image_path):
    try:
        with open(image_path, 'rb') as image_file:
            encoded = base64.b64encode(image_file.read()).decode('utf-8')
            print(f'data:image/jpeg;base64,{encoded}')
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)

if __name__ == '__main__':
    image_path = r'C:\Mission Interlectia\unnamed.jpg'
    image_to_base64(image_path)
