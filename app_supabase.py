import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

@app.route('/')
def index():
    return jsonify({
        'status': 'B-roll Mapper is running!',
        'message': 'Supabase connection configured',
        'supabase_url': SUPABASE_URL[:50] if SUPABASE_URL else 'Not configured'
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'supabase': 'configured' if SUPABASE_URL else 'missing',
        'openai': 'configured' if os.getenv('OPENAI_API_KEY') else 'missing'
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5002))
    print(f"🚀 Starting B-roll Mapper on port {port}")
    print(f"📊 Supabase URL: {SUPABASE_URL}")
    app.run(host='0.0.0.0', port=port, debug=False)
