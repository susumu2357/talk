import os
import re

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
