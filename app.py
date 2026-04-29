# AI Subtitle Generator
# Cloud Application Development Project
# 4th Semester
# Using IBM Watson Speech to Text API

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from ibm_watson import SpeechToTextV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from moviepy import VideoFileClip
import os
import traceback

# NOTE: removed dotenv import
# Railway sets environment variables directly
# dotenv is only needed for local development

# try to load dotenv only if available
# this way it works both locally and on Railway
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("dotenv loaded for local development")
except:
    print("dotenv not loaded - using Railway environment variables")

# get current folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')

# setup flask
app = Flask(__name__, template_folder=TEMPLATE_DIR)
CORS(app)

# folders
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'outputs')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

# get IBM credentials from environment
# Railway sets these as environment variables
IBM_API_KEY = os.environ.get('IBM_API_KEY')
IBM_URL = os.environ.get('IBM_URL')

# debug print to check credentials
print("\n--- IBM CREDENTIALS CHECK ---")
print(f"IBM_API_KEY exists: {IBM_API_KEY is not None}")
print(f"IBM_API_KEY length: {len(IBM_API_KEY) if IBM_API_KEY else 0}")
print(f"IBM_URL exists: {IBM_URL is not None}")
print(f"IBM_URL value: {IBM_URL}")
print("-----------------------------\n")

# only confirmed working models
LANGUAGES = {
    'en-US': 'English (US)',
    'en-GB': 'English (UK)',
    'fr-FR': 'French',
    'de-DE': 'German',
    'es-ES': 'Spanish',
    'ja-JP': 'Japanese',
    'ko-KR': 'Korean',
    'pt-BR': 'Portuguese',
    'ar-AR': 'Arabic',
    'zh-CN': 'Chinese (Simplified)',
}

# connect IBM Watson
print("connecting to IBM Watson...")
ibm_stt = None

try:
    if not IBM_API_KEY:
        print("ERROR: IBM_API_KEY is missing!")
        print("Add IBM_API_KEY in Railway Variables tab")
    elif not IBM_URL:
        print("ERROR: IBM_URL is missing!")
        print("Add IBM_URL in Railway Variables tab")
    else:
        print(f"trying to connect with key length: {len(IBM_API_KEY)}")
        authenticator = IAMAuthenticator(IBM_API_KEY)
        ibm_stt = SpeechToTextV1(authenticator=authenticator)
        ibm_stt.set_service_url(IBM_URL)
        
        # test connection
        models = ibm_stt.list_models().get_result()
        print(f"IBM Watson connected!")
        print(f"available models: {len(models['models'])}")
        ibm_stt = ibm_stt
        
except Exception as e:
    print(f"IBM Watson connection failed!")
    print(f"Error: {e}")
    traceback.print_exc()
    ibm_stt = None

# convert seconds to srt time
def convert_to_srt_time(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"

# extract audio from video
def extract_audio(video_file_path):
    try:
        print(f"extracting audio...")
        vid = VideoFileClip(video_file_path)
        audio_file_path = video_file_path.rsplit('.', 1)[0] + '.wav'
        vid.audio.write_audiofile(
            audio_file_path,
            fps=16000,
            codec='pcm_s16le',
            logger=None
        )
        vid.close()
        size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)
        print(f"audio extracted! size: {size_mb:.2f} MB")
        return audio_file_path
    except Exception as e:
        print(f"audio extraction error: {e}")
        traceback.print_exc()
        return None

# get subtitles from IBM Watson
def get_subtitles_from_ibm(audio_path, lang_code='en-US'):
    try:
        print(f"sending to IBM Watson...")
        print(f"language: {lang_code}")

        if not os.path.exists(audio_path):
            print("ERROR: audio file not found!")
            return None

        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        print(f"audio size: {file_size_mb:.2f} MB")

        if file_size_mb > 90:
            print("ERROR: audio too large!")
            return None

        model_name = lang_code + '_BroadbandModel'
        print(f"model: {model_name}")

        with open(audio_path, 'rb') as audio_file:
            ibm_response = ibm_stt.recognize(
                audio=audio_file,
                content_type='audio/wav',
                model=model_name,
                timestamps=True,
                smart_formatting=True,
            ).get_result()

        print(f"response received!")
        print(f"results: {len(ibm_response.get('results', []))}")

        segments_list = []
        for res in ibm_response.get('results', []):
            if res.get('alternatives'):
                best_alt = res['alternatives'][0]
                text = best_alt.get('transcript', '').strip()
                word_times = best_alt.get('timestamps', [])
                if text and word_times:
                    segments_list.append({
                        'start': word_times[0][1],
                        'end': word_times[-1][2],
                        'text': text
                    })

        print(f"segments: {len(segments_list)}")
        return segments_list

    except Exception as e:
        print(f"IBM Watson error: {e}")
        traceback.print_exc()
        return None

# create srt file
def create_srt_file(segments, srt_output_path):
    try:
        srt_file = open(srt_output_path, 'w', encoding='utf-8')
        for idx, seg in enumerate(segments):
            srt_file.write(str(idx + 1) + '\n')
            srt_file.write(
                convert_to_srt_time(seg['start']) +
                ' --> ' +
                convert_to_srt_time(seg['end']) + '\n'
            )
            srt_file.write(seg['text'] + '\n')
            srt_file.write('\n')
        srt_file.close()
        print(f"SRT created!")
        return True
    except Exception as e:
        print(f"SRT error: {e}")
        return False

# delete temp files
def delete_temp_files(video_path, audio_path):
    try:
        if video_path and os.path.exists(video_path):
            os.remove(video_path)
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
        print("temp files deleted")
    except Exception as e:
        print(f"cleanup error: {e}")

# home page
@app.route('/')
def home():
    return render_template('index.html', languages=LANGUAGES)

# health check - use this to verify IBM connection
@app.route('/health')
def health_check():
    return jsonify({
        'server': 'running',
        'ibm_watson': 'connected' if ibm_stt is not None else 'NOT connected',
        'ibm_key_exists': IBM_API_KEY is not None,
        'ibm_url_exists': IBM_URL is not None,
        'ibm_key_length': len(IBM_API_KEY) if IBM_API_KEY else 0,
        'upload_folder': os.path.exists(UPLOAD_FOLDER),
        'output_folder': os.path.exists(OUTPUT_FOLDER)
    })

# upload route
@app.route('/upload', methods=['POST'])
def upload_video():
    print("\n--- new upload ---")

    try:
        # check IBM Watson
        if ibm_stt is None:
            return jsonify({
                'error': 'IBM Watson not connected. Check Railway Variables: IBM_API_KEY and IBM_URL'
            }), 500

        if 'video' not in request.files:
            return jsonify({'error': 'No video uploaded'}), 400

        uploaded_file = request.files['video']

        if uploaded_file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        selected_language = request.form.get('language', 'en-US')
        print(f"language: {selected_language}")

        # save video
        video_name = uploaded_file.filename
        video_save_path = os.path.join(UPLOAD_FOLDER, video_name)
        uploaded_file.save(video_save_path)
        print(f"video saved: {video_name}")

        # extract audio
        print("step 1: extracting audio...")
        audio_save_path = extract_audio(video_save_path)

        if audio_save_path is None:
            delete_temp_files(video_save_path, None)
            return jsonify({'error': 'Could not extract audio from video'}), 500

        # IBM Watson
        print("step 2: IBM Watson processing...")
        subtitle_segments = get_subtitles_from_ibm(audio_save_path, selected_language)

        if subtitle_segments is None:
            delete_temp_files(video_save_path, audio_save_path)
            return jsonify({'error': 'IBM Watson processing failed. Check Railway logs.'}), 500

        if len(subtitle_segments) == 0:
            delete_temp_files(video_save_path, audio_save_path)
            return jsonify({'error': 'No speech detected in video'}), 400

        # create SRT
        print("step 3: creating SRT...")
        base_name = video_name.rsplit('.', 1)[0]
        srt_name = base_name + '.srt'
        srt_path = os.path.join(OUTPUT_FOLDER, srt_name)
        create_srt_file(subtitle_segments, srt_path)

        # prepare response
        display_subs = []
        for seg in subtitle_segments:
            display_subs.append({
                'start': convert_to_srt_time(seg['start']),
                'end': convert_to_srt_time(seg['end']),
                'text': seg['text'],
                'startSeconds': seg['start'],
                'endSeconds': seg['end']
            })

        lang_name = LANGUAGES.get(selected_language, selected_language)

        with open(srt_path, 'r', encoding='utf-8') as f:
            srt_text = f.read()

        # cleanup
        delete_temp_files(video_save_path, audio_save_path)

        print("--- SUCCESS ---\n")

        return jsonify({
            'success': True,
            'subtitles': display_subs,
            'srt_content': srt_text,
            'srt_filename': srt_name,
            'total': len(display_subs),
            'language': lang_name
        })

    except Exception as e:
        print(f"UPLOAD ERROR: {e}")
        traceback.print_exc()
        try:
            if 'video_save_path' in locals() and os.path.exists(video_save_path):
                os.remove(video_save_path)
            if 'audio_save_path' in locals() and audio_save_path and os.path.exists(audio_save_path):
                os.remove(audio_save_path)
        except:
            pass
        return jsonify({'error': 'Error: ' + str(e)}), 500

# download route
@app.route('/download/<filename>')
def download_file(filename):
    try:
        file_path = os.path.join(OUTPUT_FOLDER, filename)
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print("\n" + "="*50)
    print("AI Subtitle Generator")
    print("IBM Watson Speech to Text")
    print("="*50)
    print(f"port: {port}")
    print(f"ibm connected: {ibm_stt is not None}")
    print("="*50 + "\n")
    app.run(debug=True, host='0.0.0.0', port=port)
