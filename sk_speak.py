import pyttsx3
import threading ,re
# from murf import Murf

# client = Murf(api_key="YOUR_API_KEY")

# class SKSpeakes_with_murf:
#     def __init__(self , client = client):
#         self.client = client


#     def speak(self):
#     response = client.text_to_speech.generate(
#     text = "The Midnight Sun is a magical experience. During summer in the polar regions, the sun stays up all day and night, casting a unique light. See how this never-ending daylight affects life in these amazing places.",
#     voice_id = "en-Uk-Heidi",
#     style = "Conversational",
#     pitch = 4,
#     rate = -12,
#     multi_native_locale = "en-US"
#     )

#     print(response.audio_file)



class SkSpeaker:
    def __init__(self, voice_index=None):
        self.voice_index = voice_index
        print("[SkSpeaker] Ready with OS voices.")

    def list_voices(self):
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        for i, v in enumerate(voices):
            print(f"{i}: {v.name} | Lang: {v.languages} | ID: {v.id}")
        engine.stop()

    def set_voice(self, index):
        self.voice_index = index
        # print(f"[SkSpeaker] Will use voice index {index} next time.")

    def _speak_sync(self, text):
        engine = pyttsx3.init()
        if self.voice_index is not None:
            voices = engine.getProperty('voices')
            if 0 <= self.voice_index < len(voices):
                engine.setProperty('voice', voices[self.voice_index].id)
        safe_text = re.sub(r'[^a-zA-Z0-9\s,.!?]', '', text)
        engine.say(safe_text)
        engine.runAndWait()
        engine.stop()

    def speak(self, text):
        # Run speaking in background thread
        threading.Thread(target=self._speak_sync, args=(text,), daemon=True).start()
