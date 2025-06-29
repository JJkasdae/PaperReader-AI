import tkinter as tk
import Processor
from multiprocessing import Process, Queue
import os, shutil

class UI:
    def __init__(self, root) -> None:
        self.process = None
        self.log_queue = Queue() # sub-process -> main process
        self.audio_command_queue = Queue() # main process -> sub-process
        self.status_update = Queue()
        self.audio_state = "stopped"  # 状态：stopped / playing / paused

        self.root = root
        self.root.title("🤖 AI Daily Paper Reader")
        self.root.geometry("880x640")
        self.root.configure(bg="#f2f2f2")  # 浅灰背景

        self.slider_dragging = False

        self.status_label = tk.Label(
            root, text="🧠 Click the button below to summarize and read AI papers~",
            font=("Segoe UI", 13), bg="#f2f2f2", fg="#333333"
        )
        self.status_label.pack(pady=(20, 10))

        # 添加语言选择标签和下拉菜单
        language_frame = tk.Frame(root, bg="#f2f2f2")
        language_frame.pack(pady=(0, 5))

        tk.Label(
            language_frame, text="🌐 Select Language:",
            font=("Segoe UI", 11), bg="#f2f2f2", fg="#333333"
        ).pack(side=tk.LEFT)

        self.selected_language = tk.StringVar(value="English")
        language_options = ["English", "Chinese"]  # 可自行扩展
        self.language_menu = tk.OptionMenu(language_frame, self.selected_language, *language_options)
        self.language_menu.config(font=("Segoe UI", 11))
        self.language_menu.pack(side=tk.LEFT, padx=10)

        button_frame = tk.Frame(root, bg="#f2f2f2")
        button_frame.pack(pady=10)

        self.play_button = tk.Button(
            button_frame, text="▶️ Play", font=("Segoe UI", 12),
            width=12, bg="#4CAF50", fg="white",
            relief="raised", command=self.start_process
        )
        self.play_button.pack(side=tk.LEFT, padx=10)

        self.pause_resume_button = tk.Button(
            button_frame, text="⏸️ Pause Audio", font=("Segoe UI", 12),
            width=12, bg="#2196F3", fg="white",
            relief="raised", command=self.toggle_pause_resume
        )
        self.pause_resume_button.pack(side=tk.LEFT, padx=10)
        self.pause_resume_button.config(state=tk.DISABLED)

        self.stop_button = tk.Button(
            button_frame, text="⏹️ Stop", font=("Segoe UI", 12),
            width=12, bg="#F44336", fg="white",
            relief="raised", command=self.stop_process
        )
        self.stop_button.pack(side=tk.LEFT, padx=10)

        # 添加进度条和当前时间标签
        slider_frame = tk.Frame(root, bg="#f2f2f2")
        slider_frame.pack(pady=(0, 10))

        self.current_time_label = tk.Label(slider_frame, text="0:00", bg="#f2f2f2", font=("Segoe UI", 10))
        self.current_time_label.pack(side=tk.LEFT, padx=(10, 5))

        self.slider = tk.Scale(
            slider_frame, from_=0, to=100, orient=tk.HORIZONTAL,
            length=500, showvalue=0, bg="#f2f2f2",
            troughcolor="#cccccc", sliderrelief="flat"
        )
        self.slider.pack(side=tk.LEFT)
        self.slider.bind("<Button-1>", self.on_slider_press)
        self.slider.bind("<ButtonRelease-1>", self.on_slider_release)
        self.slider.config(state=tk.DISABLED)

        self.total_time_label = tk.Label(slider_frame, text="0:00", bg="#f2f2f2", font=("Segoe UI", 10))
        self.total_time_label.pack(side=tk.LEFT, padx=(5, 10))

        console_frame = tk.Frame(root)
        console_frame.pack(padx=15, pady=(20, 15), fill=tk.BOTH, expand=True)

        self.console_output = tk.Text(
            console_frame, height=20, wrap="word", font=("Consolas", 10),
            bg="white", fg="black", relief="solid", bd=1
        )
        self.console_output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scroll = tk.Scrollbar(console_frame, command=self.console_output.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.console_output.config(yscrollcommand=scroll.set)

        self.check_log_queue()
        self.update_UI_status()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def toggle_pause_resume(self):
        if self.audio_state == "playing":
            self.log("pause")
            self.audio_state = "paused"
            self.pause_resume_button.config(text="▶️ Resume Audio")
            self.status_label.config(text="⏸️ Paused")
        elif self.audio_state == "paused":
            self.log("resume")
            self.audio_state = "playing"
            self.pause_resume_button.config(text="⏸️ Pause Audio")
            self.status_label.config(text="📡 Resumed")

    def start_process(self):
        if self.audio_state != "stopped":
            return  # 避免重复点击\
        self.console_output.insert(tk.END, "Process starts..." + "\n")
        language = self.selected_language.get()
        self.process = Process(target=Processor.run_main_function, args=(self.log_queue,language, self.audio_command_queue, self.status_update))
        self.process.start()
        self.audio_state = "playing"
        self.status_label.config(text="📡 Playing...")
        self.play_button.config(state=tk.DISABLED)
        self.pause_resume_button.config(state=tk.NORMAL)
        self.slider.config(state=tk.NORMAL)

    def stop_process(self):
        if self.process and self.process.is_alive():
            self.process.terminate()  # ✅ 立即终止子进程
            self.process.join()

            self.audio_state = "stopped"
            self.status_label.config(text="🛑 Process stopped.")
            self.pause_resume_button.config(state=tk.DISABLED)
            self.slider.config(state=tk.DISABLED)
            self.play_button.config(state=tk.NORMAL)  # ✅ 启用播放按钮
        
        temp_dir = "temp_audio_Daily_Reader"
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)  # 删除整个目录

        pdf_temp_dir = "temp_pdf"
        if os.path.exists(pdf_temp_dir):
            shutil.rmtree(pdf_temp_dir)

    def check_log_queue(self):
        while not self.log_queue.empty():
            message = self.log_queue.get()
            self.console_output.insert(tk.END, message + '\n')
            self.console_output.see(tk.END)  # 自动滚动到底部
        self.root.after(100, self.check_log_queue)  # 每100ms检查一次
    
    def on_close(self):
        # 1. 停止子进程（如果仍在运行）
        if self.process and self.process.is_alive():
            self.process.terminate()
            self.process.join()

        # 2. 删除 temp_audio 文件夹
        audio_temp_dir = "temp_audio_Daily_Reader"
        if os.path.exists(audio_temp_dir):
            shutil.rmtree(audio_temp_dir)

        # 3. 删除 temp_pdf 文件夹
        pdf_temp_dir = "temp_pdf"
        if os.path.exists(pdf_temp_dir):
            shutil.rmtree(pdf_temp_dir)

        # 3. 关闭窗口
        self.root.destroy()

    def on_slider_press(self, event):
        if self.audio_state == "playing":
            self.log("pause")
            self.audio_state = "paused"
            self.slider_dragging = True

    def on_slider_release(self, event):
        if self.audio_state in ("playing", "paused"):
            self.slider_dragging = False
            seek_time = self.slider.get()
            self.log(f"seek:{seek_time}")
            self.audio_state = "playing"
            # self.slider.set(seek_time)
            self.current_time_label.config(text=self.format_time(seek_time))

    def update_UI_status(self):
        if self.audio_state in ("playing", "paused") and not self.slider_dragging:
            # 从 audio 子进程读取当前播放进度（可以放到 log_queue 或 pipe 里）
            try:
                # 假设 log_queue 传来 special key，如 {"progress": 25.6}
                while not self.status_update.empty():
                    msg = self.status_update.get()
                    if isinstance(msg, dict): 
                        if "progress" in msg:
                            current = msg["progress"]
                            total = msg["duration"]
                            if self.slider.cget("to") != int(total):
                                self.slider.config(to=int(total))
                            self.slider.set(current)
                            self.current_time_label.config(text=self.format_time(current))
                            self.total_time_label.config(text=self.format_time(total))
                        elif "ended" in msg:
                            self.slider.set(0)
                            self.slider.config(to=100)
                            self.current_time_label.config(text="0:00")
                            self.total_time_label.config(text="0:00")
                        elif "workflow_done" in msg:
                            self.audio_state = "stopped"
                            self.pause_resume_button.config(state=tk.DISABLED)
                            self.slider.config(state=tk.DISABLED)
                            self.play_button.config(state=tk.NORMAL)
                            self.status_label.config(text="✅ All papers played.")
                    elif isinstance(msg, str):
                        self.console_output.insert(tk.END, msg + '\n')
            except:
                pass

        self.root.after(500, self.update_UI_status)

    def format_time(self, seconds):
        minutes = int(seconds) // 60
        secs = int(seconds) % 60
        return f"{minutes}:{secs:02d}"

    def log(self, message):
        if self.audio_command_queue:
            self.audio_command_queue.put(message)
        else:
            raise ValueError("audio_command_queue is not initialized.")

if __name__ == "__main__":
    root = tk.Tk()
    app = UI(root)
    root.mainloop()