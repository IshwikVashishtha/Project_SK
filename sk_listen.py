import speech_recognition as sr
import threading

class ListenAudio:
    def __init__(self, wake_word="jarvis"):
        self.recognizer = sr.Recognizer()
        self.mic = sr.Microphone()
        self.wake_word = wake_word.lower()
        self._stop_flag = False
        # print(f"[ListenAudio] Wake word set to '{self.wake_word}'")

    def _listen_loop(self, callback):
        with self.mic as source:
            self.recognizer.adjust_for_ambient_noise(source)
            print("🎤 Listening continuously... (say wake word)")
            while not self._stop_flag:
                try:
                    audio = self.recognizer.listen(source, timeout=None, phrase_time_limit=10)
                    query = self.recognizer.recognize_google(audio, language="en-IN").lower()
                    print(f"🗣️ Heard: {query}")
                    if self.wake_word in query:
                        print(f"✅ Wake word '{self.wake_word}' detected!")
                        callback(query)
                except sr.UnknownValueError:
                    pass
                except sr.RequestError as e:
                    print(f"⚠️ Speech recognition error: {e}")
                except Exception as e:
                    print(f"⚠️ Error: {e}")

    def start_listening(self, callback):
        threading.Thread(target=self._listen_loop, args=(callback,), daemon=True).start()

    def stop_listening(self):
        self._stop_flag = True
