import json
import tempfile

from deepgram import (
    DeepgramClient,
    PrerecordedOptions,
)
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai.chat_models import ChatOpenAI

import config

template = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an assistant helping a sales agent in a live call."
            "You are to use the context provided below to generate 1 to 2"
            "short, helpful suggestions for the sales agent."
            "Categorize each suggestion as a 💡 Tip, ⚠️ Reminder or ❗ Alert.",
        ),
        ("human", "Context: {context}"),
    ]
)
model = ChatOpenAI(
    model="gpt-4o",
    api_key=config.OPENAI_API_KEY,
    temperature=1,
)


def suggest(context):
    prompt = template.invoke({"context": context})
    response = model.invoke(prompt)
    return response.content + "\n\n---\n"


def transcribe(audio_segment):
    with tempfile.NamedTemporaryFile() as tmpfile:
        buffer_data = audio_segment.export(tmpfile.name, format="mp3").read()

        deepgram = DeepgramClient(api_key=config.DEEPGRAM_API_KEY)

        payload = {
            "buffer": buffer_data,
        }
        options = PrerecordedOptions(
            model="nova-3",
            smart_format=True,
        )

        try:
            response = deepgram.listen.rest.v("1").transcribe_file(payload, options)
        except Exception:
            return ""

        response = json.loads(response.to_json())
        transcript = response["results"]["channels"][0]["alternatives"][0][
            "paragraphs"
        ]["transcript"]

        return transcript.strip()
