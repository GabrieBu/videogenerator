from flask import Flask, render_template, request
from tiktokvideos import generate_videos
import os
import webview

# ---- TO DO ----- 
# APP CONFIG
# FIX FEATURE UPLOADING .mp4
# NEW KEY

app = Flask(__name__)
window = webview.create_window("FlashbetOfficial", app)
# CORS(app)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit_form():
    yt_link = request.form['yt_link']
    t1 = request.form['t1']
    t2 = request.form['t2']

    languages = request.form.getlist('languages')
    languages_str = ', '.join(languages) if languages else 'None selected'
    stats = request.form.getlist('stats[]')
    video_file = request.files['video_file']
    video_position = request.form.get('video_position')

    print(f"Video_file: {video_file}")
    if video_file.filename != '':
        filename = video_file.filename
        video_path = os.path.join('uploads', filename)
        video_file.save(video_path)
    else:
        video_path = None

    number_mins = request.form.getlist('number_min[]')
    number_maxs = request.form.getlist('number_max[]')
    
    ranges = []
    if len(number_mins) == 1 and number_mins[0] == '':
        ranges = []
    else:
        for min_val, max_val in zip(number_mins, number_maxs):
            if min_val is None or min_val == '' or max_val is None or max_val == '':
                error_message = "Error: Some number raaajdnakjdbawbdkjawjdknges overlap!"
                return render_template('index.html', yt_link=yt_link, t1=t1, t2=t2, stats=stats, languages=languages_str, ranges=ranges, error=error_message)
            ranges.append((int(min_val), int(max_val)))
    
    if not stats:
        error_message_stat = "Error: You must type in at least one stat."
        return render_template('index.html', yt_link=yt_link, t1=t1, t2=t2, stats=stats, languages=languages_str, ranges=ranges, error_stat=error_message_stat)
    if not languages:
        error_message_language = "Error: You must select at least one language."
        return render_template('index.html', yt_link=yt_link, t1=t1, t2=t2, stats=stats, languages=languages_str, ranges=ranges, error_language=error_message_language)

    if incorrect_ranges(ranges):
        error_message = "Error: Given ranges are not valid! Min numbers have to be greater than Max numbers"
        return render_template('index.html', yt_link=yt_link, t1=t1, t2=t2, stats=stats, languages=languages_str, ranges=ranges, error=error_message)
    else:
        if has_intersection(ranges):
            error_message = "Error: Some number ranges overlap!"
            return render_template('index.html', yt_link=yt_link, t1=t1, t2=t2, stats=stats, languages=languages_str, ranges=ranges, error=error_message)
        else:
            # Success
            generate_videos(yt_link, t1, t2, stats, ranges, languages, video_path, video_position)
            return render_template('submitting.html', yt_link=yt_link, t1=t1, t2=t2, stats=stats, languages=languages_str, ranges=ranges, success="Form submitted successfully!")


def incorrect_ranges(ranges):
    for tuple in ranges:
        if tuple[0] > tuple[1]:
            return True 
    return False


def has_intersection(ranges):
    for i in range(len(ranges)):
        for j in range(i + 1, len(ranges)):
            min_i, max_i = ranges[i]
            min_j, max_j = ranges[j]

            if (min_i <= max_j and min_j <= max_i):
                return True
    return False

if __name__ == '__main__':
    try:
        # app.run(debug=True, port=5001, use_reloader=False)
        webview.start()
    except Exception as e:
        print(e)
