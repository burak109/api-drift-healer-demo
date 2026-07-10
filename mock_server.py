from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/users', methods=['POST'])
def create_user():
    data = request.json or {}
    
    if 'email_address' not in data:
        return jsonify({"error": "missing required field: email_address"}), 400
        
    return jsonify({"message": "User created", "email": data['email_address']}), 201

if __name__ == '__main__':
    print("[*] Mock Server 3000 portunda dinliyor...")
    app.run(port=3000)