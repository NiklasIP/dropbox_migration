import os.path
from time import sleep

import dropbox
import pandas as pd
from PyQt5.QtCore import QObject, pyqtSignal


class Worker(QObject):
    report_progress = pyqtSignal(int)
    
    def __init__(self, access_token, document_to_read, locale, year, nights):
        super(Worker, self).__init__()
        self.report_progress.emit(100)
        self.access_token = access_token
        self.document_to_read = document_to_read
        self.locale = locale
        self.year = year
        self.nights = nights


    def run(self):
        #Try to establish a connection to Dropbox servers
        self.report_progress.emit(100)
        try:
            self.dbx = dropbox.Dropbox(self.access_token)

        except Exception as e:
            with open('errorlog.txt', mode='w') as writer:
                writer.writelines(f'{e}')

            self.report_progress.emit(4)

        self.report_progress.emit(5)
        relocation_paths = self.create_relocation_object()

        #Stops the job if the process failed further up the chain.
        if relocation_paths is None:
            self.report_progress.emit(2)

        self.copy_files(relocation_paths=relocation_paths)
    
    def get_files_to_copy(self):
        """Compares the files in the destination directory with those the user wishes to copy and removes those already
        at the destination"""
        #Get files already in the destination directory
        files_at_destination = []
        self.report_progress.emit(6)
        result = self.dbx.files_list_folder(f"/Appar/BatShare/{self.locale}/{self.year}",
                                            limit=None)
        files_at_destination.extend(result.entries)
        while result.has_more:
            result = self.dbx.files_list_folder_continue(result.cursor)
            files_at_destination.extend(result.entries)

        files_at_destination = [file.name for file in files_at_destination]
        #Read doc of files the user wants to copy. Remove duplicates.

        try:
            if self.locale == "Göholm":
                user_files_to_copy = pd.read_excel(self.document_to_read)
                user_files_to_copy = user_files_to_copy.loc[user_files_to_copy["Veckonatt"].isin(self.nights)]
                user_files_to_copy = user_files_to_copy["Filnamn"]

            else:
                user_files_to_copy = pd.read_excel(self.document_to_read)['Filnamn']
        except:
            self.report_progress.emit(7)


        files_to_copy = [file for file in user_files_to_copy if file not in files_at_destination]

        print(f"Number of files at destination: {len(files_at_destination)}")
        print(f"Number of files to copy: {len(files_to_copy)}")

        return files_to_copy
    
    
    def create_relocation_object(self):
        """Makes a relocation object to allow for the batch move of files."""
        files_to_copy = self.get_files_to_copy()

        #Stops the job if the document of files to migrate could not be found.
        if files_to_copy is None:
            return None

        to_directory = f"/Appar/BatShare/{self.locale}/{self.year}"
        from_directory = f"/{self.locale}/{self.year}/Autoklassat"

        # Create a relocation path to desired directory from specified directory by mapping
        def make_path(filename):
            return dropbox.files.RelocationPath(os.path.join(from_directory,filename),
                                                os.path.join(to_directory,filename))

        relocation_paths = list(map(make_path, files_to_copy))

        #Divide into chunks of 1000 if needed, as this is the limit of the API
        n = 1000
        relocation_paths_chunks = [relocation_paths[i:i + n] for i in range(0, len(relocation_paths), n)]

        return relocation_paths_chunks
    
    
    def copy_files(self, relocation_paths, refresh_rate:int=2):
        if len(relocation_paths) == 0:
            self.report_progress.emit(3)
            return

        results = []
        no_data_chunks = len(relocation_paths)

        for i, data_chunk in enumerate(relocation_paths):
            print(f"Working on copying data chunk number {i}/{no_data_chunks}")
            copy_job = dbx.files_copy_batch_v2(data_chunk)
            job_id = copy_job.get_async_job_id()

            # Check job status. Return results when done
            self.report_progress.emit(8)
            while True:
                status = dbx.files_copy_batch_check_v2(job_id)
                if status.is_complete():
                    report = status.get_complete()
                    results.append(report)
                    break

                sleep(refresh_rate) #Default 2 sec.
        
        self.report_progress.emit(1)
        
        return results