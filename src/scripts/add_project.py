import csv
import os
import sys

from typing import Tuple, Optional
from urllib.parse import urlparse

from map_artifacts import get_yaml_data_from_path, map_repos_to_names
from write_yaml import dump


LOCAL_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "projects")
VERSION = 7

def parse_url(url: str) -> Optional[str]:
    """
    Parse a GitHub URL and extract the name.

    Args:
    url (str): The GitHub URL to parse.

    Returns:
    Optional[str]: The extracted name or None if the URL is invalid.
    """
    try:
        if 'github.com' not in url:
            raise ValueError(f"Invalid GitHub URL {url}.")
            return None
        parsed_url = urlparse(url)
        path = parsed_url.path.strip("/").split("/")
        if len(path) == 2:
            return path[1] + "-" + path[0]
        elif len(path) == 1:
            return path[0]
    except Exception as e:
        print(f"Error parsing URL {url}: {e}")
    return None


def input_project() -> Tuple[str, str, str]:
    """
    Get user input for GitHub URL and project name.

    Returns:
    Tuple[str, str, str]: A tuple containing the URL, name, and project name.
    """
    url = input("Enter a GitHub URL: ").lower().strip()
    name = parse_url(url)
    if not name:
        raise ValueError(f"Invalid GitHub URL: {url}")

    project_name = input("Enter a project name: ").strip()
    return url, name, project_name


def generate_yaml(url: str, name: str, project_name: str, repo_to_name_mapping: dict = {}) -> bool:
    """
    Generate a YAML file for a given project. This function checks for duplicate entries based on the URL 
    and verifies if a YAML file already exists for the given name before proceeding to create a new YAML file.

    Args:
    url (str): The URL of the GitHub repository.
    name (str): The name derived from the GitHub URL, used as a filename.
    display_name (str): The name of the project.
    repo_to_name_mapping (dict, optional): A dictionary mapping GitHub URLs to names. Used to check for duplicates.

    Returns:
    bool: True if the YAML file was created successfully, False otherwise (e.g., in case of duplicates or file already exists).
    """
    if url in repo_to_name_mapping:
        print(f"{project_name} ({name}) : {url} already exists at: {repo_to_name_mapping[url]}")
        return False
    
    if not os.path.exists(os.path.join(LOCAL_PATH, name[0])):
        os.makedirs(os.path.join(LOCAL_PATH, name[0]))

    path = os.path.join(LOCAL_PATH, name[0], f"{name}.yaml")
    if os.path.exists(path):
        print("File already exists.")
        return False

    yaml_data = {"version": VERSION, "name": name, "display_name": project_name, "github": [{"url": url}]}
    dump(yaml_data, path)
    print(f"Generated YAML file at {path}")
    repo_to_name_mapping[url] = name
    return True


def load_from_csv(repo_to_name_mapping: dict, filepath: str, project_col: str = 'Project', github_col: str = 'GitHub') -> None:
    """
    Load project details from a CSV file and generate YAML files for each project. Projects are identified 
    by their GitHub URLs and names specified in the CSV file. The function checks for duplicates and skips 
    existing entries.

    Args:
    repo_to_name_mapping (dict): A dictionary mapping GitHub URLs to names, used for checking duplicates.
    filepath (str): The file path of the CSV file containing project details.
    project_col (str, optional): The name of the column in the CSV that contains project names. Defaults to 'Project'.
    github_col (str, optional): The name of the column in the CSV that contains GitHub URLs. Defaults to 'GitHub'.
    """    
    if not os.path.exists(filepath):
        print("File does not exist.")
        return

    names = set()
    try:
        with open(filepath, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                project = row[project_col].strip()
                url = row[github_col].lower().strip().strip("/")
                name = parse_url(url)
                if name and generate_yaml(url, name, project, repo_to_name_mapping=repo_to_name_mapping):
                    names.add(name)
    except Exception as e:
        print(f"Error processing CSV file: {e}")
        return

    for s in sorted(names):
        print(f"- {s}")


def input_from_cli(repo_to_name_mapping: dict) -> None:
    """
    Continuously prompt the user for GitHub URLs and project names from the command line interface,
    and generate YAML files for each.

    Args:
    repo_to_name_mapping (dict): A dictionary mapping from repository URLs to names.
    """
    while True:
        try:
            result = input_project()
            if result:
                url, name, project_name = result
                if not generate_yaml(url, name, project_name, repo_to_name_mapping=repo_to_name_mapping):
                    break
        except ValueError as e:
            print(e)
            continue

        if input("Generate another YAML file? (y/n): ").lower() != 'y':
            break


def main() -> None:
    repo_to_name_mapping = map_repos_to_names(get_yaml_data_from_path(path=LOCAL_PATH))
    choice = input("Add projects from a CSV file? (y/n): ").lower()
    if choice == 'y':
        filepath = input("Enter CSV file path: ").strip()
        load_from_csv(repo_to_name_mapping, filepath)
    else:
        input_from_cli(repo_to_name_mapping)


if __name__ == "__main__":
    main()