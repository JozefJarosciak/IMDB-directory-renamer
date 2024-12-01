
# IMDb Directory Renamer

IMDb Directory Renamer is a Python script that helps organize and rename movie folders based on their IMDb details. It sanitizes folder names, fetches movie details from IMDb, and renames folders with a consistent naming convention, making it easier to navigate and maintain your movie library.

## Features

- Cleans up and simplifies folder names by removing extraneous tags and encoding information.
- Fetches movie details such as title, year, IMDb rating, and votes using IMDb API.
- Allows users to select the correct movie from search results manually.
- Supports retries and fallback mechanisms for fetching IMDb details.
- Provides a dry-run option to preview changes before applying them.

## Screenshot
![image](https://github.com/user-attachments/assets/5122dfcc-8a39-42cd-8e52-2dd9d6688687)


## Requirements

- Python 3.7+
- Required Python packages:
  - requests
  - bs4
  - IMDbPY
  - argparse

Install dependencies with:
pip install requests beautifulsoup4 IMDbPY

## Configuration

Configuration options are set in the script's `CONFIG` dictionary:
- `BASE_PATH`: Path to the directory containing movie folders.
- `LOG_FILE`: Path to the log file.
- `MAX_RETRIES`: Maximum retries for network requests.
- `RETRY_DELAY`: Delay between retries.
- `GOOGLE_HEADERS`: User-Agent headers for Google search.
- `MAX_SEARCH_RESULTS`: Maximum number of IMDb search results to consider.
- `THREAD_POOL_WORKERS`: Number of threads for concurrent IMDb lookups.
- `EXTRANEOUS_WORDS`: List of words to remove from folder names.

## Usage

1. Clone or download the script to your local machine.
2. Navigate to the script's directory:
   cd path/to/imdb-renamer
3. Run the script:
   python imdb-renamer.py --base-path "path/to/movies"
4. Optional: Use the `--dry-run` flag to preview changes without applying them:
   python imdb-renamer.py --dry-run

## Workflow

1. **Sanitize Folder Name**: The script cleans up the folder name by removing unwanted tags and formatting inconsistencies.
2. **Fetch Movie Details**: It searches IMDb for matching movies using the sanitized folder name.
3. **User Prompt**: If multiple results are found, the user can choose the correct match or provide a custom name.
4. **Rename Folder**: The script renames the folder to follow the pattern: `Title (Year) - IMDb- Rating`.

## Logging

All actions and errors are logged in the specified log file (default: `imdb_renamer.log`).

## Examples

### Before Renaming
D:\Movies
├── Movie_Name.720p.BluRay.x264
├── Another_Movie.1080p.BRRip

### After Renaming
D:\Movies
├── Movie Name (2023) - IMDb- 7.5
├── Another Movie (2021) - IMDb- 8.2

## Notes

- If the script cannot find a match, it allows manual retry with a custom name.
- Ensure internet connectivity for IMDb API and Google Search.

## Troubleshooting

- **No IMDb Details Found**: Check folder name for accuracy or retry with a custom name.
- **Permission Errors**: Ensure the script has write permissions for the target directory.

## Contributing
Contributions are welcome! Feel free to submit issues or pull requests on GitHub.
