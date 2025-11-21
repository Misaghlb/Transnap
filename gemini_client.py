import os
import requests
import base64
import io
from PIL import Image

class GeminiTranslator:
    def __init__(self, api_key=None):
        if not api_key:
            api_key = os.environ.get("GEMINI_API_KEY")
        
        if not api_key:
            raise ValueError("API Key is required. Please set GEMINI_API_KEY environment variable.")
            
        self.api_key = api_key
        # Using the endpoint provided by the user for gemini-2.0-flash
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"

    def translate_image(self, image: Image.Image, target_lang: str = "Persian (Farsi)") -> str:
        
        prompt = f"You are a professional translator tasked with converting text in this image into fluent, natural {target_lang}. Extract all visible text from the image and translate it with precision, using {target_lang} idioms, formal native structures, and a refined literary tone. Preserve the original text formatting as much as possible, including paragraph structure and any visible formatting. Provide only the translated content without any additional comments or explanations."
        try:
            # Convert image to base64
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": img_str
                            }
                        }
                    ]
                }]
            }

            headers = {'Content-Type': 'application/json'}
            
            print("Sending request to Gemini API...")
            response = requests.post(self.api_url, json=payload, headers=headers)
            
            if response.status_code != 200:
                return f"Error: API returned status {response.status_code}: {response.text}"
                
            result = response.json()
            
            # Parse the response
            try:
                return result['candidates'][0]['content']['parts'][0]['text']
            except (KeyError, IndexError) as e:
                return f"Error parsing response: {result}"

        except Exception as e:
            return f"Error during translation: {str(e)}"
