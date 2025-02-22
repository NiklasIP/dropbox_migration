import json
import os.path
from time import sleep

import dropbox
import pandas as pd
#from PyQt5.QtNfc import title
from PyQt5.QtWidgets import QDialog, QMessageBox, QApplication, QFileDialog, QButtonGroup
from PyQt5 import uic
from PyQt5.QtCore import QThread, pyqtSignal
from dropbox.files import download


class GUI(QDialog):
    def __init__(self):
        super(GUI, self).__init__()
        uic.loadUi("layout.ui", self)
        self.show()

        title = "Bat Migration"
        self.setWindowTitle(title)

        app_info = json.loads(open("./defaults.json").read())

        self.document_to_read = app_info["document"]
        self.year = app_info["year"]
        self.locale = str(app_info["station"]).title()
        self.nights = app_info["selectedNights"]

        self.filesDocument.setPlainText(self.document_to_read)
        self.stationBox.setPlainText(self.locale)
        self.yearBox.setPlainText(self.year)

        self.fileSelectButton.clicked.connect(self.set_download_folder)
        self.migrateButton.clicked.connect(self.download_files)



    def set_download_folder(self) -> None:
        document = QFileDialog.getOpenFileName()
        self.filesDocument.setPlainText(document[0])


    def get_files_to_copy(self):
        """Compares the files in the destination directory with those the user wishes to copy and removes those already
        at the destination"""
        #Get files already in the destination directory
        files_at_destination = []

        print("Trimming away files already at destination...")
        result = self.dbx.files_list_folder(f"/Appar/BatShare/{self.locale}/{self.year}",
                                            limit=None)
        files_at_destination.extend(result.entries)
        while result.has_more:
            result = self.dbx.files_list_folder_continue(result.cursor)
            files_at_destination.extend(result.entries)

        files_at_destination = [file.name for file in files_at_destination]
        #Read doc of files the user wants to copy. Remove duplicates.
        if self.locale == "Göholm":
            user_files_to_copy = pd.read_excel(self.document_to_read)
            user_files_to_copy = user_files_to_copy.loc[user_files_to_copy["Veckonatt"].isin(self.nights)]
            user_files_to_copy = user_files_to_copy["Filnamn"]

        else:
            user_files_to_copy = pd.read_excel(self.document_to_read)['Filnamn']



        files_to_copy = [file for file in user_files_to_copy if file not in files_at_destination]

        print(f"Number of files at destination: {len(files_at_destination)}")
        print(f"Number of files to copy: {len(files_to_copy)}")

        return files_to_copy


    def create_relocation_object(self):
        """Makes a relocation object to allow for the batch move of files."""
        files_to_copy = self.get_files_to_copy()
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
            message = "Nothing to move"
            message_box = QMessageBox()
            message_box.setText(message)
            message_box.exec_()
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

    def write_new_defaults(self):
        self.year = self.yearBox.toPlainText()
        self.locale = self.stationBox.toPlainText()
        self.document_to_read = self.filesDocument.toPlainText()

        new_defaults = {"document": self.document_to_read,
                        "station": self.locale,
                        "year": self.year,
                        "selectedNights": self.nights}

        with open("defaults.json", mode="w") as out_file:
            json.dump(new_defaults, out_file,indent=6)

    def download_files(self):
        self.write_new_defaults()

        access_token = self.accessToken.toPlainText()
        self.dbx = dropbox.Dropbox(access_token)

        relocation_paths = self.create_relocation_object()
        self.copy_files(relocation_paths=relocation_paths)




def main():
    app = QApplication([])
    window = GUI()
    app.exec_()


    # relocation_paths = create_relocation_object()
    # results = copy_files(relocation_paths=relocation_paths)
    #
    # print(results)

if __name__ == "__main__":
    main()