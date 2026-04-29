# AI Subtitle Generator
# Cloud Application Development Project
# 4th Semester
# Using IBM Watson Speech to Text API

# importing all required libraries
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from ibm_watson import SpeechToTextV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from moviepy import VideoFileClip
from dotenv import load_dotenv
import os

# loading the .env file to get IBM credentials
load_dotenv()

# getting the current folder where app.py is
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# template folder path
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')

# setting up flask app
app = Flask(__name__, template_folder=TEMPLATE_DIR)
CORS(app)  # this is needed so frontend can talk to backend

# folders for saving uploaded videos and output files
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'outputs')

# create folders if they dont exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

# getting IBM Watson credentials from .env file
# dont share these keys with anyone!
IBM_API_KEY = os.getenv('IBM_API_KEY')
IBM_URL = os.getenv('IBM_URL')

# languages supported by IBM Watson
# found these model names from IBM Watson documentation
LANGUAGES = {
    'en-US': 'English (US)',
    'en-GB': 'English (UK)',
    'hi-IN': 'Hindi',
    'ta-IN': 'Tamil',
    'te-IN': 'Telugu',
    'ja-JP': 'Japanese',
    'ko-KR': 'Korean',
    'zh-CN': 'Chinese (Simplified)',
    'ar-AR': 'Arabic',
    'fr-FR': 'French',
    'de-DE': 'German',
    'es-ES': 'Spanish',
    'it-IT': 'Italian',
    'pt-BR': 'Portuguese',
    'nl-NL': 'Dutch',
}

# connecting to IBM Watson API
# this runs when app starts
print("connecting to IBM Watson...")
try:
    authenticator = IAMAuthenticator(IBM_API_KEY)
    ibm_stt = SpeechToTextV1(authenticator=authenticator)
    ibm_stt.set_service_url(IBM_URL)
    print("IBM Watson connected successfully!")
except Exception as e:
    print("IBM Watson connection failed:", e)
    print("check your API key and URL in .env file")
    ibm_stt = None

# this function converts seconds into SRT time format
# SRT format is like: 00:00:01,500
# took me some time to figure out the format
def convert_to_srt_time(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    
    # format with leading zeros
    time_str = f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"
    return time_str

# this function extracts audio from the uploaded video
# moviepy library is used for this
# learned this from moviepy documentation
def extract_audio(video_file_path):
    try:
        print("starting audio extraction...")
        
        # load the video file
        vid = VideoFileClip(video_file_path)
        
        # audio will be saved with same name but .wav extension
        audio_file_path = video_file_path.rsplit('.', 1)[0] + '.wav'
        
        # extract and save audio
        # fps=16000 because IBM Watson works best with 16kHz audio
        # codec pcm_s16le is standard wav format
        vid.audio.write_audiofile(
            audio_file_path,
            fps=16000,
            codec='pcm_s16le',
            logger=None  # this stops moviepy from printing too much
        )
        
        # close video to free memory
        vid.close()
        
        print("audio extracted successfully!")
        print("audio saved at:", audio_file_path)
        return audio_file_path
        
    except Exception as e:
        print("error during audio extraction:", e)
        return None

# this is the main function that sends audio to IBM Watson
# and gets back the transcription
def get_subtitles_from_ibm(audio_path, lang_code='en-US'):
    try:
        print(f"sending audio to IBM Watson...")
        print(f"language selected: {lang_code}")
        
        # IBM Watson needs the model name in specific format
        # format is: language_BroadbandModel
        # example: en-US_BroadbandModel
        model_name = lang_code + '_BroadbandModel'
        print(f"using model: {model_name}")
        
        # open audio file and send to IBM Watson
        audio_file = open(audio_path, 'rb')
        
        # calling IBM Watson recognize function
        # timestamps=True gives us word timings
        # smart_formatting makes numbers and dates look better
        ibm_response = ibm_stt.recognize(
            audio=audio_file,
            content_type='audio/wav',
            model=model_name,
            timestamps=True,
            smart_formatting=True,
        ).get_result()
        
        audio_file.close()
        
        # process IBM response and create segments list
        # each segment has start time, end time and text
        segments_list = []
        
        for res in ibm_response.get('results', []):
            if res.get('alternatives'):
                # get the best alternative (first one)
                best_alt = res['alternatives'][0]
                
                # get transcript text
                text = best_alt.get('transcript', '').strip()
                
                # get word timestamps
                word_times = best_alt.get('timestamps', [])
                
                # only add if we have both text and timestamps
                if text and word_times:
                    # first word start time
                    start = word_times[0][1]
                    # last word end time
                    end = word_times[-1][2]
                    
                    segments_list.append({
                        'start': start,
                        'end': end,
                        'text': text
                    })
        
        print(f"IBM Watson done! total segments: {len(segments_list)}")
        return segments_list
        
    except Exception as e:
        print("IBM Watson error:", e)
        # common errors:
        # - wrong model name (language not supported)
        # - audio format not supported
        # - API key expired
        return None

# this function creates the SRT subtitle file
# SRT format reference from wikipedia
def create_srt_file(segments, srt_output_path):
    try:
        print("creating SRT file...")
        
        # open file for writing
        srt_file = open(srt_output_path, 'w', encoding='utf-8')
        
        # write each segment in SRT format
        for idx, seg in enumerate(segments):
            # subtitle number (starts from 1)
            sub_num = idx + 1
            
            # convert times to SRT format
            start_time = convert_to_srt_time(seg['start'])
            end_time = convert_to_srt_time(seg['end'])
            
            # subtitle text
            sub_text = seg['text']
            
            # write to file
            # SRT format:
            # number
            # start --> end
            # text
            # blank line
            srt_file.write(str(sub_num) + '\n')
            srt_file.write(start_time + ' --> ' + end_time + '\n')
            srt_file.write(sub_text + '\n')
            srt_file.write('\n')
        
        srt_file.close()
        print("SRT file created:", srt_output_path)
        return True
        
    except Exception as e:
        print("error creating SRT file:", e)
        return False

# delete temp files after processing
# this saves disk space
def delete_temp_files(video_path, audio_path):
    try:
        if os.path.exists(video_path):
            os.remove(video_path)
            print("deleted temp video:", video_path)
            
        if os.path.exists(audio_path):
            os.remove(audio_path)
            print("deleted temp audio:", audio_path)
            
    except Exception as e:
        print("cleanup error (not critical):", e)

# ==============================
# FLASK ROUTES START HERE
# ==============================

# home page route
# renders the main HTML page
@app.route('/')
def home():
    print("home page loaded")
    return render_template('index.html', languages=LANGUAGES)

# upload route
# this is called when user clicks Generate Subtitles
@app.route('/upload', methods=['POST'])
def upload_video():
    print("\n--- new upload request ---")
    
    try:
        # check if video file is in the request
        if 'video' not in request.files:
            print("no video in request")
            return jsonify({'error': 'No video file uploaded'}), 400
        
        # get the uploaded file
        uploaded_file = request.files['video']
        
        # check if file is selected
        if uploaded_file.filename == '':
            print("empty filename")
            return jsonify({'error': 'No file selected'}), 400
        
        # get language from form
        selected_language = request.form.get('language', 'en-US')
        print(f"language selected by user: {selected_language}")
        
        # save the uploaded video
        video_name = uploaded_file.filename
        video_save_path = os.path.join(UPLOAD_FOLDER, video_name)
        uploaded_file.save(video_save_path)
        print(f"video saved: {video_name}")
        
        # step 1 - extract audio from video
        print("\nstep 1: extracting audio...")
        audio_save_path = extract_audio(video_save_path)
        
        if audio_save_path is None:
            return jsonify({'error': 'Could not extract audio from video'}), 500
        
        # step 2 - send audio to IBM Watson
        print("\nstep 2: getting subtitles from IBM Watson...")
        subtitle_segments = get_subtitles_from_ibm(audio_save_path, selected_language)
        
        if subtitle_segments is None:
            return jsonify({'error': 'IBM Watson could not process the audio'}), 500
        
        if len(subtitle_segments) == 0:
            return jsonify({'error': 'No speech detected in video'}), 400
        
        # step 3 - create SRT file
        print("\nstep 3: creating SRT file...")
        base_video_name = video_name.rsplit('.', 1)[0]
        srt_file_name = base_video_name + '.srt'
        srt_file_path = os.path.join(OUTPUT_FOLDER, srt_file_name)
        
        srt_created = create_srt_file(subtitle_segments, srt_file_path)
        
        if not srt_created:
            return jsonify({'error': 'Could not create subtitle file'}), 500
        
        # step 4 - prepare data for frontend
        print("\nstep 4: preparing response...")
        
        # format subtitle data for display
        display_subtitles = []
        for seg in subtitle_segments:
            display_subtitles.append({
                'start': convert_to_srt_time(seg['start']),
                'end': convert_to_srt_time(seg['end']),
                'text': seg['text'],
                'startSeconds': seg['start'],
                'endSeconds': seg['end']
            })
        
        # get language name for display
        lang_name = LANGUAGES.get(selected_language, selected_language)
        
        # read SRT file content
        srt_file_read = open(srt_file_path, 'r', encoding='utf-8')
        srt_text = srt_file_read.read()
        srt_file_read.close()
        
        # step 5 - cleanup temp files
        print("\nstep 5: cleaning up temp files...")
        delete_temp_files(video_save_path, audio_save_path)
        
        print("\n--- upload completed successfully! ---\n")
        
        # send response back to frontend
        return jsonify({
            'success': True,
            'subtitles': display_subtitles,
            'srt_content': srt_text,
            'srt_filename': srt_file_name,
            'total': len(display_subtitles),
            'language': lang_name
        })
    
    except Exception as e:
        print("unexpected error in upload:", e)
        
        # try to cleanup if error happened
        try:
            if 'video_save_path' in locals():
                if os.path.exists(video_save_path):
                    os.remove(video_save_path)
            if 'audio_save_path' in locals():
                if audio_save_path and os.path.exists(audio_save_path):
                    os.remove(audio_save_path)
        except:
            pass
        
        return jsonify({'error': 'Something went wrong: ' + str(e)}), 500

# download route
# user can download the SRT file
@app.route('/download/<filename>')
def download_file(filename):
    try:
        print(f"download request for: {filename}")
        file_path = os.path.join(OUTPUT_FOLDER, filename)
        
        # check if file exists
        if not os.path.exists(file_path):
            print("file not found:", file_path)
            return jsonify({'error': 'File not found'}), 404
        
        # send file to user
        return send_file(file_path, as_attachment=True)
        
    except Exception as e:
        print("download error:", e)
        return jsonify({'error': str(e)}), 500

# health check route
# just to check if server is running
@app.route('/health')
def health_check():
    status = {
        'server': 'running',
        'ibm_watson': 'connected' if ibm_stt is not None else 'not connected'
    }
    print("health check:", status)
    return jsonify(status)

# ==============================
# RUN THE APP
# ==============================

if __name__ == '__main__':
    # get port from environment variable
    # railway and other platforms set PORT automatically
    port = int(os.environ.get('PORT', 5000))
    
    print("\n" + "="*50)
    print("AI Subtitle Generator")
    print("IBM Watson Speech to Text")
    print("Cloud Application Development Project")
    print("="*50)
    print(f"template folder: {TEMPLATE_DIR}")
    print(f"upload folder: {UPLOAD_FOLDER}")
    print(f"output folder: {OUTPUT_FOLDER}")
    print(f"IBM Watson: {'connected' if ibm_stt else 'NOT connected - check .env'}")
    print(f"server starting on port: {port}")
    print("open browser: http://localhost:" + str(port))
    print("press CTRL+C to stop server")
    print("="*50 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=port)