import json
import os
import re
import time

import gradio as gr
import openai
from dotenv import load_dotenv

from utils.azure import (
    grade_pronunciation,
    play_audio,
    play_example,
)

load_dotenv()
openai.api_key = os.environ.get("OPENAI_API_KEY")

INITIAL_PROMPT = {lang: {} for lang in ["en-US", "ja-JP"]}

INITIAL_PROMPT["en-US"] = {
    topic: f"""You are an experienced English teacher. Students will practice pronunciation on {topic}-related English.
    You will provide them with assigned sentences for their practice.
    The student's pronunciation will be graded and a score out of 100 will be given for each word.
    Based on that score, you adjust the difficulty level and present the next assigned sentence.
    If a word has a pronunciation score lower than 80, the next assigned sentence should contain that word.
    However, if the same word is not improved after practicing it three or more times in a row, present another assignment sentence.
    Only one sentence at a time should be presented.
    The assignment should start with a simple phrase and gradually increase in difficulty.
    Example sentences should be enclosed in back quotes ``.

    <Example score from the student>
    Pronunciation score:
    good: 75.0
    morning: 95.0

    <Example response from the teacher>
    Great! If you could improve your pronunciation of "good" a little more, you would be perfect. Let's practice "good morning" again.
    `Good morning How are you?`
    """
    for topic in ["Business", "Hobby", "Daily life"]
}

TOPIC_JP = {"Business": "ビジネス", "Hobby": "趣味", "Daily life": "日常生活"}
INITIAL_PROMPT["ja-JP"] = {
    topic: f"""あなたは経験豊富な日本語教師です。生徒は{TOPIC_JP[topic]}に関連した日本語の発音を練習します。
    あなたは生徒に練習用の課題文を与えます。
    生徒の発音は採点され、単語ごとに100点満点で点数がつけられます。
    そのスコアに基づいて難易度を調整し、次の課題文を提示します。
    発音の点数が80点以下の単語があれば、次の課題文にその単語を含めてください。
    ただし、三度以上続けて同じ単語を練習しても改善しない場合は、他の課題文を提示してください。
    提示する課題文は一度に一つだけにしてください。
    課題は簡単なフレーズから始め、徐々に難易度を上げてください。
    例文はバッククォート``で囲んでください。

    <Example score from the student>
    Pronunciation score:
    おはよう: 75.0
    ござい: 98.0
    ます: 98.0

    <Example response from the teacher>
    いいですね！"おはよう"の発音がもう少し良くなれば完璧です。もう一度 "おはよう"を練習しましょう。
    `おはようございます。今日もよろしくお願いします。`
    """
    for topic in ["Business", "Hobby", "Daily life"]
}

FIRST_USER_MESSAGE = {lang: {} for lang in ["en-US", "ja-JP"]}
FIRST_USER_MESSAGE["en-US"] = {
    topic: f"Start practicing {topic} related English! Remember placing an example in back quotes"
    for topic in ["Business", "Hobby", "Daily life"]
}
FIRST_USER_MESSAGE["ja-JP"] = {
    topic: f"{TOPIC_JP[topic]}に関連した日本語の練習を始めましょう。例文をバッククォートで囲むことを忘れずに。"
    for topic in ["Business", "Hobby", "Daily life"]
}


def sleep(n_sec: int = 3):
    time.sleep(n_sec)
    return


def compose_pronunciation_messages(
    history: gr.Chatbot, topic: str, language: str
) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": INITIAL_PROMPT[language][topic]}]

    for t in history:
        for i, elm in enumerate(t):
            match i:
                case i if i % 2 == 0:
                    user_input = re.sub(r"\<audio.*\/audio\>", "", elm)
                    messages += [
                        {
                            "role": "user",
                            "content": user_input,
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


def user(audio: str, history: gr.Chatbot, language: str) -> gr.Chatbot:
    grading = json.loads(grade_pronunciation(audio, history, language))
    grades = [
        f'{elm["Word"]}: {elm["PronunciationAssessment"]["AccuracyScore"]}'
        for elm in grading["NBest"][0]["Words"]
    ]
    history += [
        [
            "Pronunciation score:\n" + "\n".join(grades) + "\n\n" + play_audio(audio),
            None,
        ]
    ]
    return history


def kick_start(
    topic: str, language: str, history: gr.Chatbot
) -> list[gr.Chatbot, gr.update]:
    history = [
        [
            FIRST_USER_MESSAGE[language][topic],
            None,
        ]
    ]
    messages = compose_pronunciation_messages(history, topic, language)
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", messages=messages, temperature=0.8
    )
    history[-1][1] = response["choices"][0]["message"]["content"]
    return [history, gr.update(interactive=True)]


def bot(history: gr.Chatbot, topic: str, language: str) -> gr.Chatbot:
    messages = compose_pronunciation_messages(history, topic, language)

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", messages=messages, temperature=0.5
    )
    history[-1][1] = ""
    for word in response["choices"][0]["message"]["content"].split():
        history[-1][1] += word + " "
        time.sleep(0.1)
        yield history
    # start = time.time()
    # elapsed_time = 0.0
    # response = openai.ChatCompletion.create(
    #     model="gpt-3.5-turbo", messages=messages, temperature=0.5, stream=True
    # )

    # history[-1][1] = ""
    # for chunk in response:
    #     history[-1][1] += chunk.choices[0].delta.get("content", "")
    #     if not chunk.choices[0].delta.get("finish_reason", ""):
    #         elapsed_time = time.time() - start
    #         print(f"{elapsed_time=}")
    #     elif chunk.choices[0].delta.get("finish_reason", "") == "stop":
    #         print('Break due to "finish_reason": "stop"')
    #         break
    #     else:
    #         print(
    #             f'unknown stop reason: {chunk.choices[0].delta.get("finish_reason", "")}'
    #         )
    #     if elapsed_time >= 30:
    #         break
    #     yield history


with gr.Blocks() as demo:
    with gr.Row():
        lang = gr.Dropdown(
            label="Language",
            choices=["en-US", "en-GB", "ja-JP"],
            value="en-US",
        )
        topic = gr.Dropdown(
            label="Topic",
            choices=["Business", "Hobby", "Daily life"],
            value="Business",
        )
        start = gr.Button("Start practice")
        clear = gr.Button("Clear conversation", size="sm")
    chatbot = gr.Chatbot()
    with gr.Row():
        audio = gr.Audio(source="microphone", type="filepath", format="wav")
        # text = gr.Textbox(label="Recognized input", interactive=True)
        btn_text = gr.Button("Submit text", interactive=False)
        reset_recording = gr.Button("Clear recording")
    assessment = gr.Textbox(label="Pronunciation assessment result", interactive=False)

    start.click(kick_start, [topic, lang, chatbot], [chatbot, btn_text]).success(
        play_example, [chatbot, lang], chatbot, queue=True
    )

    # audio.change(
    #     speech_recognize_continuous_from_file,
    #     [audio, chatbot, lang],
    #     [text],
    #     queue=True,
    # )
    btn_text.click(
        grade_pronunciation, [audio, chatbot, lang], assessment, queue=True
    ).success(user, [audio, chatbot, lang], chatbot, queue=True).success(
        bot, [chatbot, topic, lang], chatbot, queue=True
    ).success(
        play_example, [chatbot, lang], chatbot, queue=True
    ).success(
        lambda: None, None, audio, queue=False
    )

    reset_recording.click(
        lambda: None,
        None,
        audio,
        queue=False,
    )
    clear.click(
        lambda: None,
        None,
        chatbot,
        queue=False,
    )

demo.queue()
demo.launch(debug=True)
