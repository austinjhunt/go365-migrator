import logging 
import os 
from .constants import LOG_FOLDER_PATH
from datetime import timedelta
from pathlib import PurePath

class BaseLogging: 
    def __init__(self, name: str = '', verbose: bool = False): 
        self.name = name
        self.verbose = verbose 
        self.setup_logging() 
    
    def setup_logging(self):
        """ set up self.logger for Driver logging """ 
        self.logger = logging.getLogger(self.name)
        format = "[%(prefix)s - %(filename)s:%(lineno)s - %(funcName)3s() ] %(message)s"
        formatter = logging.Formatter(format)
        handlerStream = logging.StreamHandler()
        handlerStream.setFormatter(formatter) 
        self.logger.addHandler(handlerStream)  
        os.makedirs(LOG_FOLDER_PATH, exist_ok=True) 
        handlerFile = logging.FileHandler(f'{LOG_FOLDER_PATH}/{self.name}.log')
        handlerFile.setFormatter(formatter) 
        self.logger.addHandler(handlerFile)  
        if self.verbose:
            self.logger.setLevel(logging.DEBUG) 
        else:
            self.logger.setLevel(logging.INFO)
    
    def get_name_of_folder_or_file_from_path(self, path):  
        name = str(PurePath(path).parts[-1]) 
        return name

    def format_elapsed_time_seconds(self, elapsed_time_seconds): 
        time_string = str(timedelta(seconds=elapsed_time_seconds))
        h,m,s = time_string.split(':')
        return f'{h} hours, {m} minutes, and {s} seconds'

    def sizeof_fmt(self, num, suffix='B'):
        """ format the file size """
        for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
            if abs(num) < 1024.0:
                return "%3.1f%s%s" % (num, unit, suffix)
            num /= 1024.0
        return "%.1f%s%s" % (num, 'Yi', suffix) 

    def get_directory_tree(self, startpath):
        tree_string = ''
        for root, dirs, files in os.walk(startpath):
            level = root.replace(startpath, '').count(os.sep)
            indent = ' ' * 4 * (level)
            tree_string += '\n{}{}/'.format(indent, os.path.basename(root))
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                tree_string += '\n{}{}'.format(subindent, f)
        return tree_string

    def count_local_folders_files_recursively(self, folder_path): 
        self.info(f'Counting folders/files recursively from {folder_path}')
        num_dirs = 0
        num_files = 0
        for base, dirs, files in os.walk(folder_path): 
            for directories in dirs:
                num_dirs += 1
            for Files in files:
                num_dirs += 1
        # include base
        num_dirs += 1
        return num_dirs + num_files  
    
    def shutdown_logging(self):
        logging.shutdown()

    def disable_logging(self): 
        self.logger.disabled = True 

    def enable_logging(self):
        self.logger.disabled = False 
        
    def debug(self, msg):
        self.logger.debug(msg, extra={'prefix': self.name}, stacklevel=2)

    def info(self, msg):
        self.logger.info(msg, extra={'prefix': self.name}, stacklevel=2)

    def error(self, msg):
        self.logger.error(msg, extra={'prefix': self.name}, stacklevel=2)