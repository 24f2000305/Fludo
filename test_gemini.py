import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
print(f"API Key found: {api_key[:20]}..." if api_key else "No API key found")

if api_key:
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        print("\nListing available models:")
        models = []
        for model in genai.list_models():
            if 'generateContent' in model.supported_generation_methods:
                models.append(model.name)
                print(f"  - {model.name}")
        
        if models:
            print(f"\nTesting first model: {models[0]}")
            test_model = genai.GenerativeModel(models[0])
            response = test_model.generate_content("Say hello")
            print(f"Success! Response: {response.text[:100]}")
        else:
            print("No models found!")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
