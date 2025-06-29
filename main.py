from Agent import Agent
from Audio import Audio
from Extraction import Extraction
from dotenv import load_dotenv
import json, time, os

class Execution():
    def __init__(self, log_queue, language, audio_command_queue, status_update) -> None:
        load_dotenv()
        self.extractor = Extraction(log_queue)
        key = os.getenv("OPENAI_API_KEY")
        self.agent = Agent(api_key=key)
        self.audio_player = Audio(log_queue, audio_command_queue, status_update)
        self.language = language
        self.log_queue = log_queue
        self.audio_command_queue = audio_command_queue
        self.status_update = status_update

    def main_function(self):
        papers = self.extractor.fetch_daily_papers()
        self.extractor.save_papers_to_json(papers)
        output = []
        try:
            with open("daily_papers.json", "r", encoding="utf-8") as f:
                papers = json.load(f)
        except:
            raise FileNotFoundError("The daily_papers.json file is not found.")
        
        for i, paper in enumerate(papers):
            self.log(f"\n[{i+1}] Processing: {paper['title']}")
            summary = self.agent.summarize_paper(paper["title"], paper["abstract"], self.language, pdf_path=paper["pdf_path"])
            output.append({
                "title": paper["title"],
                "summary": summary
            })
            time.sleep(1)  # 防止请求过快

        self.extractor.save_papers_to_json(papers=output, filename="summary.json")

        self.extractor.cleanup_temp_pdfs(papers=papers)

        self.audio_player.play_all_papers(papers=output, language = self.language)

    def log(self, message):
        if self.log_queue:
            self.log_queue.put(message)
        else:
            raise ValueError("log_queue is not initialized.")