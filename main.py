import json

from PyQt5.QtWidgets import QDialog, QApplication, QFileDialog
from PyQt5 import uic
from PyQt5 import QtCore

from Thread import Worker

class GUI(QDialog):
    def __init__(self):
        super(GUI, self).__init__()
        uic.loadUi("layout.ui", self)
        self.show()

        title = "Bat Migration"
        self.setWindowTitle(title)

        try:
            app_info = json.loads(open("./defaults.json").read())

        except:
            self.document_to_read = ''
            self.year = ''
            self.locale = ''
            self.nights = ['Söndag']

        else:
            self.document_to_read = app_info["document"]
            self.year = app_info["year"]
            self.locale = str(app_info["station"]).title()
            self.nights = app_info["selectedNights"]

        self.filesDocument.setPlainText(self.document_to_read)
        self.stationBox.setPlainText(self.locale)
        self.yearBox.setPlainText(self.year)

        self.fileSelectButton.clicked.connect(self.set_download_folder)
        self.migrateButton.clicked.connect(self.copy_files)

    def set_download_folder(self) -> None:
        document = QFileDialog.getOpenFileName()
        self.filesDocument.setPlainText(document[0])


    def write_new_defaults(self):
        self.year = self.yearBox.toPlainText()
        self.locale = self.stationBox.toPlainText().title()
        self.document_to_read = self.filesDocument.toPlainText()

        new_defaults = {"document": self.document_to_read,
                        "station": self.locale,
                        "year": self.year,
                        "selectedNights": self.nights}

        with open("defaults.json", mode="w") as out_file:
            json.dump(new_defaults, out_file,indent=6)

    def copy_files(self):
        self.write_new_defaults()
        access_token = self.accessToken.toPlainText()


        self.worker = Worker(access_token,
                             self.document_to_read,
                             self.locale,
                             self.year,
                             self.nights)
        self.worker_thread = QtCore.QThread()
        self.worker_thread.started.connect(self.worker.run)
        self.worker.report_progress.connect(self.signal_progress)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.start()

    def signal_progress(self, progress):
        possible_messages = {1: "Migration complete.",
                             2: "Migration failed.",
                             3: "No files to move.",
                             4: "Failed to connect to dropbox. Check your access token.\nAn error file has been generated. ",
                             5: "Comparing files at destination to list of files to be moved...",
                             6: "Trimming away files already at destination...",
                             7: "Could not find the document of files to be migrated. Check the path.",
                             8: "Copy job in progress...",
                             100: "Starting job"}
        message = possible_messages[progress]
        print(message)
        self.curr_status.setText(message)
        self.curr_status.repaint()


def main():
    app = QApplication([])
    window = GUI()
    app.exec_()

if __name__ == "__main__":
    main()