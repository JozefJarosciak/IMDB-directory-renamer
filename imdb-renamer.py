import os
import re
import datetime
import concurrent.futures
import requests
from bs4 import BeautifulSoup
from imdb import Cinemagoer
import argparse
import logging
import time
from functools import wraps

# Configuration Section
CONFIG = {
    "BASE_PATH": r"D:\Test",  # Directory containing movie folders
    "LOG_FILE": "imdb_renamer.log",  # Log file name
    "MAX_RETRIES": 3,  # Maximum retries for network requests
    "RETRY_DELAY": 10,  # Delay (seconds) between retries
    "CURRENT_YEAR": datetime.datetime.now().year,  # Dynamically calculated current year
    "GOOGLE_HEADERS": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36"
        )
    },
    "MAX_SEARCH_RESULTS": 10,  # Maximum IMDb search results to consider
    "THREAD_POOL_WORKERS": 5,  # Number of threads for concurrent IMDb lookups
    "EXTRANEOUS_WORDS": [  # Words to remove when simplifying folder names
        "COMPLETE", "720p", "1080p", "BRrip", "BluRay", "HDRip", "sujaidr", "pimprg", "YTS", "MX",
        "x264", "x265", "HEVC", "AAC", "WEBRip", "WebDL", "H.264", "H.265", "DVDrip", "BRRip"
    ]
}

# Configure logging
logging.basicConfig(
    filename=CONFIG["LOG_FILE"],
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Retry decorator
def retry(max_retries=CONFIG["MAX_RETRIES"], delay=CONFIG["RETRY_DELAY"]):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts >= max_retries:
                        raise
                    logging.warning(
                        f"Retrying {func.__name__} due to error: {e}. Attempt {attempts} of {max_retries}. Retrying in {delay} seconds..."
                    )
                    time.sleep(delay)
        return wrapper
    return decorator

# Create an instance of the Cinemagoer class
ia = Cinemagoer()

def sanitize_folder_name(folder_name):
    """Cleans folder name by removing unnecessary tags and formatting."""
    clean_name = re.sub(r"\[.*?\]|\b\d+p\b|\.|\-|_", " ", folder_name)
    clean_name = re.sub(r"[\(\)]", " ", clean_name)
    clean_name = re.sub(r"\s+", " ", clean_name).strip()
    year_match = re.search(r"\b(19|20)\d{2}\b", clean_name)
    if year_match:
        year = int(year_match.group(0))
        if 1900 <= year <= CONFIG["CURRENT_YEAR"]:
            title_part = clean_name[:year_match.start()].strip()
            clean_name = f"{title_part} {year}"
    return clean_name

def extract_year(folder_name):
    """Extracts the year from the folder name if within a valid range."""
    match = re.search(r"\b(19|20)\d{2}\b", folder_name)
    if match:
        year = int(match.group(0))
        if 1900 <= year <= CONFIG["CURRENT_YEAR"]:
            return str(year)
    return None

def safe_name(name):
    """Replaces illegal characters in filenames."""
    return re.sub(r'[<>:"/\\|?*]', "-", name)

def already_properly_named(folder_name):
    """Checks if folder name already follows the expected naming convention."""
    pattern = r".* \((19|20)\d{2}\) - IMDb[-:]\s?\d+(\.\d+)?$"
    return bool(re.match(pattern, folder_name))

@retry()
def fetch_movie_details(ia, result):
    """Fetches detailed information for a single movie."""
    try:
        movie = ia.get_movie(result.movieID)
        title = movie.get("title", "Unknown Title")
        year = movie.get("year", "Unknown Year")
        rating = movie.get("rating", 0.0)  # Default to 0.0 if no rating
        votes = movie.get("votes", 0)
        return {
            "title": title,
            "year": year,
            "rating": rating,
            "votes": votes,
        }
    except Exception as e:
        logging.error(f"Error fetching details for movie ID {result.movieID}: {e}")
        raise
    return None

@retry()
def fallback_search_imdb_id(sanitized_name):
    """Performs a Google search to find IMDb ID."""
    query = f"{sanitized_name} site:imdb.com"
    try:
        response = requests.get(
            f"https://www.google.com/search?q={query}&num=1&hl=en",
            headers=CONFIG["GOOGLE_HEADERS"],
            timeout=5,
        )
        if response.status_code != 200:
            logging.error(f"Failed to fetch Google search page. Status code: {response.status_code}")
            return None
        soup = BeautifulSoup(response.text, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if "imdb.com/title/tt" in href:
                match = re.search(r"tt\d+", href)
                if match:
                    imdb_id = match.group(0)
                    logging.info(f"Found IMDb ID {imdb_id} for '{sanitized_name}'")
                    return imdb_id
        logging.warning(f"No IMDb ID found in Google results for '{sanitized_name}'")
    except Exception as e:
        logging.error(f"Error during Google search for '{sanitized_name}': {e}")
        raise
    return None

@retry()
def get_movie_details(ia, movie_name):
    """Fetches movie details from IMDb."""
    try:
        search_results = ia.search_movie(movie_name)[:CONFIG["MAX_SEARCH_RESULTS"]]
        if not search_results:
            return []
        details = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=CONFIG["THREAD_POOL_WORKERS"]) as executor:
            future_to_result = {executor.submit(fetch_movie_details, ia, result): result for result in search_results}
            for future in concurrent.futures.as_completed(future_to_result):
                movie_details = future.result()
                if movie_details:
                    details.append(movie_details)
        return details
    except Exception as e:
        logging.error(f"Error during IMDb search for '{movie_name}': {e}")
        raise

def prompt_user_choice(choices):
    """Prompts the user to select a choice or provide a custom name."""
    print("\nPlease choose one of the following options:")
    for i, choice in enumerate(choices, start=1):
        formatted_votes = f"{choice['votes']:,}"  # Format votes with commas
        print(f"{i}. {choice['title']} ({choice['year']}) - IMDb- {choice['rating']} "
              f"(Ranked by {formatted_votes} people)")
    print(f"{len(choices) + 1}. Enter a custom name")

    while True:
        try:
            user_input = input("Enter the number of your choice or custom name: ").strip()

            # If input is a number, validate it
            if user_input.isdigit():
                choice_number = int(user_input)
                if 1 <= choice_number <= len(choices):
                    return choices[choice_number - 1]  # Return selected choice
                elif choice_number == len(choices) + 1:
                    custom_name = input("Enter the custom name: ").strip()
                    if custom_name:  # Ensure valid non-empty name
                        return {"title": custom_name, "custom": True}
                    else:
                        print("Custom name cannot be empty. Please try again.")
                else:
                    print("Invalid choice number. Please try again.")
            else:
                # Assume custom name if input is not a digit
                if user_input:  # Ensure valid non-empty input
                    return {"title": user_input, "custom": True}
                else:
                    print("Custom name cannot be empty. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a valid number or name.")


def rename_folder(folder_path, choice, dry_run=False):
    """Renames a folder to the new name."""
    # Extract only the essential parts of the folder name for renaming
    new_name = f"{choice['title']} ({choice['year']}) - IMDb- {choice['rating']}"
    parent_dir = os.path.dirname(folder_path)
    safe_new_name = safe_name(new_name)
    new_folder_path = os.path.join(parent_dir, safe_new_name)

    if dry_run:
        print(f"Would rename '{folder_path}' to '{new_folder_path}'")
        logging.info(f"Would rename '{folder_path}' to '{new_folder_path}'")
        return

    try:
        os.rename(folder_path, new_folder_path)
        print(f"Renamed to: {safe_new_name}")
        logging.info(f"Renamed '{folder_path}' to '{new_folder_path}'")
    except Exception as e:
        print(f"Failed to rename '{folder_path}' to '{new_folder_path}': {e}")
        logging.error(f"Failed to rename '{folder_path}' to '{new_folder_path}': {e}")


def simplify_name(sanitized_name):
    """Simplifies the name by removing common extraneous words and focusing on core title."""
    extraneous_words = CONFIG["EXTRANEOUS_WORDS"]
    # Remove extraneous words
    words = sanitized_name.split()
    simplified_words = [word for word in words if word.upper() not in extraneous_words]

    # Remove group tags or parentheses
    simplified_name = " ".join(simplified_words)
    simplified_name = re.sub(r"\(.*?\)", "", simplified_name).strip()

    return simplified_name


def extract_core_title(sanitized_name):
    """Extracts the core title, removing season, episode, and residual extraneous details."""
    # Remove "Season X", "Episode X" patterns
    core_title = re.sub(r"\bSeason\s?\d+\b", "", sanitized_name, flags=re.IGNORECASE)
    core_title = re.sub(r"\bEpisode\s?\d+\b", "", core_title, flags=re.IGNORECASE)

    # Remove anything that looks like a file encoding or group tag
    core_title = re.sub(r"\b\d{3,4}p\b", "", core_title, flags=re.IGNORECASE)  # e.g., 720p, 1080p
    core_title = re.sub(r"\b(BRRip|BluRay|HDRip|WebDL|WEBRip|x264|x265|HEVC|AAC|H.264|H.265|DVDrip)\b", "", core_title, flags=re.IGNORECASE)
    core_title = re.sub(r"\b(sujaidr|pimprg|YTS|MX)\b", "", core_title, flags=re.IGNORECASE)

    # Remove multiple spaces and strip the result
    core_title = re.sub(r"\s+", " ", core_title).strip()

    return core_title



def main():
    """Main function to rename movie folders."""
    parser = argparse.ArgumentParser(description="IMDb Folder Renamer")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without renaming folders")
    args = parser.parse_args()

    base_path = CONFIG["BASE_PATH"]
    if not os.path.exists(base_path):
        print(f"Path does not exist: {base_path}")
        logging.error(f"Path does not exist: {base_path}")
        return

    for folder in os.listdir(base_path):
        folder_path = os.path.join(base_path, folder)
        if not os.path.isdir(folder_path):
            continue

        if already_properly_named(folder):
            logging.info(f"Skipping already properly named folder: {folder}")
            continue

        print(f"\nProcessing folder: {folder}")
        logging.info(f"Processing folder: {folder}")
        sanitized_name = sanitize_folder_name(folder)
        year = extract_year(folder)

        if year and year not in sanitized_name:
            sanitized_name = f"{sanitized_name} {year}"

        print(f"Sanitized name: {sanitized_name}")
        logging.info(f"Sanitized name: {sanitized_name}")

        # Step 1: Try with sanitized name
        search_results = get_movie_details(ia, sanitized_name)
        choices = [
            {
                "title": result["title"],
                "year": result["year"],
                "rating": result["rating"],
                "votes": result["votes"],
            }
            for result in search_results
        ]

        # Step 2: Sort results by year (priority) and votes
        if year:
            year_int = int(year)
            choices.sort(key=lambda x: (x["year"] == year_int, x["votes"]), reverse=True)
        else:
            choices.sort(key=lambda x: x["votes"], reverse=True)

        if choices:
            final_choice = prompt_user_choice(choices)
            if final_choice:
                rename_folder(folder_path, final_choice, dry_run=args.dry_run)
            else:
                print(f"Skipping folder: {folder}")
                logging.info(f"Skipped folder: {folder}")
            continue

        # Step 3: Retry with simplified name
        simplified_name = simplify_name(sanitized_name)
        if simplified_name != sanitized_name:
            print(f"No valid options found. Retrying with simplified name: {simplified_name}")
            logging.info(f"Retrying with simplified name: {simplified_name}")
            search_results = get_movie_details(ia, simplified_name)
            choices = [
                {
                    "title": result["title"],
                    "year": result["year"],
                    "rating": result["rating"],
                    "votes": result["votes"],
                }
                for result in search_results
            ]
            if choices:
                final_choice = prompt_user_choice(choices)
                if final_choice:
                    rename_folder(folder_path, final_choice, dry_run=args.dry_run)
                else:
                    print(f"Skipping folder: {folder}")
                    logging.info(f"Skipped folder: {folder}")
                continue

        # Step 4: Retry with core title
        core_title = extract_core_title(simplified_name)
        if core_title != simplified_name:
            print(f"No valid options found. Retrying with core title: {core_title}")
            logging.info(f"Retrying with core title: {core_title}")
            search_results = get_movie_details(ia, core_title)
            choices = [
                {
                    "title": result["title"],
                    "year": result["year"],
                    "rating": result["rating"],
                    "votes": result["votes"],
                }
                for result in search_results
            ]
            if choices:
                final_choice = prompt_user_choice(choices)
                if final_choice:
                    rename_folder(folder_path, final_choice, dry_run=args.dry_run)
                else:
                    print(f"Skipping folder: {folder}")
                    logging.info(f"Skipped folder: {folder}")
                continue

        # Step 5: Final fallback with user input
        print(f"No valid options found for '{sanitized_name}'. Would you like to retry with a custom name? (yes/no)")
        user_input = input().strip().lower()
        if user_input == "yes":
            custom_name = input("Enter the custom name to retry: ").strip()
            if custom_name:
                print(f"Retrying with custom name: {custom_name}")
                logging.info(f"Retrying with custom name: {custom_name}")
                search_results = get_movie_details(ia, custom_name)
                choices = [
                    {
                        "title": result["title"],
                        "year": result["year"],
                        "rating": result["rating"],
                        "votes": result["votes"],
                    }
                    for result in search_results
                ]
                if choices:
                    final_choice = prompt_user_choice(choices)
                    if final_choice:
                        rename_folder(folder_path, final_choice, dry_run=args.dry_run)
                    else:
                        print(f"Skipping folder: {folder}")
                        logging.info(f"Skipped folder: {folder}")
                    continue
            else:
                print("No custom name provided. Skipping folder...")
                logging.info("No custom name provided. Skipping folder.")



if __name__ == "__main__":
    main()
