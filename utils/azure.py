import base64
import os
import re
import time
import uuid

import azure.cognitiveservices.speech as speechsdk
import gradio as gr
from dotenv import load_dotenv

load_dotenv()


SPEECH_DICT = {
    "en-US": "en-US-JennyNeural",
    "en-GB": "en-GB-SoniaNeural",
    "sv-SE": "sv-SE-SofieNeural",
    "ja-JP": "ja-JP-NanamiNeural",
}


def speech_recognize_continuous_from_file(
    audio: str, history: list[list[str]], language: str
) -> str:
    """performs continuous speech recognition with input from an audio file"""
    # <SpeechContinuousRecognitionWithFile>
    speech_config = speechsdk.SpeechConfig(
        subscription=os.environ.get("SPEECH_KEY"),
        region=os.environ.get("SPEECH_REGION"),
    )
    audio_config = speechsdk.audio.AudioConfig(filename=audio)

    speech_recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config, audio_config=audio_config, language=language
    )

    done = False
    recognized_text = ""

    def recognized(evt):
        print(f"RECOGNIZED: {evt}")
        nonlocal recognized_text
        recognized_text += evt.result.text

    def stop_cb(evt):
        """callback that signals to stop continuous recognition upon receiving an event `evt`"""
        print("CLOSING on {}".format(evt))
        nonlocal done
        done = True

    # Connect callbacks to the events fired by the speech recognizer
    # speech_recognizer.recognizing.connect(lambda evt: print('RECOGNIZING: {}'.format(evt)))
    speech_recognizer.recognized.connect(recognized)
    speech_recognizer.session_started.connect(
        lambda evt: print("SESSION STARTED: {}".format(evt))
    )
    speech_recognizer.session_stopped.connect(
        lambda evt: print("SESSION STOPPED {}".format(evt))
    )
    speech_recognizer.canceled.connect(lambda evt: print("CANCELED {}".format(evt)))
    # stop continuous recognition on either session stopped or canceled events
    speech_recognizer.session_stopped.connect(stop_cb)
    speech_recognizer.canceled.connect(stop_cb)

    # Start continuous speech recognition
    speech_recognizer.start_continuous_recognition()
    while not done:
        time.sleep(0.5)

    speech_recognizer.stop_continuous_recognition()

    return recognized_text


def play_audio(file_path: str):
    print(file_path)
    with open(file_path, "rb") as f:
        audio_bytes = f.read()

    audio = base64.b64encode(audio_bytes).decode("utf-8")
    audio_player = (
        f'<audio src="data:audio/mpeg;base64,{audio}" controls autoplay></audio>'
    )

    return audio_player


def to_sppech(audio: str, history: gr.Chatbot, lang: str) -> gr.Chatbot:
    output_path = audio.replace(".wav", "output.wav")
    speech_config = speechsdk.SpeechConfig(
        subscription=os.environ.get("SPEECH_KEY"),
        region=os.environ.get("SPEECH_REGION"),
    )
    audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)
    speech_config.speech_synthesis_voice_name = SPEECH_DICT[lang]

    speech_synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config, audio_config=audio_config
    )

    text = history[-1][1]
    speech_synthesis_result = speech_synthesizer.speak_text_async(text).get()

    if (
        speech_synthesis_result.reason
        == speechsdk.ResultReason.SynthesizingAudioCompleted
    ):
        print("Speech synthesized for text [{}]".format(text))
        history[-1][1] += "\n\n" + play_audio(output_path)
        return history
    elif speech_synthesis_result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = speech_synthesis_result.cancellation_details
        print("Speech synthesis canceled: {}".format(cancellation_details.reason))
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            if cancellation_details.error_details:
                print("Error details: {}".format(cancellation_details.error_details))
                print("Did you set the speech resource key and region values?")


def play_example(history: gr.Chatbot, lang: str) -> gr.Chatbot:
    dir = f"/tmp/gradio/{uuid.uuid4()}"
    os.mkdir(dir)
    output_path = os.path.join(dir, "example.wav")
    speech_config = speechsdk.SpeechConfig(
        subscription=os.environ.get("SPEECH_KEY"),
        region=os.environ.get("SPEECH_REGION"),
    )
    audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)
    speech_config.speech_synthesis_voice_name = SPEECH_DICT[lang]

    speech_synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config, audio_config=audio_config
    )
    m = re.findall(r"\`+(.+?)\`+", history[-1][1])
    reference_text = m[0]

    speech_synthesis_result = speech_synthesizer.speak_text_async(reference_text).get()

    if (
        speech_synthesis_result.reason
        == speechsdk.ResultReason.SynthesizingAudioCompleted
    ):
        print("Speech synthesized for text [{}]".format(reference_text))
        history[-1][1] += "\n\n" + play_audio(output_path)
        return history
    elif speech_synthesis_result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = speech_synthesis_result.cancellation_details
        print("Speech synthesis canceled: {}".format(cancellation_details.reason))
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            if cancellation_details.error_details:
                print("Error details: {}".format(cancellation_details.error_details))
                print("Did you set the speech resource key and region values?")


def grade_pronunciation(audio: str, history: gr.Chatbot, language: str) -> str:
    speech_config = speechsdk.SpeechConfig(
        subscription=os.environ.get("SPEECH_KEY"),
        region=os.environ.get("SPEECH_REGION"),
    )
    audio_config = speechsdk.audio.AudioConfig(filename=audio)
    speech_recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config, audio_config=audio_config, language=language
    )

    m = re.findall(r"\`+(.+?)\`+", history[-1][1])
    reference_text = m[0]
    pronunciation_assessment_config = speechsdk.PronunciationAssessmentConfig(
        reference_text=reference_text,
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        enable_miscue=True,
    )
    pronunciation_assessment_config.apply_to(speech_recognizer)

    speech_recognition_result = speech_recognizer.recognize_once()

    # The pronunciation assessment result as a JSON string
    pronunciation_assessment_result_json = speech_recognition_result.properties.get(
        speechsdk.PropertyId.SpeechServiceResponse_JsonResult
    )
    return pronunciation_assessment_result_json
