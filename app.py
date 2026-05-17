import json
import os
import uuid
import pygame
import subprocess
# redirect と url_for を追加
from flask import Flask, render_template, jsonify, request, redirect, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024 
app.config['UPLOAD_SOUNDS'] = 'static/sounds'
app.config['UPLOAD_IMAGES'] = 'static/images'

os.makedirs(app.config['UPLOAD_SOUNDS'], exist_ok=True)
os.makedirs(app.config['UPLOAD_IMAGES'], exist_ok=True)

pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=4096)
pygame.mixer.init()

def load_data():
    if not os.path.exists('sounds.json'):
        return {
            "site": {
                "title": "soundboard", 
                "copyright": "2026 nuru", 
                "url": "https://keke-dev.net",
                "notes": ["Please upload only royalty-free or permitted audio.", "Max upload size is 500MB."]
            }, 
            "sounds": []
        }
    with open('sounds.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    with open('sounds.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route('/')
def index():
    # URLパラメータ ?allstop=true が来たら強制停止してリダイレクト
    if request.args.get('allstop') == 'true':
        try:
            pygame.mixer.stop()
        except Exception as e:
            pass
        # パラメータなしのトップページへ自動で飛ばす
        return redirect(url_for('index'))

    data = load_data()
    return render_template('index.html', data=data)

@app.route('/play/<sound_id>', methods=['POST'])
def play_sound(sound_id):
    data = load_data()
    sounds = data.get('sounds', [])
    target_sound = next((s for s in sounds if s['id'] == sound_id), None)
    
    if target_sound:
        filepath = os.path.join(app.config['UPLOAD_SOUNDS'], target_sound['file'])
        if os.path.exists(filepath):
            try:
                sound = pygame.mixer.Sound(filepath)
                sound.set_volume(1.0)
                sound.play()
                return jsonify({"status": "success"})
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
    return jsonify({"status": "not found"}), 404

@app.route('/upload', methods=['POST'])
def upload_sound():
    name = request.form.get('name')
    start_time = float(request.form.get('start_time', 0))
    end_time = float(request.form.get('end_time', 0))
    audio_file = request.files.get('audio')
    image_file = request.files.get('image')

    if not name or not audio_file:
        return jsonify({"status": "error", "message": "Required fields missing"}), 400

    temp_filename = "temp_" + secure_filename(audio_file.filename)
    temp_path = os.path.join(app.config['UPLOAD_SOUNDS'], temp_filename)
    audio_file.save(temp_path)

    final_filename = str(uuid.uuid4())[:8] + ".wav"
    final_path = os.path.join(app.config['UPLOAD_SOUNDS'], final_filename)

    try:
        command = [
            'ffmpeg', '-y',
            '-i', temp_path,
            '-ss', str(start_time),
            '-to', str(end_time),
	    '-af', 'volume=2.0',
            '-c:a', 'pcm_s16le',
            '-ar', '44100',
            '-ac', '2',
            final_path
        ]
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        duration_sec = round(end_time - start_time, 1)
        if duration_sec < 0: duration_sec = 0.0
        os.remove(temp_path)
        
    except Exception as e:
        if os.path.exists(temp_path): os.remove(temp_path)
        return jsonify({"status": "error", "message": "Audio processing error: " + str(e)}), 500

    image_filename = None
    if image_file and image_file.filename != '':
        orig_img_name = secure_filename(image_file.filename)
        image_filename = str(uuid.uuid4())[:8] + "_" + orig_img_name
        image_path = os.path.join(app.config['UPLOAD_IMAGES'], image_filename)
        image_file.save(image_path)

    data = load_data()
    new_id = str(uuid.uuid4())[:8]
    new_sound = {
        "id": new_id,
        "name": name,
        "duration": duration_sec,
        "image": image_filename,
        "file": final_filename
    }
    
    if 'sounds' not in data: data['sounds'] = []
    data['sounds'].append(new_sound)
    save_data(data)

    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
