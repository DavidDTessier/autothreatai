import os
import logging

def load_file_content(file_path: str, fallback: str = None) -> str:
    """
    Generic utility to load the content of a text file.

    This function reads the specified file and returns its content as a string.
    If the file is not found and a fallback is provided, it returns the fallback.

    Args:
        file_path (str): The path to the file to be read.
        fallback (str, optional): Default content if file is missing.

    Returns:
        str: The contents of the file or fallback.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except (FileNotFoundError, IOError) as e:
        if fallback is not None:
            logging.warning(f"File not found or unreadable: {file_path}. Using fallback.")
            return fallback
        logging.error(f"Error reading file {file_path}: {e}")
        raise

def load_instructions_file(file_path: str, fallback: str = "Perform your tasks as an expert agent.") -> str:
    """
    Loads agent instructions from a specified file with a default fallback.
    """
    return load_file_content(file_path, fallback=fallback)


