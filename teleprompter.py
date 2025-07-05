import asyncio
import json
import queue
import time
from datetime import datetime, timedelta

import pydub
import streamlit as st
from streamlit_webrtc import WebRtcMode, webrtc_streamer

from utils import suggest, transcribe

LLM_INTERVAL = 15  # seconds

TRANSCRIPT_HISTORY_KEY = "transcript_history"
TRANSCRIPT_CONTEXT_KEY = "transcript_context"
AI_TIPS_HISTORY_KEY = "ai_tips_history"
PAUSED_TIME_KEY = "paused_time"

st.title("Sales Teleprompter")

webrtc_ctx = webrtc_streamer(
    key="sendonly-audio",
    mode=WebRtcMode.SENDONLY,
    audio_receiver_size=2048,
    media_stream_constraints={"audio": True},
)

status = st.empty()
status.write("Microphone is OFF")

timer_column, save_column = st.columns(2)
timer = timer_column.empty()
save = save_column.empty()

st.header("Transcript")
transcript_container = st.container(height=250)
transcript = transcript_container.chat_message("T")

st.header("AI Tips")
ai_tips_container = st.container(height=250)
ai_tips = ai_tips_container.chat_message("AI")


def load_history(key, container):
    if key not in st.session_state:
        st.session_state[key] = []
    else:
        for line in st.session_state[key]:
            container.write(line)


load_history(TRANSCRIPT_HISTORY_KEY, transcript)
load_history(AI_TIPS_HISTORY_KEY, ai_tips)

if TRANSCRIPT_CONTEXT_KEY not in st.session_state:
    st.session_state[TRANSCRIPT_CONTEXT_KEY] = ""

if PAUSED_TIME_KEY not in st.session_state:
    st.session_state[PAUSED_TIME_KEY] = 0
else:
    timer.write(
        f"Session Duration: **{timedelta(seconds=st.session_state[PAUSED_TIME_KEY])}**"
    )


async def main():
    async def timer_loop():
        while not webrtc_ctx.audio_receiver:
            await asyncio.sleep(0.1)

        start_time = time.time()
        offset = st.session_state[PAUSED_TIME_KEY]

        while True:
            time_elapsed = offset + int(time.time() - start_time)
            timer.write(f"Session Duration: **{timedelta(seconds=time_elapsed)}**")
            st.session_state[PAUSED_TIME_KEY] = time_elapsed
            await asyncio.sleep(1)

    async def teleprompter_loop():
        last_llm_time = time.time()
        last_llm_index = 0

        while True:
            if webrtc_ctx.audio_receiver:
                status.write("Microphone is ON")

                try:
                    audio_frames = webrtc_ctx.audio_receiver.get_frames(timeout=0.5)
                except queue.Empty:
                    continue

                sound_chunk = pydub.AudioSegment.empty()
                for audio_frame in audio_frames:
                    sound = pydub.AudioSegment(
                        data=audio_frame.to_ndarray().tobytes(),
                        sample_width=audio_frame.format.bytes,
                        frame_rate=audio_frame.sample_rate,
                        channels=len(audio_frame.layout.channels),
                    )
                    sound_chunk += sound

                if len(sound_chunk) > 0:
                    text = await asyncio.to_thread(transcribe, sound_chunk)

                    if text:
                        timestamped_text = (  # e.g. Jun 30 2025, 02:49AM
                            datetime.now().strftime("**%b %d %Y, %I:%M%p**: ") + text
                        )
                        transcript.write(timestamped_text)
                        st.session_state[TRANSCRIPT_HISTORY_KEY].append(timestamped_text)

                        st.session_state[TRANSCRIPT_CONTEXT_KEY] += f"{text}\n"

                if (now := time.time()) - last_llm_time > LLM_INTERVAL:
                    current_context = st.session_state[TRANSCRIPT_CONTEXT_KEY][
                        last_llm_index:
                    ]
                    if current_context:
                        llm_response = await asyncio.to_thread(suggest, current_context)
                        ai_tips.write(llm_response)
                        st.session_state[AI_TIPS_HISTORY_KEY].append(llm_response)
                        last_llm_time = now
                        last_llm_index = len(st.session_state[TRANSCRIPT_CONTEXT_KEY])
            else:
                if (
                    st.session_state[TRANSCRIPT_HISTORY_KEY]
                    or st.session_state[AI_TIPS_HISTORY_KEY]
                ):
                    log_dict = {
                        "transcript": st.session_state[TRANSCRIPT_HISTORY_KEY],
                        "ai_tips": st.session_state[AI_TIPS_HISTORY_KEY],
                    }

                    save.download_button(
                        label="Save Transcript & Tips Log",
                        data=json.dumps(log_dict, indent=4),
                        file_name=f"sales_teleprompter_logs_{int(time.time())}.json",
                        icon=":material/download:",
                        use_container_width=True,
                    )
                break

    await asyncio.gather(timer_loop(), teleprompter_loop())


if __name__ == "__main__":
    asyncio.run(main())
