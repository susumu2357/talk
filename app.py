import base64
import os
import re
import time

import azure.cognitiveservices.speech as speechsdk
import gradio as gr
import openai
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.environ.get("OPENAI_API_KEY")

SYSTEM_DESCRIPTION_EN = """You are an experienced English teacher.
You are teaching English through a dialog with the student.
Your response should be at the same level of fluency as the student.
If the student is a beginner, your response should be simple and short.
If the student is an advanced English speaker, your response may be elaborate and long.
"""

SYSTEM_DESCRIPTION_SV = """Du är en erfaren lärare i svenska.
Du lär ut svenska genom en dialog med eleven.
Ditt svar bör vara på samma nivå som elevens.
Om eleven är nybörjare bör ditt svar vara enkelt och kort.
Om eleven är en avancerad svensktalare kan ditt svar vara utförligt och långt.
"""

SYSTEM_DESCRIPTION_JP = """あなたは経験豊富な日本語教師です。
あなたは生徒との対話を通して日本語を教えます。
あなたの返答は、生徒と同じレベルの流暢さでなければなりません。
もし生徒が初心者であれば、あなたの返答はシンプルで短いものであるべきです。
もし生徒が日本語上級者であれば、あなたの返答は詳細で長くてもよいです。
"""

SYSTEM_DESCRIPTION_DICT = {
    "en-US": SYSTEM_DESCRIPTION_EN,
    "en-GB": SYSTEM_DESCRIPTION_EN,
    "sv-SE": SYSTEM_DESCRIPTION_SV,
    "ja-JP": SYSTEM_DESCRIPTION_JP,
}

SPEECH_DICT = {
    "en-US": "en-US-JennyNeural",
    "en-GB": "en-GB-SoniaNeural",
    "sv-SE": "sv-SE-SofieNeural",
    "ja-JP": "ja-JP-NanamiNeural",
}

# def recognize_from_file(audio: str, language: str) -> str:
#     speech_config = speechsdk.SpeechConfig(
#         subscription=os.environ.get("SPEECH_KEY"),
#         region=os.environ.get("SPEECH_REGION"),
#     )
#     audio_config = speechsdk.audio.AudioConfig(filename=audio)
#     speech_recognizer = speechsdk.SpeechRecognizer(
#         speech_config=speech_config, audio_config=audio_config, language=language
#     )

#     speech_recognition_result = speech_recognizer.recognize_once_async().get()

#     if speech_recognition_result.reason == speechsdk.ResultReason.RecognizedSpeech:
#         print(f"Recognized: {speech_recognition_result.text}")
#         return speech_recognition_result.text
#     elif speech_recognition_result.reason == speechsdk.ResultReason.NoMatch:
#         print(
#             f"No speech could be recognized: {speech_recognition_result.no_match_details}"
#         )
#         return ""
#     elif speech_recognition_result.reason == speechsdk.ResultReason.Canceled:
#         cancellation_details = speech_recognition_result.cancellation_details
#         print(f"Speech Recognition canceled: {cancellation_details.reason}")
#         if cancellation_details.reason == speechsdk.CancellationReason.Error:
#             print(f"Error details: {cancellation_details.error_details}")
#             print("Did you set the speech resource key and region values?")
#         return ""


def speech_recognize_continuous_from_file(audio: str, language: str) -> str:
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


# # https://github.com/Azure-Samples/cognitive-services-speech-sdk/blob/513c0d8e4370f47dcf241c0682265c2b2fa37db6/samples/python/console/speech_sample.py
# def speech_recognition_with_pull_stream(audio: str, language: str):
#     """gives an example how to use a pull audio stream to recognize speech from a custom audio
#     source"""

#     class WavFileReaderCallback(speechsdk.audio.PullAudioInputStreamCallback):
#         """Example class that implements the Pull Audio Stream interface to recognize speech from
#         an audio file"""

#         def __init__(self, filename: str):
#             super().__init__()
#             self._file_h = wave.open(filename, mode=None)

#             self.sample_width = self._file_h.getsampwidth()

#             assert self._file_h.getnchannels() == 1
#             assert self._file_h.getsampwidth() == 2
#             assert self._file_h.getframerate() == 48000
#             assert self._file_h.getcomptype() == "NONE"

#         def read(self, buffer: memoryview) -> int:
#             """read callback function"""
#             size = buffer.nbytes
#             frames = self._file_h.readframes(size // self.sample_width)

#             buffer[: len(frames)] = frames

#             return len(frames)

#         def close(self):
#             """close callback function"""
#             self._file_h.close()

#     speech_config = speechsdk.SpeechConfig(
#         subscription=os.environ.get("SPEECH_KEY"),
#         region=os.environ.get("SPEECH_REGION"),
#     )

#     # specify the audio format
#     wave_format = speechsdk.audio.AudioStreamFormat(
#         samples_per_second=48000, bits_per_sample=16, channels=1
#     )

#     # setup the audio stream
#     callback = WavFileReaderCallback(audio)
#     stream = speechsdk.audio.PullAudioInputStream(callback, wave_format)
#     audio_config = speechsdk.audio.AudioConfig(stream=stream)

#     # instantiate the speech recognizer with pull stream input
#     speech_recognizer = speechsdk.SpeechRecognizer(
#         speech_config=speech_config, audio_config=audio_config, language=language
#     )

#     done = False
#     recognized_text = ""

#     def recognized(evt):
#         print(f"RECOGNIZED: {evt}")
#         nonlocal recognized_text
#         recognized_text += evt.result.text

#     def stop_cb(evt):
#         """callback that signals to stop continuous recognition upon receiving an event `evt`"""
#         print("CLOSING on {}".format(evt))
#         nonlocal done
#         done = True

#     # Connect callbacks to the events fired by the speech recognizer
#     # speech_recognizer.recognizing.connect(
#     #     lambda evt: print("RECOGNIZING: {}".format(evt))
#     # )
#     speech_recognizer.recognized.connect(recognized)
#     speech_recognizer.session_started.connect(
#         lambda evt: print("SESSION STARTED: {}".format(evt))
#     )
#     speech_recognizer.session_stopped.connect(
#         lambda evt: print("SESSION STOPPED {}".format(evt))
#     )
#     speech_recognizer.canceled.connect(lambda evt: print("CANCELED {}".format(evt)))
#     # stop continuous recognition on either session stopped or canceled events
#     speech_recognizer.session_stopped.connect(stop_cb)
#     speech_recognizer.canceled.connect(stop_cb)

#     # Start continuous speech recognition
#     speech_recognizer.start_continuous_recognition()

#     while not done:
#         time.sleep(0.5)

#     speech_recognizer.stop_continuous_recognition()

#     return recognized_text


# def whisper(audio: str, language: str):
#     audio_file = open(audio, "rb")
#     transcript = openai.Audio.transcribe("whisper-1", audio_file, language=language)
#     return transcript["text"]


def compose_messages(history: gr.Chatbot, language: str) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": SYSTEM_DESCRIPTION_DICT[language]}]

    for t in history:
        for i, elm in enumerate(t):
            match i:
                case i if i % 2 == 0:
                    messages += [
                        {
                            "role": "user",
                            "content": re.sub(r"\<audio.*\/audio\>", "", elm),
                        }
                    ]
                case i if i % 2 == 1 and elm:
                    messages += [
                        {
                            "role": "assistant",
                            "content": re.sub(r"\<audio.*\/audio\>", "", elm),
                        }
                    ]
    return messages


# def transcribe(audio, lang, state=""):
#     # text = speech_recognition_with_pull_stream(audio, lang)
#     # text = whisper(audio, lang)
#     text = speech_recognize_continuous_from_file(audio, lang)
#     print(f"text: {text}")
#     print(f"state: {state}")
#     if text:
#         state += text + " "
#     return state, state


def user(audio: str, text: str, history: gr.Chatbot) -> gr.Chatbot:
    return history + [[text + "\n\n" + play_audio(audio), None]]


def bot(history: gr.Chatbot, language: str) -> gr.Chatbot:
    messages = compose_messages(history, language)
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", messages=messages, temperature=0.8, stream=True
    )

    history[-1][1] = ""
    for chunk in response:
        chunk_message = chunk["choices"][0]["delta"]
        if "content" in chunk_message:
            history[-1][1] += chunk_message["content"]
            yield history


with gr.Blocks() as demo:
    with gr.Row():
        lang = gr.Dropdown(
            label="Language",
            choices=["en-US", "en-GB", "sv-SE", "ja-JP"],
            value="ja-JP",
        )
        clear = gr.Button("Clear conversation", size="sm")
    chatbot = gr.Chatbot()
    with gr.Row():
        audio = gr.Audio(source="microphone", type="filepath", format="wav")
        text = gr.Textbox(label="Recognized input", interactive=True)
        btn_text = gr.Button("Submit text")
        reset_recording = gr.Button("Clear recording")

    audio.change(
        speech_recognize_continuous_from_file, [audio, lang], [text], queue=True
    )
    btn_text.click(user, [audio, text, chatbot], chatbot, queue=True).success(
        bot, [chatbot, lang], chatbot, queue=True
    ).success(to_sppech, [audio, chatbot, lang], chatbot, queue=True).then(
        lambda: [None, None], None, [audio, text], queue=False
    )

    reset_recording.click(
        lambda: [None, None],
        None,
        [audio, text],
        queue=False,
    )
    clear.click(lambda: None, None, [chatbot], queue=False)

demo.queue()
demo.launch(debug=True)

# gr.Interface(
#     fn=transcribe,
#     inputs=[
#         gr.Dropdown(choices=["en-US", "en-GB", "sv-SE", "ja-JP"], value="en-US"),
#         gr.Audio(source="microphone", type="filepath", format="wav", streaming=True),
#         "state",
#     ],
#     outputs=[gr.Textbox(), "state"],
#     live=True,
# ).launch(debug=True)
