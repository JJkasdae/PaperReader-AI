from openai import OpenAI
import re

section_headers = {
    "English": {
        "motivation": "Motivation of the study",
        "methodology": "Methodology or strategy",
        "contributions": "Key contributions",
        "challenges": "Limitations or challenges"
    },
    "Chinese": {
        "motivation": "研究动机",
        "methodology": "方法或策略",
        "contributions": "主要贡献",
        "challenges": "挑战或局限"
    }
}

class Agent:
    def __init__(self, api_key, model = "gpt-4o", temperature = 0.3):
        self.model = model
        self.client = OpenAI(api_key=api_key)
        self.temperature = temperature
        self.assistant_id = self.get_or_create_assistant()

    def get_or_create_assistant(self):
        assistants = self.client.beta.assistants.list()
        for assistant in assistants.data:
            if assistant.name == "Academic Summarizer":
                return assistant.id

        instruction = f"""
            You are a professional academic summary assistant.

            I will provide you with the title and abstract of a paper. Your task is to:
            1. Based on the provided content, extract the paper's core insight, methodology or strategy, key contributions, and limitations or challenges.

            Additional instructions:
            - If a PDF file is provided, carefully read and analyze the PDF to produce a detailed and accurate summary of the motivation, methodology, contributions, and challenges.
            - All information, facts, and data **must be strictly derived from the PDF content**. Do not add assumptions, speculation, or information beyond the PDF.
            - Ensure factual accuracy and reflect the author's original intentions and findings.
            - If no PDF is provided, summarize based on the abstract instead.

            Output format:

            ① motivation:  
            ② methodology:  
            ③ contributions:  
            ④ challenges:  
        """

        assistant = self.client.beta.assistants.create(
            name="Academic Summarizer",
            instructions=instruction,
            model=self.model,
            tools=[{"type": "file_search"}],
            temperature=self.temperature
        )
        return assistant.id

    def summarize_paper(self, title, abstract, language, pdf_path = None):
        headers = section_headers.get(language, section_headers["English"])
        Instruction = f"""
            You are a professional academic summary assistant.

            I will provide you with the title and abstract of a paper. Your task is to:
            1. Based on the provided content, extract the paper's core insight, methodology or strategy, key contributions, and limitations or challenges.
            2. Your response must be fully in {language}.

            Additional instructions:
            - If a PDF file is provided, carefully read and analyze the PDF to produce a detailed and accurate summary of the motivation, methodology, contributions, and challenges.
            - All information, facts, and data **must be strictly derived from the PDF content**. Do not add assumptions, speculation, or information beyond the PDF.
            - Ensure factual accuracy and reflect the author's original intentions and findings.
            - If no PDF is provided, summarize based on the abstract instead.

            Output format:

            ① {headers['motivation']}:  
            ② {headers['methodology']}:  
            ③ {headers['contributions']}:  
            ④ {headers['challenges']}:  
        """

        model_input = f"Title: {title}\nAbstract: {abstract}"

        try:
            file_id = None
            message_content = [{"type": "text", "text": model_input}]
            if pdf_path:
                with open(pdf_path, "rb") as f:
                    uploaded_file = self.client.files.create(file=f, purpose="assistants")
                file_id = uploaded_file.id

            thread = self.client.beta.threads.create(
                messages=[
                    {
                        "role": "user",
                        "content": message_content,
                        "attachments": [
                            {"file_id": file_id, "tools": [{"type": "file_search"}]}
                        ],
                    }
                ]
            )

            run = self.client.beta.threads.runs.create_and_poll(
                thread_id=thread.id,
                assistant_id=self.assistant_id,
                instructions=Instruction
            )

            messages = self.client.beta.threads.messages.list(thread_id=thread.id, run_id=run.id)
            final_response = re.sub(r"【[^】]*】", "", messages.data[0].content[0].text.value)

            return final_response
        except Exception as e:
            return f"调用出错：{e}"