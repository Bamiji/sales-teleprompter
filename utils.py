import tempfile

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai.chat_models import ChatOpenAI
from requests import Session

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

dg_session = Session()
dg_session.headers.update(
    {"Authorization": f"Token {config.DEEPGRAM_API_KEY}", "Content-Type": "audio/*"}
)
dg_session.params.update(
    {
        "model": "nova-3",
        "smart_format": "true",
    }
)


def suggest(context):
    prompt = template.invoke({"context": context})
    response = model.invoke(prompt)
    return response.content + "\n\n---\n"


def transcribe(audio_segment):
    with tempfile.NamedTemporaryFile() as tmpfile:
        buffer_data = audio_segment.export(tmpfile.name, format="mp3").read()

        resp = dg_session.post(
            "https://api.deepgram.com/v1/listen", data=buffer_data
        )
        try:
            resp.raise_for_status()
        except Exception:
            return ""
        
        transcript = resp.json()["results"]["channels"][0]["alternatives"][0][
            "paragraphs"
        ]["transcript"]

        return transcript.strip()
