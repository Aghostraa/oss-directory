import json
import logging
import os
import toml
import yaml

from map_artifacts import generate_repo_snapshot
from add_project import parse_url, generate_yaml
from add_collection import generate_collection_yaml

LOCAL_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "projects")
CRYPTO_SNAPSHOT = "crypto_ecosystems_snapshot.yaml"
OSSD_SNAPSHOT = LOCAL_PATH + "/ossd_repo_snapshot.yaml"
LOGGING_PATH = "data/logs/toml_adder.log"

SCHEMA_VERSION = 7

def map_crypto_ecosystems(ecosystems_path, load_snapshot=False):
    '''
    Creates a mapping of ecosystem titles to TOML file paths.
    '''

    yaml_path = ecosystems_path + "/crypto_ecosystems_map.yaml"
    if load_snapshot:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)


    ecosystem_map = {}
    for root, dirs, files in os.walk(ecosystems_path):
        for file in files:
            if file.endswith(".toml"):
                toml_path = os.path.join(root, file)
                with open(toml_path, 'r', encoding='utf-8') as f:
                    toml_data = toml.load(f)
                ecosystem_map[toml_data['title']] = toml_path
        
    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(ecosystem_map, f, default_flow_style=False, allow_unicode=True)

    return ecosystem_map


def initialize_session():
    '''
    Initializes a new session by creating a new log file and prompting the user to enter the path to the ecosystems directory.
    Rteturns a dictionary containing the ecosystem name, the mapping of ecosystem titles to TOML file paths, and the snapshot of the repos already in oss directory.
    '''
    # Generate log for the session
    logging.basicConfig(filename=LOGGING_PATH, filemode='a', format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

    # Prompt user to enter the path to the ecosystems directory
    ecosystems_path = input("Enter the path to the ecosystems directory: ")
    while not os.path.isdir(ecosystems_path):
        print(f"The directory '{ecosystems_path}' does not exist. Please enter a valid directory.")
        ecosystems_path = input("Enter the path to the ecosystems directory: ")
    create_new_snapshot = input("Do you want to load from a previous snapshot of the crypto ecosystems database? (yes/no): ").strip().lower()
    if create_new_snapshot == 'yes':
        crypto_ecosystems_map = map_crypto_ecosystems(ecosystems_path, load_snapshot=True)        
    else:
        crypto_ecosystems_map = map_crypto_ecosystems(ecosystems_path)
        

    # Prompt user to take a name of the ecosystem to index
    ecosystem_name = input("Enter the name of the ecosystem you want to index: ")
    while ecosystem_name not in crypto_ecosystems_map:
        # Find names that are similar to their input and ask the user to try again
        similar_names = [name for name in crypto_ecosystems_map.keys() if ecosystem_name.lower() in name.lower()]
        print(f"The ecosystem '{ecosystem_name}' does not exist. Did you mean one of the following?")
        for name in similar_names:
            print(f"- {name}")
        print()
        ecosystem_name = input("Enter the name of the ecosystem you want to index: ")
    
    # Prompt user to take a snapshot of the repos already in oss directory
    snapshot_option = input("Do you want to load from a previous snapshot of the repos already in oss directory? (yes/no): ").strip().lower()
    if snapshot_option != 'yes':
        generate_repo_snapshot(OSSD_SNAPSHOT)
    with open(OSSD_SNAPSHOT, 'r') as f:
        ossd_repo_snapshot = yaml.safe_load(f)
    
    # Store everything in a dictionary and return it
    session = {
        'ecosystem_name': ecosystem_name,
        'crypto_ecosystems_map': crypto_ecosystems_map,
        'ossd_repo_snapshot': ossd_repo_snapshot
    }
    return session


def load_toml_file(file_path):
    '''
    Loads and parses a TOML file from the given file path.
    Returns the parsed data and an error message (if any).
    '''
    try:
        with open(file_path, 'r') as file:
            return toml.load(file), None
    except Exception as e:
        return None, str(e)
    

def process_project_toml_file(toml_path, ossd_repo_snapshot, write_file=True):
    """
    Process a TOML file containing project information. It reads the TOML file,
    extracts the title and github_organizations, and returns a list of slugs.
    """

    toml_data, error = load_toml_file(toml_path)
    if toml_data is None:
        logging.error(f"Error loading TOML data at {toml_path}: {error}")
        return

    title = toml_data['title']
    github_orgs = toml_data['github_organizations']
    print(f"\n\nProcessing TOML file at {toml_path} for project {title}, including the following GitHub organizations: {github_orgs}.")
    slugs = []
    for github_org in github_orgs:
        url = github_org.lower().strip().strip("/")
        if url in ossd_repo_snapshot:
            slug = ossd_repo_snapshot[url]
            print(f"Slug for {url} already exists: {slug}")
            logging.info(f"Slug for {url} already exists: {slug}")
        else:
            slug = parse_url(url)
            if not slug:
                logging.error(f"Error parsing URL: {url}")
                continue            
            logging.info(f"Slug for {url} does not exist. Generating slug: {slug}")
            if write_file:
                add_project = input(f"Add new project {slug} for {url}? (Y/N): ").strip().lower()
                if add_project == 'q':
                    return slugs
                if add_project == 'y':
                    generate_yaml(url, slug, title)
                    ossd_repo_snapshot[url] = slug
                    logging.info(f"Added slug for {url} to ossd_repo_snapshot: {slug}")
                else:
                    logging.info(f"Skipping {url}")
                    continue
        slugs.append(slug)
    return slugs


def convert_collection_toml_file_to_json(ecosystem_name, crypto_ecosystems_map, ossd_repo_snapshot):
    """
    Process a TOML file containing collection information. It reads the TOML file,
    extracts the title and sub_ecosystems, and creates/returns a list of project slugs.
    For each slug, it distinguishes between existing and new projects in OSSD.
    Finally, it prepares a JSON file with the slugs, the repo, and their status.
    """

    toml_path = crypto_ecosystems_map[ecosystem_name]
    toml_data, error = load_toml_file(toml_path)
    if toml_data is None:
        logging.error(f"Error loading TOML data at {toml_path}: {error}")
        return
    logging.info(f"Processing TOML file at {toml_path} for ecosystem {ecosystem_name}...")

    sub_ecosystem_titles = toml_data['sub_ecosystems']
    data = []
    for title in sub_ecosystem_titles:
        if title in crypto_ecosystems_map:
            sub_ecosystem_toml_path = crypto_ecosystems_map[title]
            sub_ecosystem_slugs = process_project_toml_file(sub_ecosystem_toml_path, ossd_repo_snapshot, write_file=False)
            if not sub_ecosystem_slugs:
                continue
            slugs = set(sub_ecosystem_slugs)
            for s in slugs:
                slug_path = f"{LOCAL_PATH}/{s[0]}/{s}.yaml"
                exists = os.path.exists(slug_path)
                data.append({
                    "slug": s,
                    "ecosystem": title,
                    "status": "existing" if exists else "new"
                })
        else:
            logging.error(f"Sub-ecosystem {title} does not exist.")

    json_path = f"temp/toml_{ecosystem_name.lower()}.json"
    with open(json_path, 'w') as file:
        json.dump(data, file, indent=4)
        

def process_collection_toml_file(ecosystem_name, crypto_ecosystems_map, ossd_repo_snapshot):
    """
    Process a TOML file containing collection information. It reads the TOML file,
    extracts the title and sub_ecosystems, and creates/returns a list of project slugs.
    """

    toml_path = crypto_ecosystems_map[ecosystem_name]
    toml_data, error = load_toml_file(toml_path)
    if toml_data is None:
        logging.error(f"Error loading TOML data at {toml_path}: {error}")
        return
    logging.info(f"Processing TOML file at {toml_path} for ecosystem {ecosystem_name}...")

    sub_ecosystem_titles = toml_data['sub_ecosystems']
    slugs = []
    for title in sub_ecosystem_titles:
        if title in crypto_ecosystems_map:
            sub_ecosystem_toml_path = crypto_ecosystems_map[title]
            sub_ecosystem_slugs = process_project_toml_file(sub_ecosystem_toml_path, ossd_repo_snapshot)
            if not sub_ecosystem_slugs:
                continue
            add_slugs = input(f"Add slugs {sub_ecosystem_slugs} for {title} to {ecosystem_name} collection? (Y/N): ").strip().lower()
            if add_slugs == 'y':
                slugs.extend(sub_ecosystem_slugs)
        else:
            logging.error(f"Sub-ecosystem {title} does not exist.")

    for github_organizations in toml_data['github_organizations']:
        url = github_organizations.lower().strip().strip("/")
        if url in ossd_repo_snapshot:
            slug = ossd_repo_snapshot[url]
            print(f"Slug for {url} already exists: {slug}")
            logging.info(f"Slug for {url} already exists: {slug}")
        else:
            slug = parse_url(url)
            if not slug:
                logging.error(f"Error parsing URL: {url}")
                continue            
            logging.info(f"Slug for {url} does not exist. Generating slug: {slug}")
            add_project = input(f"Add new project {slug} for {url}? (Y/N): ").strip().lower()
            if add_project == 'y':
                display_name = input("Enter a display name for the project: ").strip()
                generate_yaml(url, slug, display_name)
                ossd_repo_snapshot[url] = slug
                logging.info(f"Added slug for {url} to ossd_repo_snapshot: {slug}")
            else:
                logging.info(f"Skipping {url}")
                continue
        slugs.append(slug)

    slugs = sorted(list(set(slugs)))
    return slugs

                    
def main(version=SCHEMA_VERSION):
    '''
    Main function that orchestrates the processing of ecosystems, projects, and collections.
    '''

    # Initialize a new session
    session = initialize_session()
    ecosystem_name = session['ecosystem_name']

    # Determine whether to process the collection or generate a JSON file
    process_collection = input("Process the ecosystem as a new collection? (Y/N): ").strip().lower()
    if process_collection == 'n':
        convert_collection_toml_file_to_json(**session)
        return

    # Process the ecosystem as a collection
    project_slugs = process_collection_toml_file(**session)
    if project_slugs:
        for slug in project_slugs:
            print(f"- {slug}")
        make_collection = input(f"Make collection for {ecosystem_name}? (Y/N): ").strip().lower()
        if make_collection == 'y':
            collection_slug = input("Enter a slug for the collection: ").strip().lower()
            collection_name = input("Enter a name for the collection: ").strip()
            if not collection_name:
                collection_name = ecosystem_name
            collection_path = generate_collection_yaml(collection_slug, collection_name, project_slugs, version=version)
        if collection_path:
            logging.info(f"Created collection file at {collection_path}")
        

if __name__ == "__main__":
    main()