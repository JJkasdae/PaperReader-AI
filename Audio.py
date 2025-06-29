import time
import asyncio
import edge_tts
from numpy import isin
import pygame
import tempfile, os
from mutagen.mp3 import MP3

languages = {
    "English": "en-US-JennyNeural",
    "Chinese": "zh-CN-XiaoxiaoNeural"
}

class Audio():
    def __init__(self, log_queue, audio_command_queue, status_update) -> None:
        self.log_queue = log_queue
        self.audio_command_queue = audio_command_queue
        self.status_update = status_update
        self.temp_path = None
        self.is_paused = False
        self.duration = None
        pygame.mixer.init()
        self.temp_dir = "temp_audio_Daily_Reader"
        os.makedirs(self.temp_dir, exist_ok=True)
        self.seek_offset = 0.0

    async def speak(self, text, voice):
        self.seek_offset = 0.0
        self.duration = None
        self.temp_path = None

        # 生成临时 MP3 文件
        temp_file = tempfile.NamedTemporaryFile(
            delete=False, suffix=".mp3", dir=self.temp_dir
        )
        self.temp_path = temp_file.name
        temp_file.close()

        # 生成语音
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(self.temp_path)
        audio_info = MP3(self.temp_path)
        self.duration = audio_info.info.length

        pygame.mixer.music.load(self.temp_path)
        pygame.mixer.music.play()

        while True:
            await asyncio.sleep(0.2)

            # 每 0.5 秒发送一次播放进度
            if not self.is_paused:
                current_sec = self.get_current_position()
                self.log(self.status_update, {"progress": current_sec, "duration": self.duration})

            # 优先处理命令
            if not self.audio_command_queue.empty():
                command = self.audio_command_queue.get()
                if command == "pause" and not self.is_paused:
                    pygame.mixer.music.pause()
                    self.is_paused = True
                    self.log(self.log_queue, "⏸️ Audio paused.")
                elif command == "resume" and self.is_paused:
                    pygame.mixer.music.unpause()
                    self.is_paused = False
                    self.log(self.log_queue, "▶️ Audio resumed.")
                elif command == "stop":
                    pygame.mixer.music.stop()
                    self.log(self.log_queue, "⏹️ Audio stopped.")
                    break
                elif isinstance(command, str) and command.startswith("seek:"):
                    try:
                        seconds = float(command.split(":")[1])
                        self.seek(seconds=seconds)
                        # self.log(self.status_update, f"⏩ Seeked to {seconds:.1f} seconds")
                    except Exception as e:
                        self.log(self.log_queue, f"⚠️ Seek error: {e}")

            # 如果在暂停状态，不检查播放是否完成
            if self.is_paused:
                continue

            # 检查是否播放完毕
            if not pygame.mixer.music.get_busy():
                self.log(self.status_update, {"ended": True})
                break

        pygame.mixer.music.stop()
        pygame.mixer.music.unload()

    async def _play_all_papers_async(self, papers, language):
        for i, paper in enumerate(papers, 1):
            title = paper.get("title", "无标题")
            summary = paper.get("summary", {})
            text = f"{title}\n{summary}"

            self.log(self.log_queue, f"\n🎧 Play: {title}。\n{summary}")
            await self.speak(text, languages[language])
            await asyncio.sleep(1)  # 每篇之间停顿 1 秒
        self.log(self.status_update, {"workflow_done": True})


    def play_all_papers(self, papers, language):
        asyncio.run(self._play_all_papers_async(papers, language))

    def get_current_position(self):
        return self.seek_offset + (pygame.mixer.music.get_pos() / 1000)  # 转换为秒

    def seek(self, seconds):
        pygame.mixer.music.stop()
        pygame.mixer.music.play(start=seconds)
        self.seek_offset = seconds
        self.is_paused = False


    def log(self, queue, message):
        if queue:
            queue.put(message)
        else:
            raise ValueError("Queue is not initialized.")
