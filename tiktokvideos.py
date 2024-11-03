import json
import google.generativeai as genai
import os
from pytubefix import YouTube
import argparse
import requests
from moviepy.editor import *
import glob
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from typing import Sequence
# import google.cloud.texttospeech as tts
from pathlib import Path
from google.cloud import texttospeech_v1beta1 as tts

os.environ["IMAGEMAGICK_BINARY"] = "/opt/homebrew/bin/magick"
voices = {
        "it": "it-IT-Neural2-C", 
        "fr": "fr-FR-Neural2-B", 
        "es": "es-ES-Neural2-B", 
        "en": "en-GB-Neural2-B",
        "de": "de-DE-Neural2-B",
        "pl": "pl-PL-Standard-B",
    }


def go_ssml(basename: Path, ssml, name_voice):
    client = tts.TextToSpeechClient()
    voice = tts.VoiceSelectionParams(
        language_code=name_voice[:5],
        name=name_voice,
        ssml_gender=tts.SsmlVoiceGender.MALE,
    )

    response = client.synthesize_speech(
        request=tts.SynthesizeSpeechRequest(
            input=tts.SynthesisInput(ssml=ssml),
            voice=voice,
            audio_config = tts.AudioConfig(audio_encoding=tts.AudioEncoding.LINEAR16),
            enable_time_pointing=[
                tts.SynthesizeSpeechRequest.TimepointType.SSML_MARK]
        )
    )
    # cheesy conversion of array of Timepoint proto.Message objects into plain-old data
    marks = [dict(sec=t.time_seconds, name=t.mark_name)
             for t in response.timepoints]

    name = basename.with_suffix('.json')
    with name.open('w') as out:
        json.dump(marks, out)
        print(f'Marks content written to file: {name}')

    name = basename.with_suffix('.wav')
    with name.open('wb') as out:
        out.write(response.audio_content)
        print(f'Audio content written to file: {name}')


def text_to_wav(voice_name: str, text: str):
    language_code = "-".join(voice_name.split("-")[:2])
    text_input = tts.SynthesisInput(text=text)
    voice_params = tts.VoiceSelectionParams(
        language_code=language_code, name=voice_name
    )
    audio_config = tts.AudioConfig(audio_encoding=tts.AudioEncoding.LINEAR16)

    client = tts.TextToSpeechClient()
    response = client.synthesize_speech(
        input=text_input,
        voice=voice_params,
        audio_config=audio_config,
    )
    filename = f"{voice_name}.wav"
    with open(filename, "wb") as out:
        out.write(response.audio_content)
        print(f'Generated speech saved to "{filename}"')


# pip install pillow==9.5.0
# brew install ffmpeg
"""
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    RESET = "\033[0m"
"""

def generate_text(stats, t1, t2, languages):
    genai.configure(api_key="")
    model = genai.GenerativeModel("gemini-1.5-pro-latest")
    cfg = genai.GenerationConfig(response_mime_type="application/json")

    prompt = """ 
    You are an expert of content creation. Your specialising field is football. Your audience has a very low attention span, so try to be catchy yet coincise.

    You are given a set of past statistics you can generate comprehensive summary using all of them. They are reported below:
    Game: TA-TB"""

    for stat in stats:
        prompt = prompt + f"\n-{stat}"
           
    prompt = prompt + """
    \nReturn just a the JSON containing only text (no emojis) with the small script, giving if necessary explicit numerical statistics I wrote above,   in 6 different languages: Italian, English, Spanish, French, German, Polish. To create the script follow this format: 
    intro <mark name="stat1"/> comment_about_stat1  <mark name="stat2"/> comment_about_stat2... <"mark name="stat5"/> comment_about_stat5 conclusion. You dont need to close the marks, just follow the template.

    Use this format for the output json:
    {"it": "italian_script_video", "en": "english_script_video", "fr: "french_script_video", "es": "spanish_script_video", "de": "german_script_video", "pl" : "polish_script_video"}

    Follow strictly the format of the json to be returned, nothing else.
    """

    prompt = prompt\
        .replace("TA", str(t1))\
        .replace("TB", str(t2))

    response = model.generate_content(prompt, generation_config=cfg)
    parsed_data = json.loads(response.text)

    for key, text in parsed_data.items():
        if key in languages:
            api_voice = voices.get(key.lower())
            if api_voice:
                # text_to_wav(api_voice, text)
                text = "<speak>" + text + "</speak>"
                go_ssml(Path.cwd() / api_voice, text, api_voice)
    return parsed_data


def list_voices(language_code=None):
    client = tts.TextToSpeechClient()
    response = client.list_voices(language_code=language_code)
    voices = sorted(response.voices, key=lambda voice: voice.name)

    print(f" Voices: {len(voices)} ".center(60, "-"))
    for voice in voices:
        languages = ", ".join(voice.language_codes)
        name = voice.name
        gender = tts.SsmlVoiceGender(voice.ssml_gender).name
        rate = voice.natural_sample_rate_hertz
        print(f"{languages:<8} | {name:<24} | {gender:<8} | {rate:,} Hz")


def delete_wav():
    directory = os.getcwd()
    wav_files = glob.glob(os.path.join(directory, '*.wav'))
    for wav_file in wav_files:
        try:
            os.remove(wav_file)
            print(f"Deleted: {wav_file}")
        except OSError as e:
            print(f"Error: {wav_file} : {e.strerror}")


def delete_mp4():
    directory = os.getcwd()
    wav_files = glob.glob(os.path.join(directory, 'highlights.mp4'))
    for wav_file in wav_files:
        try:
            os.remove(wav_file)
            print(f"Deleted: {wav_file}")
        except OSError as e:
            print(f"Error: {wav_file} : {e.strerror}")


def download_highlights(yt_link):
    yt = YouTube(str(yt_link))
    print(yt.title)
    ys = yt.streams.get_highest_resolution()
    ys.download(filename="highlights.mp4")


def crop_clip(clip):
    width, height = clip.size

    target_aspect_ratio = 9 / 16 

    if width / height > target_aspect_ratio:
        new_width = int(height * target_aspect_ratio)
        new_height = height
        x_center = (width - new_width) / 2
        clip = clip.crop(x1=x_center, width=new_width, height=new_height)
    else:
        new_height = int(width / target_aspect_ratio)
        new_width = width
        y_center = (height - new_height) / 2
        clip = clip.crop(y1=y_center, width=new_width, height=new_height)

    return clip


def generate_videos(yt_link, t1, t2, stats, ranges, languages, uploaded_video_path, video_position):
    output_dir = "output_videos"

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    download_highlights(yt_link)
    generate_text(stats, t1, t2, languages)
    
    for voice in languages:
        audio_clip = AudioFileClip(f"{voices[voice]}.wav") # audio from tts
        duration_wav = audio_clip.duration
        highlights = VideoFileClip("highlights.mp4")
        if ranges:
            sub_clips = []
            sum_subclips = 0
            for range in ranges:
                sub_clip = highlights.subclip(int(range[0]), int(range[1]))
                sum_subclips += (int(range[1]) - int(range[0]))
                sub_clips.append(sub_clip)

            remaining_time = duration_wav - sum_subclips  # time left to cover

            if remaining_time > 0:
                last_end_time = ranges[-1][1]  # end of the last subclip
                
                while remaining_time > 0:
                    next_start = last_end_time
                    next_end = min(next_start + remaining_time, highlights.duration)  # ensure we don't exceed the video duration
                    if next_start >= highlights.duration:
                        break  # no more video to cut from

                    additional_clip = highlights.subclip(int(next_start), int(next_end))
                    sub_clips.append(additional_clip)

                    sub_duration = next_end - next_start
                    remaining_time -= sub_duration
                    last_end_time = next_end
            concatenated_clips = concatenate_videoclips(sub_clips)
        else:
            # if not specified take from 0 to second to be covered
            concatenated_clips = highlights.subclip(0, duration_wav)

        clip = concatenated_clips.with_audio(audio_clip)
        
        clip = crop_clip(clip)

        if uploaded_video_path:
            uploaded_video = VideoFileClip(uploaded_video_path)
            uploaded_video_cropped = crop_clip(uploaded_video).resize(clip.size)  # Resize to match highlight clip size
            if video_position == "start":
                final_clip = concatenate_videoclips([uploaded_video_cropped, clip])
            else: # only start or end is acceptable
                final_clip = concatenate_videoclips([clip, uploaded_video_cropped])

 
        video_file = os.path.join(output_dir, f"video_{voice}.mp4")
        final_clip.write_videofile(video_file, codec="libx264", fps=30)
    delete_wav()
    delete_mp4()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='tiktokvideos')
    parser.add_argument('--filename', required=True)
    args = parser.parse_args()
    
    assert os.path.exists(args.filename), "The file has to exist in the same folder of this program"

    with open(args.filename) as f:
        data = json.load(f)

    generate_videos()