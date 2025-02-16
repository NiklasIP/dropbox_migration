import json
import os.path
from time import sleep

import dropbox
import pandas as pd

app_info = json.loads(open("./settings.json").read())

access_token = app_info["accessToken"]
document_to_read = app_info["document"]
year = app_info["year"]
locale = str(app_info["station"]).title()

dbx = dropbox.Dropbox(access_token)

def get_files_to_copy():
    """Compares the files in the destination directory with those the user wishes to copy and removes those already
    at the destination"""
    #Get files already in the destination directory
    files_at_destination = []

    print("Trimming away files already at destination...")
    result = dbx.files_list_folder(f"/Appar/BatShare/{locale}/{year}", limit=None)
    files_at_destination.extend(result.entries)
    while result.has_more:
        result = dbx.files_list_folder_continue(result.cursor)
        files_at_destination.extend(result.entries)

    files_at_destination = [file.name for file in files_at_destination]
    #Read doc of files the user wants to copy. Remove duplicates.
    user_files_to_copy = pd.read_excel(document_to_read)['Filnamn']
    files_to_copy = [file for file in user_files_to_copy if file not in files_at_destination]

    with open("missing_files.txt",mode='w') as writer:
        for file in files_to_copy:
            writer.write(f"{file}\n")

    print(f"Number of files at destination: {len(files_at_destination)}")
    print(f"Number of files to copy: {len(files_to_copy)}")

    return files_to_copy


def create_relocation_object():
    """Makes a relocation object to allow for the batch move of files."""
    files_to_copy = get_files_to_copy()
    to_directory = f"/Appar/BatShare/{locale}/{year}"
    from_directory = f"/{locale}/{year}/Autoklassat"

    # Create a relocation path to desired directory from specified directory by mapping
    def make_path(filename):
        return dropbox.files.RelocationPath(os.path.join(from_directory,filename), os.path.join(to_directory,filename))

    relocation_paths = list(map(make_path, files_to_copy))

    #Divide into chunks of 1000 as this is the limit of the API
    n = 1000
    relocation_paths_chunks = [relocation_paths[i:i + n] for i in range(0, len(relocation_paths), n)]

    return relocation_paths_chunks

def copy_files(relocation_paths:dropbox.files.RelocationPath, refresh_rate:int=2):
    if len(relocation_paths) == 0:
        print("Nothing to move")
        return

    results = []
    no_data_chunks = len(relocation_paths)

    for i, data_chunk in enumerate(relocation_paths):
        print(f"Working on copying data chunk number {i}/{no_data_chunks}")
        copy_job = dbx.files_copy_batch_v2(data_chunk)
        job_id = copy_job.get_async_job_id()

        # Check job status. Return results when done
        while True:
            status = dbx.files_copy_batch_check_v2(job_id)
            if status.is_complete():
                # noinspection PyTypeChecker
                report = status.get_complete()
                results.append(report)
                break

            print("Copy job in progress...")
            sleep(refresh_rate) #Default 2 sec.

    return results

def main():
    relocation_paths = create_relocation_object()
    results = copy_files(relocation_paths=relocation_paths)

    print(results)

if __name__ == "__main__":
    main()