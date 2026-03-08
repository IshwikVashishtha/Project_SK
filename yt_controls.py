from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time


class YouTubeController:
    def __init__(self):
        self.driver = None

    def play_song(self, query: str) -> str:
        try:
            self.driver = webdriver.Chrome()
            self.driver.maximize_window()
            self.driver.get("https://www.youtube.com/")
            time.sleep(2)
            search_box = self.driver.find_element(By.NAME, "search_query")
            search_box.send_keys(query)
            search_box.send_keys(Keys.RETURN)
            time.sleep(3)
            first_video = self.driver.find_element(By.ID, "video-title")
            first_video.click()
            time.sleep(3)
            return f"Now playing '{query}' on YouTube!"
        except Exception as e:
            return f"Error while playing YouTube song: {e}"

    def play_pause(self) -> str:
        if self.driver is None:
            return "No YouTube session found. Please play a song first."
        try:
            self.driver.execute_script(
                "var video = document.querySelector('video');"
                "if(video){ video.paused ? video.play() : video.pause(); }"
            )
            return "Toggled Play/Pause on YouTube."
        except Exception as e:
            return f"Error controlling YouTube video: {e}"

    def skip_ad(self) -> str:
        if self.driver is None:
            return "No YouTube session found. Please play a song first."
        try:
            buttons = self.driver.find_elements(By.CLASS_NAME, "ytp-ad-skip-button-text")
            if buttons:
                buttons[0].click()
                return "Ad skipped!"
            return "No ad to skip right now."
        except Exception as e:
            return f"Error trying to skip ad: {e}"

    def close(self) -> str:
        if self.driver:
            self.driver.quit()
            self.driver = None
            return "Closed YouTube session."
        return "No active session to close."