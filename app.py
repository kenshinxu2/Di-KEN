from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import os

app = Flask(__name__)
# CORS lagana zaroori hai warna tumhara HTML direct baat nahi kar payega
CORS(app) 

# Gemini API ko setup karna (Yeh API key Railway se aayegi)
API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Website ka text yaad rakhne ke liye temporary variable
scraped_data = ""

@app.route('/learn', methods=['POST'])
def learn_website():
    global scraped_data
    data = request.json
    url = data.get('url')

    try:
        # 1. Website se data nikalna (Scraping)
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Faltu chizein (code, style) hata kar sirf text nikalna
        for script in soup(["script", "style"]):
            script.extract()
        scraped_data = soup.get_text(separator=' ', strip=True)

        # AI ke dimagh ki ek limit hoti hai, isliye pehle 15,000 words hi lenge
        scraped_data = scraped_data[:15000]

        # 2. AI se Report banwana
        prompt = f"Niche diye gaye text ko padho aur ek short summary/report do (Hindi-English mix mein) ki is page par kya information hai:\n\n{scraped_data}"
        report = model.generate_content(prompt).text

        return jsonify({"status": "success", "report": report})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route('/ask', methods=['POST'])
def ask_question():
    global scraped_data
    data = request.json
    question = data.get('question')

    if not scraped_data:
        return jsonify({"error": "Pehle koi website padhao bhai!"})

    try:
        # 3. AI ko website ka data aur tumhara sawal dena
        prompt = f"""
        Tumhe niche diye gaye 'Website Content' ke basis par user ke 'Question' ka jawab dena hai. 
        Agar jawab is content mein nahi hai, toh saaf bol do 'Sorry, yeh info is link me nahi hai'. 
        Khud se kahani mat banana.
        
        Website Content:
        {scraped_data}
        
        User Question: {question}
        """
        
        answer = model.generate_content(prompt).text
        return jsonify({"answer": answer})
    
    except Exception as e:
        return jsonify({"error": str(e)})

# Yeh line local testing ke liye hai, Railway ise ignore karega aur Gunicorn use karega
if __name__ == '__main__':
    app.run(debug=True, port=5000)
