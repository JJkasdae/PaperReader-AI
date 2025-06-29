from main import Execution
from Audio import Audio

def run_main_function(log_queue,language, audio_command_queue, status_update):
    executor = Execution(log_queue=log_queue,language=language, audio_command_queue=audio_command_queue, status_update=status_update)
    executor.main_function()