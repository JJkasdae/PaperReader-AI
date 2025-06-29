import requests
from bs4 import BeautifulSoup
import time
import json
import tempfile, os

class Extraction():
    def __init__(self, log_queue):
        self.log_queue = log_queue
        self.temp_pdf_dir = "temp_pdf"
        os.makedirs(self.temp_pdf_dir, exist_ok=True)

    def extract_abstract(self, paper_url):
        try:
            response = requests.get(paper_url)
            soup = BeautifulSoup(response.text, "html.parser")

            abstract_header = soup.find("h2", string="Abstract")
            pdf_temp_path = None

            # Step 1: Abstract Extraction
            if abstract_header:
                abstract_container = abstract_header.find_next_sibling("div")
                if abstract_container:
                    # 只提取 <p class="text-gray-600"> 的内容
                    p_tags = abstract_container.find_all("p", class_="text-gray-600")
                    abstract_text = "\n".join(p.get_text(strip=True) for p in p_tags)
                    if not abstract_text:
                        abstract_text = "The abstract is empty."
            
            # Step 2: PDF Extraction
            pdf_link = None
            for a in soup.find_all("a", class_="btn inline-flex h-9 items-center", href=True):
                href = a["href"]
                if href.lower().endswith(".pdf") or "/pdf/" in href.lower():
                    pdf_link = href
                    break

            # Step 3: 判断是否有效 PDF 链接
            if pdf_link:
                head = requests.head(pdf_link, allow_redirects=True, timeout=5)
                if head.status_code == 200 and "pdf" in head.headers.get("Content-Type", "").lower():
                    pdf_response = requests.get(pdf_link, stream=True)
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=self.temp_pdf_dir)
                    with open(temp_file.name, "wb") as f:
                        for chunk in pdf_response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    pdf_temp_path = temp_file.name                
            return {
                "abstract": abstract_text,
                "pdf_path": pdf_temp_path
            }

        except Exception as e:
            self.log(f"Error extracting abstract/pdf: {e}")
            return {
                "abstract": "Error occurred while extracting abstract.",
                "pdf_path": None
            }

    def save_papers_to_json(self, papers, filename="daily_papers.json"):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(papers, f, ensure_ascii=False, indent=4)

    def fetch_daily_papers(self, url="https://huggingface.co/papers", max_count = 2):
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        count = 0

        papers = []

        for card in soup.select("article"):  # 每篇论文是一个 <article> 元素
            if count == max_count:
                break
            title_tag = card.select_one("h3")
            if not title_tag:
                continue
            title = title_tag.text.strip()

            link_tag = card.find("a", href=True)
            url = "https://huggingface.co" + link_tag['href'] if link_tag else "no link"

            self.log(f"Trying to extract papers: {title}")
            data = self.extract_abstract(url)
            abstract = data["abstract"]
            pdf_path = data["pdf_path"]

            papers.append({
                "title": title,
                "url": url,
                "abstract": abstract,
                "pdf_path": pdf_path
            })
            time.sleep(1)  # 礼貌抓取，避免太快被封IP
            count += 1
        
        return papers

    def log(self, message):
        if self.log_queue:
            self.log_queue.put(message)
        else:
            raise ValueError("log_queue is not initialized.")
    
    def delete_temp_pdf(self, paper):
        pdf_path = paper.get("pdf_path")
        if pdf_path and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
                self.log(f"🧹 Deleted temp PDF: {pdf_path}")
            except Exception as e:
                self.log(f"⚠️ Failed to delete {pdf_path}: {e}")

    def cleanup_temp_pdfs(self, papers):
        for paper in papers:
            self.delete_temp_pdf(paper)
"""
    控制代码执行 ：你可以在这个判断下写一些代码，这些代码只有在文件被直接运行时才会执行，而不会在文件被导入时执行。
"""
if __name__ == "__main__":
    extractor = Extraction(log_queue=None)
    papers = extractor.fetch_daily_papers()
    for i, paper in enumerate(papers[:5], 1):  # 显示前5篇做测试
        print(f"{i}. {paper['title']}\n Abstract: {paper['abstract']}\n Link: {paper['url']}\n")
    extractor.save_papers_to_json(papers=papers)
    print(f"\n已保存 {len(papers)} 篇论文摘要到 daily_papers.json")